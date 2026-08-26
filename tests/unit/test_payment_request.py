import pytest

from acorn.payment_request import (
    PaymentRequest,
    PaymentRequestError,
    decode_payment_request,
    encode_payment_request,
    nostr_nip17_transport,
)


OFFICIAL_NUT18_EXAMPLE = (
    "creqApWF0gaNhdGVub3N0cmFheKlucHJvZmlsZTFxeTI4d3VtbjhnaGo3dW45ZDNzaGp0"
    "bnl2OWtoMnVld2Q5aHN6OW1od2RlbjV0ZTB3ZmprY2N0ZTljdXJ4dmVuOWVlaHFjdHJ2"
    "NWhzenJ0aHdkZW41dGUwZGVoaHh0bnZkYWtxcWd5ZGFxeTdjdXJrNDM5eWtwdGt5c3Y3"
    "dWRoZGh1NjhzdWNtMjk1YWtxZWZkZWhrZjBkNDk1Y3d1bmw1YWeBgmFuYjE3YWloYjdh"
    "OTAxNzZhYQphdWNzYXRhbYF4Imh0dHBzOi8vbm9mZWVzLnRlc3RudXQuY2FzaHUuc3Bh"
    "Y2U="
)


def test_decodes_official_nut18_example() -> None:
    request = decode_payment_request(OFFICIAL_NUT18_EXAMPLE)

    assert request.payment_id == "b7a90176"
    assert request.amount == 10
    assert request.unit == "sat"
    assert request.mints == ("https://nofees.testnut.cashu.space",)
    assert request.transports[0].transport_type == "nostr"
    assert request.transports[0].tags == (("n", "17"),)


def test_round_trips_clear_payment_request() -> None:
    request = PaymentRequest(
        payment_id="request-1",
        amount=25,
        unit="cmu-example",
        single_use=True,
        mints=("https://clear.example",),
        mint_list_preferred=False,
        description="Boardroom credit",
        transports=(nostr_nip17_transport("nprofile1example"),),
    )

    assert decode_payment_request(encode_payment_request(request)) == request


@pytest.mark.parametrize("encoded", ("", "creqBabc", "creqA!!!"))
def test_rejects_invalid_encoded_requests(encoded: str) -> None:
    with pytest.raises(PaymentRequestError):
        decode_payment_request(encoded)
