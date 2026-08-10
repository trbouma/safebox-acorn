"""Nostr Silent Payments receipt and sweep primitives owned by Acorn.

The NSP derivation was first explored in OpenETR. Acorn is the canonical home
for the user-controlled Bitcoin capability: public address derivation,
txid-targeted receipt detection, explicit sweep construction, and broadcast.
"""

from __future__ import annotations

from decimal import getcontext, setcontext
import hashlib
import json
import math
import re
import time
from urllib import error, parse, request

import bech32
from coincurve import PublicKey
from monstr.encrypt import Keys
import secp256k1


# BTClib currently changes the process-wide Decimal context during import.
# Preserve the caller's context until that upstream side effect is removed.
_decimal_context = getcontext().copy()
try:
    from btclib.ecc import ssa
    from btclib.script import sig_hash
    from btclib.script.script_pub_key import ScriptPubKey
    from btclib.script.witness import Witness
    from btclib.tx import OutPoint, Tx, TxIn, TxOut
finally:
    setcontext(_decimal_context)
    del _decimal_context


SECP256K1_ORDER = (
    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
)
BECH32M_CONST = 0x2BC830A3
SILENT_PAYMENT_SCAN_TAG = "nostr-sp/scan"
SILENT_PAYMENT_SPEND_TAG = "nostr-sp/spend"
SCAN_OUTPUT_SEARCH_LIMIT = 4096
DEFAULT_BITCOIN_API_BASE = "https://blockstream.info/api"
_HRP_PATTERN = re.compile(r"[a-z0-9]{1,15}")
_TXID_PATTERN = re.compile(r"[0-9a-f]{64}")


class BitcoinCapabilityError(RuntimeError):
    """A safe, caller-facing failure in Acorn's Bitcoin capability."""


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _tagged_hash(tag: str, payload: bytes) -> bytes:
    tag_hash = _sha256(tag.encode("utf-8"))
    return _sha256(tag_hash + tag_hash + payload)


def _normalize_txid(txid: str) -> str:
    normalized = str(txid or "").strip().lower()
    if _TXID_PATTERN.fullmatch(normalized) is None:
        raise BitcoinCapabilityError(
            "Bitcoin transaction id must be 64 hexadecimal characters."
        )
    return normalized


def _nostr_keys(nostr_key: str) -> tuple[Keys, str]:
    candidate = str(nostr_key or "").strip()
    try:
        if candidate.startswith("nsec1"):
            return Keys(priv_k=candidate), "nsec"
        if candidate.startswith("npub1"):
            return Keys(pub_k=candidate), "npub"
    except Exception as exc:
        raise BitcoinCapabilityError("A valid nsec or npub is required.") from exc
    raise BitcoinCapabilityError("A valid nsec or npub is required.")


def _derive_compressed_pubkey(private_key: bytes) -> bytes:
    try:
        return PublicKey.from_valid_secret(private_key).format(compressed=True)
    except (TypeError, ValueError) as exc:
        raise BitcoinCapabilityError("The private key is not valid secp256k1 material.") from exc


def _normalize_bip340_private_key(private_key_hex: str) -> tuple[bytes, bytes]:
    scalar = int(private_key_hex, 16)
    if scalar <= 0 or scalar >= SECP256K1_ORDER:
        raise BitcoinCapabilityError(
            "The private key is outside the valid secp256k1 scalar range."
        )
    private_key = bytes.fromhex(private_key_hex)
    compressed = _derive_compressed_pubkey(private_key)
    if compressed[0] == 0x02:
        return private_key, compressed
    normalized = (SECP256K1_ORDER - scalar).to_bytes(32, "big")
    compressed = _derive_compressed_pubkey(normalized)
    if compressed[0] != 0x02:
        raise BitcoinCapabilityError("Unable to normalize the Nostr private key.")
    return normalized, compressed


def _derive_tweak_scalar(base_pubkey: bytes, tag: str) -> int:
    tweak = int.from_bytes(_tagged_hash(tag, base_pubkey), "big") % SECP256K1_ORDER
    if tweak == 0:
        raise BitcoinCapabilityError(f"{tag} derivation produced an invalid zero tweak.")
    return tweak


def _tweak_pubkey(base_pubkey: bytes, tweak: int) -> bytes:
    try:
        return PublicKey(base_pubkey).add(
            tweak.to_bytes(32, "big")
        ).format(compressed=True)
    except (TypeError, ValueError) as exc:
        raise BitcoinCapabilityError("Unable to derive a Silent Payment public key.") from exc


def _bech32m_encode(hrp: str, data: list[int]) -> str:
    values = bech32.bech32_hrp_expand(hrp) + data
    polymod = (
        bech32.bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ BECH32M_CONST
    )
    checksum = [(polymod >> (5 * (5 - index))) & 31 for index in range(6)]
    return hrp + "1" + "".join(bech32.CHARSET[value] for value in data + checksum)


def _encode_silent_payment_address(
    scan_pubkey: bytes,
    spend_pubkey: bytes,
    *,
    hrp: str,
) -> str:
    if len(scan_pubkey) != 33 or len(spend_pubkey) != 33:
        raise BitcoinCapabilityError(
            "Silent Payment scan and spend public keys must be compressed."
        )
    converted = bech32.convertbits(scan_pubkey + spend_pubkey, 8, 5, True)
    if converted is None:
        raise BitcoinCapabilityError("Unable to encode Silent Payment public keys.")
    return _bech32m_encode(hrp, [0, *converted])


def _derive_silent_payment_material(
    nostr_key: str,
    *,
    hrp: str = "sp",
) -> dict[str, str]:
    normalized_hrp = str(hrp or "").strip().lower()
    if _HRP_PATTERN.fullmatch(normalized_hrp) is None:
        raise BitcoinCapabilityError("Silent Payment address prefix is invalid.")

    keys, input_kind = _nostr_keys(nostr_key)
    npub = keys.public_key_bech32()
    if not npub:
        raise BitcoinCapabilityError("Unable to derive the Nostr public key.")

    private_key_hex = keys.private_key_hex()
    if private_key_hex:
        normalized_private, base_pubkey = _normalize_bip340_private_key(
            private_key_hex
        )
        base_scalar: int | None = int.from_bytes(normalized_private, "big")
    else:
        public_key_hex = keys.public_key_hex()
        if not public_key_hex or len(public_key_hex) != 64:
            raise BitcoinCapabilityError("A valid Nostr public key is required.")
        try:
            base_pubkey = b"\x02" + bytes.fromhex(public_key_hex)
            PublicKey(base_pubkey)
        except (TypeError, ValueError) as exc:
            raise BitcoinCapabilityError(
                "The npub does not encode a valid secp256k1 public key."
            ) from exc
        base_scalar = None

    scan_tweak = _derive_tweak_scalar(base_pubkey, SILENT_PAYMENT_SCAN_TAG)
    spend_tweak = _derive_tweak_scalar(base_pubkey, SILENT_PAYMENT_SPEND_TAG)
    scan_pubkey = _tweak_pubkey(base_pubkey, scan_tweak)
    spend_pubkey = _tweak_pubkey(base_pubkey, spend_tweak)

    scan_private_key_hex = ""
    spend_private_key_hex = ""
    if base_scalar is not None:
        scan_scalar = (base_scalar + scan_tweak) % SECP256K1_ORDER
        spend_scalar = (base_scalar + spend_tweak) % SECP256K1_ORDER
        if scan_scalar == 0 or spend_scalar == 0:
            raise BitcoinCapabilityError(
                "Silent Payment derivation produced an invalid zero private key."
            )
        scan_private_key_hex = scan_scalar.to_bytes(32, "big").hex()
        spend_private_key_hex = spend_scalar.to_bytes(32, "big").hex()

    return {
        "input_kind": input_kind,
        "npub": npub,
        "scan_private_key_hex": scan_private_key_hex,
        "spend_private_key_hex": spend_private_key_hex,
        "scan_public_key_hex": scan_pubkey.hex(),
        "spend_public_key_hex": spend_pubkey.hex(),
        "silent_payment_address": _encode_silent_payment_address(
            scan_pubkey,
            spend_pubkey,
            hrp=normalized_hrp,
        ),
    }


def derive_nostr_silent_payment_address(
    nostr_key: str,
    *,
    hrp: str = "sp",
) -> str:
    """Derive an Acorn NSP address from an nsec or npub."""

    return _derive_silent_payment_material(nostr_key, hrp=hrp)[
        "silent_payment_address"
    ]


def _script_type(script_hex: str) -> str:
    if script_hex.startswith("76a914") and script_hex.endswith("88ac") and len(script_hex) == 50:
        return "p2pkh"
    if script_hex.startswith("a914") and script_hex.endswith("87") and len(script_hex) == 46:
        return "p2sh"
    if script_hex.startswith("0014") and len(script_hex) == 44:
        return "p2wpkh"
    if script_hex.startswith("5120") and len(script_hex) == 68:
        return "p2tr"
    return "unknown"


def _normalize_script_type(script_type: str) -> str:
    aliases = {
        "v0_p2wpkh": "p2wpkh",
        "v1_p2tr": "p2tr",
        "v0_p2wsh": "p2wsh",
        "p2sh-p2wpkh": "p2sh",
    }
    normalized = str(script_type or "").strip().lower()
    return aliases.get(normalized, normalized)


def _extract_input_pubkey(txin: dict[str, object]) -> bytes | None:
    prevout = txin.get("prevout")
    if not isinstance(prevout, dict):
        return None
    script_hex = str(prevout.get("scriptpubkey") or "")
    script_type = _normalize_script_type(
        str(prevout.get("scriptpubkey_type") or _script_type(script_hex))
    )
    witness = txin.get("witness") or []
    scriptsig_hex = str(txin.get("scriptsig") or "")
    try:
        if script_type == "p2wpkh" and isinstance(witness, list) and witness:
            pubkey = bytes.fromhex(str(witness[-1]))
            return pubkey if len(pubkey) == 33 else None
        if script_type == "p2sh":
            redeem_hex = scriptsig_hex[2:] if scriptsig_hex.startswith("16") else scriptsig_hex
            if redeem_hex.startswith("0014") and isinstance(witness, list) and witness:
                pubkey = bytes.fromhex(str(witness[-1]))
                return pubkey if len(pubkey) == 33 else None
            return None
        if script_type == "p2tr" and script_hex.startswith("5120"):
            xonly = bytes.fromhex(script_hex[4:])
            return b"\x02" + xonly if len(xonly) == 32 else None
        if script_type == "p2pkh":
            script = bytes.fromhex(scriptsig_hex)
            for index in range(len(script), 32, -1):
                candidate = script[index - 33:index]
                if len(candidate) == 33 and candidate[0] in (0x02, 0x03):
                    return candidate
    except ValueError:
        return None
    return None


def _combine_pubkeys(pubkeys: list[bytes]) -> bytes | None:
    if not pubkeys:
        return None
    try:
        objects = [secp256k1.PublicKey(pubkey, raw=True) for pubkey in pubkeys]
        combined = secp256k1.PublicKey()
        combined.combine([pubkey.public_key for pubkey in objects])
        return combined.serialize(compressed=True)
    except Exception:
        return None


def _outpoint_bytes(txid: str, vout: int) -> bytes:
    return bytes.fromhex(txid)[::-1] + int(vout).to_bytes(4, "little")


def _fetch_json(url: str, *, timeout: float, operation: str) -> object:
    req = request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "safebox-acorn/0.1"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise BitcoinCapabilityError(f"{operation} failed with HTTP {exc.code}.") from exc
    except error.URLError as exc:
        raise BitcoinCapabilityError(f"{operation} failed: {exc.reason}.") from exc
    except TimeoutError as exc:
        raise BitcoinCapabilityError(f"{operation} timed out.") from exc
    except json.JSONDecodeError as exc:
        raise BitcoinCapabilityError(f"{operation} returned invalid JSON.") from exc


def fetch_bitcoin_transaction(
    txid: str,
    *,
    api_base: str = DEFAULT_BITCOIN_API_BASE,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Fetch one public transaction from a Blockstream-compatible backend."""

    normalized_txid = _normalize_txid(txid)
    url = f"{api_base.rstrip('/')}/tx/{parse.quote(normalized_txid)}"
    last_rate_limit_error: error.HTTPError | None = None
    for attempt in range(4):
        try:
            payload = _fetch_json(
                url,
                timeout=timeout,
                operation="Bitcoin transaction lookup",
            )
            break
        except BitcoinCapabilityError as exc:
            cause = exc.__cause__
            if isinstance(cause, error.HTTPError) and cause.code == 429 and attempt < 3:
                last_rate_limit_error = cause
                retry_after = cause.headers.get("Retry-After") if cause.headers else None
                try:
                    delay = float(retry_after) if retry_after else 1.5 * (2**attempt)
                except ValueError:
                    delay = 1.5 * (2**attempt)
                time.sleep(min(delay, 12.0))
                continue
            raise
    else:
        raise BitcoinCapabilityError(
            "Bitcoin transaction lookup remained rate-limited after retries."
        ) from last_rate_limit_error
    if not isinstance(payload, dict):
        raise BitcoinCapabilityError("Bitcoin transaction lookup returned an unexpected payload.")
    return payload


def fetch_bitcoin_address_utxos(
    address: str,
    *,
    api_base: str = DEFAULT_BITCOIN_API_BASE,
    timeout: float = 5.0,
) -> list[dict[str, object]]:
    """Fetch public UTXO state from a Blockstream-compatible backend."""

    normalized_address = str(address or "").strip()
    if not normalized_address:
        raise BitcoinCapabilityError("A Bitcoin address is required for UTXO lookup.")
    payload = _fetch_json(
        f"{api_base.rstrip('/')}/address/{parse.quote(normalized_address)}/utxo",
        timeout=timeout,
        operation="Bitcoin UTXO lookup",
    )
    if not isinstance(payload, list):
        raise BitcoinCapabilityError("Bitcoin UTXO lookup returned an unexpected payload.")
    utxos: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        status = item.get("status") or {}
        status = status if isinstance(status, dict) else {}
        utxos.append(
            {
                "txid": str(item.get("txid") or "").lower(),
                "vout": int(item.get("vout", 0)),
                "value": int(item.get("value", 0)),
                "confirmed": bool(status.get("confirmed")),
                "block_height": int(status.get("block_height", 0) or 0),
            }
        )
    return utxos


def _scan_transaction(
    nsec: str,
    transaction: dict[str, object],
) -> dict[str, object]:
    material = _derive_silent_payment_material(nsec)
    if not material["scan_private_key_hex"]:
        raise BitcoinCapabilityError("An nsec is required to scan Silent Payments.")
    vin = transaction.get("vin")
    vout = transaction.get("vout")
    if not isinstance(vin, list) or not isinstance(vout, list):
        raise BitcoinCapabilityError("Transaction payload is missing vin or vout arrays.")

    input_pubkeys: list[bytes] = []
    outpoints: list[bytes] = []
    for txin in vin:
        if not isinstance(txin, dict):
            continue
        pubkey = _extract_input_pubkey(txin)
        input_txid = str(txin.get("txid") or "").lower()
        if pubkey is None or _TXID_PATTERN.fullmatch(input_txid) is None:
            continue
        input_pubkeys.append(pubkey)
        outpoints.append(_outpoint_bytes(input_txid, int(txin.get("vout", 0) or 0)))

    if not input_pubkeys:
        return {
            "txid": str(transaction.get("txid") or "").lower(),
            "matched_outputs": [],
            "input_pubkey_count": 0,
            "warning": "No eligible input public keys were found.",
        }
    summed_input_pubkey = _combine_pubkeys(input_pubkeys)
    if summed_input_pubkey is None:
        return {
            "txid": str(transaction.get("txid") or "").lower(),
            "matched_outputs": [],
            "input_pubkey_count": len(input_pubkeys),
            "warning": "Input public keys summed to an invalid point.",
        }

    input_hash = _tagged_hash(
        "BIP0352/Inputs",
        min(outpoints) + summed_input_pubkey,
    )
    input_hash_scalar = int.from_bytes(input_hash, "big") % SECP256K1_ORDER
    scan_private_scalar = int(material["scan_private_key_hex"], 16)
    shared_scalar = (input_hash_scalar * scan_private_scalar) % SECP256K1_ORDER
    if input_hash_scalar == 0 or shared_scalar == 0:
        return {
            "txid": str(transaction.get("txid") or "").lower(),
            "matched_outputs": [],
            "input_pubkey_count": len(input_pubkeys),
            "warning": "Silent Payment shared-secret derivation produced zero.",
        }

    ecdh_point = secp256k1.PublicKey(summed_input_pubkey, raw=True).tweak_mul(
        shared_scalar.to_bytes(32, "big")
    )
    ecdh_compressed = ecdh_point.serialize(compressed=True)
    remaining: dict[bytes, tuple[int, dict[str, object]]] = {}
    for output_index, output in enumerate(vout):
        if not isinstance(output, dict):
            continue
        script_hex = str(output.get("scriptpubkey") or "")
        script_type = _normalize_script_type(
            str(output.get("scriptpubkey_type") or _script_type(script_hex))
        )
        if script_type != "p2tr" or not script_hex.startswith("5120"):
            continue
        try:
            xonly = bytes.fromhex(script_hex[4:])
        except ValueError:
            continue
        if len(xonly) == 32:
            remaining[xonly] = (output_index, output)

    spend_pubkey = bytes.fromhex(material["spend_public_key_hex"])
    matches: list[dict[str, object]] = []
    for shared_secret_index in range(SCAN_OUTPUT_SEARCH_LIMIT):
        if not remaining:
            break
        tweak = _tagged_hash(
            "BIP0352/SharedSecret",
            ecdh_compressed + shared_secret_index.to_bytes(4, "big"),
        )
        tweak_scalar = int.from_bytes(tweak, "big") % SECP256K1_ORDER
        if tweak_scalar == 0:
            continue
        derived = (
            secp256k1.PublicKey(spend_pubkey, raw=True)
            .tweak_add(tweak_scalar.to_bytes(32, "big"))
            .serialize(compressed=True)
        )
        matched = remaining.pop(derived[1:], None)
        if matched is None:
            continue
        output_index, output = matched
        matches.append(
            {
                "vout": output_index,
                "value": int(output.get("value", 0) or 0),
                "scriptpubkey_address": str(output.get("scriptpubkey_address") or ""),
                "output_pubkey_hex": derived.hex(),
                "priv_key_tweak_hex": tweak.hex(),
                "shared_secret_index": shared_secret_index,
            }
        )

    return {
        "txid": str(transaction.get("txid") or "").lower(),
        "matched_outputs": matches,
        "input_pubkey_count": len(input_pubkeys),
        "warning": "" if matches else "No matching Silent Payment output was found.",
    }


def _raw_receipt_scan(
    *,
    nsec: str,
    txid: str,
    api_base: str,
    timeout: float,
) -> tuple[dict[str, str], dict[str, object]]:
    normalized_txid = _normalize_txid(txid)
    material = _derive_silent_payment_material(nsec)
    if not material["scan_private_key_hex"]:
        raise BitcoinCapabilityError("An nsec is required to scan Silent Payments.")
    transaction = fetch_bitcoin_transaction(
        normalized_txid,
        api_base=api_base,
        timeout=timeout,
    )
    return material, _scan_transaction(nsec, transaction)


def detect_silent_payment_receipts(
    *,
    nsec: str,
    txid: str,
    api_base: str = DEFAULT_BITCOIN_API_BASE,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Detect matching outputs and expose only public availability fields."""

    material, transaction = _raw_receipt_scan(
        nsec=nsec,
        txid=txid,
        api_base=api_base,
        timeout=timeout,
    )
    normalized_txid = str(transaction["txid"])
    matches: list[dict[str, object]] = []
    for match in transaction["matched_outputs"]:
        address = str(match["scriptpubkey_address"])
        vout = int(match["vout"])
        exact_utxo = next(
            (
                item
                for item in fetch_bitcoin_address_utxos(
                    address,
                    api_base=api_base,
                    timeout=timeout,
                )
                if str(item["txid"]) == normalized_txid and int(item["vout"]) == vout
            ),
            None,
        )
        confirmed = bool(exact_utxo and exact_utxo["confirmed"])
        availability = (
            "available"
            if confirmed
            else "unconfirmed"
            if exact_utxo is not None
            else "spent_or_unavailable"
        )
        matches.append(
            {
                "txid": normalized_txid,
                "vout": vout,
                "value": int(match["value"]),
                "source_address": address,
                "confirmed": confirmed,
                "block_height": int(exact_utxo["block_height"] if exact_utxo else 0),
                "availability": availability,
            }
        )
    return {
        "txid": normalized_txid,
        "silent_payment_address": material["silent_payment_address"],
        "matches": matches,
    }


_DUST_THRESHOLDS = {"p2tr": 330, "p2wpkh": 294, "p2pkh": 546, "p2sh": 540}


def _dust_threshold(script_pubkey: ScriptPubKey) -> int:
    return _DUST_THRESHOLDS.get(script_pubkey.type, 546)


def _estimate_signed_p2tr_vsize(
    input_count: int,
    output_script_pubkeys: list[ScriptPubKey],
) -> int:
    vin = [
        TxIn(
            prev_out=OutPoint(bytes.fromhex("11" * 32), index, check_validity=False),
            sequence=0xFFFFFFFD,
            script_witness=Witness([b"\x00" * 64]),
            check_validity=False,
        )
        for index in range(input_count)
    ]
    vout = [
        TxOut(1000, script_pubkey, check_validity=False)
        for script_pubkey in output_script_pubkeys
    ]
    return Tx(vin=vin, vout=vout, check_validity=False).vsize


def _output_private_key(
    spend_private_key_hex: str,
    tweak_hex: str,
    output_pubkey_hex: str,
) -> str:
    spend_scalar = int(spend_private_key_hex, 16)
    tweak_scalar = int(tweak_hex, 16) % SECP256K1_ORDER
    output_scalar = (spend_scalar + tweak_scalar) % SECP256K1_ORDER
    if tweak_scalar == 0 or output_scalar == 0:
        raise BitcoinCapabilityError("Silent Payment output key derivation failed.")
    if output_pubkey_hex.startswith("03"):
        output_scalar = (SECP256K1_ORDER - output_scalar) % SECP256K1_ORDER
    if output_scalar == 0:
        raise BitcoinCapabilityError("Silent Payment output key normalization failed.")
    return output_scalar.to_bytes(32, "big").hex()


def _build_signed_sweep(
    *,
    private_key_hex: str,
    source_address: str,
    utxo: dict[str, object],
    destination_address: str,
    fee_rate: float,
) -> dict[str, object]:
    if fee_rate <= 0:
        raise BitcoinCapabilityError("Bitcoin fee rate must be greater than zero.")
    destination = str(destination_address or "").strip()
    if not destination:
        raise BitcoinCapabilityError("A Bitcoin destination address is required.")
    try:
        source_spk = ScriptPubKey.from_address(source_address)
        destination_spk = ScriptPubKey.from_address(destination)
    except Exception as exc:
        raise BitcoinCapabilityError("The Bitcoin destination address is invalid.") from exc

    fee_sats = math.ceil(_estimate_signed_p2tr_vsize(1, [destination_spk]) * fee_rate)
    total_in = int(utxo["value"])
    amount_sats = total_in - fee_sats
    if amount_sats <= 0:
        raise BitcoinCapabilityError("The receipt cannot cover the requested miner fee.")
    dust = _dust_threshold(destination_spk)
    if amount_sats < dust:
        raise BitcoinCapabilityError(
            f"The sweep amount is dust for {destination_spk.type}; at least {dust} sats are required."
        )

    tx = Tx(
        vin=[
            TxIn(
                prev_out=OutPoint(
                    bytes.fromhex(str(utxo["txid"])),
                    int(utxo["vout"]),
                    check_validity=False,
                ),
                sequence=0xFFFFFFFD,
                check_validity=False,
            )
        ],
        vout=[TxOut(amount_sats, destination_spk, check_validity=False)],
        check_validity=False,
    )
    prevouts = [TxOut(total_in, source_spk, check_validity=False)]
    sighash = sig_hash.taproot(tx, 0, prevouts, 0, 0, b"", b"")
    signature = ssa.sign_(sighash, int(private_key_hex, 16)).serialize()
    tx.vin[0].script_witness = Witness([signature])
    return {
        "tx_hex": tx.serialize(include_witness=True, check_validity=False).hex(),
        "txid": tx.id.hex(),
        "vsize": tx.vsize,
        "weight": tx.weight,
        "fee_sats": fee_sats,
        "fee_rate": fee_rate,
        "amount_sats": amount_sats,
        "source_address": source_address,
        "destination_address": destination,
        "total_in_sats": total_in,
    }


def _create_sweep_result(
    *,
    nsec: str,
    txid: str,
    vout: int,
    destination_address: str,
    fee_rate: float,
    api_base: str,
    timeout: float,
) -> dict[str, object]:
    material, transaction = _raw_receipt_scan(
        nsec=nsec,
        txid=txid,
        api_base=api_base,
        timeout=timeout,
    )
    selected = next(
        (match for match in transaction["matched_outputs"] if int(match["vout"]) == vout),
        None,
    )
    if selected is None:
        raise BitcoinCapabilityError(
            f"The transaction has no Silent Payment receipt at output {vout}."
        )
    source_address = str(selected["scriptpubkey_address"])
    normalized_txid = str(transaction["txid"])
    utxos = fetch_bitcoin_address_utxos(
        source_address,
        api_base=api_base,
        timeout=timeout,
    )
    exact = next(
        (
            item
            for item in utxos
            if str(item["txid"]) == normalized_txid and int(item["vout"]) == vout
        ),
        None,
    )
    if exact is None:
        raise BitcoinCapabilityError("The matched Silent Payment output appears to be spent.")
    if not exact["confirmed"]:
        raise BitcoinCapabilityError("The matched Silent Payment output is not yet confirmed.")

    private_key = _output_private_key(
        material["spend_private_key_hex"],
        str(selected["priv_key_tweak_hex"]),
        str(selected["output_pubkey_hex"]),
    )
    result = _build_signed_sweep(
        private_key_hex=private_key,
        source_address=source_address,
        utxo=exact,
        destination_address=destination_address,
        fee_rate=fee_rate,
    )
    result.update(
        {
            "matched_txid": normalized_txid,
            "matched_vout": vout,
            "matched_value": int(selected["value"]),
        }
    )
    return result


def _sanitize_sweep(result: dict[str, object]) -> dict[str, object]:
    return {
        "txid": str(result["txid"]).lower(),
        "receipt_txid": str(result["matched_txid"]).lower(),
        "vout": int(result["matched_vout"]),
        "source_address": str(result["source_address"]),
        "destination_address": str(result["destination_address"]),
        "matched_value": int(result["matched_value"]),
        "amount_sats": int(result["amount_sats"]),
        "fee_sats": int(result["fee_sats"]),
        "fee_rate": float(result["fee_rate"]),
        "vsize": int(result["vsize"]),
    }


def create_silent_payment_sweep_preview(
    *,
    nsec: str,
    txid: str,
    vout: int,
    destination_address: str,
    fee_rate: float,
    api_base: str = DEFAULT_BITCOIN_API_BASE,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Construct a sweep in memory but expose no key or signed transaction."""

    return _sanitize_sweep(
        _create_sweep_result(
            nsec=nsec,
            txid=txid,
            vout=vout,
            destination_address=destination_address,
            fee_rate=fee_rate,
            api_base=api_base,
            timeout=timeout,
        )
    )


def _broadcast_transaction(
    tx_hex: str,
    *,
    api_base: str,
    timeout: float,
) -> str:
    req = request.Request(
        f"{api_base.rstrip('/')}/tx",
        data=tx_hex.encode("utf-8"),
        headers={
            "Content-Type": "text/plain",
            "Accept": "text/plain",
            "User-Agent": "safebox-acorn/0.1",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8").strip().lower()
    except error.HTTPError as exc:
        raise BitcoinCapabilityError(f"Bitcoin broadcast failed with HTTP {exc.code}.") from exc
    except error.URLError as exc:
        raise BitcoinCapabilityError(f"Bitcoin broadcast failed: {exc.reason}.") from exc
    except TimeoutError as exc:
        raise BitcoinCapabilityError("Bitcoin broadcast timed out.") from exc


def broadcast_silent_payment_sweep(
    *,
    nsec: str,
    txid: str,
    vout: int,
    destination_address: str,
    fee_rate: float,
    api_base: str = DEFAULT_BITCOIN_API_BASE,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Rebuild against live state, broadcast once, and return public evidence."""

    raw = _create_sweep_result(
        nsec=nsec,
        txid=txid,
        vout=vout,
        destination_address=destination_address,
        fee_rate=fee_rate,
        api_base=api_base,
        timeout=timeout,
    )
    expected_txid = str(raw["txid"]).lower()
    try:
        broadcast_txid = _broadcast_transaction(
            str(raw["tx_hex"]),
            api_base=api_base,
            timeout=timeout,
        )
    except BitcoinCapabilityError as exc:
        raise BitcoinCapabilityError(
            "The broadcast result is uncertain. Do not retry automatically; "
            f"inspect expected transaction {expected_txid}."
        ) from exc
    if broadcast_txid != expected_txid:
        raise BitcoinCapabilityError(
            "The Bitcoin backend returned an unexpected transaction id. "
            f"Do not retry automatically; inspect expected transaction {expected_txid}."
        )
    result = _sanitize_sweep(raw)
    result["broadcast_txid"] = broadcast_txid
    return result


__all__ = [
    "BitcoinCapabilityError",
    "broadcast_silent_payment_sweep",
    "create_silent_payment_sweep_preview",
    "derive_nostr_silent_payment_address",
    "detect_silent_payment_receipts",
    "fetch_bitcoin_address_utxos",
    "fetch_bitcoin_transaction",
]
