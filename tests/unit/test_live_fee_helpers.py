import pytest

from tests.helpers import confirmed_transfer_amount


@pytest.mark.parametrize("net", [9, 10])
def test_confirmed_credit_allows_fees(net):
    assert confirmed_transfer_amount({"confirmed_count": 1, "provisional_count": 0,
                                     "accepted_amount": net, "failed": []}, 10) == net


@pytest.mark.parametrize("changes", [
    {"confirmed_count": 0, "provisional_count": 1},
    {"accepted_amount": 0}, {"accepted_amount": 11},
    {"failed": [{"reason": "mint unavailable"}]},
])
def test_pending_or_invalid_credit_is_not_success(changes):
    result = {"confirmed_count": 1, "provisional_count": 0, "accepted_amount": 9, "failed": []}
    with pytest.raises(AssertionError):
        confirmed_transfer_amount({**result, **changes}, 10)
