import asyncio, sys, click, os, yaml, logging, stat
from pathlib import Path
from typing import List
from monstr.encrypt import Keys
from monstr.client.client import Client, ClientPool
from monstr.event.event import Event
from monstr.util import util_funcs
def _import_acorn_runtime():
    from acorn.acorn import Acorn
    from acorn.models import nostrProfile, SafeboxItem, SafeboxRecord
    from acorn.lightning import lightning_address_pay
    from acorn.func_utils import (
        generate_seed_phrase_and_nsec,
        recover_nsec_from_seed,
        seed_phrase_and_nsec_from_entropy,
    )

    return (
        Acorn,
        nostrProfile,
        SafeboxItem,
        SafeboxRecord,
        lightning_address_pay,
        generate_seed_phrase_and_nsec,
        recover_nsec_from_seed,
        seed_phrase_and_nsec_from_entropy,
    )


(
    Acorn,
    nostrProfile,
    SafeboxItem,
    SafeboxRecord,
    lightning_address_pay,
    generate_seed_phrase_and_nsec,
    recover_nsec_from_seed,
    seed_phrase_and_nsec_from_entropy,
) = _import_acorn_runtime()
from datetime import datetime, timedelta
import json

from time import sleep, time
import qrcode
from acorn.config import (
    ConfigError,
    harden_config_permissions,
    load_config,
    write_config as persist_config,
)
from acorn.prompts import (
    WELCOME_MSG,
    INFO_HELP,
    SET_HELP,
    RELAYS_HELP,
    HOME_RELAY_HELP,
    MINTS_HELP,
    NOSTR_PROFILE_HELP

)

default_relays  = [ "wss://nostr-pub.wellorder.net", 
            "wss://relay.damus.io", 
            "wss://relay.primal.net",
            "wss://nos.lol"
        ]
default_public_relays = []
default_mints = ["https://mint.getsafebox.app"]
default_home_relay = "wss://relay.getsafebox.app"
default_logging_level = 30

# List of mints https://nostrapps.github.io/cashu/mints.json

def _normalize_relay(relay: str) -> str:
    relay = str(relay).strip()
    if relay.startswith(("wss://", "ws://")):
        return relay
    return f"wss://{relay}"


def _normalize_mint(mint: str) -> str:
    mint = str(mint).strip()
    if mint.startswith(("https://", "http://")):
        return mint
    return f"https://{mint}"


def _split_csv(value: str) -> list[str]:
    return [each for each in str(value).replace(" ", "").split(",") if each]


def _normalize_relay_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [_normalize_relay(each) for each in _split_csv(value)]


def _minimize_config(config: dict) -> dict:
    return {
        "nsec": config.get("nsec"),
        "home_relay": config.get("home_relay", default_home_relay),
    }


def _config_for_display(config: dict) -> dict:
    displayed = dict(config)
    if displayed.get("nsec"):
        displayed["nsec"] = "<redacted; use 'acorn set --show-recovery'>"
    return displayed


def _format_recovery_material(recovery: dict) -> str:
    seed_phrase = recovery.get("seed_phrase") or "unavailable (back up the nsec)"
    return "\n".join(
        [
            f"home_relay: {recovery.get('home_relay')}",
            f"seed_phrase: {seed_phrase}",
            f"nsec: {recovery.get('nsec')}",
        ]
    )


def _read_secret_file(secret_file: str, label: str) -> str:
    """Read a secret from stdin or a permission-restricted regular file."""
    if secret_file == "-":
        value = sys.stdin.read().strip()
    else:
        path = Path(secret_file).expanduser()
        try:
            file_stat = path.stat()
        except OSError as exc:
            raise click.ClickException(f"Unable to read {label} file: {exc}") from exc
        if not stat.S_ISREG(file_stat.st_mode):
            raise click.ClickException(f"{label.capitalize()} file must be a regular file: {path}")
        if stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise click.ClickException(
                f"{label.capitalize()} file permissions are too open: {path}. "
                "Use chmod 600 and try again."
            )
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise click.ClickException(f"Unable to read {label} file: {exc}") from exc
    if not value:
        raise click.ClickException(f"{label.capitalize()} input is empty.")
    return value


def _prompt_secret(prompt: str, confirmation_prompt: str | None = None) -> str:
    """Prompt for a secret without echoing it or placing it in process arguments."""
    prompt_options = {"hide_input": True, "err": True}
    if confirmation_prompt:
        prompt_options["confirmation_prompt"] = confirmation_prompt
    return click.prompt(prompt, **prompt_options).strip()


def _private_key_from_secure_input(
    prompt_requested: bool,
    secret_file: str | None,
    *,
    confirm: bool = False,
) -> str | None:
    if prompt_requested and secret_file:
        raise click.ClickException("Use either the hidden private-key prompt or --nsec-file, not both.")
    if secret_file:
        return _read_secret_file(secret_file, "private key")
    if prompt_requested:
        return _prompt_secret(
            "nsec private key",
            "Repeat nsec private key" if confirm else None,
        )
    return None

def _extract_early_config_path(argv: list[str] | None = None) -> str | None:
    args = list(sys.argv[1:] if argv is None else argv)
    for index, arg in enumerate(args):
        if arg == "--config" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--config="):
            return arg.split("=", 1)[1]
    return os.getenv("ACORN_CONFIG")


def _resolve_config_path(config_path: str | None = None) -> str:
    configured_path = config_path or _extract_early_config_path()
    if configured_path:
        return os.path.abspath(os.path.expanduser(configured_path))
    return os.path.join(os.path.expanduser("~"), ".acorn", "config.yml")


file_path = _resolve_config_path()
config_directory = os.path.dirname(file_path)
CONFIG_FILE_EXISTED = False
CONFIG_LOAD_ERROR = None
config_obj = {}
HOME_RELAY = default_home_relay
RELAYS = [HOME_RELAY]
PUBLIC_RELAYS = default_public_relays
NSEC = None
MINTS = default_mints
REPLICATE_RELAYS = []
LOGGING_LEVEL = default_logging_level


def write_config():
    persist_config(
        file_path,
        config_obj,
        harden_directory=os.path.basename(config_directory) == ".acorn",
    )


def _load_config():
    global CONFIG_FILE_EXISTED, config_obj, HOME_RELAY, RELAYS, PUBLIC_RELAYS, NSEC, MINTS, REPLICATE_RELAYS, LOGGING_LEVEL

    CONFIG_FILE_EXISTED = os.path.exists(file_path)
    config_obj = load_config(file_path)

    HOME_RELAY = config_obj.get('home_relay', default_home_relay)
    RELAYS = config_obj.get('relays') or [HOME_RELAY]
    PUBLIC_RELAYS = config_obj.get('public_relays') or default_public_relays
    NSEC = config_obj.get('nsec', None)
    MINTS = config_obj.get('mints') or default_mints
    REPLICATE_RELAYS = config_obj.get('replicate_relays') or []
    LOGGING_LEVEL = int(config_obj.get('logging_level', default_logging_level))


try:
    _load_config()
except ConfigError as exc:
    CONFIG_LOAD_ERROR = exc


def _configure_cli_logging(verbose: bool = False) -> int:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.getLogger().setLevel(level)
    logging.getLogger("Acorn").setLevel(level)
    return level


def _format_record(record: SafeboxRecord, kind: int) -> str:
    title = record.tag[0] if record.tag else "(untitled)"
    lines = [
        f"Record: {title}",
        f"Kind: {kind}",
        f"Type: {record.type}",
        "",
        record.payload or "",
    ]
    if record.blobref:
        lines.extend(
            [
                "",
                f"Blob: {record.blobref}",
                f"Blob type: {record.blobtype or 'unknown'}",
            ]
        )
    return "\n".join(lines).rstrip()


def _json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "data"):
        return value.data()
    return str(value)


def _emit_json(payload) -> None:
    click.echo(json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2))


def _record_to_dict(record: SafeboxRecord, kind: int) -> dict:
    data = record.model_dump()
    data["kind"] = kind
    data["label"] = record.tag[0] if record.tag else None
    return data


def _format_tx_history_entry(entry: dict) -> str:
    tx_type = str(entry.get("tx_type") or "").upper()
    direction = {
        "C": "Credit",
        "D": "Debit",
        "X": "Advisory",
    }.get(tx_type, tx_type or "Unknown")
    sign = "+" if tx_type == "C" else "-" if tx_type == "D" else ""
    amount = entry.get("amount", 0)
    tendered_amount = entry.get("tendered_amount")
    tendered_currency = entry.get("tendered_currency") or "SAT"
    current_balance = entry.get("current_balance")
    comment = entry.get("comment") or ""
    fees = entry.get("fees") or 0

    lines = [
        f"{entry.get('create_time', 'unknown time')}  {direction}",
        f"  amount:  {sign}{amount} sats",
    ]
    if tendered_amount is not None:
        lines.append(f"  tender:  {tendered_amount} {tendered_currency}")
    if fees:
        lines.append(f"  fees:    {fees} sats")
    if current_balance is not None:
        lines.append(f"  balance: {current_balance} sats")
    if comment:
        lines.append(f"  note:    {comment}")
    if entry.get("payment_hash"):
        lines.append(f"  payment: {entry['payment_hash']}")
    return "\n".join(lines)


def _balance_by_mint(acorn_obj: Acorn) -> list[dict]:
    all_proofs, keyset_amounts = acorn_obj._proofs_by_keyset()
    mint_rows: dict[str, dict] = {}

    for keyset, amount in keyset_amounts.items():
        mint = acorn_obj.known_mints.get(keyset) or "unknown"
        row = mint_rows.setdefault(
            mint,
            {
                "mint": mint,
                "balance": 0,
                "unit": "sat",
                "proof_count": 0,
                "keysets": [],
            },
        )
        proofs = all_proofs.get(keyset, [])
        row["balance"] += amount
        row["proof_count"] += len(proofs)
        row["keysets"].append(
            {
                "keyset": keyset,
                "balance": amount,
                "unit": "sat",
                "proof_count": len(proofs),
            }
        )

    return sorted(mint_rows.values(), key=lambda row: (-row["balance"], row["mint"]))


def _format_balance_by_mint(rows: list[dict]) -> str:
    if not rows:
        return "No mint balances found."

    lines = ["Mint balances:"]
    for row in rows:
        lines.append(f"- {row['mint']}: {row['balance']} sats in {row['proof_count']} proofs")
        for keyset in sorted(row["keysets"], key=lambda each: each["keyset"]):
            lines.append(
                f"  - keyset {keyset['keyset']}: "
                f"{keyset['balance']} sats in {keyset['proof_count']} proofs"
            )
    return "\n".join(lines)


def _lightning_capacity(acorn_obj: Acorn) -> dict:
    all_proofs, keyset_amounts = acorn_obj._proofs_by_keyset()
    candidates = [
        (str(keyset), int(amount), acorn_obj.known_mints.get(keyset))
        for keyset, amount in keyset_amounts.items()
        if int(amount) > 0 and acorn_obj.known_mints.get(keyset)
    ]
    if not candidates:
        return {
            "amount": 0,
            "unit": "sat",
            "mint": None,
            "keyset": None,
            "proof_count": 0,
            "constraint": "single_keyset",
            "fee_reserve_included": False,
        }

    keyset, amount, mint = sorted(
        candidates,
        key=lambda each: (-each[1], each[0]),
    )[0]
    return {
        "amount": amount,
        "unit": "sat",
        "mint": mint,
        "keyset": keyset,
        "proof_count": len(all_proofs.get(keyset, [])),
        "constraint": "single_keyset",
        "fee_reserve_included": False,
    }


def _format_lightning_capacity(capacity: dict) -> str:
    amount = int(capacity["amount"])
    if amount <= 0:
        return (
            "Lightning payment capacity: 0 sats "
            "(no mint-mapped spendable keyset)."
        )

    return "\n".join(
        [
            f"Lightning payment capacity: up to {amount} sats before mint fees.",
            f"  Mint: {capacity['mint']}",
            f"  Keyset: {capacity['keyset']}",
            "  Limit: one keyset per Lightning payment.",
        ]
    )


def _format_proof_check(report: dict) -> str:
    wallet = report["wallet"]
    confirmed = report["mint_confirmed_unspent"]
    lines = [
        "Proof check (read-only)",
        f"Status: {report['status']}",
        (
            f"Wallet state: {wallet['amount']} sats in "
            f"{wallet['proof_count']} proofs"
        ),
        (
            f"Mint-confirmed unspent: {confirmed['amount']} sats in "
            f"{confirmed['proof_count']} proofs"
        ),
        "Proof states:",
    ]
    for state in ("UNSPENT", "SPENT", "PENDING", "UNKNOWN"):
        totals = report["states"][state]
        lines.append(
            f"- {state}: {totals['amount']} sats in "
            f"{totals['proof_count']} proofs"
        )

    structural = report["structural"]
    if structural["duplicate_proofs"]:
        lines.append(f"Structural warning: {structural['duplicate_proofs']} duplicate proofs")
    if structural["invalid_proofs"]:
        lines.append(f"Structural warning: {structural['invalid_proofs']} invalid proofs")
    if structural["unknown_keysets"]:
        lines.append(
            "Structural warning: unknown keysets "
            + ", ".join(structural["unknown_keysets"])
        )
    for error in report["errors"]:
        lines.append(f"Check warning: {error}")

    lines.extend(
        [
            f"Recommendation: {report['recommendation']}",
            "No wallet state was changed.",
        ]
    )
    return "\n".join(lines)



@click.group()
@click.option("--config", "config_path", default=None, help="Path to Acorn config file; defaults to ~/.acorn/config.yml or ACORN_CONFIG")
@click.option("--verbose", "-v", is_flag=True, help="Show debug logs.")
@click.pass_context
def cli(ctx, config_path, verbose):
    global file_path, config_directory, CONFIG_LOAD_ERROR, LOGGING_LEVEL
    if config_path:
        requested_path = _resolve_config_path(config_path)
        if requested_path != file_path:
            file_path = requested_path
            config_directory = os.path.dirname(file_path)
            try:
                _load_config()
            except ConfigError as exc:
                CONFIG_LOAD_ERROR = exc
            else:
                CONFIG_LOAD_ERROR = None

    ctx.ensure_object(dict)
    LOGGING_LEVEL = _configure_cli_logging(verbose)
    ctx.obj["logging_level"] = LOGGING_LEVEL
    ctx.obj["config_path"] = file_path

    if CONFIG_LOAD_ERROR is not None:
        raise click.ClickException(str(CONFIG_LOAD_ERROR))

    if CONFIG_FILE_EXISTED:
        try:
            harden_config_permissions(
                file_path,
                harden_directory=os.path.basename(config_directory) == ".acorn",
            )
        except ConfigError as exc:
            raise click.ClickException(str(exc)) from exc

    config_creation_commands = {"init", "recover", "set"}
    if ctx.invoked_subcommand not in config_creation_commands and NSEC is None:
        raise click.ClickException(
            f"No initialized Acorn config found at {file_path}. "
            f"Run 'acorn --config {file_path} init' first."
        )

@click.command("info", help=INFO_HELP)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
@click.pass_context
def info(ctx, json_output):
    
    logging_level = ctx.obj.get("logging_level", LOGGING_LEVEL)
    acorn_obj = Acorn(nsec=NSEC, mints=MINTS, home_relay=HOME_RELAY, logging_level=logging_level)
   
    if json_output:
        _emit_json(
            {
                "npub": acorn_obj.pubkey_bech32,
                "pubkey": acorn_obj.pubkey_hex,
                "home_relay": HOME_RELAY,
                "home_mint": acorn_obj.home_mint,
            }
        )
        return

    click.echo(r"""
        ___                            
       /   |  _________  _________     
      / /| | / ___/ __ \/ ___/ __ \    
     / ___ |/ /__/ /_/ / /  / / / /    
    /_/  |_|\___/\____/_/  /_/ /_/     

      Safeguarding Keys, Funds and Records
    """.rstrip())
    click.echo()
    click.echo("A protocol-first component for safeguarding user-controlled keys, funds, and records.")
    click.echo("Reciprocal resilience without shared secrets.")
    click.echo()
    click.echo(WELCOME_MSG.strip())
    click.echo()
    click.echo("Keys")
    click.echo(f"  npub:       {acorn_obj.pubkey_bech32}")
    click.echo(f"  pubkey:     {acorn_obj.pubkey_hex}")
    click.echo()
    click.echo("Infrastructure")
    click.echo(f"  home relay: {HOME_RELAY}")
    click.echo(f"  home mint:  {acorn_obj.home_mint}")
    click.echo()
    click.echo("Useful commands")
    click.echo("  acorn balance")
    click.echo("  acorn get_user_records --labels")
    click.echo("  acorn set --show-recovery")
    click.echo("  acorn replicate --target <relay>")
    # click.echo(f"instance: {acorn_obj.get_instance()}")
    
    

@click.command(help="initialize a new acorn wallet")

@click.option(
    "--import-nsec",
    is_flag=True,
    help="Import an existing nsec through a hidden prompt.",
)
@click.option(
    "--nsec-file",
    default=None,
    metavar="PATH",
    help="Read an existing nsec from a chmod-600 file, or '-' for stdin.",
)
@click.option(
    "--entropy",
    "use_entropy",
    is_flag=True,
    help="Initialize from externally generated 256-bit entropy entered at a hidden prompt.",
)
@click.option(
    "--words",
    type=click.Choice(["12", "24"]),
    default=None,
    metavar="12|24",
    help="Generate a 12- or 24-word BIP39 offline mnemonic (default: 12).",
)
@click.option("--homerelay","-h", default=None, help=HOME_RELAY_HELP)
@click.option("--mint", "-m", default=None, help="home mint")
@click.option("--keepkey","-k", is_flag=True, show_default=True, default=False, help="Keep existing key(nsec).")
@click.option("--force", "-f", is_flag=True, show_default=True, default=False, help="Bypass safety confirmations and use defaults for omitted values.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
@click.option(
    "--include-recovery",
    is_flag=True,
    help="Include the seed phrase and nsec in JSON output. Requires --json.",
)

def init(import_nsec, nsec_file, use_entropy, words, keepkey, homerelay, mint, force, json_output, include_recovery):
    if include_recovery and not json_output:
        raise click.ClickException("--include-recovery requires --json")
    if use_entropy and (import_nsec or nsec_file):
        raise click.ClickException("--entropy cannot be combined with --import-nsec or --nsec-file")
    if use_entropy and keepkey:
        raise click.ClickException("--entropy and --keepkey are mutually exclusive")
    if keepkey and (import_nsec or nsec_file):
        raise click.ClickException("--keepkey cannot be combined with --import-nsec or --nsec-file")
    if words is not None and (use_entropy or import_nsec or nsec_file or keepkey):
        raise click.ClickException(
            "--words applies only to Acorn-generated keys and cannot be combined "
            "with --entropy, --import-nsec, --nsec-file, or --keepkey"
        )

    existing_nsec = config_obj.get("nsec")
    existing_home_relay = config_obj.get("home_relay")
    config_created = not CONFIG_FILE_EXISTED
    existing_wallet_config = CONFIG_FILE_EXISTED and existing_nsec
    existing_npub = None

    if existing_wallet_config:
        if json_output and not force:
            try:
                existing_acorn = Acorn(
                    nsec=existing_nsec,
                    relays=RELAYS,
                    mints=MINTS,
                    home_relay=existing_home_relay or HOME_RELAY,
                    logging_level=LOGGING_LEVEL,
                )
                existing_npub = existing_acorn.pubkey_bech32
            except Exception:
                pass
            _emit_json(
                {
                    "ok": False,
                    "reason": "confirmation_required",
                    "message": "Existing Acorn configuration detected. Re-run with --force to replace it non-interactively.",
                    "existing": {
                        "home_relay": existing_home_relay,
                        "npub": existing_npub,
                    },
                    "force": force,
                    "confirmations_completed": False,
                    "config_path": file_path,
                    "config_created": config_created,
                }
            )
            return

        if not json_output:
            click.echo("Existing Acorn configuration detected.")
            click.echo(f"home_relay: {existing_home_relay}")
        existing_acorn = None
        try:
            existing_acorn = Acorn(
                nsec=existing_nsec,
                relays=RELAYS,
                mints=MINTS,
                home_relay=existing_home_relay or HOME_RELAY,
                logging_level=LOGGING_LEVEL,
            )
            existing_npub = existing_acorn.pubkey_bech32
            if not json_output:
                click.echo(f"npub: {existing_npub}")
        except Exception:
            pass

        if not force and click.confirm("Display existing recovery/bootstrap material before continuing?", default=False):
            click.echo("Sensitive recovery material:")
            existing_seed_phrase = None
            if existing_acorn:
                try:
                    asyncio.run(existing_acorn.load_data())
                    existing_seed_phrase = existing_acorn.seed_phrase
                except Exception:
                    pass
            click.echo(
                _format_recovery_material(
                    {
                        "home_relay": existing_home_relay,
                        "seed_phrase": existing_seed_phrase,
                        "nsec": existing_nsec,
                    }
                )
            )

        if not force and not click.confirm("Initialize a new wallet and replace the local Acorn config?", default=False):
            raise click.ClickException("Initialization cancelled.")

    prompted_nsec = _private_key_from_secure_input(import_nsec, nsec_file)
    supplied_seed_phrase = None
    key_source = "imported_nsec" if prompted_nsec else "acorn_generated"
    if use_entropy:
        entropy_hex = click.prompt(
            "256-bit entropy (64 hexadecimal characters)",
            hide_input=True,
            confirmation_prompt="Repeat 256-bit entropy",
            err=True,
        )
        try:
            supplied_seed_phrase, prompted_nsec = seed_phrase_and_nsec_from_entropy(entropy_hex)
        except ValueError as exc:
            raise click.ClickException(f"Invalid entropy: {exc}") from exc
        key_source = "external_entropy"
    elif words is not None:
        strength = 128 if words == "12" else 256
        supplied_seed_phrase, prompted_nsec = generate_seed_phrase_and_nsec(
            strength=strength
        )
        key_source = "acorn_generated"
    if keepkey and not prompted_nsec:
        prompted_nsec = existing_nsec
        if prompted_nsec:
            key_source = "existing_nsec"
    generated_nsec = False
    if prompted_nsec:
        try:
            Keys(priv_k=prompted_nsec)
        except Exception as exc:
            raise click.ClickException(f"Invalid nsec: {exc}") from exc
        if supplied_seed_phrase is None and key_source == "acorn_generated":
            key_source = "imported_nsec"
        keepkey = supplied_seed_phrase is None
        generated_nsec = supplied_seed_phrase is not None
    else:
        prompted_nsec = Keys().private_key_bech32()
        keepkey = False
        generated_nsec = True

    home_relay = _normalize_relay(
        homerelay
        or (
            (HOME_RELAY or default_home_relay)
            if force or json_output
            else click.prompt("home relay", default=HOME_RELAY or default_home_relay)
        )
    )
    home_mint = _normalize_mint(
        mint
        or (
            (MINTS[0] if MINTS else default_mints[0])
            if force or json_output
            else click.prompt("home mint", default=(MINTS[0] if MINTS else default_mints[0]))
        )
    )
    init_mints = [home_mint]

    if not json_output:
        click.echo("Creating a new Acorn wallet.")
        click.echo(f"config: {file_path}")
        if config_created:
            click.echo("config_created: true")
        click.echo(f"home_relay: {home_relay}")
        click.echo(f"home_mint: {home_mint}")

    acorn_obj = Acorn(nsec=prompted_nsec, relays=[home_relay], mints=init_mints, home_relay=home_relay, logging_level=LOGGING_LEVEL)

    try:
        create_kwargs = {"keepkey": keepkey}
        if supplied_seed_phrase is not None:
            create_kwargs["seed_phrase"] = supplied_seed_phrase
        initialized_nsec = asyncio.run(acorn_obj.create_instance(**create_kwargs))
        asyncio.run(acorn_obj.load_data())
    except RuntimeError as exc:
        recovery = {
            "home_relay": home_relay,
            "seed_phrase": acorn_obj.seed_phrase,
            "nsec": acorn_obj.privkey_bech32,
        }
        if json_output:
            result = {
                "ok": False,
                "reason": "relay_wallet_readback_failed",
                "message": (
                    "Acorn could not verify the wallet record on the selected home relay. "
                    "The relay may reject this event kind, delay indexing, require authentication, "
                    "or be incompatible with Acorn wallet storage."
                ),
                "relay": home_relay,
                "home_mint": home_mint,
                "force": force,
                "confirmations_completed": bool(force or not existing_wallet_config),
                "local_config_replaced": False,
                "config_path": file_path,
                "config_created": config_created,
                "error": str(exc),
                "recovery_included": include_recovery,
            }
            if include_recovery:
                result["recovery"] = recovery
            _emit_json(result)
            return

        click.echo()
        click.echo("Acorn could not verify the wallet record on the selected home relay.")
        click.echo()
        click.echo(f"Relay: {home_relay}")
        click.echo("Possible causes:")
        click.echo("- the relay rejected Acorn's wallet event kind;")
        click.echo("- the relay accepted the write but did not return it on readback yet;")
        click.echo("- the relay requires authentication or has restrictive policies;")
        click.echo("- the relay is not compatible with Acorn wallet storage.")
        click.echo()
        click.echo("Your local config was not replaced.")
        click.echo()
        if not force and click.confirm(
            "Display recovery material for this attempted wallet?",
            default=False,
        ):
            click.echo("Sensitive recovery material:")
            click.echo(_format_recovery_material(recovery))
            click.echo()
        else:
            click.echo("Recovery material was not displayed or saved locally.")
            click.echo()
        raise click.ClickException(
            "Initialization was not completed. Try another relay, or retry this relay if you expect delayed indexing."
        ) from exc

    config_obj['nsec'] = initialized_nsec
    config_obj['home_relay'] = home_relay
    config_obj['mints'] = init_mints

    write_config()

    if json_output:
        result = {
            "ok": True,
            "replaced_existing": bool(existing_wallet_config),
            "force": force,
            "confirmations_completed": bool(force or not existing_wallet_config),
            "generated_nsec": generated_nsec,
            "key_source": key_source,
            "config_path": file_path,
            "config_created": config_created,
            "npub": acorn_obj.pubkey_bech32,
            "pubkey": acorn_obj.pubkey_hex,
            "home_relay": home_relay,
            "home_mint": home_mint,
            "recovery_included": include_recovery,
        }
        if include_recovery:
            result["recovery"] = {
                "home_relay": home_relay,
                "seed_phrase": acorn_obj.seed_phrase,
                "nsec": acorn_obj.privkey_bech32,
            }
        _emit_json(result)
        return

    click.echo("Acorn wallet initialized.")
    click.echo(f"config: {file_path}")
    click.echo(f"npub: {acorn_obj.pubkey_bech32}")
    if not force and click.confirm("Display new recovery/bootstrap material now?", default=True):
        click.echo("Sensitive recovery material:")
        click.echo(
            _format_recovery_material(
                {
                    "home_relay": home_relay,
                    "seed_phrase": acorn_obj.seed_phrase,
                    "nsec": acorn_obj.privkey_bech32,
                }
            )
        )
    elif force:
        click.echo("Recovery material was not displayed. Use 'acorn set --show-recovery' when ready.")
    


@click.command("set", help="set local config options")
@click.option('--import-nsec', is_flag=True, help='Replace the nsec through a hidden, confirmed prompt')
@click.option('--nsec-file', default=None, metavar='PATH', help="Read replacement nsec from a chmod-600 file, or '-' for stdin")
@click.option('--relays', '-r', default=None, help=RELAYS_HELP)
@click.option('--home', '-h', default=None, help=HOME_RELAY_HELP)
@click.option('--mints', '-m', default=None, help=MINTS_HELP)
@click.option('--xrelays', '-x', default=None, help='set replicate relays')
@click.option('--public-relays', default=None, help='store preferred public relays as an encrypted reserved record')
@click.option('--show-public-relays', is_flag=True, help='show preferred public relays from encrypted reserved record')
@click.option('--show-mint', is_flag=True, help='show effective home mint from wallet data')
@click.option('--show-recovery', is_flag=True, help='show recovery information: seed phrase and home relay')
@click.option('--logging', '-l', default=None, help='set logging level')
@click.option('--minimal', is_flag=True, help='rewrite config with only nsec and home_relay')
def set(import_nsec, nsec_file, home, relays, mints, xrelays, public_relays, show_public_relays, show_mint, show_recovery, logging: int, minimal):
    nsec = _private_key_from_secure_input(import_nsec, nsec_file, confirm=True)
    if nsec is not None:
        try:
            Keys(priv_k=nsec)
        except Exception as exc:
            raise click.ClickException(f"Invalid nsec: {exc}") from exc
    
    if nsec == None and relays == None and mints == None and home == None and xrelays==None and public_relays == None and not show_public_relays and not show_mint and not show_recovery and logging == None and not minimal:
        click.echo(yaml.safe_dump(_config_for_display(config_obj), default_flow_style=False, sort_keys=False))
        return

    show_only = (show_public_relays or show_mint or show_recovery) and nsec == None and relays == None and mints == None and home == None and xrelays == None and public_relays == None and logging == None and not minimal
   
    if minimal:
        config_obj.clear()
        config_obj.update(_minimize_config({"nsec": NSEC, "home_relay": HOME_RELAY, **config_obj}))

    if nsec != None:
        config_obj['nsec']=nsec

    if logging != None:
        config_obj['logging_level']= int(logging)

    
    if home != None:
        home_relay = _normalize_relay(home)
        config_obj['home_relay']=home_relay
    
    if relays != None:
        relay_array_wss = [_normalize_relay(each) for each in _split_csv(relays)]
        config_obj['relays']=relay_array_wss

    if xrelays != None:
        relay_array_wss = [_normalize_relay(each) for each in _split_csv(xrelays)]
        config_obj['replicate_relays']=relay_array_wss

    if mints != None:
        mint_array_https = [_normalize_mint(each) for each in _split_csv(mints)]
        config_obj['mints']=mint_array_https

    if public_relays != None:
        relay_array_wss = [_normalize_relay(each) for each in _split_csv(public_relays)]
        acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
        asyncio.run(acorn_obj.load_data())
        saved_relays = asyncio.run(acorn_obj.set_public_relays(relay_array_wss))
        click.echo("public_relays:")
        for each in saved_relays:
            click.echo(f"- {each}")

    if show_public_relays:
        acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
        asyncio.run(acorn_obj.load_data())
        saved_relays = asyncio.run(acorn_obj.get_public_relays())
        click.echo("public_relays:")
        for each in saved_relays:
            click.echo(f"- {each}")
        if not saved_relays:
            click.echo("(none set)")

    if show_mint:
        acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
        asyncio.run(acorn_obj.load_data())
        click.echo(f"home_mint: {acorn_obj.home_mint}")

    if show_recovery:
        if not click.confirm("Sensitive recovery material will be displayed. Continue?", default=False):
            raise click.ClickException("Recovery display cancelled.")
        acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
        asyncio.run(acorn_obj.load_data())
        click.echo(
            _format_recovery_material(
                {
                    "home_relay": acorn_obj.home_relay,
                    "seed_phrase": acorn_obj.seed_phrase,
                    "nsec": acorn_obj.privkey_bech32,
                }
            )
        )

    if show_only:
        return

    click.echo("set!")

    # print(config_obj)
    click.echo(yaml.safe_dump(_config_for_display(config_obj), default_flow_style=False, sort_keys=False))
    write_config()



@click.command("profile", help="get profile")
@click.option('--name', '-n', default="wallet", help=HOME_RELAY_HELP)
@click.option("--force","-f", is_flag=True, show_default=True, default=False, help="Force creation of profile.")
def get_profile(name, force):
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data(force_profile_creation=force))
    click.echo(acorn_obj.get_profile(name))

    asyncio.run(acorn_obj.get_ecash_latest())

@click.command("publish_kind0", help="Publish NIP-01 kind 0 metadata event")
@click.option("--name", default=None, help="profile name")
@click.option("--about", default=None, help="short bio")
@click.option("--picture", default=None, help="profile picture URL")
@click.option("--display-name", "display_name", default=None, help="display name")
@click.option("--nip05", default=None, help="nip05 identifier")
@click.option("--banner", default=None, help="banner URL")
@click.option("--website", default=None, help="website URL")
@click.option("--lud16", default=None, help="lightning address")
@click.option("--extra-json", default=None, help="extra metadata fields as JSON object")
@click.option("--relays", "-r", default=None, help="comma-separated relay list override")
def publish_kind0(
    name,
    about,
    picture,
    display_name,
    nip05,
    banner,
    website,
    lud16,
    extra_json,
    relays,
):
    relay_list = None
    if relays:
        relay_list = []
        for each in relays.split(","):
            each = each.strip()
            if not each:
                continue
            relay_list.append(each if each.startswith("wss://") else f"wss://{each}")

    extra_fields = {}
    if display_name is not None:
        extra_fields["display_name"] = display_name
    if nip05 is not None:
        extra_fields["nip05"] = nip05
    if banner is not None:
        extra_fields["banner"] = banner
    if website is not None:
        extra_fields["website"] = website
    if lud16 is not None:
        extra_fields["lud16"] = lud16

    if extra_json:
        try:
            parsed_extra = json.loads(extra_json)
            if not isinstance(parsed_extra, dict):
                click.echo("extra-json must be a JSON object")
                return
            extra_fields.update(parsed_extra)
        except Exception as exc:
            click.echo(f"Invalid extra-json: {exc}")
            return

    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        home_relay=HOME_RELAY,
        mints=MINTS,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    result = asyncio.run(
        acorn_obj.publish_kind0_metadata(
            name=name,
            about=about,
            picture=picture,
            extra_fields=extra_fields if extra_fields else None,
            relays=relay_list,
        )
    )
    click.echo(json.dumps(result, indent=2))

@click.command("publish_kind1", help="Publish NIP-01 kind 1 text note")
@click.argument("content", type=str)
@click.option("--relays", "-r", default=None, help="comma-separated relay list override")
def publish_kind1(content: str, relays: str | None):
    relay_list = None
    if relays:
        relay_list = []
        for each in relays.split(","):
            each = each.strip()
            if not each:
                continue
            relay_list.append(each if each.startswith("wss://") else f"wss://{each}")

    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        home_relay=HOME_RELAY,
        mints=MINTS,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    try:
        result = asyncio.run(acorn_obj.publish_kind1_post(content=content, relays=relay_list))
    except Exception as exc:
        click.echo(f"Failed to publish kind1: {exc}")
        return
    click.echo(json.dumps(result, indent=2))


@click.command("react", help="Publish NIP-25 reaction (kind 7) to an event")
@click.argument("event_id", type=str)
@click.option("--content", "-c", default="❤️", help="reaction content, default heart emoji")
@click.option("--pubkey", default=None, help="reacted event author pubkey (npub or hex)")
@click.option("--kind", "reacted_kind", default=None, type=int, help="reacted event kind")
@click.option("--relay-hint", default=None, help="relay hint for the e/p tags")
@click.option("--a-tag", default=None, help="optional addressable event coordinate")
@click.option("--extra-tags-json", default=None, help="optional extra tags as JSON array of arrays")
@click.option("--relays", "-r", default=None, help="comma-separated relay list override")
def react(
    event_id: str,
    content: str,
    pubkey: str | None,
    reacted_kind: int | None,
    relay_hint: str | None,
    a_tag: str | None,
    extra_tags_json: str | None,
    relays: str | None,
):
    relay_list = None
    if relays:
        relay_list = []
        for each in relays.split(","):
            each = each.strip()
            if not each:
                continue
            relay_list.append(each if each.startswith("wss://") else f"wss://{each}")

    extra_tags = None
    if extra_tags_json:
        try:
            parsed = json.loads(extra_tags_json)
            if not isinstance(parsed, list):
                click.echo("extra-tags-json must be a JSON array")
                return
            extra_tags = parsed
        except Exception as exc:
            click.echo(f"Invalid extra-tags-json: {exc}")
            return

    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        home_relay=HOME_RELAY,
        mints=MINTS,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    try:
        result = asyncio.run(
            acorn_obj.publish_reaction(
                target_event_id=event_id,
                content=content,
                reacted_pubkey=pubkey,
                reacted_kind=reacted_kind,
                relay_hint=relay_hint,
                a_tag=a_tag,
                extra_tags=extra_tags,
                relays=relay_list,
            )
        )
    except Exception as exc:
        click.echo(f"Failed to publish reaction: {exc}")
        return
    click.echo(json.dumps(result, indent=2))


@click.command("reply", help="Publish a kind 1 reply to an event")
@click.argument("event_id", type=str)
@click.argument("content", type=str)
@click.option("--pubkey", default=None, help="target event author pubkey (npub or hex)")
@click.option("--kind", "target_kind", default=None, type=int, help="target event kind")
@click.option("--relay-hint", default=None, help="relay hint for reply tags")
@click.option("--extra-tags-json", default=None, help="optional extra tags as JSON array of arrays")
@click.option("--relays", "-r", default=None, help="comma-separated relay list override")
def reply(
    event_id: str,
    content: str,
    pubkey: str | None,
    target_kind: int | None,
    relay_hint: str | None,
    extra_tags_json: str | None,
    relays: str | None,
):
    relay_list = None
    if relays:
        relay_list = []
        for each in relays.split(","):
            each = each.strip()
            if not each:
                continue
            relay_list.append(each if each.startswith("wss://") else f"wss://{each}")

    extra_tags = None
    if extra_tags_json:
        try:
            parsed = json.loads(extra_tags_json)
            if not isinstance(parsed, list):
                click.echo("extra-tags-json must be a JSON array")
                return
            extra_tags = parsed
        except Exception as exc:
            click.echo(f"Invalid extra-tags-json: {exc}")
            return

    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        home_relay=HOME_RELAY,
        mints=MINTS,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    try:
        result = asyncio.run(
            acorn_obj.publish_reply(
                target_event_id=event_id,
                content=content,
                target_pubkey=pubkey,
                target_kind=target_kind,
                relay_hint=relay_hint,
                extra_tags=extra_tags,
                relays=relay_list,
            )
        )
    except Exception as exc:
        click.echo(f"Failed to publish reply: {exc}")
        return
    click.echo(json.dumps(result, indent=2))

@click.command("setowner", help="get profile")
@click.option('--owner', '-o', default=None, help="set owner npub")
@click.option('--currency', '-c', default=None, help="set local currency")
def set_owner(owner, currency):
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    msg_out = asyncio.run(acorn_obj.set_owner_data(npub=owner,local_currency=currency))
    click.echo(msg_out)

@click.command("txhistory", help="transaction history")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def tx_history(json_output):   
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS,home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    tx_history = asyncio.run(acorn_obj.get_tx_history())
    if json_output:
        _emit_json(tx_history)
        return
    if not tx_history:
        click.echo("No transaction history found.")
        return
    for each in tx_history:
        click.echo(_format_tx_history_entry(each))
        click.echo()


@click.command("deposit", help="deposit funds into wallet via lightning invoice")
@click.argument('amount')
@click.option('--mint', '-m', default=None, help="deposit mint")
def deposit(amount: int, mint:str):
    lninvoice = None
    qr = qrcode.QRCode()
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS,home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    effective_mint = _normalize_mint(mint) if mint else acorn_obj.home_mint
    click.echo(f"amount: {amount} mint:{effective_mint}")
    cli_quote = acorn_obj.deposit(amount, mint)
    qr.add_data(cli_quote.invoice)
    qr.make(fit=True)
    click.echo(f"\n\nQuote:\n{cli_quote.quote}\n") 
    click.echo(f"\n\nPlease pay invoice:\n{cli_quote.invoice}\n") 
    qr.print_ascii(out=sys.stdout)
    click.echo()
    
    click.pause("Pay the invoice, then press Enter to check payment status...")
    start_time = time()
    end_time = start_time + 60

    while time() < end_time:
        click.echo("checking...")
        success, lninvoice = asyncio.run(acorn_obj.check_quote(cli_quote.quote, int(amount), mint))
        if success:
            break
        sleep(3)

    if not lninvoice:
        raise click.ClickException("Deposit was not confirmed before timeout.")

    asyncio.run(acorn_obj.add_tx_history(tx_type='C',amount=int(amount), comment="acorn deposit"))
    click.echo("Deposit confirmed.")
    click.echo(f"Amount: {int(amount)} sats")
    click.echo(f"Mint: {effective_mint}")
    click.echo(f"Balance: {acorn_obj.get_balance()} sats in {len(acorn_obj.proofs)} proofs")
    # asyncio.run(acorn_obj.get_tx_history())
 
@click.command("proofs", help="list proofs") 
def proofs():
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    click.echo(f"{acorn_obj.balance} sats in {len(acorn_obj.proofs)} proofs in {acorn_obj.events} events")
    for each in acorn_obj.proofs:
        click.echo(f"id: {each.id} amount: {each.amount} Y: {each.Y}")
    click.echo(f"{acorn_obj.powers_of_2_sum(acorn_obj.balance)}")
    click.echo("Proofs by keyset")
    all_proofs, keyset_amounts = acorn_obj._proofs_by_keyset()
    click.echo(f"{keyset_amounts}")
    click.echo(f"Known mints: {acorn_obj.known_mints}")
    # asyncio.run(acorn_obj.backup_proof_events())

@click.command("swap", help="swap proofs for new proofs")
@click.option("--consolidate","-c", is_flag=True, show_default=True, default=False, help="Consolidate proofs")
def swap(consolidate):
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # msg_out = wallet_obj.get_proofs()
    # wallet_obj.delete_proofs()
    # click.echo(msg_out)
    
    if consolidate:
        click.echo("Consolidate proofs")
        result_out = asyncio.run(acorn_obj.swap_multi_consolidate())
        click.echo(result_out)
    else:
        click.echo("Swap proofs")
        result_out = asyncio.run(acorn_obj.swap_multi_each())
        click.echo(result_out)

@click.command("repair-proofs", help="Prune spent proofs and rewrite wallet proof state")
@click.option("--force", "-f", is_flag=True, default=False, help="Allow repair to clear the wallet if no usable proofs survive")
def repair_proofs(force):
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    click.echo("Repair proofs")
    result_out = asyncio.run(acorn_obj.repair_proofs(force_prune_stale=force))
    click.echo(result_out)

@click.command("check-proofs", help="Check proof state at each mint without changing the wallet")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def check_proofs(json_output):
    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        mints=MINTS,
        home_relay=HOME_RELAY,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    report = asyncio.run(acorn_obj.check_proofs())
    if json_output:
        _emit_json(report)
    else:
        click.echo(_format_proof_check(report))

@click.command("pay", help="Payout funds to lightning address")
@click.argument('amount', default=21)
@click.argument('lnaddress', default='trbouma@openbalance.app')
@click.option('--comment','-c', default='Paid!')
def pay(amount,lnaddress: str, comment:str):
    click.echo(f"Pay to: {lnaddress}")
    acorn_obj = Acorn(nsec=NSEC, home_relay=HOME_RELAY, relays=RELAYS,mints=MINTS, logging_level=LOGGING_LEVEL)
    
    async def async_pay():
        await acorn_obj.load_data()
        try:
            msg_out, final_fees = await acorn_obj.pay_multi(amount,lnaddress,comment)
            click.echo(msg_out)
        except Exception as e:
            raise click.ClickException(str(e)) from e
    
    asyncio.run(async_pay())

@click.command("reconcile-payments", help="Resume pending Lightning payment reconciliation")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def reconcile_payments(json_output):
    acorn_obj = Acorn(
        nsec=NSEC,
        home_relay=HOME_RELAY,
        relays=RELAYS,
        mints=MINTS,
        logging_level=LOGGING_LEVEL,
    )

    async def run_reconciliation():
        await acorn_obj.load_data()
        await acorn_obj.acquire_lock()
        try:
            return await acorn_obj.reconcile_pending_melts()
        finally:
            await acorn_obj.release_lock()

    result = asyncio.run(run_reconciliation())
    if json_output:
        _emit_json(result)
        return

    click.echo("Lightning payment reconciliation")
    click.echo(f"Paid and finalized: {result['paid']}")
    click.echo(f"Confirmed unpaid: {result['unpaid']}")
    click.echo(f"Still unresolved: {result['unresolved']}")
    for quote in result["quotes"]:
        line = f"- {quote.get('quote') or '(invalid quote)'}: {quote['state']}"
        if quote.get("error"):
            line += f" ({quote['error']})"
        click.echo(line)
    if result["unresolved"]:
        click.echo("Do not retry unresolved payments; run this command again later.")

@click.command("put", help='write a private record')
@click.argument('label', default='default')
@click.argument('label_info', default='hello')
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
@click.option('--file','-f', default=None)
@click.option('--relays', '-r', default=None, help=RELAYS_HELP)
def put(label, label_info, kind, origin, file, relays):
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())
    blob_data = None
    if file:
        with open(file, 'rb') as f:
            blob_data = f.read()

    if click.confirm('Do you want to continue?'):
        try:
            stored = asyncio.run(
                acorn_obj.put_record(
                    label,
                    label_info,
                    record_kind=kind,
                    record_origin=origin,
                    blob_data=blob_data,
                    relays=relays,
                    return_result=True,
                )
            )
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Stored and verified: {stored['label']}")
        click.echo(f"Event: {stored['event_id']}")
        click.echo(f"Relays: {', '.join(stored['relays'])}")

@click.command("get", help='get a private wallet record')
@click.argument('label', default = "default")
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
@click.option('--relays', '-r', default=None, help=RELAYS_HELP)
@click.option('--raw', is_flag=True, help="Print the raw record object.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
@click.pass_context
def get(ctx, label,kind,origin,relays,raw,json_output):
    
    out_info = "None"
    logging_level = ctx.obj.get("logging_level", LOGGING_LEVEL)
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=logging_level)
    asyncio.run(acorn_obj.load_data())

    try:
        out_info = asyncio.run(
            acorn_obj.get_record_safebox(
                record_name=label,
                record_kind=kind,
                record_origin=origin,
                relays=relays,
            )
        )
        # safebox_info = wallet_obj.get_record(label)
        pass

    except Exception as exc:
        raise click.ClickException(
            f"Unable to read record {label!r}: {exc}"
        ) from exc
    
    if json_output:
        _emit_json(_record_to_dict(out_info, kind))
    else:
        click.echo(out_info if raw else _format_record(out_info, kind))

@click.command("get_blob", help='get blob data from private wallet record')
@click.argument('label', default = "default")
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
@click.option('--relays', '-r', default=None, help=RELAYS_HELP)
def get_blob(label,kind,origin,relays):
    
    out_info = "None"
    blob_type = None
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())

    try:
        blob_type, blob_data = asyncio.run(
            acorn_obj.get_record_blobdata(
                label,
                record_kind=kind,
                record_origin=origin,
                relays=relays,
            )
        )
        # safebox_info = wallet_obj.get_record(label)
        pass

    except Exception as exc:
        raise click.ClickException(
            f"Unable to read blob record {label!r}: {exc}"
        ) from exc
    
    click.echo(f"blob type: {blob_type} ")

@click.command("delete", help='request deletion of a private wallet record')
@click.argument('label', default = "default")
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
@click.option('--relays', '-r', default=None, help=RELAYS_HELP)
@click.option('--delete-blob', is_flag=True, help="Also request deletion of an associated encrypted blob.")
@click.option('--yes', '-y', is_flag=True, help="Skip the deletion confirmation.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def delete_record(label, kind, origin, relays, delete_blob, yes, json_output):
    if not yes:
        target = f"record {label!r} (kind {kind})"
        if delete_blob:
            target += " and its associated encrypted blob"
        click.confirm(
            f"Request deletion of {target}?",
            default=False,
            abort=True,
        )

    out_info = "None"
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())

    try:
        out_info = asyncio.run(
            acorn_obj.delete_record(
                label,
                record_kind=kind,
                record_origin=origin,
                relays=relays,
                delete_blob=delete_blob,
            )
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        _emit_json(out_info)
    else:
        click.echo(out_info["message"])
        click.echo(out_info.get("advisory", ""))
        if out_info.get("hidden_on"):
            click.echo(f"No longer visible on: {', '.join(out_info['hidden_on'])}")

@click.command("deletekind", help='delete kind records')
@click.option('--kind','-k', default=30000)
def delete_kind(kind):
    
    if not click.confirm("This is a sensitive operation. Continue?"):
        return
    
    out_info = "None"
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())

    try:
        out_info = asyncio.run(acorn_obj.delete_kind_events(kind))
        
        pass

    except:
        out_info = "No label found!"
    
    click.echo(out_info)

@click.command("burn", help="Burn this wallet's relay data and remove local wallet config")
@click.option("--send-to", default=None, help="NIP-05/npub/pubkey recipient for remaining ecash before burn")
@click.option("--send-relay", default=None, help="Relay to publish the optional ecash sweep transfer")
@click.option("--pay-to", default=None, help="Lightning address recipient for remaining funds before burn")
@click.option("--pay-amount", default=None, type=int, help="Lightning amount in sats; defaults to the maximum amount that fits mint fees")
@click.option("--relay", "relays", default=None, help="Comma-separated relays to burn from; defaults to home relay")
@click.option("--kinds", default=None, help="Comma-separated event kinds to burn; defaults to Acorn wallet/data kinds")
@click.option("--allow-funded", is_flag=True, default=False, help="Burn even if funds remain and no sweep/payment recipient is provided")
@click.option("--keep-local-config", is_flag=True, default=False, help="Do not remove the local Acorn config file after burn")
@click.option("--limit", default=1024, show_default=True, help="Maximum events to query for deletion")
@click.option("--force", "-f", is_flag=True, default=False, help="Bypass confirmation prompts")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output")
def burn(send_to, send_relay, pay_to, pay_amount, relays, kinds, allow_funded, keep_local_config, limit, force, json_output):
    burn_relays = [_normalize_relay(each) for each in _split_csv(relays)] if relays else None
    burn_kinds = [int(each) for each in _split_csv(kinds)] if kinds else None
    transfer_relay = _normalize_relay(send_relay) if send_relay else None
    if send_to and pay_to:
        raise click.ClickException("Use only one of --send-to for Acorn ecash or --pay-to for Lightning.")
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)

    try:
        asyncio.run(acorn_obj.load_data())
    except Exception as exc:
        if json_output:
            _emit_json({"status": "ERROR", "error": f"Wallet load failed: {exc}"})
            return
        raise click.ClickException(f"Wallet load failed: {exc}") from exc

    if not force:
        click.echo("This will publish deletion requests for this Acorn wallet's relay-backed data.")
        click.echo("NIP-09 deletion is advisory; relay retention behavior can vary.")
        click.echo(f"npub: {acorn_obj.pubkey_bech32}")
        click.echo(f"home_relay: {acorn_obj.home_relay}")
        click.echo(f"balance: {acorn_obj.get_balance()} sats")
        if pay_to and pay_amount is None:
            click.echo("Lightning pay amount will be reduced automatically, if needed, to fit mint fee reserve.")
        if acorn_obj.get_balance() > 0 and not send_to and not pay_to and not allow_funded:
            raise click.ClickException("Wallet has funds. Provide --send-to, --pay-to, or --allow-funded.")
        expected = f"burn {acorn_obj.pubkey_bech32[-8:]}"
        entered = click.prompt(f"Type '{expected}' to continue", default="", show_default=False)
        if entered.strip() != expected:
            raise click.ClickException("Burn cancelled.")

    try:
        result = asyncio.run(
            acorn_obj.burn_wallet(
                send_to=send_to,
                send_relay=transfer_relay,
                pay_to=pay_to,
                pay_amount=pay_amount,
                relays=burn_relays,
                kinds=burn_kinds,
                allow_funded=allow_funded,
                limit=limit,
            )
        )
    except Exception as exc:
        if json_output:
            _emit_json({"status": "ERROR", "error": str(exc)})
            return
        raise click.ClickException(f"Burn failed: {exc}") from exc

    local_config_removed = False
    if not keep_local_config:
        try:
            os.remove(file_path)
            config_obj.clear()
            local_config_removed = True
        except FileNotFoundError:
            local_config_removed = True
        except Exception as exc:
            result["local_config_error"] = str(exc)

    result["local_config_removed"] = local_config_removed
    result["local_config_path"] = file_path

    if json_output:
        _emit_json(result)
        return

    if result.get("sweep"):
        click.echo("Funds swept before burn.")
        click.echo(f"Sweep event: {result['sweep']['event_id']}")
        click.echo(f"Sweep amount: {result['sweep']['amount']} {result['sweep']['unit']}")
    elif result.get("payment"):
        click.echo("Funds paid by Lightning before burn.")
        click.echo(f"Payment recipient: {result['payment']['pay_to']}")
        click.echo(f"Payment amount: {result['payment']['amount']} {result['payment']['unit']}")
        click.echo(f"Payment fees: {result['payment']['fees']} sats")
        if result["payment"].get("auto_amount"):
            click.echo(f"Auto amount: yes (balance before: {result['payment'].get('balance_before')} sats)")
            if result["payment"].get("estimated_total") is not None:
                click.echo(f"Estimated total with fee reserve: {result['payment']['estimated_total']} sats")
        click.echo(f"Payment message: {result['payment']['message']}")
    elif result.get("balance_before", 0) > 0:
        click.echo("Funds were present and were not swept.")

    click.echo("Burn deletion request published." if result.get("delete_event_id") else "No matching relay events found to burn.")
    click.echo(f"Matched events: {result['matched']}")
    click.echo(f"Deleted events requested: {result['deleted']}")
    click.echo(f"Delete event: {result.get('delete_event_id') or '(none)'}")
    click.echo(f"Relays: {', '.join(result['relays'])}")
    click.echo("Kinds:")
    for kind, count in sorted(result.get("by_kind", {}).items(), key=lambda item: int(item[0])):
        click.echo(f"- {kind}: {count}")
    if not result.get("by_kind"):
        click.echo("- (none)")
    click.echo(f"Local config removed: {local_config_removed}")
    click.echo(result["advisory"])

@click.command("get_user_records", help='list private wallet records')
@click.option('--kind','-k', default=37375)
@click.option('--since','-s', default=None, help='since in hours')
@click.option('--relays', '-r', default=None, help=RELAYS_HELP)
@click.option('--labels', is_flag=True, help='print record labels only')
@click.option('--raw', is_flag=True, help='print raw record objects')
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def get_user_records(kind, since, relays, labels, raw, json_output):
    
    out_info = "None"
    relay_array = None
    relay_array_wss = []
    if relays != None:
        
        relay_array = str(relays).replace(" ","").split(',')
        relay_array_wss = _normalize_relay_csv(relays)
        if not json_output:
            click.echo(relay_array_wss)


    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())

    if since != None:
        since_adjusted = util_funcs.date_as_ticks((datetime.now()-timedelta(hours=int(since))))
        if not json_output:
            click.echo(since_adjusted)
    else:
        since_adjusted = None
    
    try:
        if labels:
            out_info = asyncio.run(
                acorn_obj.get_user_record_labels(
                    record_kind=kind,
                    since=since_adjusted,
                    relays=relay_array_wss,
                )
            )
            if json_output:
                _emit_json({"kind": kind, "count": len(out_info), "labels": out_info})
                return
            for each in out_info:
                click.echo(each)
            click.echo(f"No. of RECORDS: {len(out_info)}")
            return

        out_info = asyncio.run(acorn_obj.get_user_records(record_kind=kind, since=since_adjusted, relays=relay_array_wss))

        if json_output:
            _emit_json({"kind": kind, "count": len(out_info), "records": out_info})
        elif raw:
            for each in out_info:
                click.echo(each)
        else:
            for each in out_info:
                record_labels = each.get("tag") or ["(untitled)"]
                record_label = record_labels[0] if isinstance(record_labels, list) and record_labels else record_labels
                record_type = each.get("type", "unknown")
                click.echo(f"{record_label} ({record_type})")
        click.echo(f"No. of RECORDS: {len(out_info)}" )

    except Exception as e:
        click.echo(f"No label found! {e}")
    




@click.command("balance", help="show balance")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
@click.option("--mints", "show_mints", is_flag=True, help="Show balance grouped by mint and keyset.")
@click.option(
    "--verify",
    "verify_mint_state",
    is_flag=True,
    help="Read-only check of each proof at its mint.",
)
def balance(json_output, show_mints, verify_mint_state):
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    try:
        asyncio.run(acorn_obj.load_data())
    except RuntimeError as exc:
        msg = str(exc)
        if "No wallet data" in msg:
            raise click.ClickException(
                f"{msg} Run 'acorn recover \"<seed phrase>\" --homerelay <relay>' with the relay that holds your wallet events."
            )
        raise click.ClickException(f"Unable to load wallet data: {msg}")

    balance_sats = acorn_obj.get_balance()
    proof_count = len(acorn_obj.proofs)
    lightning_capacity = _lightning_capacity(acorn_obj)
    mint_balances = _balance_by_mint(acorn_obj) if show_mints else []
    verification = (
        asyncio.run(acorn_obj.check_proofs())
        if verify_mint_state
        else None
    )
    if json_output:
        payload = {
            "balance": balance_sats,
            "balance_basis": "relay-visible",
            "relay_visible_balance": balance_sats,
            "unit": "sat",
            "proof_count": proof_count,
            "lightning_capacity": lightning_capacity,
        }
        if verification is not None:
            payload["mint_verification"] = verification
            payload["mint_confirmed_balance"] = verification[
                "mint_confirmed_unspent"
            ]["amount"]
        if show_mints:
            payload["mints"] = mint_balances
        _emit_json(payload)
    else:
        click.echo(
            f"Relay-visible balance: {balance_sats} sats in {proof_count} proofs."
        )
        if verification is None:
            click.echo("Mint state not checked. Use 'acorn balance --verify'.")
        else:
            confirmed = verification["mint_confirmed_unspent"]
            click.echo(
                "Mint-confirmed spendable balance: "
                f"{confirmed['amount']} sats in {confirmed['proof_count']} proofs."
            )
            if verification["status"] != "clean":
                click.echo(
                    f"Proof verification status: {verification['status']}. "
                    f"{verification['recommendation']}"
                )
        click.echo(_format_lightning_capacity(lightning_capacity))
        if show_mints:
            click.echo(_format_balance_by_mint(mint_balances))

@click.command("receive-ecash", help="Receive Acorn ecash transfers into this Acorn")
@click.option("--since", default=None, type=int, help="Override incoming ecash transfer cursor.")
@click.option("--relay", "-r", default=None, help="Relay to sweep for incoming kind 1059 gift wraps or direct kind 7378 transfers.")
@click.option("--receive-key", is_flag=True, help="Prompt privately for a transient receiving nsec; it is not stored.")
@click.option("--receive-nsec-file", default=None, metavar="PATH", help="Read a transient receiving nsec from a chmod-600 file, or '-' for stdin.")
@click.option("--event-id", default=None, help="Receive a specific kind 1059 gift-wrap or direct kind 7378 event id; bypasses recipient tag and cursor query.")
@click.option("--no-advance", is_flag=True, help="Do not advance the stored receive cursor.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def receive_ecash(since, relay, receive_key, receive_nsec_file, event_id, no_advance, json_output):
    receive_nsec = _private_key_from_secure_input(receive_key, receive_nsec_file)
    if receive_nsec is not None:
        try:
            Keys(priv_k=receive_nsec)
        except Exception as exc:
            raise click.ClickException(f"Invalid receiving nsec: {exc}") from exc
    sweep_relays = [_normalize_relay(relay)] if relay else None
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    try:
        asyncio.run(acorn_obj.load_data())
        result = asyncio.run(
            acorn_obj.sweep_ecash_transfers(
                since=since,
                relays=sweep_relays,
                advance_cursor=not no_advance,
                receive_nsec=receive_nsec,
                event_id=event_id,
            )
        )
    except Exception as exc:
        if json_output:
            _emit_json({"status": "ERROR", "error": str(exc)})
            return
        raise click.ClickException(f"Receive ecash failed: {exc}") from exc

    if json_output:
        _emit_json(result)
        return

    if receive_nsec:
        click.echo("Used transient receive key; key was not stored.")
    relay_discovery = result.get("relay_discovery") or {}
    if relay_discovery:
        if relay_discovery.get("verified") and relay_discovery.get("relays"):
            click.echo(f"Resolved receive NIP-05: {relay_discovery.get('nip05')}")
            click.echo(f"Receive relays: {', '.join(relay_discovery.get('relays'))}")
        else:
            click.echo(f"Receive relay discovery: {relay_discovery.get('reason', 'not available')}")
    if result.get("event_id"):
        click.echo(f"Direct event lookup: {result['event_id']}")
    click.echo(f"Queried {result['queried']} transfer event(s).")
    if result["accepted_count"]:
        click.echo(
            f"Accepted {result['accepted_amount']} sats from "
            f"{result['accepted_count']} incoming ecash transfer(s)."
        )
    else:
        click.echo("No incoming ecash accepted.")
    if result.get("failed"):
        click.echo(f"Stopped after {len(result['failed'])} failed transfer event(s).")

@click.command("delete-ecash-transfers", help="Delete direct kind 7378 ecash transfer events authored by this Acorn")
@click.option("--relay", "-r", default=None, help="Relay to delete transfer events from; defaults to home relay")
@click.option("--recipient", default=None, help="Only delete transfers addressed to this nip05, npub, or pubkey")
@click.option("--since", default=None, type=int, help="Only match transfer events since this timestamp")
@click.option("--until", default=None, type=int, help="Only match transfer events until this timestamp")
@click.option("--limit", default=1024, type=int, help="Maximum transfer events to query")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output")
def delete_ecash_transfers(relay, recipient, since, until, limit, yes, json_output):
    delete_relays = [_normalize_relay(relay)] if relay else None
    if not yes and not json_output:
        click.echo("This will publish a NIP-09 deletion request for direct kind 7378 ecash transfer events authored by this wallet.")
        click.echo("Gift-wrapped transfers use a transient outer key and are not matched by this sender cleanup command.")
        click.echo(f"Relay: {delete_relays[0] if delete_relays else HOME_RELAY}")
        if recipient:
            click.echo(f"Recipient filter: {recipient}")
        if since:
            click.echo(f"Since: {since}")
        if until:
            click.echo(f"Until: {until}")
        if not click.confirm("Continue?", default=False):
            raise click.ClickException("Delete cancelled.")
    elif not yes and json_output:
        _emit_json({
            "status": "ERROR",
            "reason": "confirmation_required",
            "message": "Re-run with --yes to delete ecash transfer events non-interactively.",
        })
        return

    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    try:
        asyncio.run(acorn_obj.load_data())
        result = asyncio.run(
            acorn_obj.delete_ecash_transfer_events(
                relays=delete_relays,
                recipient=recipient,
                since=since,
                until=until,
                limit=limit,
            )
        )
    except Exception as exc:
        if json_output:
            _emit_json({"status": "ERROR", "error": str(exc)})
            return
        raise click.ClickException(f"Delete ecash transfers failed: {exc}") from exc

    if json_output:
        _emit_json(result)
        return

    click.echo(f"Matched {result['matched']} kind 7378 transfer event(s).")
    if result["deleted"]:
        click.echo(f"Published delete request: {result['delete_event_id']}")
    else:
        click.echo("No delete request published.")

@click.command("ecash-transfer", help="Send ecash to another Acorn using NIP-59 gift wrap with inner kind 7378")
@click.argument('amount', type=int)
@click.argument('recipient')
@click.option('--relay', '-r', default=None, help='relay to publish the transfer to; defaults to home relay')
@click.option('--comment', '-c', default='ecash transfer', help='transfer comment')
@click.option('--direct', is_flag=True, help='Publish direct sender-authored NIP-44 event instead of default gift-wrapped event')
@click.option('--json', "json_output", is_flag=True, help="Emit JSON output.")
def ecash_transfer(amount: int, recipient: str, relay: str | None, comment: str, direct: bool, json_output: bool):
    transfer_relay = _normalize_relay(relay) if relay else None
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    try:
        asyncio.run(acorn_obj.load_data())
        result = asyncio.run(
            acorn_obj.send_ecash_transfer(
                amount=amount,
                recipient=recipient,
                relay=transfer_relay,
                comment=comment,
                direct=direct,
            )
        )
    except Exception as exc:
        if json_output:
            _emit_json({"status": "ERROR", "error": str(exc)})
            return
        raise click.ClickException(f"Ecash transfer failed: {exc}") from exc

    if json_output:
        _emit_json(result)
        return

    click.echo("Ecash transfer published.")
    click.echo(f"Kind: {result['kind']}")
    if result.get("transfer_kind") and result["transfer_kind"] != result["kind"]:
        click.echo(f"Inner transfer kind: {result['transfer_kind']}")
    click.echo(f"Mode: {result['mode']}")
    click.echo(f"Event: {result['event_id']}")
    click.echo(f"Relays: {', '.join(result['relays'])}")
    if result.get("recipient_relays") and not transfer_relay:
        click.echo("Relay source: recipient NIP-05")
    click.echo(f"Recipient: {result['recipient_pubkey']}")
    click.echo(f"Amount: {result['amount']} {result['unit']}")
    if not result.get("deletable_by_sender"):
        click.echo("Deletion: outer event uses a transient key and is not sender-deletable unless that key is retained.")

@click.command("zap", help="Zap amount to event or to recipient")
@click.argument('amount', default=1)
@click.argument('event')
@click.option('--comment','-c', default='⚡️')
@click.option('--relays', '-r', default=None, help='comma-separated relays to search for the event')
def zap(amount:int, event, comment, relays):

    if event == None:
        click.echo("Need an event!")
        return
    if int(amount) <= 0:
        click.echo("Amount must be greater than zero.")
        return
    
    relay_array_wss = None
    if relays:
        relay_array_wss = [_normalize_relay(each) for each in _split_csv(relays)]

    acorn_obj = Acorn(
        nsec=NSEC,
        home_relay=HOME_RELAY,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        logging_level=LOGGING_LEVEL,
    )
    try:
        asyncio.run(acorn_obj.load_data())
        result_out = asyncio.run(acorn_obj.zap(amount,event,comment, relays=relay_array_wss))
        click.echo(result_out)
    except Exception as exc:
        click.echo(f"Zap failed: {exc}")

@click.command("accept_token", help="Accept cashu token")
@click.argument('token')
def accept_token(token):
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # msg_out = wallet_obj.get_proofs()
    # wallet_obj.delete_proofs()
    # click.echo(msg_out)
    try:
        result_out = asyncio.run(acorn_obj.accept_token(token))
        click.echo(result_out)
    except Exception as e:
        click.echo(f"Error: {e}")

@click.command("issue_token", help="Issue token amount")
@click.argument('amount', default=1)
def issue_token(amount:int):
    click.echo(f"Issue token amount: {amount}")
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS,mints=MINTS,home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    try:
        token = asyncio.run(acorn_obj.issue_token(amount))
        click.echo(token)
    except Exception as e:
        click.echo(f"Error: {e}")

@click.command("send", help="Send amount to nip05 address or npub")
@click.argument('amount', default=21)
@click.argument('nrecipient', default=None)
@click.option('--comment','-c', default='Paid!')
@click.option('--relays','-r', default=HOME_RELAY)
def send(amount,nrecipient: str, relays:str, comment:str):
    ecash_relays = []

   
    for each in relays.split(","):
        each = "wss://" + each if not each.startswith("wss://") else each
        ecash_relays.append(each)
    
    click.echo(f"Send to: {amount} to {nrecipient} via {ecash_relays}")
    acorn_obj = Acorn(nsec=NSEC, home_relay=HOME_RELAY, relays=RELAYS,mints=MINTS)
    asyncio.run(acorn_obj.load_data())
    token = asyncio.run(acorn_obj.issue_token(amount))
    out_msg = asyncio.run(acorn_obj.secure_transmittal(nrecipient=nrecipient, dm_relays=ecash_relays,message=token, kind=1059))
    click.echo(out_msg)

@click.command("dm", help="Send message to nip05 address or npub")
@click.argument('nrecipient', default=None)
@click.argument('message', default="hello")
@click.option('--relays','-r', default=HOME_RELAY)
def dm_recipient(nrecipient: str, message: str, relays:str):
    dm_relays = []

   
    for each in relays.split(","):
        each = "wss://" + each if not each.startswith("wss://") else each
        dm_relays.append(each)
    
    click.echo(f"Send: {message} to {nrecipient} via {dm_relays}")
    acorn_obj = Acorn(nsec=NSEC, home_relay=HOME_RELAY, relays=RELAYS,mints=MINTS)
    asyncio.run(acorn_obj.load_data())
    msg_out = asyncio.run(acorn_obj.secure_dm(nrecipient=nrecipient,message=message,dm_relays=dm_relays))
    click.echo(msg_out)

@click.command("stx", help="Send secure transmitta to nip05 address or npub")
@click.argument('nrecipient', default=None)
@click.argument('message', default="hello")
@click.option('--relays','-r', default=HOME_RELAY)
@click.option('--kind','-k', default=1059)
def stx_recipient(nrecipient: str, message: str, relays:str, kind:int):
    dm_relays = []

   
    for each in relays.split(","):
        each = "wss://" + each if not each.startswith("wss://") else each
        dm_relays.append(each)
    
    click.echo(f"Send: {message} to {nrecipient} via {dm_relays}")
    acorn_obj = Acorn(nsec=NSEC, home_relay=HOME_RELAY, relays=RELAYS,mints=MINTS)
    asyncio.run(acorn_obj.load_data())
    msg_out = asyncio.run(acorn_obj.secure_transmittal(nrecipient=nrecipient,message=message,dm_relays=dm_relays,kind=kind))
    click.echo(msg_out)    

@click.command("run", help='run as a service')
@click.option('--relays','-r', default=HOME_RELAY)
def run(relays):
    # click.echo(WELCOME_MSG)
    # click.echo(f"Running as a service...")
    relay_array = []
    relays_str = relays.split(',')
    for each in relays_str:
        each = "wss://" + each if not each.startswith("wss://") else each
        relay_array.append(each)
    acorn_obj = Acorn(nsec=NSEC,relays=RELAYS,mints=MINTS,home_relay=HOME_RELAY)
    asyncio.run(acorn_obj.load_data())    
    acorn_obj.run(relay_array)

@click.command("recover", help='Recover a wallet from a privately entered seed phrase')
@click.option('--seed-file', default=None, metavar='PATH', help="Read the seed phrase from a chmod-600 file, or '-' for stdin")
@click.option('--homerelay','-h', default=HOME_RELAY)
@click.option('--legacy', is_flag=True, default=False, help='Use legacy key derivation (default: False)')
@click.option('--yes', '-y', is_flag=True, help="Skip the recovery confirmation; required with --seed-file '-'")
def recover(seed_file, homerelay, legacy, yes):
    if seed_file == "-" and not yes:
        raise click.ClickException("--seed-file '-' requires --yes because stdin cannot also answer the confirmation prompt.")
    seedphrase = (
        _read_secret_file(seed_file, "seed phrase")
        if seed_file
        else _prompt_secret("BIP39 seed phrase")
    )

    normalized_seedphrase = " ".join(seedphrase.strip().split())
    try:
        nsec = recover_nsec_from_seed(seed_phrase=normalized_seedphrase, legacy=legacy)
    except ValueError as exc:
        raise click.ClickException(
            f"Invalid recovery phrase: {exc}. "
            "Check spelling and ensure you entered the exact BIP39 words in order."
        )
   
    


        
    if homerelay != None:
        if "wss://" in homerelay:
            home_relay = homerelay
        elif "ws://" in homerelay:
            home_relay = homerelay
        else:
            home_relay = f"wss://{homerelay}"
    
    if yes or click.confirm(f"Do you want to recover to this wallet using {home_relay}?"):
        wallet_obj = Acorn(nsec=nsec, relays=RELAYS, home_relay=home_relay, logging_level=LOGGING_LEVEL)
        try:
            asyncio.run(wallet_obj.load_data())
        except RuntimeError as exc:
            msg = str(exc)
            if "No wallet data" in msg:
                raise click.ClickException(
                    f"{msg} Try again with --homerelay set to the relay where this wallet was created."
                )
            raise click.ClickException(f"Unable to verify recovered wallet data: {msg}")

        NSEC = nsec
        config_obj['home_relay'] = home_relay
        config_obj['nsec'] = nsec
        write_config()
        click.echo("Acorn wallet recovered.")
        click.echo(f"npub: {wallet_obj.pubkey_bech32}")
        click.echo(f"home_relay: {home_relay}")

@click.command("replicate", help="replicate this wallet's signed events to a target relay")
@click.option('--target', '-t', required=True, help='target relay to copy wallet events to')
@click.option('--source', '-s', default=None, help='source relay; defaults to home_relay')
@click.option('--kinds', '-k', default=None, help='comma-separated event kinds; defaults to core Acorn wallet kinds')
@click.option('--limit', '-l', default=1024, type=int, help='maximum events to query from the source relay')
@click.option('--yes', '-y', is_flag=True, help='skip confirmation prompt')
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def replicate(target, source, kinds, limit, yes, json_output):
    target_relay = _normalize_relay(target)
    source_relay = _normalize_relay(source) if source else HOME_RELAY
    try:
        event_kinds = [int(each) for each in _split_csv(kinds)] if kinds else None
    except ValueError as exc:
        raise click.ClickException("--kinds must be a comma-separated list of integers") from exc

    if not yes:
        click.echo("This will copy this wallet's signed relay events to another relay.")
        click.echo(f"Source: {source_relay}")
        click.echo(f"Target: {target_relay}")
        if event_kinds:
            click.echo(f"Kinds: {', '.join(str(each) for each in event_kinds)}")
        else:
            click.echo("Kinds: core Acorn wallet kinds")
        if not click.confirm("Continue?", default=False):
            raise click.ClickException("Replication cancelled.")

    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, mints=MINTS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    result = asyncio.run(
        acorn_obj.replicate_to_relay(
            target_relay=target_relay,
            source_relay=source_relay,
            kinds=event_kinds,
            limit=limit,
        )
    )

    if json_output:
        _emit_json(result)
        return

    click.echo(f"Replication status: {result['status']}")
    click.echo(f"Source: {result['source_relay']}")
    click.echo(f"Target: {result['target_relay']}")
    click.echo(f"Events: {result['replicated']}")
    click.echo(f"Target readback verified: {result['verified']}")
    if result["missing_event_ids"]:
        click.echo(f"Missing after readback: {len(result['missing_event_ids'])}")
    if result["source_may_be_truncated"]:
        click.echo(
            "Warning: source query reached the event limit; replication may "
            "be incomplete. Increase --limit or use a backend replication tool."
        )
    click.echo("Kinds:")
    for kind, count in sorted(result["by_kind"].items(), key=lambda item: int(item[0])):
        click.echo(f"- {kind}: {count}")

@click.command("checklock", help='acquire lock')
def check_lock():
    click.echo("check lock")
    acorn_obj = Acorn(nsec=NSEC,relays=RELAYS,mints=MINTS,home_relay=HOME_RELAY)
    asyncio.run(acorn_obj.load_data()) 
    msg_out = asyncio.run(acorn_obj.check_lock()) 
    click.echo(f"Check {msg_out}")

@click.command("acquirelock", help='acquire lock')
def acquire_lock():
    click.echo("get lock")
    acorn_obj = Acorn(nsec=NSEC,relays=RELAYS,mints=MINTS,home_relay=HOME_RELAY)
    asyncio.run(acorn_obj.load_data()) 
    asyncio.run(acorn_obj.acquire_lock()) 
    click.echo("lock is acquired via cli")

@click.command("releaselock", help='release lock')
def release_lock():
    click.echo("get lock")
    acorn_obj = Acorn(nsec=NSEC,relays=RELAYS,mints=MINTS,home_relay=HOME_RELAY)
    asyncio.run(acorn_obj.load_data()) 
    asyncio.run(acorn_obj.release_lock()) 

@click.command("issue_record", help="Issue private record")
@click.argument('content', default="hello")
@click.option('--tags','-t', default=[])
@click.option('--kind','-k', default=34002, help="kind for record")

def issue_record(content:str, tags, kind:int):
  
    
    click.echo(f"Issue content: {content}")
    acorn_obj = Acorn(nsec=NSEC, home_relay=HOME_RELAY, relays=RELAYS,mints=MINTS)
    asyncio.run(acorn_obj.load_data()) 
    tags = ["p", acorn_obj.pubkey_hex]
    issued_record = asyncio.run(acorn_obj.issue_private_record(content=content, tags=tags, kind=kind))
    issued_str = json.dumps(issued_record.data())
    asyncio.run(acorn_obj.put_record(record_name="test credential", record_value=issued_str,record_type="private_record", record_kind=kind)) 
   
    retrieved_record =    asyncio.run(acorn_obj.get_record(record_name="test credential", record_kind=kind)) 
    safebox_record = SafeboxRecord(**retrieved_record)
    click.echo(f"-"*80)
    click.echo(f"Event data string: {issued_str} : ")
    click.echo(f"-"*80)
    click.echo(f"Is Valid: {issued_record.is_valid()} Is parameter replaceable {issued_record.is_parameter_replacable()} Is ephemeral {issued_record.is_ephemeral()} tags: {issued_record.tags}")
    click.echo(f"-"*80)
    
    click.echo(f"Retrieve Record: {retrieved_record} Safebox Record:{safebox_record}")
    payload_json = json.loads(retrieved_record["payload"])
    click.echo(f"Payload in json {payload_json}")
    event_from_record = Event.load(payload_json)
    click.echo(f"Even from Record: {event_from_record}")


@click.command("set_trusted_entities", help='set trusted_entities')
@click.argument('trusted_entities', default='default')
def set_trusted_entities(trusted_entities):    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  

    if click.confirm('Do you want to set trusted entities?'):    
     asyncio.run(acorn_obj.set_trusted_entities(pub_list_str=trusted_entities))
    
@click.command("get_trusted_entities", help='get trusted_entities')
def get_trusted_entities():    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  

      
    record_out = asyncio.run(acorn_obj.get_trusted_entities(relays=RELAYS))
    click.echo(record_out)

@click.command("get_root_entities", help='get root entities')
def get_root_entities():    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  

      
    record_out = asyncio.run(acorn_obj.get_root_entities(relays=RELAYS))
    click.echo(record_out)   

@click.command("set_wot_entities", help='set wot entities npub:tag:relay')
@click.argument('wot_entities', default='default')
def set_wot_entities(wot_entities):    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  

    if click.confirm(f'Do you want to set wot entities? {wot_entities}'):    
     asyncio.run(acorn_obj.set_wot_entities(pub_list_str=wot_entities))

@click.command("get_wot_entities", help='get wot entities')
def get_wot_entities():    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  
      
    record_out = asyncio.run(acorn_obj.get_wot_entities(relays=RELAYS))
    click.echo(record_out) 

@click.command("get_wot_scores", help='get wot score')
@click.argument('pubkey', default="pubkey")
@click.option('--relays','-r', default=[])
def get_wot_scores(pubkey, relays):    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info()) 
    if relays:
        relay_list = []
        for each in relays.split(','):
            
            relay_list.append(each if each.startswith("wss://") else "wss://" + each) 
    click.echo(relay_list)  
    record_out = asyncio.run(acorn_obj.get_wot_scores(pub_key_to_score=pubkey, relays=relay_list))
    click.echo(record_out) 

@click.command("create_grant", help='create grant from offer')
@click.argument('offer_name', type=str)
@click.argument('holder',type=str )
@click.option('--offer','-o', type=int, help='offer kind')
@click.option('--grant','-g' ,type=str, default=None, help='grant kind, if not provided it default to offer_kind+1')

def create_grant_from_offer(offer_name:str, holder:str, offer:int, grant: int):    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  

    # if click.confirm('Do you want to create a grant from an offer?'): 
    try:   
        asyncio.run(acorn_obj.create_grant_from_offer(offer_kind=offer,offer_name=offer_name,holder=holder))
    except Exception as e:
        click.echo(e)

@click.command("create_request", help='create request from grant')
@click.argument('grant_name', type=str)
@click.option('--grant','-g' ,type=int, default=34100, help='grant kind')

def create_request_from_grant(grant_name:str, grant: int):    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())  

    # if click.confirm('Do you want to create a grant from an offer?'): 
    try:   
        asyncio.run(acorn_obj.create_request_from_grant(grant_name=grant_name, grant_kind=grant))
    except Exception as e:
        click.echo(e)

@click.command("get_social_profile", help='get wot score')
@click.argument('npub', default="npub")
@click.option('--relays','-r', default=[])
def get_social_profile(npub, relays):   
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info()) 
    if relays:
        relay_list = []
        for each in relays.split(','):
            
            relay_list.append(each if each.startswith("wss://") else "wss://" + each) 
    click.echo(relay_list)  
    click.echo(f"npub: {npub} relay_list: {relay_list}") 
    record_out = asyncio.run(acorn_obj.get_social_profile(npub, relay_list))
    
    click.echo(record_out) 

@click.command("get_latest_posts", help="Get latest kind 1 posts by nip05 and print post content")
@click.argument("nip05", type=str)
@click.option("--limit", "-l", default=10, help="maximum number of posts to return")
@click.option("--relays", "-r", default=None, help="comma-separated relay list to override defaults")
def get_latest_posts(nip05: str, limit: int, relays: str | None):
    relay_list = None
    if relays:
        relay_list = []
        for each in relays.split(","):
            each = each.strip()
            if not each:
                continue
            relay_list.append(each if each.startswith("wss://") else "wss://" + each)

    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        home_relay=HOME_RELAY,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    try:
        posts = asyncio.run(
            acorn_obj.get_latest_kind1_posts_by_nip05(
                nip05=nip05,
                limit=limit,
                relays=relay_list,
            )
        )
    except Exception as exc:
        click.echo(f"Failed to fetch posts: {exc}")
        return

    if not posts:
        click.echo("No posts found.")
        return

    for each_post in posts:
        click.echo(f"id: {each_post.get('id')}")
        click.echo(f"pubkey: {each_post.get('pubkey')}")
        click.echo(f"created_at: {each_post.get('created_at')}")
        click.echo(each_post.get("content", ""))
        click.echo("-" * 40)


@click.command("get_follow_posts", help="Get latest kind 1 posts from your follow list")
@click.option("--limit", "-l", default=20, help="maximum number of posts to return")
@click.option("--relays", "-r", default=None, help="comma-separated relay list to override defaults")
def get_follow_posts(limit: int, relays: str | None):
    relay_list = None
    if relays:
        relay_list = []
        for each in relays.split(","):
            each = each.strip()
            if not each:
                continue
            relay_list.append(each if each.startswith("wss://") else "wss://" + each)

    acorn_obj = Acorn(
        nsec=NSEC,
        relays=RELAYS,
        public_relays=PUBLIC_RELAYS,
        home_relay=HOME_RELAY,
        logging_level=LOGGING_LEVEL,
    )
    asyncio.run(acorn_obj.load_data())
    try:
        posts = asyncio.run(
            acorn_obj.get_latest_kind1_posts_from_follow_list(
                limit=limit,
                relays=relay_list,
            )
        )
    except Exception as exc:
        click.echo(f"Failed to fetch follow posts: {exc}")
        return

    if not posts:
        click.echo("No follow posts found.")
        return

    for each_post in posts:
        click.echo(f"id: {each_post.get('id')}")
        click.echo(f"pubkey: {each_post.get('pubkey')}")
        click.echo(f"created_at: {each_post.get('created_at')}")
        click.echo(each_post.get("content", ""))
        click.echo("-" * 40)

cli.add_command(info)
cli.add_command(init)
cli.add_command(set)

cli.add_command(check_lock)
cli.add_command(acquire_lock)
cli.add_command(release_lock)

cli.add_command(get_profile)
cli.add_command(publish_kind0)
cli.add_command(publish_kind1)
cli.add_command(react)
cli.add_command(reply)
cli.add_command(tx_history)
cli.add_command(deposit)
cli.add_command(proofs)
cli.add_command(swap)
cli.add_command(check_proofs)
cli.add_command(repair_proofs)
cli.add_command(pay)
cli.add_command(reconcile_payments)
cli.add_command(put)
cli.add_command(get)
cli.add_command(get_blob)
cli.add_command(delete_record)
cli.add_command(delete_kind)
cli.add_command(burn)
cli.add_command(get_user_records)
cli.add_command(balance)
cli.add_command(ecash_transfer)
cli.add_command(receive_ecash)
cli.add_command(delete_ecash_transfers)
cli.add_command(zap)
cli.add_command(accept_token)
cli.add_command(issue_token)
cli.add_command(send)
cli.add_command(recover)
cli.add_command(replicate)
cli.add_command(set_owner)
cli.add_command(dm_recipient)
cli.add_command(stx_recipient)
cli.add_command(run)
cli.add_command(issue_record)
cli.add_command(set_trusted_entities)
cli.add_command(get_trusted_entities)
cli.add_command(get_root_entities)
cli.add_command(set_wot_entities)
cli.add_command(get_wot_entities)
cli.add_command(get_wot_scores)
cli.add_command(get_social_profile)
cli.add_command(get_latest_posts)
cli.add_command(get_follow_posts)
cli.add_command(create_grant_from_offer)
cli.add_command(create_request_from_grant)


if __name__ == "__main__":
   cli()
