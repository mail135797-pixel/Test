#!/usr/bin/env python3
"""
Extract Costco-style price cards from a video, de-duplicate, and build a PDF.

Heuristic approach:
- Sample frames at a fixed interval for the first N minutes
- Detect the most "price-card-like" rectangle (large, convex quad, rectangular)
- Crop with padding, reject blurry crops, de-duplicate with perceptual hash (pHash)
- Export crops + a single PDF
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2  # type: ignore
import imagehash  # type: ignore
import numpy as np  # type: ignore
from PIL import Image, ImageEnhance  # type: ignore
from tqdm import tqdm  # type: ignore


@dataclass(frozen=True)
class CropResult:
    t_sec: float
    frame_idx: int
    bbox_xyxy: tuple[int, int, int, int]  # in original frame coordinates
    phash: str
    path: str


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _laplacian_var(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _center_distance_score(cx: float, cy: float, w: int, h: int) -> float:
    # Prefer rectangles near the center (typical framing).
    dx = (cx - w / 2.0) / (w / 2.0)
    dy = (cy - h / 2.0) / (h / 2.0)
    d = math.sqrt(dx * dx + dy * dy)
    return 1.0 / (1.0 + d)


def detect_price_card_bbox(frame_bgr: np.ndarray) -> tuple[int, int, int, int] | None:
    """
    Return best bbox (x1,y1,x2,y2) in original frame coordinates, or None.
    """
    h0, w0 = frame_bgr.shape[:2]
    target_w = 960
    scale = target_w / float(w0) if w0 > target_w else 1.0
    if scale != 1.0:
        small = cv2.resize(frame_bgr, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = frame_bgr

    h, w = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    # 1) Edge-based rectangles
    edges = cv2.Canny(gray, 60, 180)
    closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours_edges, _ = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 2) "White board" rectangles (price cards are mostly white with low saturation)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)
    white_mask = cv2.inRange(hsv, (0, 0, 170), (179, 85, 255))
    white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours_white, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    contours = list(contours_edges or []) + list(contours_white or [])
    if not contours:
        return None

    img_area = float(w * h)
    best: tuple[float, tuple[int, int, int, int]] | None = None

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # In some shots the card is small; allow down to ~1% of frame area.
        if area < img_area * 0.01 or area > img_area * 0.92:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue

        x, y, ww, hh = cv2.boundingRect(approx)
        if ww <= 0 or hh <= 0:
            continue
        ar = ww / float(hh)
        if ar < 1.0 or ar > 6.5:
            continue

        rect_area = float(ww * hh)
        rectangularity = float(area) / rect_area if rect_area else 0.0
        if rectangularity < 0.70:
            continue

        cx = x + ww / 2.0
        cy = y + hh / 2.0
        center_score = _center_distance_score(cx, cy, w, h)

        # Prefer "white-ish" rectangles (cheap check in HSV)
        roi = hsv[y:y + hh, x:x + ww]
        if roi.size == 0:
            continue
        roi_s = roi[:, :, 1]
        roi_v = roi[:, :, 2]
        white_ratio = float(np.mean((roi_v > 170) & (roi_s < 85)))
        if white_ratio < 0.20:
            continue

        # Score: prefer large, rectangular, centered, and white-ish
        score = (area / img_area) * rectangularity * center_score * (0.6 + 0.8 * white_ratio)
        if best is None or score > best[0]:
            best = (score, (x, y, x + ww, y + hh))

    if best is None:
        return None

    x1, y1, x2, y2 = best[1]
    if scale != 1.0:
        inv = 1.0 / scale
        x1 = int(round(x1 * inv))
        y1 = int(round(y1 * inv))
        x2 = int(round(x2 * inv))
        y2 = int(round(y2 * inv))
    x1 = _clamp(x1, 0, w0 - 1)
    y1 = _clamp(y1, 0, h0 - 1)
    x2 = _clamp(x2, x1 + 1, w0)
    y2 = _clamp(y2, y1 + 1, h0)
    return (x1, y1, x2, y2)


def crop_and_normalize(
    frame_bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    pad_frac: float = 0.02,
) -> Image.Image:
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    pad_x = int(round((x2 - x1) * pad_frac))
    pad_y = int(round((y2 - y1) * pad_frac))
    x1p = _clamp(x1 - pad_x, 0, w - 1)
    y1p = _clamp(y1 - pad_y, 0, h - 1)
    x2p = _clamp(x2 + pad_x, x1p + 1, w)
    y2p = _clamp(y2 + pad_y, y1p + 1, h)

    crop_bgr = frame_bgr[y1p:y2p, x1p:x2p]
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(crop_rgb)

    # Normalize orientation: price cards are typically wider than tall.
    if img.width < img.height:
        img = img.rotate(90, expand=True)

    # Mild contrast boost (helps readability in PDF)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    return img


def is_blurry(img: Image.Image, threshold: float) -> bool:
    gray = np.array(img.convert("L"))
    return _laplacian_var(gray) < threshold


def looks_like_price_card(img: Image.Image) -> bool:
    """
    Additional post-crop filter to reduce false positives.
    Price cards are typically: lots of near-white background + some dark text.
    """
    arr = np.array(img.convert("RGB"))
    if arr.size == 0:
        return False
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    near_white = (r > 190) & (g > 190) & (b > 190)
    dark = (r < 80) & (g < 80) & (b < 80)
    white_ratio = float(np.mean(near_white))
    dark_ratio = float(np.mean(dark))

    # Costco JP price cards are usually inside an orange holder; require some orange
    # pixels near the crop border to reduce false positives (product close-ups, etc).
    h, w = arr.shape[:2]
    border = 0.10
    bw = max(1, int(w * border))
    bh = max(1, int(h * border))
    border_mask = np.zeros((h, w), dtype=bool)
    border_mask[:bh, :] = True
    border_mask[-bh:, :] = True
    border_mask[:, :bw] = True
    border_mask[:, -bw:] = True
    orange = (r > 130) & (g > 60) & (b < 140) & (r > g) & (g > b)
    border_orange_ratio = float(np.mean(orange & border_mask))

    # Require meaningful white background + some black text/lines + orange holder context.
    return white_ratio > 0.42 and dark_ratio > 0.004 and border_orange_ratio > 0.10


def phash_str(img: Image.Image) -> str:
    # Stabilize hash against minor perspective/lighting changes
    base = img.convert("L").resize((800, 500), Image.Resampling.LANCZOS)
    h = imagehash.phash(base, hash_size=16)
    return str(h)


def is_duplicate(hash_hex: str, existing: list[str], max_dist: int) -> bool:
    h = imagehash.hex_to_hash(hash_hex)
    for ex in existing:
        if h - imagehash.hex_to_hash(ex) <= max_dist:
            return True
    return False


def iter_sampled_frames(
    cap: cv2.VideoCapture,
    fps: float,
    start_seconds: float,
    max_seconds: float,
    sample_interval_s: float,
) -> Iterable[tuple[int, float, np.ndarray]]:
    step = max(1, int(round(fps * sample_interval_s)))
    start_frame = int(round(fps * start_seconds))
    max_frame = int(round(fps * (start_seconds + max_seconds)))

    # Seek close to the requested start.
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES) or start_frame)

    # Sequential read is fastest/most reliable.
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx > max_frame:
            break
        if frame_idx >= start_frame and (frame_idx - start_frame) % step == 0:
            yield frame_idx, frame_idx / fps, frame
        frame_idx += 1


def build_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    if not image_paths:
        raise RuntimeError("No images to build PDF.")
    images = []
    for p in image_paths:
        img = Image.open(p).convert("RGB")
        images.append(img)
    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Path to input video file")
    ap.add_argument("--out-dir", required=True, help="Output directory (will be created)")
    ap.add_argument("--minutes", type=float, default=5.0, help="How many minutes from start to process")
    ap.add_argument("--start-seconds", type=float, default=0.0, help="Start time (seconds from beginning)")
    ap.add_argument("--sample-interval", type=float, default=0.5, help="Seconds between sampled frames")
    ap.add_argument("--blur-threshold", type=float, default=55.0, help="Laplacian variance threshold")
    ap.add_argument("--hash-dist", type=int, default=6, help="Max pHash distance to treat as duplicate")
    ap.add_argument("--min-crops", type=int, default=1, help="Fail if fewer crops are extracted")
    ap.add_argument("--pdf-name", default="costco_price_cards.pdf", help="Output PDF filename")
    args = ap.parse_args()

    video_path = Path(args.video)
    out_dir = Path(args.out_dir)
    crops_dir = out_dir / "crops"
    out_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    start_seconds = max(0.0, float(args.start_seconds))
    max_seconds = max(0.0, float(args.minutes) * 60.0)

    kept_hashes: list[str] = []
    results: list[CropResult] = []
    dupes = 0
    no_bbox = 0
    non_card = 0
    blurry = 0

    pbar_total = int(max_seconds / max(0.001, float(args.sample_interval))) + 1
    for frame_idx, t_sec, frame in tqdm(
        iter_sampled_frames(
            cap,
            fps=fps,
            start_seconds=start_seconds,
            max_seconds=max_seconds,
            sample_interval_s=float(args.sample_interval),
        ),
        total=pbar_total,
        desc="Scanning",
    ):
        bbox = detect_price_card_bbox(frame)
        if bbox is None:
            no_bbox += 1
            continue

        img = crop_and_normalize(frame, bbox)
        if is_blurry(img, threshold=float(args.blur_threshold)):
            blurry += 1
            continue
        if not looks_like_price_card(img):
            non_card += 1
            continue

        hstr = phash_str(img)
        if is_duplicate(hstr, kept_hashes, max_dist=int(args.hash_dist)):
            dupes += 1
            continue

        kept_hashes.append(hstr)
        name = f"card_{len(results)+1:04d}_t{t_sec:07.2f}s_f{frame_idx}.png"
        out_path = crops_dir / name
        img.save(out_path, format="PNG", optimize=True)
        results.append(
            CropResult(
                t_sec=float(t_sec),
                frame_idx=int(frame_idx),
                bbox_xyxy=tuple(map(int, bbox)),  # type: ignore[arg-type]
                phash=hstr,
                path=str(out_path.relative_to(out_dir)),
            )
        )

    cap.release()

    meta: dict[str, Any] = {
        "video": str(video_path),
        "start_seconds": start_seconds,
        "minutes_processed": float(args.minutes),
        "sample_interval_s": float(args.sample_interval),
        "fps": float(fps),
        "kept": len(results),
        "duplicates_filtered": dupes,
        "no_bbox_frames": no_bbox,
        "non_card_filtered": non_card,
        "blurry_filtered": blurry,
        "hash_dist": int(args.hash_dist),
        "blur_threshold": float(args.blur_threshold),
        "results": [r.__dict__ for r in results],
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if len(results) < int(args.min_crops):
        raise SystemExit(
            f"Extracted {len(results)} crops (< {args.min_crops}). "
            f"Try lowering --blur-threshold or adjusting detection heuristics."
        )

    image_paths = [out_dir / r.path for r in results]
    pdf_path = out_dir / str(args.pdf_name)
    build_pdf(image_paths, pdf_path)

    print(f"Saved {len(results)} unique cards to: {pdf_path}")
    print(f"Crops folder: {crops_dir}")
    print(f"Metadata: {out_dir / 'metadata.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

