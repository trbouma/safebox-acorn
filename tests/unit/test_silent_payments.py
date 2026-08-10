from decimal import getcontext

import pytest
import secp256k1
from monstr.encrypt import Keys

import acorn.silent_payments as bitcoin


SCALAR_ONE_HEX = "00" * 31 + "01"
SCALAR_ONE_NPUB = (
    "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d"
)
EXPECTED_NSP_ADDRESS = (
    "sp1qqt0uh8dlt9ypxxyl5s9p03ym2t87dxgzqsp8vndjzl4cfn7h4hckqqkh372"
    "d773sgqpka3qlm9kpyyf6p9nmdkzqpepdhhtq79klfq3zlq750cmd"
)
TXID = "ab" * 32


def _scalar_one_nsec() -> str:
    return Keys(priv_k=SCALAR_ONE_HEX).private_key_bech32()


def _taproot_address(compressed_pubkey: bytes) -> str:
    converted = bitcoin.bech32.convertbits(compressed_pubkey[1:], 8, 5, True)
    assert converted is not None
    return bitcoin._bech32m_encode("bc", [1, *converted])


def _synthetic_receipt_transaction(nsec: str) -> dict[str, object]:
    material = bitcoin._derive_silent_payment_material(nsec)
    sender_private_scalar = 7
    sender_private = sender_private_scalar.to_bytes(32, "big")
    sender_pubkey = secp256k1.PrivateKey(sender_private, raw=True).pubkey.serialize(
        compressed=True
    )
    input_txid = "11" * 32
    outpoint = bytes.fromhex(input_txid)[::-1] + (0).to_bytes(4, "little")
    input_hash_scalar = int.from_bytes(
        bitcoin._tagged_hash("BIP0352/Inputs", outpoint + sender_pubkey),
        "big",
    ) % bitcoin.SECP256K1_ORDER
    sender_shared_scalar = (
        input_hash_scalar * sender_private_scalar
    ) % bitcoin.SECP256K1_ORDER
    scan_pubkey = secp256k1.PublicKey(
        bytes.fromhex(material["scan_public_key_hex"]), raw=True
    )
    shared_point = scan_pubkey.tweak_mul(
        sender_shared_scalar.to_bytes(32, "big")
    ).serialize(compressed=True)
    tweak = bitcoin._tagged_hash(
        "BIP0352/SharedSecret",
        shared_point + (0).to_bytes(4, "big"),
    )
    tweak_scalar = int.from_bytes(tweak, "big") % bitcoin.SECP256K1_ORDER
    output_pubkey = (
        secp256k1.PublicKey(
            bytes.fromhex(material["spend_public_key_hex"]), raw=True
        )
        .tweak_add(tweak_scalar.to_bytes(32, "big"))
        .serialize(compressed=True)
    )
    receipt_address = _taproot_address(output_pubkey)
    return {
        "txid": TXID,
        "vin": [
            {
                "txid": input_txid,
                "vout": 0,
                "prevout": {
                    "scriptpubkey": "0014" + "22" * 20,
                    "scriptpubkey_type": "v0_p2wpkh",
                },
                "witness": ["30", sender_pubkey.hex()],
                "scriptsig": "",
            }
        ],
        "vout": [
            {
                "value": 1_000,
                "scriptpubkey": "0014" + "33" * 20,
                "scriptpubkey_type": "v0_p2wpkh",
                "scriptpubkey_address": "bc1qchange",
            },
            {
                "value": 2_500,
                "scriptpubkey": "5120" + output_pubkey[1:].hex(),
                "scriptpubkey_type": "v1_p2tr",
                "scriptpubkey_address": receipt_address,
            },
        ],
    }


def test_import_restores_decimal_context() -> None:
    before = getcontext().copy()
    # The module import above has already loaded BTClib.
    after = getcontext()
    assert after.prec == before.prec
    assert after.traps == before.traps


def test_public_and_private_derivation_match_existing_nsp_vector() -> None:
    nsec = _scalar_one_nsec()
    assert bitcoin.derive_nostr_silent_payment_address(SCALAR_ONE_NPUB) == EXPECTED_NSP_ADDRESS
    assert bitcoin.derive_nostr_silent_payment_address(nsec) == EXPECTED_NSP_ADDRESS


@pytest.mark.parametrize("scalar", range(1, 9))
def test_nsec_and_npub_derivations_match_across_key_parity(scalar: int) -> None:
    keys = Keys(priv_k=scalar.to_bytes(32, "big").hex())
    assert bitcoin.derive_nostr_silent_payment_address(
        keys.private_key_bech32()
    ) == bitcoin.derive_nostr_silent_payment_address(keys.public_key_bech32())


def test_targeted_detection_finds_nonzero_output_and_hides_private_material(
    monkeypatch,
) -> None:
    nsec = _scalar_one_nsec()
    transaction = _synthetic_receipt_transaction(nsec)
    receipt_address = transaction["vout"][1]["scriptpubkey_address"]
    monkeypatch.setattr(
        bitcoin,
        "fetch_bitcoin_transaction",
        lambda *args, **kwargs: transaction,
    )
    monkeypatch.setattr(
        bitcoin,
        "fetch_bitcoin_address_utxos",
        lambda *args, **kwargs: [
            {
                "txid": TXID,
                "vout": 1,
                "value": 2_500,
                "confirmed": True,
                "block_height": 900_000,
            }
        ],
    )

    result = bitcoin.detect_silent_payment_receipts(nsec=nsec, txid=TXID)

    assert result["matches"] == [
        {
            "txid": TXID,
            "vout": 1,
            "value": 2_500,
            "source_address": receipt_address,
            "confirmed": True,
            "block_height": 900_000,
            "availability": "available",
        }
    ]
    assert "private" not in repr(result).lower()
    assert "tweak" not in repr(result).lower()
    assert nsec not in repr(result)


def test_detection_reports_unconfirmed_without_enabling_spend(monkeypatch) -> None:
    nsec = _scalar_one_nsec()
    transaction = _synthetic_receipt_transaction(nsec)
    monkeypatch.setattr(bitcoin, "fetch_bitcoin_transaction", lambda *args, **kwargs: transaction)
    monkeypatch.setattr(
        bitcoin,
        "fetch_bitcoin_address_utxos",
        lambda *args, **kwargs: [
            {
                "txid": TXID,
                "vout": 1,
                "value": 2_500,
                "confirmed": False,
                "block_height": 0,
            }
        ],
    )

    result = bitcoin.detect_silent_payment_receipts(nsec=nsec, txid=TXID)

    assert result["matches"][0]["availability"] == "unconfirmed"
    assert result["matches"][0]["confirmed"] is False


def test_real_sweep_builder_produces_fee_disclosed_sanitized_preview(
    monkeypatch,
) -> None:
    nsec = _scalar_one_nsec()
    transaction = _synthetic_receipt_transaction(nsec)
    receipt_address = transaction["vout"][1]["scriptpubkey_address"]
    # A P2WPKH destination reproduces the 99-vbyte shape validated during the
    # first controlled 2,500-sat Safebox Web receipt preview.
    destination = "bc1qx49d4rjg9pkaygep2z5e3aesmmel04v846vzh5"
    monkeypatch.setattr(
        bitcoin,
        "fetch_bitcoin_transaction",
        lambda *args, **kwargs: transaction,
    )
    monkeypatch.setattr(
        bitcoin,
        "fetch_bitcoin_address_utxos",
        lambda *args, **kwargs: [
            {
                "txid": TXID,
                "vout": 1,
                "value": 2_500,
                "confirmed": True,
                "block_height": 900_000,
            }
        ],
    )

    result = bitcoin.create_silent_payment_sweep_preview(
        nsec=nsec,
        txid=TXID,
        vout=1,
        destination_address=destination,
        fee_rate=2.0,
    )

    assert result["source_address"] == receipt_address
    assert result["destination_address"] == destination
    assert result["matched_value"] == 2_500
    assert result["fee_sats"] == 198
    assert result["amount_sats"] == 2_302
    assert result["vsize"] == 99
    assert len(result["txid"]) == 64
    assert "tx_hex" not in result


def test_sweep_preview_excludes_signed_transaction_and_private_derivation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        bitcoin,
        "_create_sweep_result",
        lambda **kwargs: {
            "tx_hex": "signed-secret-bearing-transaction",
            "txid": "cd" * 32,
            "matched_txid": TXID,
            "matched_vout": 1,
            "source_address": "bc1preceipt",
            "destination_address": "bc1pdestination",
            "matched_value": 2_500,
            "amount_sats": 2_302,
            "fee_sats": 198,
            "fee_rate": 2.0,
            "vsize": 99,
        },
    )

    result = bitcoin.create_silent_payment_sweep_preview(
        nsec="nsec-not-returned",
        txid=TXID,
        vout=1,
        destination_address="bc1pdestination",
        fee_rate=2,
    )

    assert result["amount_sats"] == 2_302
    assert result["fee_sats"] == 198
    assert "tx_hex" not in result
    assert "secret" not in repr(result)


def test_broadcast_failure_is_uncertain_and_never_auto_retries(monkeypatch) -> None:
    expected_txid = "cd" * 32
    monkeypatch.setattr(
        bitcoin,
        "_create_sweep_result",
        lambda **kwargs: {
            "tx_hex": "signed-transaction",
            "txid": expected_txid,
            "matched_txid": TXID,
            "matched_vout": 1,
            "source_address": "bc1preceipt",
            "destination_address": "bc1pdestination",
            "matched_value": 2_500,
            "amount_sats": 2_302,
            "fee_sats": 198,
            "fee_rate": 2.0,
            "vsize": 99,
        },
    )
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise bitcoin.BitcoinCapabilityError("backend timeout")

    monkeypatch.setattr(bitcoin, "_broadcast_transaction", fail_once)

    with pytest.raises(bitcoin.BitcoinCapabilityError, match="uncertain") as exc_info:
        bitcoin.broadcast_silent_payment_sweep(
            nsec="nsec",
            txid=TXID,
            vout=1,
            destination_address="bc1pdestination",
            fee_rate=2,
        )

    assert calls == 1
    assert expected_txid in str(exc_info.value)


def test_broadcast_rejects_unexpected_transaction_id(monkeypatch) -> None:
    expected_txid = "cd" * 32
    monkeypatch.setattr(
        bitcoin,
        "_create_sweep_result",
        lambda **kwargs: {
            "tx_hex": "signed-transaction",
            "txid": expected_txid,
            "matched_txid": TXID,
            "matched_vout": 1,
            "source_address": "bc1preceipt",
            "destination_address": "bc1pdestination",
            "matched_value": 2_500,
            "amount_sats": 2_302,
            "fee_sats": 198,
            "fee_rate": 2.0,
            "vsize": 99,
        },
    )
    monkeypatch.setattr(bitcoin, "_broadcast_transaction", lambda *args, **kwargs: "ef" * 32)

    with pytest.raises(bitcoin.BitcoinCapabilityError, match="unexpected transaction id"):
        bitcoin.broadcast_silent_payment_sweep(
            nsec="nsec",
            txid=TXID,
            vout=1,
            destination_address="bc1pdestination",
            fee_rate=2,
        )
