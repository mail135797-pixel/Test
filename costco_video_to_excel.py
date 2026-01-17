#!/usr/bin/env python3
import argparse
import datetime as dt
import logging
import os
import re
import sys
from pathlib import Path

import requests

try:
    import cv2
    _cv2_exc = None
except Exception as exc:  # pragma: no cover - import guard
    cv2 = None
    _cv2_exc = exc

try:
    import img2pdf
    _img2pdf_exc = None
except Exception as exc:  # pragma: no cover - import guard
    img2pdf = None
    _img2pdf_exc = exc

try:
    import pytesseract
    _pytesseract_exc = None
except Exception as exc:  # pragma: no cover - import guard
    pytesseract = None
    _pytesseract_exc = exc

try:
    from openpyxl import Workbook
    _openpyxl_exc = None
except Exception as exc:  # pragma: no cover - import guard
    Workbook = None
    _openpyxl_exc = exc

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    _google_exc = None
except Exception as exc:  # pragma: no cover - import guard
    Credentials = None
    build = None
    MediaFileUpload = None
    _google_exc = exc

try:
    from PIL import Image
    _pil_exc = None
except Exception as exc:  # pragma: no cover - import guard
    Image = None
    _pil_exc = exc


LOGGER = logging.getLogger("costco")


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    LOGGER.handlers = [file_handler, stream_handler]


def ensure_dependency_available(dep, err, name: str) -> None:
    if dep is None:
        raise RuntimeError(
            f"Missing dependency: {name}. Install required packages. Detail: {err}"
        )


def parse_drive_file_id(url: str) -> str:
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise ValueError("Unable to parse Google Drive file id.")


def download_drive_file(url: str, output_path: Path) -> None:
    file_id = parse_drive_file_id(url)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        LOGGER.info("Video already exists: %s", output_path)
        return

    session = requests.Session()
    base_url = "https://docs.google.com/uc?export=download"
    response = session.get(base_url, params={"id": file_id}, stream=True, timeout=60)
    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
            break

    if token:
        response = session.get(
            base_url, params={"id": file_id, "confirm": token}, stream=True, timeout=60
        )

    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    LOGGER.info("Downloaded video to %s", output_path)


def get_video_duration(video_path: Path) -> tuple[float, float, int]:
    ensure_dependency_available(cv2, _cv2_exc, "opencv-python")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps else 0.0
    cap.release()
    return duration, fps, frame_count


def extract_frames(video_path: Path, output_dir: Path, interval_sec: int = 1) -> list[Path]:
    ensure_dependency_available(cv2, _cv2_exc, "opencv-python")
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    duration, fps, _ = get_video_duration(video_path)
    total_seconds = int(duration)

    frame_paths: list[Path] = []
    for sec in range(0, total_seconds + 1, interval_sec):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        success, frame = cap.read()
        if not success:
            LOGGER.warning("Failed to read frame at %ss", sec)
            continue
        frame_name = f"frame_{sec + 1:03d}.jpg"
        frame_path = output_dir / frame_name
        cv2.imwrite(str(frame_path), frame)
        frame_paths.append(frame_path)

    cap.release()
    LOGGER.info("Extracted %s frames to %s", len(frame_paths), output_dir)
    return frame_paths


def images_to_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    ensure_dependency_available(img2pdf, _img2pdf_exc, "img2pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    if not image_paths:
        raise RuntimeError("No images found for PDF creation.")

    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert([str(p) for p in sorted(image_paths)]))
    LOGGER.info("PDF created at %s", pdf_path)


def preprocess_for_ocr(image_path: Path):
    ensure_dependency_available(Image, _pil_exc, "Pillow")
    image = Image.open(image_path)
    image = image.convert("L")
    scale = 2
    image = image.resize((image.width * scale, image.height * scale))
    image = image.point(lambda x: 0 if x < 160 else 255, mode="1")
    return image


def ocr_image(image_path: Path, lang: str) -> str:
    ensure_dependency_available(pytesseract, _pytesseract_exc, "pytesseract")
    image = preprocess_for_ocr(image_path)
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    text = pytesseract.image_to_string(image, lang=lang)
    return text


def parse_price_card(text: str) -> dict | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    joined = " ".join(lines)
    item_match = re.search(r"\b\d{6,8}\b", joined)
    item_no = item_match.group(0) if item_match else ""

    price_candidates = re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b", joined)
    price = price_candidates[-1] if price_candidates else ""

    sale_price = ""
    sale_match = re.search(r"(행사가|할인가|SALE)\s*([0-9,]+)", joined, re.IGNORECASE)
    if sale_match:
        sale_price = sale_match.group(2)

    note_match = re.search(
        r"\d{1,2}[/-]\d{1,2}\s*[-~]\s*\d{1,2}[/-]\d{1,2}", joined
    )
    note = note_match.group(0) if note_match else ""

    title = ""
    for line in lines:
        if not re.search(r"\d", line):
            title = line
            break
    if not title:
        title = lines[0]

    return {
        "title": title,
        "item_no": item_no,
        "price": price,
        "sale_price": sale_price,
        "note": note,
    }


def extract_price_cards(frame_paths: list[Path], lang: str) -> list[dict]:
    seen = set()
    results: list[dict] = []
    for frame_path in frame_paths:
        try:
            text = ocr_image(frame_path, lang=lang)
            parsed = parse_price_card(text)
            if not parsed:
                continue
            key = (parsed["title"], parsed["item_no"], parsed["price"], parsed["sale_price"])
            if key in seen:
                continue
            seen.add(key)
            if frame_path.name:
                if parsed["note"]:
                    parsed["note"] = f"{parsed['note']} | {frame_path.name}"
                else:
                    parsed["note"] = frame_path.name
            results.append(parsed)
        except Exception as exc:
            LOGGER.warning("OCR failed for %s: %s", frame_path, exc)
    LOGGER.info("Extracted %s unique price cards", len(results))
    return results


def write_excel(data: list[dict], output_path: Path) -> None:
    ensure_dependency_available(Workbook, _openpyxl_exc, "openpyxl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "prices"
    ws.append(["상품 Title", "상품 번호", "상품 가격", "최종 가격", "비고"])

    for row in data:
        ws.append(
            [
                row.get("title", ""),
                row.get("item_no", ""),
                row.get("price", ""),
                row.get("sale_price", ""),
                row.get("note", ""),
            ]
        )

    wb.save(output_path)
    LOGGER.info("Excel saved to %s", output_path)


def upload_to_drive(file_path: Path, folder_id: str, credentials_path: Path) -> str:
    ensure_dependency_available(Credentials, _google_exc, "google-auth")
    ensure_dependency_available(build, _google_exc, "google-api-python-client")
    ensure_dependency_available(MediaFileUpload, _google_exc, "google-api-python-client")

    if not credentials_path.exists():
        raise FileNotFoundError(f"Service account key not found: {credentials_path}")

    creds = Credentials.from_service_account_file(
        str(credentials_path), scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    service = build("drive", "v3", credentials=creds)

    file_metadata = {"name": file_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(file_path), resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")
    LOGGER.info("Uploaded %s to Drive (id=%s)", file_path, file_id)
    return file_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Costco price card OCR pipeline.")
    parser.add_argument(
        "--video-url",
        required=True,
        help="Google Drive video URL",
    )
    parser.add_argument("--work-dir", default="outputs", help="Working directory")
    parser.add_argument(
        "--service-account",
        default="gen-lang-client-0487281252-b9d796c96834.json",
        help="Service account JSON path",
    )
    parser.add_argument(
        "--drive-folder-id",
        default="1_LafaOLXNuTjJPdgyCCnuw_J4UgZYzjD",
        help="Target Drive folder id",
    )
    parser.add_argument(
        "--ocr-lang",
        default="kor+jpn+eng",
        help="Tesseract language codes",
    )
    parser.add_argument("--interval-sec", type=int, default=1, help="Frame interval")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    log_path = work_dir / "logs" / "pipeline.log"
    setup_logging(log_path)

    date_str = dt.date.today().strftime("%Y%m%d")
    video_path = work_dir / f"costco_video_{date_str}.mp4"
    frames_dir = work_dir / "frames"
    pdf_path = work_dir / f"costco_frames_{date_str}.pdf"
    excel_path = work_dir / f"costco_prices_{date_str}.xlsx"

    try:
        LOGGER.info("Downloading video...")
        download_drive_file(args.video_url, video_path)

        duration, fps, frame_count = get_video_duration(video_path)
        minutes = duration / 60.0 if duration else 0.0
        LOGGER.info(
            "Video duration: %.2f minutes (%.2f seconds, fps=%.2f, frames=%s)",
            minutes,
            duration,
            fps,
            frame_count,
        )
        print(f"Video duration: {minutes:.2f} minutes")

        LOGGER.info("Extracting frames...")
        frame_paths = extract_frames(video_path, frames_dir, interval_sec=args.interval_sec)

        LOGGER.info("Creating PDF...")
        images_to_pdf(frame_paths, pdf_path)

        LOGGER.info("Running OCR...")
        extracted = extract_price_cards(frame_paths, lang=args.ocr_lang)

        LOGGER.info("Writing Excel...")
        write_excel(extracted, excel_path)

        LOGGER.info("Uploading to Google Drive...")
        upload_to_drive(pdf_path, args.drive_folder_id, Path(args.service_account))
        upload_to_drive(excel_path, args.drive_folder_id, Path(args.service_account))

        LOGGER.info("Pipeline complete.")
        return 0
    except Exception as exc:
        LOGGER.exception("Pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
