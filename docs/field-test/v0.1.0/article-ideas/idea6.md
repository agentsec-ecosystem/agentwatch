# The pid File Is the Crash Signal: Why One Missing File Silently Disabled Gap Detection

> Your daemon crashes. You restart it. It should record a `recording-gap` anomaly — proof
> that recording was interrupted. But it doesn't. The gap detection code checks
> `pid_path.exists()` and the pid file is gone. Your test harness deleted it during cleanup.

## The Hook

Here's a scenario that will make any developer building crash-recovery logic break into a
cold sweat: your daemon crashes, you restart it, and the system records a `recording-gap`
anomaly — proof that recording was interrupted, evidence that there's a hole in the trace.
This is critical for forensic integrity. The gap anomaly is how you tell the operator "hey,
something happened between the last record and now, and I don't have the data for it."

Now imagine the same crash, the same restart, but no gap anomaly. The system looks healthy.
The trust report says `gap:unexplained = 0`. Everything appears fine. But there IS a gap —
the daemon was down for 30 seconds, and 15 tool calls happened during that time. They're
not recorded. The gap is invisible. And nobody knows.

This happened to us. The gap detection was silently disabled because the test harness
deleted the wrong file during cleanup. The daemon's code was correct. The test's cleanup
was wrong. And the failure was invisible — no error, no warning, no log. Just a missing
anomaly that nobody noticed until the test explicitly asserted "the gap anomaly should
exist" and it didn't.

## The Design

The `agentwatch` daemon synthesizes a `recording-gap` anomaly when it restarts after a
crash. This is F1 in the fault taxonomy — a first-class fault that the system must detect
and record. The signal that distinguishes "first start" from "restart after crash" is a
file: `daemon.pid`.

```python
def _record_gap_if_needed(self):
    """Synthesize a recording-gap record after a crash (F1)."""
    if not self.pid_path.exists():
        return  # ← first start, no gap to synthesize
    records = self.store.records()
    if not records:
        return
    last = records[-1]
    now = datetime.now(timezone.utc)
    gap_seconds = (now - last.started_at).total_seconds()
    if gap_seconds < self.gap_threshold_seconds:
        return
    # ... synthesize the gap anomaly ...
    gap = AgentRecord(
        session_id=last.session_id,
        tool=ToolCall(name="recording-gap", arguments={"reason": "daemon-restart"}),
        outcome=Outcome.ERROR,
        started_at=last.started_at,
        ended_at=now,
        duration_ms=gap_seconds * 1000.0,
    )
    self._append(gap)
```

The logic is clean: if `daemon.pid` exists, the daemon was running before (it wrote the pid
file on start). If it doesn't exist, this is a first start — no previous session, no gap to
synthesize. The pid file is the crash signal.

The pid file is written by the launcher (`install.start_daemon`), not by the daemon itself.
The launcher starts the daemon, gets its PID, and writes it to `daemon.pid`. When the
daemon crashes, the pid file stays on disk — it's not cleaned up by the crash. On restart,
the new daemon sees the pid file and knows: "I was running before, there might be a gap."

## The Failure

The FT-14 test case simulates a crash: kill the daemon with SIGKILL, then restart it and
assert the `recording-gap` anomaly exists. The kill step also cleans up:

```bash
# Kill the daemon
kill -9 $(cat /data/agentwatch/daemon.pid)
# Clean up stale state
rm -f /data/agentwatch/daemon.pid      # ← THIS IS THE BUG
rm -f /run/agentwatch/agentwatch.sock
```

The cleanup removes the pid file as "stale state." But the pid file is not stale — it's the
crash signal. When the daemon restarts, `_record_gap_if_needed()` checks
`self.pid_path.exists()`. The pid file is gone. The function returns immediately. No gap
anomaly. No log. No warning. Silent skip.

The test asserts the gap anomaly exists. It doesn't. Test fails.

## The Diagnosis

The first reaction: "the gap detection logic is broken. Why isn't it synthesizing the gap?"

But reading the code: `_record_gap_if_needed()` checks `pid_path.exists()` as its very first
line. If the pid file doesn't exist, it returns. This is correct behavior for a first start
— you don't want to synthesize a gap on the very first daemon start. The bug is not in the
daemon's code. The bug is in the test's cleanup.

The test harness deleted the pid file as part of "stale state cleanup." The harness didn't
understand that the pid file is not stale state — it's the crash signal. It's the evidence
that the daemon was running before. Deleting it is like deleting the crime scene before the
detective arrives.

## The Fix

The test harness must keep the pid file and only clear the stale socket:

```bash
# Kill the daemon
kill -9 $(cat /data/agentwatch/daemon.pid)
# Clean up stale state — but KEEP the pid file (it's the crash signal)
rm -f /run/agentwatch/agentwatch.sock
# DO NOT: rm -f /data/agentwatch/daemon.pid
```

But there's a subtlety: the daemon doesn't write its own pid file — the launcher does. When
the test harness starts the daemon directly (not via the launcher), no pid file is written.
So the harness must replicate the launcher's behavior:

```bash
# Start the daemon
(agentwatch-daemon >/tmp/daemon.log 2>&1 &)
# Write the pid file (replicate what install.start_daemon does)
pgrep -f "[a]gentwatch-daemon" | head -1 > /data/agentwatch/daemon.pid
```

The `[a]gentwatch-daemon` bracket trick prevents `pgrep` from matching its own process. The
pid file is written before the daemon starts processing, just like the launcher does. When
the daemon crashes and restarts, it sees the pid file and synthesizes the gap.

After the fix: `recording-gap` anomaly present. Test passes. The gap carries
`duration_ms` matching the crash-to-restart interval.

## The Deeper Lesson

This is a pattern that goes beyond pid files. Any state that serves as a signal — crash
recovery, feature flags, migration markers, health checks — must be managed by the code
that reads it, not by external cleanup.

The test harness thought it was cleaning up "stale state." It was actually deleting the
crash signal. The harness didn't understand the semantics of the files it was cleaning up.
It treated all files in `/data/agentwatch/` as "stale state" to be removed between test
cases. But `daemon.pid` is not stale — it's the evidence that the daemon was running before.

This pattern appears everywhere:

| Signal | What it means | What cleanup does | What happens |
|---|---|---|---|
| `daemon.pid` | "daemon was running before" | deleted as "stale" | gap detection silently disabled |
| `.migration_complete` | "migration ran" | deleted as "old marker" | migration re-runs, data corrupted |
| `health_check.json` | "last health status" | overwritten with empty | health history lost |
| `.env` | "config was set" | deleted as "temp" | config reset to defaults |

In every case, the cleanup code doesn't understand the semantics of the file. It just sees
a file and deletes it. The code that reads the file silently skips — no error, no warning.
The system appears healthy. The signal is gone.

## The Silent Skip Problem

The worst part of this bug is not that the gap wasn't synthesized. It's that the failure
was **invisible**. The daemon didn't error. It didn't log a warning. It didn't crash. It
just... skipped. `_record_gap_if_needed()` returned without doing anything, and nobody knew.

Silent skips are the worst failure mode because:

1. **No error signal.** The function returns normally. No exception, no error code, no log.
2. **No observable effect.** The gap anomaly is absent, but absence is not an error — it's
   just "nothing happened." You have to explicitly check for the anomaly's presence to
   notice.
3. **No feedback loop.** The daemon doesn't know it should have synthesized a gap. It
   doesn't know the pid file was deleted. It just sees "no pid file → first start → no gap."
   The logic is correct for the input it received. The input was wrong.

The only way to catch a silent skip is to **assert the expected behavior explicitly.** The
FT-14 test does this: it asserts the `recording-gap` anomaly exists after a crash-restart.
Without that assertion, the silent skip would have shipped to production, and real crash
gaps would have been invisible.

## Key Takeaways

1. **The crash signal must survive cleanup.** If your recovery logic keys on a file's
   existence, your test harness must not delete that file. The pid file is not stale — it's
   the evidence.
2. **Silent skips are worse than errors.** The daemon didn't error — it just skipped. No
   log, no warning, no trace. The gap was invisible. Always assert the expected recovery
   behavior, not just that the daemon started.
3. **External cleanup must distinguish signals from stale state.** Not all files in a
   directory are "stale." Some are signals, markers, or evidence. Cleanup code must
   understand the semantics of what it's deleting.
4. **The test must verify the recovery happened, not just the startup.** "Daemon is
   running" ≠ "gap was synthesized." These are different assertions. The first is
   necessary but not sufficient.
5. **Replicate the launcher's behavior in tests.** If the launcher writes a pid file, the
   test harness must write one too. If it doesn't, the daemon's behavior changes (first
   start vs restart after crash), and the test doesn't exercise the recovery path.

## Questions for You

- What file or state does your crash-recovery logic key on? A pid file? A lock file? A
  database flag?
- Does your test harness delete that state during cleanup? What happens to your recovery
  logic if it does?
- How would you know if your gap detection was silently disabled? Would your tests catch
  it, or would it ship to production?
- Do your tests assert the recovery behavior (gap synthesized, state restored), or just
  that the process started?
- Have you ever had a test harness delete a file that was actually a signal? How did you
  find out?
- What's the difference between "stale state" and "crash evidence" in your cleanup logic?
  Does your cleanup know the difference?

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The gap
detection code, test harness, and fix are in `packages/python-sdk/src/agentwatch/daemon.py`
and `scripts/fieldtest/cases/steps/FT-14.sh`.*
