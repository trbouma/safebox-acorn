import asyncio, sys, click, os, yaml, logging, warnings, contextlib, io
from typing import List
from monstr.encrypt import Keys
from monstr.client.client import Client, ClientPool
from monstr.event.event import Event
from monstr.util import util_funcs
def _import_acorn_runtime():
    warnings.filterwarnings(
        "ignore",
        message=r"liboqs version .* differs from liboqs-python version .*",
        category=UserWarning,
        module=r"oqs.*",
    )
    if os.getenv("ACORN_SHOW_IMPORT_WARNINGS"):
        from acorn.acorn import Acorn
        from acorn.models import nostrProfile, SafeboxItem, SafeboxRecord
        from acorn.lightning import lightning_address_pay
        from acorn.func_utils import recover_nsec_from_seed
        return Acorn, nostrProfile, SafeboxItem, SafeboxRecord, lightning_address_pay, recover_nsec_from_seed

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from acorn.acorn import Acorn
        from acorn.models import nostrProfile, SafeboxItem, SafeboxRecord
        from acorn.lightning import lightning_address_pay
        from acorn.func_utils import recover_nsec_from_seed
        return Acorn, nostrProfile, SafeboxItem, SafeboxRecord, lightning_address_pay, recover_nsec_from_seed


(
    Acorn,
    nostrProfile,
    SafeboxItem,
    SafeboxRecord,
    lightning_address_pay,
    recover_nsec_from_seed,
) = _import_acorn_runtime()
from datetime import datetime, timedelta
import json

from time import sleep, time
import qrcode
from acorn.prompts import (
    WELCOME_MSG,
    INFO_HELP,
    SET_HELP,
    NSEC_HELP,
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

home_directory = os.path.expanduser('~')
cli_directory = '.acorn'
config_file = 'config.yml'
config_directory = os.path.join(home_directory, cli_directory)
file_path = os.path.join(home_directory, cli_directory, config_file)
def write_config():
     with open(file_path, 'w') as file:        
        yaml.dump(config_obj, file)


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


def _looks_like_relay(value: str) -> bool:
    value = str(value).strip()
    return value.startswith(("wss://", "ws://"))


def _split_csv(value: str) -> list[str]:
    return [each for each in str(value).replace(" ", "").split(",") if each]


def _minimize_config(config: dict) -> dict:
    return {
        "nsec": config.get("nsec"),
        "home_relay": config.get("home_relay", default_home_relay),
    }

os.makedirs(config_directory, exist_ok=True)

CONFIG_FILE_EXISTED = os.path.exists(file_path)

if CONFIG_FILE_EXISTED:
    with open(file_path, 'r') as file:
        config_obj = yaml.safe_load(file)
else:
   
    config_obj = {  'nsec': Keys().private_key_bech32(),
                    "home_relay": default_home_relay}
    with open(file_path, 'w') as file:        
        yaml.dump(config_obj, file)

HOME_RELAY = config_obj.get('home_relay', default_home_relay)
RELAYS  = config_obj.get('relays') or [HOME_RELAY]
PUBLIC_RELAYS = config_obj.get('public_relays') or default_public_relays
NSEC    = config_obj.get('nsec',None)
MINTS   = config_obj.get('mints') or default_mints
REPLICATE_RELAYS = config_obj.get('replicate_relays') or []
LOGGING_LEVEL = int(config_obj.get('logging_level', default_logging_level))

if NSEC == None:
    click.echo("Private key is not set")
    if click.confirm("Do you want to generate a new key?"):
        
        write_config()

    sys.exit()

write_config()


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



@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Show debug logs.")
@click.pass_context
def cli(ctx, verbose):
    global LOGGING_LEVEL
    ctx.ensure_object(dict)
    LOGGING_LEVEL = _configure_cli_logging(verbose)
    ctx.obj["logging_level"] = LOGGING_LEVEL

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

      A Protocol-First Sovereign Data Haven
    """.rstrip())
    click.echo()
    click.echo("A sovereign protocol component for identity, records, value, and recovery.")
    click.echo("Reciprocal resilience without shared secrets.")
    click.echo()
    click.echo(WELCOME_MSG.strip())
    click.echo()
    click.echo("Identity")
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

@click.option("--nsec", "-n", default=None, help=NSEC_HELP)
@click.option("--homerelay","-h", default=None, help=HOME_RELAY_HELP)
@click.option("--mint", "-m", default=None, help="home mint")
@click.option("--keepkey","-k", is_flag=True, show_default=True, default=False, help="Keep existing key(nsec).")
@click.option("--longseed","-l", is_flag=True, show_default=True, default=False, help="Generate long seed of 24 words")
@click.option("--force", "-f", is_flag=True, show_default=True, default=False, help="Bypass safety confirmations and use defaults for omitted values.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")

def init(nsec, keepkey, longseed, homerelay, mint, force, json_output):
    existing_nsec = config_obj.get("nsec")
    existing_home_relay = config_obj.get("home_relay")
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
            click.echo(f"home_relay: {existing_home_relay}")
            if existing_acorn:
                try:
                    asyncio.run(existing_acorn.load_data())
                    click.echo(f"seed_phrase: {existing_acorn.seed_phrase}")
                except Exception:
                    click.echo("seed_phrase: unavailable")
            click.echo(f"nsec: {existing_nsec}")

        if not force and not click.confirm("Initialize a new wallet and replace the local Acorn config?", default=False):
            raise click.ClickException("Initialization cancelled.")

    prompted_nsec = nsec
    if keepkey and not prompted_nsec:
        prompted_nsec = existing_nsec
    generated_nsec = False
    if not prompted_nsec and not (force or json_output):
        prompted_nsec = click.prompt(
            "nsec private key (leave blank to generate a new wallet key)",
            default="",
            show_default=False,
        ).strip()
    if prompted_nsec and _looks_like_relay(prompted_nsec) and not homerelay:
        homerelay = prompted_nsec
        prompted_nsec = ""
        if not json_output:
            click.echo("Relay URL detected; using it as the home relay and generating a new nsec.")
    if prompted_nsec:
        try:
            Keys(priv_k=prompted_nsec)
        except Exception as exc:
            raise click.ClickException(f"Invalid nsec: {exc}") from exc
        keepkey = True
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
        click.echo(f"home_relay: {home_relay}")
        click.echo(f"home_mint: {home_mint}")

    acorn_obj = Acorn(nsec=prompted_nsec, relays=[home_relay], mints=init_mints, home_relay=home_relay, logging_level=LOGGING_LEVEL)

    try:
        initialized_nsec = asyncio.run(acorn_obj.create_instance(keepkey=keepkey, longseed=longseed))
        asyncio.run(acorn_obj.load_data())
    except RuntimeError as exc:
        recovery = {
            "home_relay": home_relay,
            "seed_phrase": acorn_obj.seed_phrase,
            "nsec": acorn_obj.privkey_bech32,
        }
        if json_output:
            _emit_json(
                {
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
                    "error": str(exc),
                    "recovery": recovery,
                }
            )
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
        click.echo("Recovery material for this attempted wallet:")
        click.echo(f"home_relay: {recovery['home_relay']}")
        click.echo(f"seed_phrase: {recovery['seed_phrase']}")
        click.echo(f"nsec: {recovery['nsec']}")
        click.echo()
        raise click.ClickException(
            "Initialization was not completed. Try another relay, or retry this relay if you expect delayed indexing."
        ) from exc

    config_obj['nsec'] = initialized_nsec
    config_obj['home_relay'] = home_relay
    config_obj['mints'] = init_mints

    write_config()

    if json_output:
        _emit_json(
            {
                "ok": True,
                "replaced_existing": bool(existing_wallet_config),
                "force": force,
                "confirmations_completed": bool(force or not existing_wallet_config),
                "generated_nsec": generated_nsec,
                "npub": acorn_obj.pubkey_bech32,
                "pubkey": acorn_obj.pubkey_hex,
                "home_relay": home_relay,
                "home_mint": home_mint,
                "recovery": {
                    "home_relay": home_relay,
                    "seed_phrase": acorn_obj.seed_phrase,
                    "nsec": acorn_obj.privkey_bech32,
                },
            }
        )
        return

    click.echo("Acorn wallet initialized.")
    click.echo(f"npub: {acorn_obj.pubkey_bech32}")
    if force or click.confirm("Display new recovery/bootstrap material now?", default=True):
        click.echo("Sensitive recovery material:")
        click.echo(f"home_relay: {home_relay}")
        click.echo(f"seed_phrase: {acorn_obj.seed_phrase}")
        click.echo(f"nsec: {acorn_obj.privkey_bech32}")
    


@click.command("set", help="set local config options")
@click.option('--nsec', '-n', default=None, help=NSEC_HELP)
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
def set(nsec, home, relays, mints, xrelays, public_relays, show_public_relays, show_mint, show_recovery, logging: int, minimal):
    
    if nsec == None and relays == None and mints == None and home == None and xrelays==None and public_relays == None and not show_public_relays and not show_mint and not show_recovery and logging == None and not minimal:
        click.echo(yaml.dump(config_obj, default_flow_style=False))
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
        click.echo(f"home_relay: {acorn_obj.home_relay}")
        click.echo(f"seed_phrase: {acorn_obj.seed_phrase}")
        click.echo(f"nsec: {acorn_obj.privkey_bech32}")

    if show_only:
        return

    click.echo("set!")

    # print(config_obj)
    click.echo(yaml.dump(config_obj,default_flow_style=False))
    with open(file_path, 'w') as file:        
        yaml.dump(config_obj, file)



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
def tx_history():   
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS,home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    tx_history = asyncio.run(acorn_obj.get_tx_history())
    for each in tx_history:
        click.echo(each)


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
            click.echo(f"MSG OUT: {msg_out}")
            if "ERROR" in msg_out:
                raise Exception(f"ERROR {msg_out}")
            
            await acorn_obj.add_tx_history(tx_type='D',amount=amount, comment=f"to {lnaddress} {comment}", fees=final_fees)
        except Exception as e:
            click.echo(f"CLI Error: {e}")
    
    asyncio.run(async_pay())

@click.command("put", help='write a private record')
@click.argument('label', default='default')
@click.argument('label_info', default='hello')
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
@click.option('--file','-f', default=None)
def put(label, label_info, kind, origin, file):
    jsons=None
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())
    # click.echo(wallet.get_wallet_info())
    blob_data = None
    if file:
        with open(file, 'rb') as f:
            blob_data = f.read()

    if click.confirm('Do you want to continue?'):    
     asyncio.run(acorn_obj.put_record(label, label_info,record_kind=kind, record_origin=origin, blob_data=blob_data))

@click.command("get", help='get a private wallet record')
@click.argument('label', default = "default")
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
@click.option('--raw', is_flag=True, help="Print the raw record object.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
@click.pass_context
def get(ctx, label,kind,origin,raw,json_output):
    
    out_info = "None"
    logging_level = ctx.obj.get("logging_level", LOGGING_LEVEL)
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=logging_level)
    asyncio.run(acorn_obj.load_data())

    try:
        out_info = asyncio.run(acorn_obj.get_record_safebox(record_name=label,record_kind=kind,record_origin=origin))
        # safebox_info = wallet_obj.get_record(label)
        pass

    except Exception:
        raise click.ClickException(f"No record found for: {label}")
    
    if json_output:
        _emit_json(_record_to_dict(out_info, kind))
    else:
        click.echo(out_info if raw else _format_record(out_info, kind))

@click.command("get_blob", help='get blob data from private wallet record')
@click.argument('label', default = "default")
@click.option('--kind','-k', default=37375)
@click.option('--origin','-o', default=None)
def get_blob(label,kind,origin):
    
    out_info = "None"
    blob_type = None
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())

    try:
        blob_type, blob_data = asyncio.run(acorn_obj.get_record_blobdata(label,record_kind=kind,record_origin=origin))
        # safebox_info = wallet_obj.get_record(label)
        pass

    except:
        click.echo("Error")
        out_info = "No label found!"
    
    click.echo(f"blob type: {blob_type} ")

@click.command("delete", help='get a private wallet record')
@click.argument('label', default = "default")
def delete_record(label):
    
    out_info = "None"
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints= MINTS, logging_level=LOGGING_LEVEL)
    asyncio.run(acorn_obj.load_data())

    try:
        out_info = asyncio.run(acorn_obj.delete_record(label))
        # safebox_info = wallet_obj.get_record(label)
        pass

    except:
        out_info = "No label found!"
    
    click.echo(out_info)

@click.command("deletekind", help='delete kind records')
@click.option('--kind','-k', default=30000)
def delete_kind(kind):
    
    if not click.confirm("Are you really sure? This is a dangerous option"):
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
        
        for each in relay_array:
            if each.startswith("ws://"):
                continue
            relay_array_wss.append(each if "wss://" in each else "wss://"+each)
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
def balance(json_output):
    
    acorn_obj = Acorn(nsec=NSEC, relays=RELAYS, home_relay=HOME_RELAY, mints=MINTS, logging_level=LOGGING_LEVEL)
    try:
        asyncio.run(acorn_obj.load_data())
    except RuntimeError as exc:
        msg = str(exc)
        if "No wallet data on" in msg:
            raise click.ClickException(
                f"{msg} Run 'acorn recover \"<seed phrase>\" --homerelay <relay>' with the relay that holds your wallet events."
            )
        raise click.ClickException(f"Unable to load wallet data: {msg}")

    balance_sats = acorn_obj.get_balance()
    proof_count = len(acorn_obj.proofs)
    if json_output:
        _emit_json({
            "balance": balance_sats,
            "unit": "sat",
            "proof_count": proof_count,
        })
    else:
        click.echo(f"{balance_sats} sats in {proof_count} proofs.")

@click.command("receive-ecash", help="Receive kind 7378 ecash transfers into this Acorn")
@click.option("--since", default=None, type=int, help="Override incoming ecash transfer cursor.")
@click.option("--relay", "-r", default=None, help="Relay to sweep for incoming kind 7378 ecash transfers.")
@click.option("--receive-nsec", default=None, help="Transient receiving nsec used only to decrypt incoming transfers; it is not stored.")
@click.option("--event-id", default=None, help="Receive a specific kind 7378 event id; bypasses recipient tag and cursor query.")
@click.option("--no-advance", is_flag=True, help="Do not advance the stored receive cursor.")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON output.")
def receive_ecash(since, relay, receive_nsec, event_id, no_advance, json_output):
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

@click.command("delete-ecash-transfers", help="Delete kind 7378 ecash transfer events authored by this Acorn")
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
        click.echo("This will publish a NIP-09 deletion request for kind 7378 ecash transfer events authored by this wallet.")
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

@click.command("ecash-transfer", help="Send ecash to another Acorn using kind 7378")
@click.argument('amount', type=int)
@click.argument('recipient')
@click.option('--relay', '-r', default=None, help='relay to publish the transfer to; defaults to home relay')
@click.option('--comment', '-c', default='ecash transfer', help='transfer comment')
@click.option('--json', "json_output", is_flag=True, help="Emit JSON output.")
def ecash_transfer(amount: int, recipient: str, relay: str | None, comment: str, json_output: bool):
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
    click.echo(f"Event: {result['event_id']}")
    click.echo(f"Relays: {', '.join(result['relays'])}")
    if result.get("recipient_relays") and not transfer_relay:
        click.echo("Relay source: recipient NIP-05")
    click.echo(f"Recipient: {result['recipient_pubkey']}")
    click.echo(f"Amount: {result['amount']} {result['unit']}")

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

@click.command("recover", help='Recover a wallet from seed phrase')
@click.argument('seedphrase', default=None)
@click.option('--homerelay','-h', default=HOME_RELAY)
@click.option('--legacy', is_flag=True, default=False, help='Use legacy key derivation (default: False)')
def recover(seedphrase, homerelay, legacy):
    if not seedphrase:
        raise click.ClickException("Missing seed phrase. Usage: acorn recover \"word1 word2 ...\"")

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
    
    if click.confirm(f"Do you want to recover to this wallet using {home_relay}?"):
        wallet_obj = Acorn(nsec=nsec, relays=RELAYS, home_relay=home_relay, logging_level=LOGGING_LEVEL)
        try:
            asyncio.run(wallet_obj.load_data())
        except RuntimeError as exc:
            msg = str(exc)
            if "No wallet data on" in msg:
                raise click.ClickException(
                    f"{msg} Try again with --homerelay set to the relay where this wallet was created."
                )
            raise click.ClickException(f"Unable to verify recovered wallet data: {msg}")

        click.echo(f"Recover seed phrase {nsec}")
        NSEC = nsec
        config_obj['home_relay'] = home_relay
        config_obj['nsec'] = nsec
        write_config()

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

    click.echo("Replicated wallet events.")
    click.echo(f"Source: {result['source_relay']}")
    click.echo(f"Target: {result['target_relay']}")
    click.echo(f"Events: {result['replicated']}")
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
cli.add_command(repair_proofs)
cli.add_command(pay)
cli.add_command(put)
cli.add_command(get)
cli.add_command(get_blob)
cli.add_command(delete_record)
cli.add_command(delete_kind)
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
