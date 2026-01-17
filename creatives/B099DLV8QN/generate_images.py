import json
import os
from PIL import Image, ImageDraw, ImageFont

# Config
ASIN = "B099DLV8QN"
BASE_DIR = f"creatives/{ASIN}"
IMG_DIR = os.path.join(BASE_DIR, "images")
JSON_PATH = os.path.join(BASE_DIR, "03_jp_copy.json")
FONT_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

def create_placeholder(image_data):
    img_idx = image_data['image']
    headline = image_data.get('headline', '')
    subcopy = image_data.get('subcopy', '')
    labels = image_data.get('labels', [])

    # Create canvas
    img = Image.new('RGB', (2000, 2000), color=(240, 248, 255)) # AliceBlue background
    draw = ImageDraw.Draw(img)

    try:
        font_h = ImageFont.truetype(FONT_PATH, 80)
        font_s = ImageFont.truetype(FONT_PATH, 60)
        font_l = ImageFont.truetype(FONT_PATH, 40)
        font_big = ImageFont.truetype(FONT_PATH, 200)
    except Exception as e:
        print(f"Font loading failed: {e}")
        return

    # Draw Image Number
    draw.text((100, 100), f"IMAGE {img_idx}", fill=(0, 0, 139), font=font_big)

    # Draw Text
    y = 500
    if headline:
        draw.text((100, y), f"Headline:\n{headline}", fill=(0, 0, 0), font=font_h)
        y += 250
    
    if subcopy:
        draw.text((100, y), f"Subcopy:\n{subcopy}", fill=(50, 50, 50), font=font_s)
        y += 200

    if labels:
        draw.text((100, y), "Labels:", fill=(0, 0, 0), font=font_l)
        y += 60
        for label in labels:
            draw.text((140, y), f"- {label}", fill=(0, 100, 0), font=font_l)
            y += 60
            
    # Draw Info
    draw.text((100, 1800), f"ASIN: {ASIN} - Generated Placeholder", fill=(128, 128, 128), font=font_l)

    # Save
    filename = f"{ASIN}_{img_idx:02d}.png"
    if img_idx == 1:
        filename = f"{ASIN}_{img_idx:02d}_main.png"
    
    save_path = os.path.join(IMG_DIR, filename)
    img.save(save_path)
    print(f"Saved {save_path}")

    # Save Thumbnail
    thumb_size = (800, 800)
    thumb = img.resize(thumb_size)
    thumb_filename = f"thumb_{ASIN}_{img_idx:02d}.jpg"
    if img_idx == 1:
        thumb_filename = f"thumb_{ASIN}_{img_idx:02d}_main.jpg"
        
    thumb_path = os.path.join(IMG_DIR, thumb_filename)
    thumb.save(thumb_path, "JPEG", quality=85)
    print(f"Saved thumbnail {thumb_path}")

def main():
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
        
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for img_data in data['images']:
        create_placeholder(img_data)

if __name__ == "__main__":
    main()
