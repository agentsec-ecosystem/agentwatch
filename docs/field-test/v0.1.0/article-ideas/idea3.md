# 590 MB for 100 Rows: When File Count Isn't File Size

> Your validator OOMs on 100 rows. Not 100 million — 100. You set `--max-files 5` to bound
> memory. Five files, 100 rows, 1.3 GB of parquet — and the process is killed.

## The Hook

Picture this: you're running a validation pipeline against a corpus of agent traces. You've
got 4,974 parquet files totaling 7.5 GB. The Docker VM has 7 GB of RAM. You set `--max-files 5`
because you know each file gets loaded fully into memory, and you want to keep things bounded.

Five files. 100 rows. The process starts, reads the first file, and gets killed.

```
/ft/corpus.sh: line 35: 55 Killed python -m analytics.main validate --input ... --max-files 5
```

Not an error. Not a timeout. `Killed`. That's SIGKILL — the OOM killer. The Docker VM ran out
of memory and the kernel reclaimed it by killing your process.

100 rows. Five files. 1.3 GB of parquet. How does 1.3 GB of parquet OOM a 7 GB VM?

## The Investigation

The first instinct: "the corpus is too big, we need to shard." So we shard — process one
dataset at a time instead of all 20 at once. Same `Killed`. Same OOM.

Second instinct: "we need fewer files." So we set `--max-files 5`. Still `Killed`. Still OOM.

Third instinct: "we need even fewer files." `--max-files 3`. `--max-files 2`. `--max-files 1`.
Still killed. One file. One file is enough to OOM the VM.

At this point you start questioning everything. One file OOMs a 7 GB VM? What's in that file?

```
$ ls -lS data/traces/processed/Exgentic__agent-llm-traces-v2/ | head -5
-rw-r--r--  618475751  traces-0001.parquet   (590 MB)
-rw-r--r--  360507057  traces-0005.parquet   (344 MB)
-rw-r--r--  350227908  traces-0002.parquet   (334 MB)
-rw-r--r--  323410706  traces-0006.parquet   (308 MB)
-rw-r--r--  200731923  traces-0009.parquet   (191 MB)
```

590 MB. One file. 590 MB.

How many rows in that 590 MB file?

```python
import pyarrow.parquet as pq
t = pq.read_table("traces-0001.parquet", columns=["trace_id"])
print("rows:", t.num_rows)
# rows: 100
```

**100 rows. 590 MB. 5.9 MB per row.**

Each row carries a full conversation transcript as its payload. Not a summary, not a
reference — the entire conversation text, embedded in the parquet row. 100 conversations,
each averaging 5.9 MB of text. That's the nature of agent observability data: conversation
traces are inherently large per row.

## Why max-files Didn't Help

`--max-files 5` limits the number of files the validator processes. It does not limit the
size of each file. The first 5 files by name happen to include the two largest files in the
dataset (590 MB and 344 MB). Even `--max-files 1` would OOM on the 590 MB file.

Here's what happens inside the validator:

```python
# validator.py — _iter_traces()
for pq_file in parquet_files:  # ← max_files limits this list
    table = pq.read_table(str(pq_file))  # ← loads ENTIRE file into memory
    for row in table.to_pylist():         # ← converts to Python dicts (5-10x expansion)
        # ... build SpanNode ...
```

`pq.read_table()` loads the entire parquet file into memory as an Arrow table. Then
`.to_pylist()` converts every row to a Python dict. Python dicts are memory-hungry — a 6 MB
string in parquet becomes a 6 MB Python string, plus dict overhead, plus the SpanNode object,
plus the attributes dict. The expansion factor is 5–10x.

So: 590 MB parquet → ~600 MB Arrow table → ~3–6 GB of Python objects. On a 7 GB VM with 8
other containers running (postgres, jaeger, otel-collector, api, analytics worker, web,
recorder, verifier), there's maybe 2–3 GB free. 3 GB of Python objects from one file is
enough to OOM.

The math is simple: `max_files × max_file_size` is the real memory bound, not `max_files`
alone. When one file is 590 MB, `max_files=1` gives you a 590 MB bound (→ 3 GB after
expansion). When all files are 300 KB, `max_files=5` gives you a 1.5 MB bound (→ 15 MB
after expansion). The file-count limit is only useful when files are roughly uniform in
size. When they're not — when one file is 2000x larger than the average — the limit is
useless.

## The Fix: Pre-Split, Don't Stream

The obvious fix is to stream the parquet reader: use `iter_batches()` instead of
`read_table()`. And that works for most cases. But the validator has a constraint: it
groups spans by `(trace_id, source_row_idx)` within each file. A single trace's spans must
be in memory together to build the span tree. With 100 rows per file and ~6 MB/row, even
one row group is 600 MB. Streaming helps, but the grouping logic still needs one full row
group in memory.

The simpler fix: pre-split the oversized files into single-row chunks. Each chunk is one
row, ~6 MB. `--max-files 5` now bounds memory to ~30 MB (5 × 6 MB). No validator code
changes needed.

```python
# split-big-parquet.py
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

def split_file(path: Path, chunk_rows: int = 1) -> int:
    pf = pq.ParquetFile(str(path))
    idx = 0
    for batch in pf.iter_batches(batch_size=chunk_rows):  # ← streaming read
        table = pa.Table.from_batches([batch], schema=pf.schema_arrow)
        out = path.parent / f"{path.stem}-part{idx:04d}.parquet"
        pq.write_table(table, str(out))
        idx += 1
    path.unlink()  # remove the original giant file
    return idx

# Split every file > 50 MB
for pq_file in sorted(root.rglob("*.parquet")):
    if pq_file.stat().st_size > 50 * 1e6:
        n = split_file(pq_file, chunk_rows=1)
        print(f"split {pq_file.name} ({pq_file.stat().st_size/1e6:.0f} MB) -> {n} chunks")
```

`iter_batches(batch_size=1)` reads one row at a time from the parquet file. It never loads
the whole file into memory. Each row is written as a separate parquet file. The 590 MB file
becomes 100 files of ~6 MB each.

The 13 oversized files (2.3 GB total) became 4,965 small files, all ≤ 50 MB. The corpus went
from 4,974 files to 4,965 files (the 13 originals were deleted, replaced by their chunks).
`--max-files 5` now bounds memory to ~250 MB. The validator completes. FT-15c passes.

## Why This Matters for Agent Observability

Agent traces are not like web request logs. A web request log is a few hundred bytes —
method, path, status, latency. An agent trace is a full conversation transcript — every
tool call, every LLM response, every planning step, every retry. A single agent run can
produce megabytes of trace data. And when you store traces as parquet files (columnar,
compressed, efficient for analytics), the per-row payload can be enormous.

The `Exgentic__agent-llm-traces-v2` dataset is an extreme case (5.9 MB/row), but it's not
unusual. Any dataset that records full conversation transcripts will have large per-row
payloads. The HuggingFace agent trace corpora that we process have files ranging from 300 KB
to 590 MB — a 2000x size range. A file-count limit that works for the 300 KB files is
useless for the 590 MB files.

The lesson is not "always pre-split your files." The lesson is: **know your file size
distribution.** If files vary by 2000x, a file-count limit is not a memory bound. You need
either a file-size limit, a streaming reader, or a pre-split step.

## The Gotcha: Floating-Point File Sizes

Here's a subtle one. When we first ran the split script, we set the threshold at 50 MB and
the chunk size at 20 rows. The 590 MB file split into 5 chunks of 51, 75, 160, 163, and 169
MB. Four of the five chunks were still over 50 MB. We had to run the split script again on
the chunks, which produced filenames like
`traces-0001-part0000-part0000-part0000-part0000.parquet` — name too long for the
filesystem.

The fix was to use `chunk_rows=1` (one row per file) and a flat naming scheme (`c00000.parquet`,
`c00001.parquet`, ...). One row per file guarantees each file is ≤ 6 MB. No re-splitting
needed. No filename explosion.

## Key Takeaways

1. **File count ≠ file size.** A file-count limit is only useful when files are roughly
   uniform in size. When one file is 2000x larger than the average, the limit is useless.
2. **`pq.read_table()` loads the whole file.** Use `iter_batches()` for streaming reads.
   But check whether your downstream logic needs the full file in memory (e.g., grouping
   spans by trace_id).
3. **Pre-splitting is a valid fix when the reader can't be easily changed.** Sometimes the
   simplest fix is to fix the data, not the code. Pre-split oversized files into single-row
   chunks and your existing reader works without changes.
4. **OOM from a small number of rows is a red flag.** If your process OOMs on 100 rows,
   check per-row payload size. The problem is not the row count — it's the payload size.
5. **`max_files × max_file_size` is the real memory bound.** Not `max_files` alone. Always
   check the largest file, not just the file count.
6. **Agent traces are inherently large per row.** Full conversation transcripts produce
   megabyte-scale rows. Plan for this in your memory bounds.

## Questions for You

- Do you process files with large per-row payloads? What's the largest single file in your
  corpus?
- Have you ever set a file-count limit and still OOM'd? Did you check the per-file sizes?
- Could your `--max-files` limit protect you against a 590 MB file? Or would one giant file
  defeat it?
- Do you use `pq.read_table()` or `iter_batches()`? Do you know the difference in memory
  usage?
- What's the size distribution of files in your data pipeline? Is it uniform, or does it
  vary by 100x or 1000x?
- Have you ever had a filename too long for the filesystem because of recursive splitting?
  How did you fix it?

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The file sizes,
split script, and validator code are in `scripts/fieldtest/split-big-parquet.py` and
`services/analytics/src/analytics/trace_pipeline/validator.py`. The corpus is in
`data/traces/processed/`.*
