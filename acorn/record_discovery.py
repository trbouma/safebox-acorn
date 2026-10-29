"""Bounded user-record discovery. Cursors are navigation, never authorization."""
import base64
import hashlib
import json
import re
from time import time

MAX_QUERY = 4096
HEX = re.compile(r"[0-9a-f]{64}")


def protected(wallet, label):
    from .acorn import INTERNAL_RECORD_LABELS
    names = set(INTERNAL_RECORD_LABELS)
    if getattr(wallet, "name", None):
        names.add(str(wallet.name))
    return label in names or label.split(":", 1)[-1] in names or label.split(":", 1)[-1].startswith("__acorn_")


def decode(wallet, events):
    from .acorn import INTERNAL_RECORD_LABELS, NIP44Encrypt
    names = set(INTERNAL_RECORD_LABELS)
    if getattr(wallet, "name", None):
        names.add(str(wallet.name))
    hidden = {wallet._record_label_hash(name) for name in names}
    cipher = NIP44Encrypt(wallet.k)
    rows = []
    for event in wallet._canonical_record_events(events):
        if event.pub_key != wallet.pubkey_hex or int(event.kind) != 37375:
            continue
        if not event.is_valid():
            raise ValueError("Invalid user record event signature")
        coordinate = wallet._record_event_tag(event, "d")
        if not coordinate or coordinate in hidden:
            continue
        try:
            try:
                plaintext = cipher.decrypt(event.content, wallet.pubkey_hex)
            except (ValueError, TypeError, RuntimeError):
                plaintext = cipher.decrypt_event(event).content
            value = json.loads(plaintext)
        except Exception as exc:
            raise ValueError("User record could not be decoded") from exc
        if not isinstance(value, dict):
            continue
        tag = value.get("tag")
        label = tag[0] if isinstance(tag, list) and len(tag) == 1 else tag
        if not isinstance(label, str) or not label or protected(wallet, label):
            continue
        if wallet._record_label_hash(label) != coordinate:
            raise ValueError("User record label does not match its lookup tag")
        value = dict(value)
        payload = value.get("payload", "")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                pass
        value.update(payload=payload, id=str(event.id), timestamp=wallet._event_timestamp(event),
                     sender=wallet.pubkey_hex, presenter=wallet.pubkey_hex,
                     created_at=event.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        value["content"] = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        rows.append(value)
    return rows


async def query(wallet, filters, relay):
    from .acorn import _bounded_client_pool, _bounded_client_query
    async with _bounded_client_pool([relay]) as client:
        return await _bounded_client_query(client, [filters])


def relay_for(wallet, relay):
    relays = wallet._record_relay_pool([relay] if relay else None)
    if len(relays) != 1:
        raise ValueError("Choose one authoritative relay for record discovery")
    return relays[0]


async def page(wallet, *, page_size=100, cursor=None, relay=None):
    if type(page_size) is not int or not 1 <= page_size <= 500:
        raise ValueError("page_size must be between 1 and 500")
    relay = relay_for(wallet, relay)
    scope = hashlib.sha256((wallet.pubkey_hex + "\0" + relay).encode()).hexdigest()
    until, seen = int(time()), []
    if cursor is not None:
        try:
            if not isinstance(cursor, str) or len(cursor) > 400000:
                raise ValueError()
            state = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if set(state) != {"v", "scope", "until", "seen"} or state["v"] != 1 or state["scope"] != scope:
                raise ValueError()
            until, seen = state["until"], state["seen"]
            if type(until) is not int or until < 0 or not isinstance(seen, list) or len(seen)>MAX_QUERY:
                raise ValueError()
            if len(set(seen)) != len(seen) or any(not isinstance(x,str) or not HEX.fullmatch(x) for x in seen):
                raise ValueError()
        except Exception as exc:
            raise ValueError("Invalid record cursor") from exc
    # Consume at most one relay batch per page. Empty user pages can still have a cursor.
    limit = page_size + len(seen) + 1
    if limit > MAX_QUERY:
        raise ValueError("Record timestamp bucket exceeds pagination query bound")
    filters = {"authors":[wallet.pubkey_hex], "kinds":[37375], "until":until, "limit":limit}
    events = await query(wallet, filters, relay)
    unique = {str(e.id):e for e in events if e.pub_key == wallet.pubkey_hex and int(e.kind)==37375
              and wallet._event_timestamp(e)<=until}
    ordered = sorted(unique.values(), key=lambda e:(-wallet._event_timestamp(e), str(e.id)))
    fresh = [e for e in ordered if not (wallet._event_timestamp(e)==until and str(e.id) in seen)]
    batch = fresh[:page_size]
    if not batch:
        # A full response with no progress must never be interpreted as completion.
        if len(ordered)>=limit:
            raise ValueError("Record pagination made no progress")
        if seen and until > 0:
            next_state = {"v":1,"scope":scope,"until":until-1,"seen":[]}
        else:
            return {"records":[], "next_cursor":None}
    else:
        boundary = wallet._event_timestamp(batch[-1])
        ids = (seen if boundary == until else []) + [str(e.id) for e in batch if wallet._event_timestamp(e)==boundary]
        next_state = {"v":1,"scope":scope,"until":boundary,"seen":sorted(set(ids))}
    next_cursor = base64.urlsafe_b64encode(json.dumps(next_state,separators=(",", ":")).encode()).decode()
    return {"records":decode(wallet,batch), "next_cursor":next_cursor}


async def retrieve(wallet, *, event_id=None, label=None, relay=None):
    if (event_id is None) == (label is None):
        raise ValueError("Provide exactly one of event_id or label")
    relay = relay_for(wallet, relay)
    filters = {"authors":[wallet.pubkey_hex], "kinds":[37375], "limit":16}
    if event_id is not None:
        if not isinstance(event_id,str) or not HEX.fullmatch(event_id):
            raise ValueError("Invalid user record event ID")
        filters["ids"] = [event_id]
    else:
        if not isinstance(label,str) or not label.strip():
            raise ValueError("Invalid user record label")
        if protected(wallet,label):
            return None
        filters["#d"] = [wallet._record_label_hash(label)]
    events = await query(wallet,filters,relay)
    # Defend against a relay returning unrelated events, independently of its filters.
    events = [e for e in events if (event_id is None or str(e.id)==event_id)
              and (label is None or wallet._record_event_tag(e,"d")==filters["#d"][0])]
    rows = decode(wallet,events)
    return rows[0] if rows else None
