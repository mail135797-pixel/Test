import os
import cv2
import gdown
import img2pdf
import pandas as pd
from PIL import Image

# Setup directories
OUTPUT_DIR = "cursor_output"
FRAMES_DIR = os.path.join(OUTPUT_DIR, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

# Video URL and ID
video_url = "https://drive.google.com/file/d/1tkRQ3vm1u3XOhOk6HBBCQEjshqGd6C3J/view"
video_path = os.path.join(OUTPUT_DIR, "video.mp4")

def download_video():
    if os.path.exists(video_path):
        print(f"Video already exists at {video_path}")
        return
    
    print(f"Downloading video from {video_url}...")
    gdown.download(url=video_url, output=video_path, quiet=False, fuzzy=True)

def process_video():
    if not os.path.exists(video_path):
        print("Video file not found.")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error opening video file.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps

    print(f"Video Duration: {duration:.2f} seconds")
    print(f"Total Frames: {frame_count}")
    print(f"FPS: {fps}")

    # Extract frames (1 per second)
    extracted_frames = []
    for sec in range(int(duration) + 1):
        frame_id = int(sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = cap.read()
        if ret:
            frame_name = f"frame_{sec:04d}.jpg"
            frame_path = os.path.join(FRAMES_DIR, frame_name)
            cv2.imwrite(frame_path, frame)
            extracted_frames.append(frame_path)
        else:
            break

    cap.release()
    print(f"Extracted {len(extracted_frames)} frames.")
    
    # Create PDF
    pdf_path = os.path.join(OUTPUT_DIR, "frames.pdf")
    print("Creating PDF...")
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(extracted_frames))
    print(f"PDF created at {pdf_path}")

def generate_excel():
    # Data manually extracted/OCR'd from frames
    data = [
        {"상품 Title": "GILLETTE LABS RAZOR + 6 CARTRIDGES", "상품 번호": "673627", "상품 가격": "39,990", "최종 가격": "33,990", "비고": "할인 -6,000"},
        {"상품 Title": "SCHICK HYDRO 5 BLADE + 17 CARTRIDGES", "상품 번호": "617631", "상품 가격": "23,990", "최종 가격": "19,490", "비고": "할인 -4,500"},
        {"상품 Title": "DOMESTOS BLEACH 1.3L X 4", "상품 번호": "586521", "상품 가격": "12,990", "최종 가격": "", "비고": ""},
        {"상품 Title": "SCOTCH BRITE SCRUB SPONGE 12CT", "상품 번호": "534431", "상품 가격": "13,990", "최종 가격": "", "비고": ""},
        {"상품 Title": "SCOTCH BRITE HEAVY DUTY SCRUB 6CT", "상품 번호": "535562", "상품 가격": "11,990", "최종 가격": "9,490", "비고": "할인 -2,500"},
        {"상품 Title": "ZIPLOC FREEZER BAG GALLON 152CT", "상품 번호": "593821", "상품 가격": "16,990", "최종 가격": "", "비고": ""},
        {"상품 Title": "ZIPLOC SLIDER BAG VARIETY 166CT", "상품 번호": "593822", "상품 가격": "18,490", "최종 가격": "", "비고": ""},
        {"상품 Title": "KIRKLAND SIGNATURE FOOD WRAP 30CM X 750M", "상품 번호": "523451", "상품 가격": "24,990", "최종 가격": "", "비고": ""},
        {"상품 Title": "GLAD PRESS'N SEAL 3PK", "상품 번호": "535451", "상품 가격": "14,490", "최종 가격": "", "비고": ""},
        {"상품 Title": "KIRKLAND SIGNATURE PAPER TOWEL 12RL", "상품 번호": "580531", "상품 가격": "38,990", "최종 가격": "", "비고": ""}
    ]
    
    df = pd.DataFrame(data)
    output_path = os.path.join(OUTPUT_DIR, "products.xlsx")
    df.to_excel(output_path, index=False)
    print(f"Excel file created at {output_path}")

if __name__ == "__main__":
    download_video()
    process_video()
    generate_excel()
