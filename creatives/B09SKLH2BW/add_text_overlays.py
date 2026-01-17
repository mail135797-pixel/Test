import json
import os
import requests
from PIL import Image, ImageDraw, ImageFont

ASIN = "B09SKLH2BW"
BASE_DIR = f"creatives/{ASIN}"
IMAGE_DIR = f"{BASE_DIR}/images"
JSON_PATH = f"{BASE_DIR}/03_jp_copy.json"
FONT_URL = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
FONT_PATH = "NotoSansCJKjp-Bold.otf"

def download_font():
    if not os.path.exists(FONT_PATH):
        print("Downloading font...")
        # Using a reliable URL for Noto Sans JP or similar
        # Since github raw links can change or be large, let's try a smaller font or system font if possible
        # But for reliability, I'll try to download NotoSansJP-Bold.otf from a known source or just use a fallback if fails.
        # Actually, let's use a public domain font URL.
        url = "https://github.com/googlefonts/noto-cjk/raw/refs/heads/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
        try:
            r = requests.get(url, stream=True)
            if r.status_code == 200:
                with open(FONT_PATH, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                print("Font downloaded.")
            else:
                print("Failed to download font. Using default.")
        except:
            print("Error downloading font.")

def add_text():
    # Load Copy
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check font
    download_font()
    
    try:
        font_h = ImageFont.truetype(FONT_PATH, 80)
        font_s = ImageFont.truetype(FONT_PATH, 50)
    except:
        font_h = ImageFont.load_default()
        font_s = ImageFont.load_default()
        print("Using default font (Japanese might not render).")

    for item in data['images']:
        idx = item['image']
        if idx == 1:
            continue # Skip main image
            
        img_name = f"{ASIN}_{idx:02d}.png"
        img_path = os.path.join(IMAGE_DIR, img_name)
        
        # In this environment, images might not exist if generation failed.
        # We will create dummy images for testing if they don't exist
        if not os.path.exists(img_path):
            print(f"Image {img_path} not found. Creating dummy.")
            img = Image.new('RGB', (2000, 2000), color=(240, 240, 240))
        else:
            img = Image.open(img_path).convert("RGB")
            
        draw = ImageDraw.Draw(img)
        W, H = img.size
        
        headline = item['headline']
        subcopy = item['subcopy']
        
        # Draw Box at bottom
        # Box height: 400px
        box_h = 500
        shape = [(0, H - box_h), (W, H)]
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle(shape, fill=(255, 255, 255, 200)) # White semi-transparent
        
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Text positioning
        # Center text
        # Headline
        if headline:
            bbox = draw.textbbox((0, 0), headline, font=font_h)
            w = bbox[2] - bbox[0]
            draw.text(((W - w) / 2, H - 400), headline, font=font_h, fill=(0, 0, 0))
            
        # Subcopy
        if subcopy:
            bbox = draw.textbbox((0, 0), subcopy, font=font_s)
            w = bbox[2] - bbox[0]
            draw.text(((W - w) / 2, H - 250), subcopy, font=font_s, fill=(50, 50, 50))
            
        out_path = os.path.join(IMAGE_DIR, f"{ASIN}_{idx:02d}_final.png")
        img.save(out_path)
        print(f"Saved {out_path}")

if __name__ == "__main__":
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
    add_text()
