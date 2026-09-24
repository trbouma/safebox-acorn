from unittest.mock import AsyncMock

import pytest

from acorn.acorn import Acorn
from acorn.models import DLEQWallet, Proof, TokenV3, TokenV3Token, TokenV4
from acorn.token_codec import decode_cashu_token, encode_cashu_token


def token(unit="sat", keyset="0011223344556677", dleq=False):
    return TokenV3(
        token=[TokenV3Token(mint="https://mint.example", proofs=[Proof(
            id=keyset, amount=8, secret="test-secret", C="02" + "11" * 32,
            witness='{"signatures":[]}',
            dleq=DLEQWallet(e="22" * 32, s="33" * 32, r="44" * 32) if dleq else None,
        )])], memo="test memo", unit=unit,
    )


@pytest.mark.parametrize("unit", ["sat", "cmu-example"])
@pytest.mark.parametrize("dleq", [False, True])
@pytest.mark.parametrize("encoding", ["auto", "cashuA"])
def test_roundtrip_preserves_proofs_and_metadata(unit, dleq, encoding):
    original = token(unit, dleq=dleq)
    encoded = encode_cashu_token(original, encoding)
    assert encoded.startswith("cashuB" if encoding == "auto" else "cashuA")
    decoded = decode_cashu_token("cashu:" + encoded)
    assert decoded.unit == unit
    assert decoded.memo == original.memo
    assert decoded.get_mints() == original.get_mints()
    assert decoded.get_proofs() == original.get_proofs()


def test_legacy_keyset_falls_back_to_cashua():
    original = token(keyset="legacy/base64=")
    encoded = encode_cashu_token(original)
    assert encoded.startswith("cashuA")
    assert decode_cashu_token(encoded).get_proofs() == original.get_proofs()


def test_multiple_mints_fall_back_to_cashua():
    original = token()
    original.token.append(TokenV3Token(mint="https://second.example", proofs=original.get_proofs()))
    assert encode_cashu_token(original).startswith("cashuA")


def test_invalid_cashub_is_rejected_not_reinterpreted():
    with pytest.raises(ValueError, match="Invalid Cashu token encoding"):
        decode_cashu_token("cashuBinvalid!")


def test_cashub_without_dleq_omits_optional_field():
    encoded = TokenV4.from_tokenv3(token()).serialize_to_dict(include_dleq=True)
    assert "d" not in encoded["t"][0]["p"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding", ["auto", "cashuA"])
async def test_clear_staging_accepts_both_formats(encoding):
    wallet = Acorn.__new__(Acorn)
    wallet._store_clear_receipt = AsyncMock(return_value={"status": "pending"})
    encoded = encode_cashu_token(token(unit="cmu-example"), encoding)
    await wallet.stage_pasted_clear_token(encoded)
    payload = wallet._store_clear_receipt.await_args.kwargs["payload"]
    assert payload["unit"] == "cmu-example"
    assert payload["amount"] == 8
    assert payload["comment"] == "test memo"
