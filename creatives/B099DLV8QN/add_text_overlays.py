import json
import os
from PIL import Image, ImageDraw, ImageFont

# Config
ASIN = "B099DLV8QN"
BASE_DIR = f"creatives/{ASIN}"
IMG_DIR = os.path.join(BASE_DIR, "images")
JSON_PATH = os.path.join(BASE_DIR, "03_jp_copy.json")
# Fallback font that supports CJK
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc" 

def add_text_to_image(img_path, copy_data):
    try:
        img = Image.open(img_path).convert("RGBA")
    except Exception as e:
        print(f"Failed to open {img_path}: {e}")
        return

    width, height = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    headline = copy_data.get("headline", "")
    subcopy = copy_data.get("subcopy", "")
    labels = copy_data.get("labels", [])

    # Skip if no text (e.g. Main Image)
    if not headline and not subcopy:
        print(f"Skipping text for {img_path} (No text defined)")
        return

    try:
        font_h = ImageFont.truetype(FONT_PATH, 100) # Headline
        font_s = ImageFont.truetype(FONT_PATH, 60)  # Subcopy
        font_l = ImageFont.truetype(FONT_PATH, 40)  # Labels
    except:
        # Fallback if specific font not found (though wqy is standard in this env)
        font_h = ImageFont.load_default()
        font_s = ImageFont.load_default()
        font_l = ImageFont.load_default()

    # Define Text Box Area (Bottom 30% of image)
    # Style: Premium gradient fade or semi-transparent white box
    box_height = int(height * 0.35)
    box_top = height - box_height
    
    # Draw semi-transparent background for text (White with 85% opacity)
    draw.rectangle([(0, box_top), (width, height)], fill=(255, 255, 255, 220))

    # Text Color: Dark Grey / Black
    text_color = (30, 30, 30, 255)
    accent_color = (184, 134, 11, 255) # Dark Goldenrod for subcopy/accent

    current_y = box_top + 80

    # Draw Headline
    if headline:
        # Centered text
        # getbbox returns (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), headline, font=font_h)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) / 2
        draw.text((x, current_y), headline, font=font_h, fill=text_color)
        current_y += 140

    # Draw Subcopy
    if subcopy:
        bbox = draw.textbbox((0, 0), subcopy, font=font_s)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) / 2
        draw.text((x, current_y), subcopy, font=font_s, fill=accent_color)
        current_y += 120

    # Draw Labels (Features) - horizontally if possible
    if labels:
        label_text = "  |  ".join(labels)
        bbox = draw.textbbox((0, 0), label_text, font=font_l)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) / 2
        draw.text((x, current_y), label_text, font=font_l, fill=(80, 80, 80, 255))

    # Composite
    out = Image.alpha_composite(img, overlay)
    
    # Save as RGB (remove alpha)
    out = out.convert("RGB")
    out.save(img_path)
    print(f"Added text to: {img_path}")

    # Update thumbnail
    thumb_path = img_path.replace(f"{ASIN}_", f"thumb_{ASIN}_").replace(".png", ".jpg")
    thumb = out.resize((800, 800))
    thumb.save(thumb_path, "JPEG", quality=85)


def main():
    if not os.path.exists(JSON_PATH):
        print("JSON copy file not found.")
        return
    
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data['images']:
        idx = item['image']
        # File naming convention check
        filename = f"{ASIN}_0{idx}_main.png" if idx == 1 else f"{ASIN}_0{idx}.png"
        file_path = os.path.join(IMG_DIR, filename)
        
        if os.path.exists(file_path):
            add_text_to_image(file_path, item)
        else:
            print(f"Image file not found: {file_path}")

if __name__ == "__main__":
    main()
