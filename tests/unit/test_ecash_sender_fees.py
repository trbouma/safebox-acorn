from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest
from acorn.acorn import Acorn
from acorn import acorn as module
from acorn.models import Proof
from acorn.token_codec import decode_cashu_token
from tests.unit.test_accept_token import wallet_with_key


@pytest.mark.parametrize('fee_ppk', [0, 1, 100, 1000, 2000])
def test_net_amount_is_exact_across_binary_boundaries(fee_ppk):
    for amount in range(1, 300):
        parts, fee = Acorn._net_transfer_denominations(amount, fee_ppk)
        assert all(part > 0 and part & (part - 1) == 0 for part in parts)
        assert fee == Acorn._input_fee_sats(fee_ppk, len(parts))
        assert sum(parts) - fee == amount


def wallet():
    result = wallet_with_key()
    key = '00f300c64b950282'
    result.known_mints = {key:'https://mint.example'}
    result.proofs = [Proof(amount=16, id=key, secret='input', C='02'+'11'*32)]
    return result, key


def install_mint(monkeypatch, key, fee=1000):
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            return SimpleNamespace(raise_for_status=lambda:None,
                json=lambda:{'keysets':[{'id':key,'unit':'sat','active':True,'input_fee_ppk':fee}]})
        async def post(self, *args, **kwargs):
            raise AssertionError('Quote/changed fee must not submit a swap')
    monkeypatch.setattr(module.httpx, 'AsyncClient', Client)


@pytest.mark.asyncio
async def test_quote_and_issuance_preserve_exact_net_and_debit(monkeypatch):
    acorn,key = wallet()
    install_mint(monkeypatch,key)
    quote = await acorn.quote_ecash_transfer(6)
    assert quote['denominations'] == [4,4]
    assert quote['receiver_fee'] == 2
    assert quote['sender_fee'] == 1
    assert quote['total_amount'] == 9
    acorn._keyset_input_fee_ppk = AsyncMock(return_value=1000)
    acorn.swap_for_payment_multi = AsyncMock(return_value=[
        Proof(amount=n,id=key,secret=f'output-{i}',C='02'+'22'*32)
        for i,n in enumerate([4,4,4,2,1])])
    acorn.write_proofs = AsyncMock()
    token = decode_cashu_token(await acorn.issue_token(6,fee_quote=quote))
    assert token.get_amount() == 8
    assert token.get_amount() - Acorn._input_fee_sats(1000,len(token.get_proofs())) == 6
    assert sum(p.amount for p in acorn.proofs) == 7
    assert acorn.add_tx_history.await_args.kwargs['amount'] == 6
    assert acorn.add_tx_history.await_args.kwargs['fees'] == 3
    assert acorn.swap_for_payment_multi.await_args.kwargs['fee_quote'] == quote
    acorn.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_fee_change_rejected_before_issue_or_swap(monkeypatch):
    acorn,key = wallet()
    install_mint(monkeypatch,key)
    quote = await acorn.quote_ecash_transfer(6)
    install_mint(monkeypatch,key,fee=2000)
    acorn.swap_for_payment_multi = AsyncMock()
    with pytest.raises(RuntimeError,match='review a new quote'):
        await acorn.issue_token(6,fee_quote=quote)
    acorn.swap_for_payment_multi.assert_not_awaited()
    acorn._preflight_proof_persistence = AsyncMock()
    with pytest.raises(ValueError,match='fees changed'):
        await Acorn.swap_for_payment_multi(acorn,key,acorn.proofs,quote['token_amount'],fee_quote=quote)


@pytest.mark.asyncio
async def test_insufficient_balance_including_fees_is_read_only(monkeypatch):
    acorn,key = wallet()
    install_mint(monkeypatch,key)
    with pytest.raises(ValueError,match='including mint fees'):
        await acorn.quote_ecash_transfer(16)
    acorn.acquire_lock.assert_not_awaited()


@pytest.mark.asyncio
async def test_sender_paid_receipts_are_journaled_and_settled_individually():
    from tests.unit.test_continuity_payments import wallet as receipt_wallet, serialized_token, proof
    acorn = receipt_wallet()
    token = serialized_token([proof(4,"1"),proof(4,"2")])
    receipt = await acorn._store_continuity_receipt(event_id="event-1",sender_pubkey="ab"*32,
        token=token,payload={"amount":8,"fee_payer":"sender","recipient_amount":6,"receiver_fee":2},timestamp=1)
    assert receipt['recipient_amount'] == 6
    assert receipt['fee_payer'] == 'sender'
    second = {**receipt, 'event_id':'event-2'}
    with pytest.raises(ValueError,match='individual settlement'):
        await acorn.accept_continuity_token_batch([receipt,second])
    acorn.get_continuity_receipts = AsyncMock(return_value=[receipt,second])
    acorn.accept_continuity_token_batch = AsyncMock()
    acorn.accept_token = AsyncMock(return_value=('accepted',6))
    acorn._update_continuity_receipt = AsyncMock()
    result = await acorn.reconcile_continuity_receipts()
    assert result['confirmed_amount'] == 12
    assert result['confirmed_count'] == 2
    acorn.accept_continuity_token_batch.assert_not_awaited()
    assert acorn.accept_token.await_count == 2
    assert acorn.accept_token.await_args.kwargs['tendered_amount'] == 6


@pytest.mark.asyncio
async def test_sender_paid_receipt_rejects_inconsistent_amount_before_persistence():
    from tests.unit.test_continuity_payments import wallet as receipt_wallet, serialized_token, proof
    acorn = receipt_wallet()
    with pytest.raises(ValueError,match='sender-paid receipt amounts'):
        await acorn._store_continuity_receipt(event_id="event-1",sender_pubkey="ab"*32,
            token=serialized_token([proof(4,"1")]),
            payload={"amount":4,"fee_payer":"sender","recipient_amount":4,"receiver_fee":1},timestamp=1)
    acorn.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('sender_paid', [False, True])
async def test_giftwrap_preserves_gross_amount_and_opt_in_fee_metadata(monkeypatch, sender_paid):
    import json
    from stroma import Keys
    from tests.unit.test_continuity_payments import serialized_token, proof
    acorn, key = wallet()
    recipient = Keys(priv_k="22"*32).public_key_hex()
    acorn._resolve_transfer_destination = AsyncMock(return_value={
        'recipient_pubkey':recipient,'relays':['wss://relay.example'],'relay_source':'recipient-hint'})
    acorn._require_reachable_transfer_relays = AsyncMock(return_value=['wss://relay.example'])
    token = serialized_token([proof(4,'1'),proof(4,'2')])
    acorn.issue_token = AsyncMock(return_value=token)
    captured = {}
    class Pool:
        def __init__(self,*args): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        def publish(self,event): captured['published']=event
    class Gift:
        def __init__(self,*args,**kwargs): pass
        async def wrap(self,event,**kwargs):
            captured['payload']=json.loads(event.content)
            return SimpleNamespace(kind=1059,id='outer-event'),acorn.k
    monkeypatch.setattr(module,'ClientPool',Pool)
    monkeypatch.setattr(module,'KindOtherGiftWrap',Gift)
    quote = {'receiver_fee':2} if sender_paid else None
    result = await acorn.send_ecash_transfer(6 if sender_paid else 8,recipient,fee_quote=quote)
    assert captured['payload']['amount'] == 8
    assert captured['payload']['token'] == token
    if sender_paid:
        assert captured['payload']['recipient_amount'] == 6
        assert captured['payload']['receiver_fee'] == 2
        assert captured['payload']['fee_payer'] == 'sender'
        assert acorn.issue_token.await_args.kwargs['fee_quote'] == quote
        assert result['amount'] == 6
    else:
        assert 'fee_payer' not in captured['payload']
        assert 'fee_quote' not in acorn.issue_token.await_args.kwargs
        assert 'fee_quote' not in result
