import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from stroma import Event, Keys, NIP44Encrypt
from acorn.acorn import Acorn
from acorn.models import Proof
from acorn.incoming import publish_event


def wallet():
    result = Acorn(nsec=Keys().private_key_bech32(), home_relay='wss://home.example')
    result.known_mints = {'0011223344556677': 'https://mint.example'}
    result._publish_incoming_event = AsyncMock(return_value=True)
    return result


def test_history_prepare_and_retry_use_the_same_signed_event():
    async def run():
        w = wallet()
        args = dict(tx_type='C', amount=13, invoice='invoice', comment='Thanks', created_at=1234, use_wallet_balance=False)
        prepared = await w.add_tx_history(**args, prepare_only=True)
        w._publish_incoming_event.assert_not_awaited()
        data = json.loads(NIP44Encrypt(w.k).decrypt(prepared['content'], w.pubkey_hex))
        assert data['amount'] == 13 and data['current_balance'] is None and data['create_time'] == 1234
        w._publish_incoming_event.return_value = False
        with pytest.raises(RuntimeError):
            await w.add_tx_history(**args, prepared_event=prepared)
        w._publish_incoming_event.return_value = True
        result = await w.add_tx_history(**args, prepared_event=prepared)
        assert result['event_id'] == prepared['id']
        assert all(call.args[1]['id'] == prepared['id'] for call in w._publish_incoming_event.await_args_list)
        with pytest.raises(ValueError):
            await w.add_tx_history(**{**args, 'amount': 99}, prepared_event=prepared)
        with pytest.raises(ValueError):
            await wallet().add_tx_history(**args, prepared_event=prepared)
    asyncio.run(run())


def test_proof_prepare_deliver_and_parameter_binding():
    async def run():
        w = wallet()
        proof = Proof(id='0011223344556677', amount=1, secret='secret', C='02'+'11'*32)
        prepared = await w.add_proofs_obj([proof], prepare_only=True)
        w._publish_incoming_event.assert_not_awaited()
        for _ in range(2):
            result = await w.add_proofs_obj([proof], prepared_events=prepared)
            assert result['event_ids'] == [prepared[0]['id']]
        different = proof.model_copy(update={'secret':'other'})
        with pytest.raises(ValueError):
            await w.add_proofs_obj([different], prepared_events=prepared)
        with pytest.raises(ValueError):
            await wallet().add_proofs_obj([proof], prepared_events=prepared)
        w.known_mints[proof.id] = 'https://wrong.example'
        with pytest.raises(ValueError):
            await w.add_proofs_obj([proof], prepared_events=prepared)
    asyncio.run(run())


def test_zap_receipt_prepare_retry_and_destination_boundary():
    async def run():
        w = wallet()
        sender = Keys()
        request = Event(kind=9734, pub_key=sender.public_key_hex(), tags=[['p',w.pubkey_hex],['relays','wss://relay.example']])
        request.sign(sender.private_key_hex())
        raw = json.dumps(request.data())
        prepared = await w.add_zap_receipt(raw, 'invoice', 1234, prepare_only=True)
        w._publish_incoming_event.assert_not_awaited()
        for _ in range(2):
            result = await w.add_zap_receipt(raw, 'invoice', 1234, relay='wss://relay.example', prepared_event=prepared)
            assert result['event_id'] == prepared['id']
        with pytest.raises(ValueError):
            await w.add_zap_receipt(raw, 'other', 1234, relay='wss://relay.example', prepared_event=prepared)
        with pytest.raises(ValueError):
            await wallet().add_zap_receipt(raw, 'invoice', 1234, prepare_only=True)
        history = await w.add_tx_history('C',1,prepare_only=True)
        with pytest.raises(ValueError):
            await publish_event(w, 'wss://relay.example', history, private=False)
        with pytest.raises(ValueError):
            await publish_event(w, 'wss://wrong-home.example', history, private=True)
        with pytest.raises(ValueError):
            await publish_event(w, 'wss://127.0.0.1', prepared)
    asyncio.run(run())


def test_recovery_material_and_public_identity_methods():
    material = Acorn.generate_recovery_material()
    assert len(material['phrase'].split()) == 24
    recovered = Acorn.recover_material(material['phrase'])
    assert recovered == material
    instance = Acorn(nsec=material['nsec'])
    identity = instance.public_identity()
    assert identity == {'hex': instance.pubkey_hex, 'npub': material['npub']}
    assert set(identity) == {'hex', 'npub'}
    assert material['nsec'] not in str(identity)


@pytest.mark.asyncio
async def test_prepared_delivery_uses_stroma_transport(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from acorn import incoming
    wallet = SimpleNamespace(pubkey_hex='public', home_relay='wss://home.example')
    signed = SimpleNamespace(id='event-id', is_valid=lambda: True)
    monkeypatch.setattr(incoming, 'validate_event', lambda *args: signed)
    client = SimpleNamespace(query=AsyncMock(side_effect=[[], [signed]]),
                             publish=AsyncMock(return_value=SimpleNamespace(accepted=True)))
    options = {}
    def relay_client(relay, **kwargs):
        options.update(kwargs)
        return client
    monkeypatch.setattr(incoming, 'RelayClient', relay_client)
    assert await incoming.publish_event(wallet, wallet.home_relay, {'kind': 7377}, private=True)
    client.publish.assert_awaited_once_with(signed)
    assert client.query.await_count == 2
    assert callable(options['session_factory'])
    # Retrying an already readable event never republishes it.
    client.query = AsyncMock(return_value=[signed])
    client.publish.reset_mock()
    assert await incoming.publish_event(wallet, wallet.home_relay, {'kind': 7377}, private=True)
    client.publish.assert_not_awaited()
