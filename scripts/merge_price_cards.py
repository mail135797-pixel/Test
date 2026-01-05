#!/usr/bin/env python3
"""
Merge multiple extraction runs, de-duplicate globally, and build a single PDF.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import imagehash  # type: ignore
from PIL import Image  # type: ignore


@dataclass(frozen=True)
class Item:
    run_dir: Path
    rel_path: str
    phash: str
    t_sec: float
    frame_idx: int


def is_duplicate(hash_hex: str, existing: list[str], max_dist: int) -> bool:
    h = imagehash.hex_to_hash(hash_hex)
    for ex in existing:
        if h - imagehash.hex_to_hash(ex) <= max_dist:
            return True
    return False


def build_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    if not image_paths:
        raise RuntimeError("No images to build PDF.")
    images = [Image.open(p).convert("RGB") for p in image_paths]
    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, help="Directory containing chunk run subfolders")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--hash-dist", type=int, default=10, help="Max pHash distance to treat as duplicate")
    ap.add_argument("--pdf-name", default="costco_price_cards_full.pdf", help="Output PDF filename")
    args = ap.parse_args()

    runs_dir = Path(args.runs_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    items: list[Item] = []
    for run in sorted([p for p in runs_dir.iterdir() if p.is_dir()]):
        meta_path = run / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for r in meta.get("results", []):
            items.append(
                Item(
                    run_dir=run,
                    rel_path=str(r["path"]),
                    phash=str(r["phash"]),
                    t_sec=float(r["t_sec"]),
                    frame_idx=int(r["frame_idx"]),
                )
            )

    items.sort(key=lambda x: (x.t_sec, x.frame_idx))

    kept_hashes: list[str] = []
    kept: list[Item] = []
    dupes = 0
    for it in items:
        if is_duplicate(it.phash, kept_hashes, max_dist=int(args.hash_dist)):
            dupes += 1
            continue
        kept_hashes.append(it.phash)
        kept.append(it)

    image_paths = [it.run_dir / it.rel_path for it in kept]
    pdf_path = out_dir / str(args.pdf_name)
    build_pdf(image_paths, pdf_path)

    out_meta: dict[str, Any] = {
        "runs_dir": str(runs_dir),
        "total_candidates": len(items),
        "kept": len(kept),
        "duplicates_filtered": dupes,
        "hash_dist": int(args.hash_dist),
        "results": [
            {
                "run_dir": str(it.run_dir),
                "path": it.rel_path,
                "t_sec": it.t_sec,
                "frame_idx": it.frame_idx,
                "phash": it.phash,
            }
            for it in kept
        ],
    }
    (out_dir / "metadata_merged.json").write_text(
        json.dumps(out_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Saved merged PDF: {pdf_path}")
    print(f"Kept {len(kept)} unique cards (filtered {dupes} dupes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

