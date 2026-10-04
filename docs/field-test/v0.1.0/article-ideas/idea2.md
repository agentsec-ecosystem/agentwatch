# The Lock That Starved 1000 Hooks: O(n) Verification Under a Contended Lock

> 10,000 hook sends. 1,000 silently disappear. The daemon is running. The socket is open.
> The agent got a success response. But the store doesn't have 1,000 records.

## The Hook

Your daemon handles 10,000 hook sends in 35 seconds. p99 latency is 0.36 ms. The hash chain
is intact. `verify-store` is green. Everything works.

Now look at the same daemon before one code change: 10,000 sends, 9,016 delivered, 984
silently lost. Not rejected. Not errored. Just never recorded. The agent's hook returned
`True` (fire-and-forget). The daemon accepted the connection. But the record never made it
to the store. And nobody knew.

This is the story of how a background thread's O(n) hash chain re-verification starved the
hot path under a contended lock — and why "raise the backlog" was the wrong fix that cost us
three runs before we found the real bottleneck.

## The Architecture

The agentwatch daemon has two threads:

**Thread 1 — Accept (the hot path):** Accepts Unix socket connections from hooks, reads the
message, normalizes it, appends it to the hash-chained store.

```python
def _serve(self):
    while not self._stop.is_set():
        conn, _ = self._server.accept()
        with conn:
            self._read_connection(conn)  # → handle_line → handle_message → _append

def _append(self, record):
    # ... normalize, build envelope ...
    with self._lock:        # ← needs store._lock
        self.store.append(record)  # ← writes to disk, updates hash chain
```

**Thread 2 — Sweeper (background verification):** Every 5 seconds, reloads the store from
disk and re-verifies the entire hash chain. This is "continuous verification" (M12 G2) — if
someone tampers with the store file mid-session, the sweeper detects it and flips health to
degraded.

```python
def _sweep_loop(self):
    while not self._stop.wait(self.sweep_interval_seconds):  # 5.0 s
        self._sweep_pending_pre()
        self.chain_status = self.store.refresh()  # ← the problem
        self.health.set_chain(self.chain_status)
```

And `refresh()`:

```python
def refresh(self):
    with self._lock:           # ← holds store._lock
        self._entries = self._load()   # ← reads ENTIRE file from disk
        self._recount()
        return self.verify()    # ← O(n): recomputes every hash in the chain
```

Both threads need `store._lock`. The accept thread needs it for every `append()`. The
sweeper needs it for every `refresh()`. And `refresh()` holds it for a long time.

## The Failure

At small scale (1,000 entries), `refresh()` takes 11 ms. At 5,000 entries, 56 ms. At 10,000
entries, 116 ms. At 20,000 entries — the scale of a 10k-send soak — **242 ms**.

Here's what happens during those 242 ms:

1. Sweeper acquires `store._lock`.
2. Sweeper reads the entire store file from disk (`_load()`).
3. Sweeper recomputes every hash in the chain (`verify()` — O(n)).
4. Meanwhile, the accept thread tries to `append()`. It blocks on `store._lock`.
5. New hook connections queue in the listen backlog (512 slots).
6. At 200 records/sec (10k sends at 10 ms cadence × 2 records/send), 48 appends queue
   during the 242 ms lock hold.
7. If the backlog fills before the sweeper releases the lock, `send()` connects time out
   (1 s timeout in `hook.py`).
8. `send()` returns `False`. The hook is fire-and-forget — the agent doesn't retry. The
   record is lost.

Over 100 seconds of soak, the sweeper runs 20 times (every 5 s). Each sweep blocks ~48
appends. 20 × 48 = 960 blocked appends. ~964 sends return `False`. **9,036 of 10,000
delivered. 964 silently lost.**

The worst part: the agent doesn't know. `send()` returns `False`, but the hook is
fire-and-forget — the agent ignores the return value. The daemon doesn't log the dropped
sends. The store has 9,036 records instead of 10,000, and the only way to notice is to
count.

## The Wrong Fix

The first diagnosis: "the single-threaded accept path is the bottleneck." The listen backlog
was 128. Raising it to 512 would give more queue room.

```python
# Before
server.listen(128)

# After
server.listen(512)
```

Result: 9,499/10,000 (95%). Better, but still dropping 500 sends. Why? Because more backlog
just delays the drops, it doesn't prevent them. The bottleneck is not backlog capacity —
it's the time `append()` spends blocked on the lock. More backlog means more sends queue
before timing out, but they still time out if the sweeper holds the lock long enough.

This cost us two full suite runs before we realized the backlog was a band-aid.

## The Right Fix

Move the file read and chain verification **outside the lock**. Snapshot under the lock,
process outside it.

```python
def refresh(self):
    # Read and verify OUTSIDE the lock — no blocking the accept thread
    entries = self._load()              # disk read, no lock
    status = self._verify_entries(entries)  # O(n) verify, no lock

    # Only update in-memory state under the lock — O(1) reference swap
    with self._lock:
        if len(entries) >= len(self._entries):  # length guard (see below)
            self._entries = entries
        self._recount()
    return status
```

The lock-hold time drops from O(n) (242 ms at 20k entries) to O(1) (a reference assignment,
nanoseconds). The accept thread never blocks for more than microseconds.

Result: **10,000/10,000 delivered. p99=0.36 ms. `verify-store` green.**

## The Second Bug: The Length Guard

Moving `refresh()` outside the lock introduced a new race that the first run after the fix
exposed:

```
agentwatch: chain broken at seq 815
```

The disk read (`_load()`) runs outside the lock. While it's reading, `append()` may write
new entries to the file. The disk read may complete before the new entries are flushed,
producing a shorter entry list (815 entries instead of 820).

If `refresh()` replaces `self._entries` with this shorter list, the next `append()`
computes:

```python
seq = self._entries[-1].seq + 1  # = 816
prev_hash = self._entries[-1].hash
```

But entry 816 was already written to disk by the `append()` that happened during the disk
read. Now there are **two entries with seq 816** on disk. The chain is broken.

The fix: only adopt the disk-loaded list when it's at least as long as the in-memory list:

```python
with self._lock:
    if len(entries) >= len(self._entries):  # ← guard against stale snapshot
        self._entries = entries
    self._recount()
```

If the disk snapshot is shorter (stale), keep the current in-memory list. The verification
still runs on the stale snapshot (and may detect tampering), but the in-memory state is not
corrupted. The next sweep picks up the missing entries.

## The Scaling Data

Here's the `refresh()` timing at different store sizes (measured on the host, not Docker):

| Store entries | `refresh()` time (under lock) | `refresh()` time (outside lock) |
|---|---|---|
| 1,000 | 11 ms | 11 ms (same — lock-hold is O(1)) |
| 5,000 | 56 ms | 56 ms |
| 10,000 | 116 ms | 116 ms |
| 20,000 | 242 ms | 242 ms |

The total `refresh()` time is the same — the file read and verification still take O(n).
The difference is that the lock is held for nanoseconds instead of 242 ms. The accept thread
never blocks.

## Key Takeaways

1. **O(n) under a contended lock is a scaling cliff.** It works at low n, fails at high n.
   The failure is silent and load-dependent — invisible in unit tests, visible only under
   sustained load.
2. **Raising the backlog is a band-aid, not a fix.** More backlog delays the drops, it
   doesn't prevent them. The real fix is reducing lock-hold time.
3. **Snapshot under the lock, process outside it.** Read the data without holding the lock,
   process it without holding the lock, then only swap the reference under the lock (O(1)).
4. **Guard against stale snapshots.** When you move work outside the lock, the snapshot may
   be stale (shorter than reality). Use a length guard to avoid corrupting the sequence.
5. **Silent data loss is worse than a crash.** At least a crash is visible. Silent drops
   look like success — the agent got a `True` response, the daemon is running, the store
   has records. Just not all of them.
6. **The symptom doesn't point at the cause.** "Sends are being dropped" points at the
   network, the backlog, the accept loop. The real cause is lock contention in a background
   thread. You need per-thread timing to diagnose.

## Questions for You

- Do you run background verification (health checks, integrity scans, consistency audits) in
  the same process as your hot path? What lock does it hold?
- What's the lock-hold time of your background work at 10x your current scale? Have you
  measured it?
- How would you detect silent data loss in your recording pipeline? Would your tests catch
  964 missing records out of 10,000?
- Have you ever raised a backlog, pool size, or buffer to "fix" a performance issue, only
  to find it was a band-aid? What was the real bottleneck?
- When a background thread and a hot path share a lock, who wins? In your codebase, is the
  background work O(1) or O(n)?

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The soak data,
timing measurements, and code diffs are in
`field-test/v0.1.0/results/all/cases/FT-28/` and
`packages/python-sdk/src/agentwatch/store.py`.*
