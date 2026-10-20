import pytest
from acorn.acorn import Acorn


@pytest.mark.parametrize(('pubkey', 'expected'), [
    ('00' * 32, 'abandonabandon0'),
    ('ab' * 32, 'producefront939'),
    ('ff' * 32, 'zoozoo23'),
])
def test_default_handle_uses_own_public_key(pubkey, expected):
    wallet = object.__new__(Acorn)
    wallet.pubkey_hex = pubkey
    wallet.handle = 'legacy-name'
    assert wallet.default_handle() == expected
    assert wallet.handle == 'legacy-name'
    assert len({wallet.default_handle(attempt=i) for i in range(1000)}) == 1000


@pytest.mark.parametrize('attempt', [-1, 1000, True, 1.5, '1', None])
def test_default_handle_rejects_invalid_attempt(attempt):
    wallet = object.__new__(Acorn)
    wallet.pubkey_hex = '00' * 32
    with pytest.raises(ValueError):
        wallet.default_handle(attempt=attempt)


def test_default_handle_matches_real_acorn_identity():
    wallet = Acorn(nsec=Acorn.generate_recovery_material()['nsec'], home_relay='wss://relay.example')
    public_only = object.__new__(Acorn)
    public_only.pubkey_hex = wallet.public_identity()['hex']
    assert wallet.default_handle() == public_only.default_handle()
