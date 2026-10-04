#!/usr/bin/env python3
"""Split oversized parquet files in the processed trace corpus into smaller
row-chunked files, so ``--max-files N`` bounds peak memory in the validator
(FT-15c).  Files at or below ``--threshold-mb`` are left untouched.

Reads via ``iter_batches`` (row-group streaming) so splitting never loads a
whole file into memory.  The original big file is replaced by ``<stem>-partNNNN``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def split_file(path: Path, chunk_rows: int) -> int:
    pf = pq.ParquetFile(str(path))
    stem = path.stem
    parent = path.parent
    idx = 0
    for batch in pf.iter_batches(batch_size=chunk_rows):
        table = pa.Table.from_batches([batch], schema=pf.schema_arrow)
        out = parent / f"{stem}-part{idx:04d}.parquet"
        pq.write_table(table, str(out))
        idx += 1
    path.unlink()
    return idx


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="corpus root, e.g. data/traces/processed")
    ap.add_argument("--threshold-mb", type=float, default=50.0)
    ap.add_argument("--chunk-rows", type=int, default=20)
    args = ap.parse_args()

    root = Path(args.input)
    total = 0
    for pq_file in sorted(root.rglob("*.parquet")):
        if pq_file.stat().st_size / 1e6 <= args.threshold_mb:
            continue
        size_mb = pq_file.stat().st_size / 1e6
        n = split_file(pq_file, args.chunk_rows)
        total += 1
        print(f"split {pq_file.relative_to(root)} ({size_mb:.0f} MB) -> {n} chunks")
    print(f"done: {total} oversized files split")


if __name__ == "__main__":
    main()
