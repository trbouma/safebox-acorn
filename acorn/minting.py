"""Durable Cashu issuance for applications that persist encrypted checkpoints.

The caller must durably save ``prepare`` results before exposing an invoice,
and reuse them unchanged on every ``issue`` retry. This API does not publish
wallet events, append history, own storage, or use a user's private key.
Existing Acorn deposit and mint methods are deliberately unchanged.
"""
import hashlib
import secrets
import time
from urllib.parse import quote

import bolt11
import httpx
from acorn.b_dhke import step1_alice, step3_alice, alice_verify_dleq
from acorn.models import Proof
from acorn.secp import PrivateKey, PublicKey


class MintCompatibilityError(Exception):
    pass


class DurableCashuMint:
    """Opt-in, restore-first sat issuance with a JSON-compatible checkpoint.

    ``quote(mint, amount, description)`` validates a mainnet invoice and NUT-09.
    ``state(item)`` is read-only. ``prepare(item)`` creates secret checkpoint
    material; never call it again to retry an already exposed invoice.
    ``issue(item)`` restores or issues with that same checkpoint and returns
    proof dictionaries. Persist those before wallet publication.

    Legacy OakGate checkpoints (outputs/secrets/keys) remain supported without
    migration. Treat the entire checkpoint and returned proofs as bearer data.
    Callers must serialize concurrent processing of each quote.
    """
    def __init__(self, require_description_hash=False):
        self.require_description_hash = require_description_hash

    async def request(self, mint, method, path, payload=None):
        async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
            async with client.stream(method, mint + path, json=payload) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 1_048_576:
                        raise ValueError('Mint response is too large')
                import json
                return json.loads(data)

    async def quote(self, mint, amount, description):
        info = await self.request(mint, 'GET', '/v1/info')
        if not info.get('nuts', {}).get('9', {}).get('supported'):
            raise MintCompatibilityError('Mint must support NUT-09 recovery')
        payload = {'amount': amount, 'unit': 'sat'}
        if self.require_description_hash:
            payload.update(description=description,
                           description_hash=hashlib.sha256(description.encode()).hexdigest())
        result = await self.request(mint, 'POST', '/v1/mint/quote/bolt11', payload)
        invoice = bolt11.decode(result['request'])
        if (invoice.currency != 'bc' or invoice.amount_msat != amount * 1000
                or invoice.date + invoice.expiry <= time.time()):
            raise MintCompatibilityError('Mint returned an invalid amount, network or expired invoice')
        bound = invoice.description_hash == hashlib.sha256(description.encode()).hexdigest()
        if self.require_description_hash and not bound:
            raise MintCompatibilityError('Invoice description-hash binding is missing or does not match in strict mode')
        if not isinstance(result['quote'], str) or not 1 <= len(result['quote']) <= 512:
            raise ValueError('Invalid mint quote')
        return {'quote': result['quote'], 'invoice': result['request'],
                'expiry': invoice.date + invoice.expiry, 'description_hash_bound': bound}

    async def state(self, item):
        return await self.request(item['mint'], 'GET', '/v1/mint/quote/bolt11/' + quote(item['quote'], safe=''))

    async def prepare(self, item):
        keysets = await self.request(item['mint'], 'GET', '/v1/keysets')
        keyset = next(k['id'] for k in keysets['keysets'] if k['active'] and k['unit'] == 'sat')
        result = await self.request(item['mint'], 'GET', '/v1/keys/' + quote(keyset, safe=''))
        keys = next(k['keys'] for k in result['keysets'] if k['id'] == keyset)
        outputs, secrets_list = [], []
        for power in range(item['amount'].bit_length()):
            amount = 1 << power
            if not item['amount'] & amount:
                continue
            # Validate denomination keys before committing an issuance request.
            PublicKey(bytes.fromhex(keys[str(amount)]), raw=True)
            secret = secrets.token_hex(32)
            blinded, r, y = step1_alice(secret)
            outputs.append({'amount': amount, 'id': keyset, 'B_': blinded.serialize().hex()})
            secrets_list.append({'secret': secret, 'r': r.private_key.hex(), 'Y': y.serialize().hex()})
        return {'outputs': outputs, 'secrets': secrets_list, 'keys': keys}

    async def issue(self, item):
        prepared = item['prepared']
        outputs = prepared['outputs']
        # Restore first. A previous request may have succeeded while its HTTP
        # response or the local checkpoint was lost. Reuse exactly these outputs.
        restored = await self.request(item['mint'], 'POST', '/v1/restore', {'outputs': outputs})
        returned = restored.get('signatures', restored.get('promises', []))
        if restored.get('outputs'):
            if len(restored['outputs']) != len(returned):
                raise ValueError('Invalid restore response')
            by_output = {o['B_']: s for o, s in zip(restored['outputs'], returned)}
            if set(by_output) != {o['B_'] for o in outputs}:
                raise ValueError('Partial recovery requires operator review')
            signatures = [by_output[o['B_']] for o in outputs]
        else:
            result = await self.request(item['mint'], 'POST', '/v1/mint/bolt11',
                                        {'quote': item['quote'], 'outputs': outputs})
            signatures = result['signatures']
        if len(signatures) != len(outputs):
            raise ValueError('Incomplete mint signatures')
        proofs = []
        for output, secret, sig in zip(outputs, prepared['secrets'], signatures):
            if sig['amount'] != output['amount'] or sig['id'] != output['id']:
                raise ValueError('Mint signature does not match its output')
            c = PublicKey(bytes.fromhex(sig['C_']), raw=True)
            a = PublicKey(bytes.fromhex(prepared['keys'][str(output['amount'])]), raw=True)
            r = PrivateKey(bytes.fromhex(secret['r']), raw=True)
            if sig.get('dleq'):
                dleq = sig['dleq']
                if not alice_verify_dleq(PublicKey(bytes.fromhex(output['B_']), raw=True), c,
                                         PrivateKey(bytes.fromhex(dleq['e']), raw=True),
                                         PrivateKey(bytes.fromhex(dleq['s']), raw=True), a):
                    raise ValueError('Invalid mint DLEQ proof')
            proofs.append(Proof(amount=output['amount'], id=output['id'], secret=secret['secret'],
                                Y=secret['Y'], C=step3_alice(c, r, a).serialize().hex()).model_dump())
        return proofs
