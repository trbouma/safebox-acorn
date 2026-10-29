import json
from unittest.mock import AsyncMock

import pytest
from stroma import Event
from acorn import acorn as module
from acorn import record_discovery as discovery
from test_relay_records import wallet_with_key


def event(wallet, label, stamp, payload="note", coordinate=None):
    e = Event(kind=37375, pub_key=wallet.pubkey_hex, created_at=stamp,
        tags=[["d", coordinate or wallet._record_label_hash(label)]],
        content=json.dumps({"tag":[label],"type":"generic","payload":payload}))
    e.sign(wallet.privkey_hex)
    return e


@pytest.fixture
def records(monkeypatch):
    wallet = wallet_with_key()
    wallet.name = "Private Wallet Name"
    rows, calls = [], []
    class Cipher:
        def __init__(self, key): pass
        def decrypt(self, content, key): return content
    monkeypatch.setattr(module,"NIP44Encrypt",Cipher)
    async def query(w, filters, relay):
        calls.append(filters)
        found = [e for e in rows if e.pub_key in filters['authors'] and e.kind in filters['kinds']
                 and e.created_at.timestamp() <= filters.get('until',10**12)
                 and ('ids' not in filters or e.id in filters['ids'])
                 and ('#d' not in filters or w._record_event_tag(e,'d') in filters['#d'])]
        return sorted(found,key=lambda e:(-e.created_at.timestamp(), e.id))[:filters['limit']]
    monkeypatch.setattr(discovery,'query',query)
    return wallet, rows, calls


@pytest.mark.asyncio
async def test_pagination_retrieves_more_than_legacy_limit_with_timestamp_ties(records):
    w, rows, calls = records
    rows.extend(event(w,f'health/{i}',1000+i//17) for i in range(1100))
    cursor, seen, iterations = None, [], 0
    while True:
        result = await w.get_user_records_page(page_size=100,cursor=cursor)
        seen.extend(row['id'] for row in result['records'])
        cursor=result['next_cursor'];iterations+=1
        assert iterations<40
        if cursor is None:break
    assert len(seen)==len(set(seen))==1100
    assert set(seen)=={e.id for e in rows}
    assert all(c['limit']<=discovery.MAX_QUERY for c in calls)


@pytest.mark.asyncio
async def test_all_records_at_one_timestamp_are_not_skipped(records):
    w,rows,_=records
    rows.extend(event(w,f'member/{i}',100) for i in range(12))
    cursor=None;seen=[]
    for _ in range(20):
        result=await w.get_user_records_page(page_size=3,cursor=cursor)
        seen.extend(r['id'] for r in result['records']);cursor=result['next_cursor']
        if cursor is None:break
    assert cursor is None
    assert len(seen)==len(set(seen))==12


@pytest.mark.asyncio
async def test_internal_only_pages_keep_cursor_and_direct_reads_protect_internal_records(records):
    w,rows,_=records
    for label in ['pending_melts',w.name,'__acorn_private','sender:__acorn_private','sender:pending_melts']:
        e=event(w,label,200);rows.append(e)
        assert await w.get_user_record(label=label) is None
        assert await w.get_user_record(event_id=e.id) is None
    user=event(w,'member',100);rows.append(user)
    cursor=None;found=[];empty_pages=0
    for _ in range(20):
        result=await w.get_user_records_page(page_size=2,cursor=cursor)
        if not result['records'] and result['next_cursor']:empty_pages+=1
        found.extend(result['records']);cursor=result['next_cursor']
        if cursor is None:break
    assert empty_pages>0
    assert [r['id'] for r in found]==[user.id]


@pytest.mark.asyncio
async def test_direct_read_is_exact_and_does_not_list(records):
    w,rows,calls=records
    target=event(w,'member',1);rows.extend([target,event(w,'health/new',100)])
    w.get_user_records=AsyncMock(side_effect=AssertionError('must not list'))
    assert (await w.get_user_record(event_id=target.id))['payload']=='note'
    assert calls[-1]['ids']==[target.id]
    assert (await w.get_user_record(label='member'))['id']==target.id
    assert calls[-1]['#d']==[w._record_label_hash('member')]
    assert await w.get_user_record(label='missing') is None
    with pytest.raises(ValueError): await w.get_user_record(label='member',event_id=target.id)
    with pytest.raises(ValueError): await w.get_user_record(event_id='invalid')


@pytest.mark.asyncio
async def test_fail_closed_on_relay_error_bad_ciphertext_and_wrong_lookup_tag(records,monkeypatch):
    w,rows,_=records
    e=event(w,'member',100,coordinate=w._record_label_hash('different'));rows.append(e)
    with pytest.raises(ValueError,match='lookup tag'): await w.get_user_record(event_id=e.id)
    rows.clear();e=event(w,'member',100);e.content='not json';e.sign(w.privkey_hex);rows.append(e)
    with pytest.raises(ValueError,match='decoded'): await w.get_user_record(event_id=e.id)
    monkeypatch.setattr(discovery,'query',AsyncMock(side_effect=TimeoutError()))
    with pytest.raises(TimeoutError): await w.get_user_records_page()
    with pytest.raises(TimeoutError): await w.get_user_record(label='member')


@pytest.mark.asyncio
async def test_cursor_scope_validation_and_tie_overflow(records,monkeypatch):
    w,rows,_=records
    rows.extend(event(w,f'member/{i}',100) for i in range(8))
    result=await w.get_user_records_page(page_size=2)
    with pytest.raises(ValueError,match='cursor'):
        await w.get_user_records_page(cursor=result['next_cursor'],relay='wss://different.example')
    with pytest.raises(ValueError,match='cursor'):await w.get_user_records_page(cursor='bad')
    with pytest.raises(ValueError):await w.get_user_records_page(page_size=0)
    monkeypatch.setattr(discovery,'MAX_QUERY',4)
    with pytest.raises(ValueError,match='bound'):await w.get_user_records_page(page_size=2,cursor=result['next_cursor'])


@pytest.mark.asyncio
async def test_direct_read_rejects_unrelated_or_unsigned_events(records,monkeypatch):
    w,_,_=records
    valid=event(w,'member',100)
    monkeypatch.setattr(discovery,'query',AsyncMock(return_value=[valid]))
    assert await w.get_user_record(event_id='a'*64) is None
    valid.sig='0'*128
    with pytest.raises(ValueError,match='signature'):await w.get_user_record(event_id=valid.id)


@pytest.mark.asyncio
async def test_real_signed_encrypted_record_round_trip(records,monkeypatch):
    from stroma import NIP44Encrypt
    w,rows,_=records
    monkeypatch.setattr(module,'NIP44Encrypt',NIP44Encrypt)
    e=event(w,'health/current',100,payload={'note':'private'})
    e.content=NIP44Encrypt(w.k).encrypt(e.content,to_pub_k=w.pubkey_hex)
    e.sign(w.privkey_hex);rows.append(e)
    result=await w.get_user_record(event_id=e.id)
    assert result['payload']=={'note':'private'}
    result=await w.get_user_records_page()
    assert result['records'][0]['tag']==['health/current']


@pytest.mark.asyncio
async def test_tampered_cursor_cannot_expose_internal_record(records):
    import base64
    w,rows,_=records
    rows.extend([event(w,'member',300),event(w,'pending_melts',200)])
    page=await w.get_user_records_page(page_size=1)
    cursor=json.loads(base64.urlsafe_b64decode(page['next_cursor']))
    cursor.update(until=200,seen=[])
    forged=base64.urlsafe_b64encode(json.dumps(cursor).encode()).decode()
    assert (await w.get_user_records_page(cursor=forged))['records']==[]
