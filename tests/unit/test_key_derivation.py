from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from mnemonic import Mnemonic
from monstr.encrypt import Keys

from acorn.acorn import Acorn
from acorn.func_utils import (
    generate_seed_phrase_and_nsec,
    recover_nsec_from_seed,
    seed_phrase_and_nsec_from_entropy,
    seed_phrase_matches_nsec,
)


def test_generated_seed_phrase_round_trips_to_same_nsec():
    seed_phrase, nsec = generate_seed_phrase_and_nsec()

    assert len(seed_phrase.split()) == 12
    assert recover_nsec_from_seed(seed_phrase) == nsec
    assert seed_phrase_matches_nsec(seed_phrase, nsec)


def test_external_entropy_produces_recoverable_24_word_phrase_deterministically():
    entropy_hex = "00" * 32

    first_phrase, first_nsec = seed_phrase_and_nsec_from_entropy(entropy_hex)
    second_phrase, second_nsec = seed_phrase_and_nsec_from_entropy(entropy_hex.upper())

    assert len(first_phrase.split()) == 24
    assert Mnemonic("english").check(first_phrase)
    assert (first_phrase, first_nsec) == (second_phrase, second_nsec)
    assert recover_nsec_from_seed(first_phrase) == first_nsec
    assert seed_phrase_matches_nsec(first_phrase, first_nsec)


@pytest.mark.parametrize(
    ("entropy_hex", "message"),
    [
        ("00" * 31, "exactly 64 hexadecimal characters"),
        ("00" * 33, "exactly 64 hexadecimal characters"),
        ("zz" * 32, "only hexadecimal characters"),
    ],
)
def test_external_entropy_validation(entropy_hex, message):
    with pytest.raises(ValueError, match=message):
        seed_phrase_and_nsec_from_entropy(entropy_hex)


def test_raw_private_key_mnemonic_is_not_a_recovery_phrase():
    nsec = Keys().private_key_bech32()
    raw_key_phrase = Mnemonic("english").to_mnemonic(
        bytes.fromhex(Keys(priv_k=nsec).private_key_hex())
    )

    assert len(raw_key_phrase.split()) == 24
    assert not seed_phrase_matches_nsec(raw_key_phrase, nsec)


@pytest.mark.asyncio
async def test_generated_instance_stores_original_recoverable_phrase():
    wallet = Acorn(
        nsec=Keys().private_key_bech32(),
        relays=["wss://relay.example.com"],
        mints=["https://mint.example.com"],
        home_relay="wss://relay.example.com",
    )
    wallet.set_wallet_info = AsyncMock()

    generated_nsec = await wallet.create_instance()

    assert wallet.seed_phrase
    assert recover_nsec_from_seed(wallet.seed_phrase) == generated_nsec
    stored_tags = json.loads(wallet.set_wallet_info.await_args.kwargs["label_info"])
    assert ["seedphrase", wallet.seed_phrase] in stored_tags


@pytest.mark.asyncio
async def test_external_entropy_instance_stores_supplied_recovery_phrase():
    seed_phrase, expected_nsec = seed_phrase_and_nsec_from_entropy("01" * 32)
    wallet = Acorn(
        nsec=Keys().private_key_bech32(),
        relays=["wss://relay.example.com"],
        mints=["https://mint.example.com"],
        home_relay="wss://relay.example.com",
    )
    wallet.set_wallet_info = AsyncMock()

    initialized_nsec = await wallet.create_instance(seed_phrase=seed_phrase)

    assert initialized_nsec == expected_nsec
    assert wallet.seed_phrase == seed_phrase
    stored_tags = json.loads(wallet.set_wallet_info.await_args.kwargs["label_info"])
    assert ["seedphrase", seed_phrase] in stored_tags


@pytest.mark.asyncio
async def test_imported_nsec_does_not_manufacture_seed_phrase():
    imported_nsec = Keys().private_key_bech32()
    wallet = Acorn(
        nsec=imported_nsec,
        relays=["wss://relay.example.com"],
        mints=["https://mint.example.com"],
        home_relay="wss://relay.example.com",
    )
    wallet.get_wallet_config = AsyncMock(return_value=None)
    wallet.set_wallet_info = AsyncMock()

    initialized_nsec = await wallet.create_instance(keepkey=True)

    assert initialized_nsec == imported_nsec
    assert wallet.seed_phrase is None
    stored_tags = json.loads(wallet.set_wallet_info.await_args.kwargs["label_info"])
    assert not any(tag[0] == "seedphrase" for tag in stored_tags)


def test_profile_output_excludes_private_material():
    wallet_nsec = Keys().private_key_bech32()
    lock_key = Keys().private_key_hex()
    wallet = Acorn(
        nsec=wallet_nsec,
        relays=["wss://relay.example.com"],
        mints=["https://mint.example.com"],
        home_relay="wss://relay.example.com",
    )
    wallet.seed_phrase = "alpha beta gamma secret phrase"
    wallet.owner = wallet.pubkey_bech32
    wallet.known_mints = {}
    wallet.user_records = []
    wallet.acorn_tags = [
        ["balance", "0", "sat"],
        ["privkey", lock_key],
        ["mint", "https://mint.example.com"],
        ["name", "wallet"],
        ["seedphrase", wallet.seed_phrase],
    ]

    output = wallet.get_profile()

    assert wallet.pubkey_bech32 in output
    assert wallet.pubkey_hex in output
    assert wallet_nsec not in output
    assert wallet.privkey_hex not in output
    assert wallet.seed_phrase not in output
    assert lock_key not in output
    assert wallet.access_key not in output
