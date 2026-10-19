"""Portable issuance and legacy checkpoint crash recovery; no live network."""
import asyncio
import hashlib
import json
import time

import bolt11
import pytest
from acorn.minting import DurableCashuMint, MintCompatibilityError
from acorn.b_dhke import step2_bob, verify
from acorn.secp import PrivateKey, PublicKey

def invoice(amount, description, hashed=True):
    tags = bolt11.Tags()
    tags.add(bolt11.TagChar.payment_hash, '11'*32)
    tags.add(bolt11.TagChar.payment_secret, '22'*32)
    tags.add(bolt11.TagChar.description_hash if hashed else bolt11.TagChar.description,
             hashlib.sha256(description.encode()).hexdigest() if hashed else description)
    return bolt11.encode(bolt11.Bolt11(currency='bc', date=int(time.time()), amount_msat=amount*1000, tags=tags), private_key='03'*32)


class Mint(DurableCashuMint):
    def __init__(self):
        super().__init__(require_description_hash=True)
        self.rows = {}
        self.signatures = {}
        self.key = PrivateKey(bytes.fromhex('02'*32), raw=True)
        self.issued = 0
        self.fail_after_issue = False
        self.hashed = True
        self.restorable = True
        self.calls = []

    async def request(self, mint, method, path, payload=None):
        self.calls.append((mint, method, path, payload))
        if path == '/v1/info':
            return {'nuts': {'9': {'supported': self.restorable}}}
        if path == '/v1/mint/quote/bolt11':
            q = str(len(self.rows)+1)
            row = {'quote': q, 'state': 'UNPAID', 'request': invoice(payload['amount'], payload.get('description', 'Cashu deposit'), self.hashed)}
            self.rows[q] = row
            return row.copy()
        if path.startswith('/v1/mint/quote/bolt11/'):
            return self.rows[path.rsplit('/',1)[1]].copy()
        if path == '/v1/keysets':
            return {'keysets': [{'id': '0011223344556677', 'unit': 'sat', 'active': True}]}
        if path.startswith('/v1/keys/'):
            return {'keysets': [{'id': '0011223344556677', 'keys': {str(2**i): self.key.pubkey.serialize().hex() for i in range(27)}}]}
        if path == '/v1/restore':
            outputs = [o for o in payload['outputs'] if o['B_'] in self.signatures]
            return {'outputs': list(reversed(outputs)), 'signatures': [self.signatures[o['B_']] for o in reversed(outputs)]}
        if path == '/v1/mint/bolt11':
            assert self.rows[payload['quote']]['state'] == 'PAID'
            signatures = []
            for output in payload['outputs']:
                c, e, s = step2_bob(PublicKey(bytes.fromhex(output['B_']), raw=True), self.key)
                sig = {'id': output['id'], 'amount': output['amount'], 'C_': c.serialize().hex(),
                       'dleq': {'e': e.private_key.hex(), 's': s.private_key.hex()}}
                self.signatures[output['B_']] = sig
                signatures.append(sig)
            self.issued += 1
            self.rows[payload['quote']]['state'] = 'ISSUED'
            if self.fail_after_issue:
                raise TimeoutError('PRIVATE quote')
            return {'signatures': signatures}
        raise AssertionError(path)


async def prepared(mint):
    item = {'mint': 'https://mint.example', 'amount': 13}
    item.update(await mint.quote(item['mint'], 13, 'deposit'))
    item['prepared'] = await mint.prepare(item)
    mint.rows[item['quote']]['state'] = 'PAID'
    return item


def test_restart_after_lost_issuance_response_reuses_legacy_checkpoint(monkeypatch):
    async def run():
        mint = Mint()
        item = await prepared(mint)
        assert set(item['prepared']) == {'outputs', 'secrets', 'keys'}
        checkpoint = json.dumps(item)  # Persist before the payer sees the invoice.
        mint.fail_after_issue = True
        with pytest.raises(TimeoutError):
            await mint.issue(item)
        assert mint.issued == 1
        # A fresh API instance has no state except the persisted checkpoint;
        # the fake mint retains the already-issued signatures across restart.
        restarted = DurableCashuMint(require_description_hash=True)
        restarted.request = mint.request
        def no_new_secret(*args, **kwargs):
            raise AssertionError('Recovery must not generate new blinding material')
        monkeypatch.setattr('acorn.minting.secrets.token_hex', no_new_secret)
        restored = json.loads(checkpoint)
        proofs = await restarted.issue(restored)
        assert sum(p['amount'] for p in proofs) == 13
        assert all(verify(mint.key, PublicKey(bytes.fromhex(p['C']), raw=True), p['secret']) for p in proofs)
        assert json.dumps(restored) == checkpoint
        assert await restarted.issue(json.loads(checkpoint)) == proofs
        assert mint.issued == 1
        assert [c[2] for c in mint.calls].count('/v1/mint/bolt11') == 1
    asyncio.run(run())


def test_partial_restore_refuses_to_reissue():
    async def run():
        mint = Mint()
        item = await prepared(mint)
        await mint.issue(item)
        mint.signatures.pop(next(iter(mint.signatures)))
        with pytest.raises(ValueError, match='Partial recovery'):
            await mint.issue(json.loads(json.dumps(item)))
        assert mint.issued == 1
    asyncio.run(run())


@pytest.mark.parametrize('corruption', ['amount', 'id', 'dleq'])
def test_recovered_signatures_are_verified(corruption):
    async def run():
        mint = Mint()
        item = await prepared(mint)
        await mint.issue(item)
        sig = next(iter(mint.signatures.values()))
        if corruption == 'amount': sig['amount'] += 1
        if corruption == 'id': sig['id'] = 'bad-keyset'
        if corruption == 'dleq': sig['dleq']['e'] = '01'*32
        with pytest.raises(ValueError):
            await mint.issue(item)
        assert mint.issued == 1
    asyncio.run(run())


def test_optional_description_binding_and_required_restore_support():
    async def run():
        mint = Mint()
        mint.require_description_hash = False
        mint.hashed = False
        quote = await mint.quote('https://mint.example', 13, 'deposit')
        assert quote['description_hash_bound'] is False
        mint.hashed = True
        quote = await mint.quote('https://mint.example', 13, 'different zap context')
        assert quote['description_hash_bound'] is False
        mint.hashed = False
        mint.require_description_hash = True
        with pytest.raises(MintCompatibilityError):
            await mint.quote('https://mint.example', 13, 'deposit')
        mint.restorable = False
        with pytest.raises(MintCompatibilityError, match='NUT-09'):
            await mint.quote('https://mint.example', 13, 'deposit')
    asyncio.run(run())
