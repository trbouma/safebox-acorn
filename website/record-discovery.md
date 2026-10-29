# Paginated user-record discovery

Acorn offers two additive, read-only APIs for applications managing large record
collections. Existing `get_user_records`, `get_user_record_labels` and
`get_record_safebox` calls retain their behavior. No record migration is needed.
These APIs cover owned user records of kind **37375**, not wallet messages or
internal operational state. Cryptographic operations remain inside Acorn and
use Stroma.

## Discover pages

```python
cursor = None
while True:
    page = await acorn.get_user_records_page(page_size=100, cursor=cursor)
    for record in page["records"]:
        show_record(record)  # application display/indexing
    cursor = page["next_cursor"]
    if cursor is None:
        break
```

For a web UI, fetch one page at a time and retain its `next_cursor` for the next
request. Page sizes are 1–500; the default is 100. Records are returned newest
first, with event-ID ordering for ties. The result includes full decrypted
record metadata and payload, but does not download the original attachment.
The page budget counts relay events, including internal records subsequently
excluded; a page can therefore contain fewer user records, or none at all.
**Continue until `next_cursor` is null, not until a page is empty.**

The cursor retains an inclusive timestamp and IDs already traversed at that
second. This avoids skipping records that share a timestamp. It is versioned,
bounded and scoped to the wallet public key and chosen relay. It contains no
private key or decrypted labels, but should still be treated as private activity
metadata. It is navigation state, not an authorization credential; every request
reapplies ownership and internal-record checks.

Use the default home relay, or specify `relay="wss://..."`. A traversal uses one
authoritative relay, not a merged view of multiple relay histories. The relay
must implement the requested author, kind, timestamp and limit filters and
return newest-first results. Current Spurline's 5,000-event ceiling exceeds this
API's 4,096-event query bound. Other relay limits should be checked before use;
there is no protocol guarantee that a relay has retained every record.

Queries expand within a timestamp bucket, up to 4,096 events. If the requested
page plus already-seen IDs exceeds that bound, Acorn raises an error instead of
advancing past potentially unread records. Large batches created in a single
second may therefore require operator attention; this is an explicit bound,
not an unlimited timestamp-bucket guarantee.

Pagination is not a transactional snapshot. Concurrent edits can move a record
outside the portion already traversed. A cache/index should reconcile subsequent
refreshes by record coordinate and event ID, and account for deletions; it must
not use a partial traversal as proof that a record does not exist. A fresh
traversal discovers new writes. Use exact `record_exists` for write collision
checks, with the application's writer coordination.

## Read one user record

```python
record = await acorn.get_user_record(event_id=selected_event_id)
# Or use an exact, case-sensitive label:
record = await acorn.get_user_record(label="health/current")
```

Provide exactly one of `event_id` or `label`. An event ID is the full Nostr event
ID returned by discovery, not a display fingerprint or an application's hashed
URL reference. Both forms query only the exact target instead of loading the
collection. Label reads select the canonical version returned by the relay;
event-ID reads may become unavailable after replacement or deletion.

Missing or protected records return `None`. Relay failures, invalid signatures,
failed decryption and inconsistent label bindings raise errors. Applications
must distinguish unavailable from absent and must not automatically replay a
write because a read failed.

## Internal-record boundary

Both APIs enforce the current Acorn public key and kind 37375, validate event
signatures, exclude known internal lookup tags and the wallet's configured name,
and examine the decrypted record label. Reserved labels, internal `__acorn_`
labels and origin-prefixed internal labels are not returned. A user label must
match the event's private lookup tag. Passing an internal event ID cannot bypass
these checks. Unstructured operational values are not exposed as user records.

`get_record_safebox` remains a lower-level internal-capable API for existing
callers. Applications should prefer `get_user_record` for user-facing retrieval.
These changes do not alter safebox-web's existing APIs or storage format.

## Adoption

This release supplies the Acorn primitives. OakGate still needs a separate
adapter/UI change to use paginated lists and direct retrieval, preserving its
opaque URL references, owner checks and current presentation flows. Raising the
legacy record limit is not a substitute for that integration.
