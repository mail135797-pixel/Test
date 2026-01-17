import os
import io
import time
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# Load Env
load_dotenv()

# Config
ASIN = "B099DLV8QN"
BASE_DIR = f"creatives/{ASIN}"
IMG_DIR = os.path.join(BASE_DIR, "images")
REF_IMG_PATH = os.path.join(BASE_DIR, "reference_product.jpg")
PROMPT_FILE = os.path.join(BASE_DIR, "04_nano_banana_prompts.md")

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not set.")
        return

    client = genai.Client(api_key=api_key)
    
    # Load Reference Image
    if not os.path.exists(REF_IMG_PATH):
        print(f"Error: Reference image not found at {REF_IMG_PATH}")
        return
        
    try:
        ref_image = Image.open(REF_IMG_PATH)
        print(f"Loaded reference image: {REF_IMG_PATH} ({ref_image.size})")
    except Exception as e:
        print(f"Failed to load reference image: {e}")
        return

    # Image Prompts (Hardcoded for accuracy based on previous steps)
    # We will use the REFERENCE IMAGE to guide the generation (Image-to-Image / Multimodal)
    
    tasks = [
        {
            "id": 1,
            "prompt": "Create a clean, professional main product image of this skincare lotion bottle. Pure white background. Remove any shadows or reflections that look messy. Keep the bottle exactly as it looks in the reference image. High key lighting.",
        },
        {
            "id": 2,
            "prompt": "Show this lotion bottle with 3 glowing golden droplets floating around it, representing '3GF ingredients'. Soft, premium background with white and gold gradients. Keep the bottle realistic and central.",
        },
        {
            "id": 3,
            "prompt": "Close-up macro shot of the lotion texture. A rich, thick, clear/milky droplet of the liquid on a glass surface. The bottle is visible in the blurred background. Emphasize the moisturizing 'toromi' texture.",
        },
        {
            "id": 4,
            "prompt": "The lotion bottle surrounded by botanical elements (subtle herbs or flowers) and faint scientific molecular structures overlay. Clean, medical-beauty aesthetic. White and green accents.",
        },
        {
            "id": 5,
            "prompt": "Lifestyle shot: A beautiful Asian woman (30s) with radiant skin holding this lotion bottle near her face. Soft morning light. She looks happy and confident. Focus on her glowing skin.",
        },
        {
            "id": 6,
            "prompt": "Minimalist diagram showing 'How to Use'. Step 1: Water splash (wash). Step 2: This lotion bottle. Step 3: A cream jar. Connected by arrows. Clean white background.",
        },
        {
            "id": 7,
            "prompt": "A premium cosmetic store display shelf with this lotion bottle prominently featured. 'cos:mura' branding visible on the shelf. Bright, clean, modern interior.",
        },
        {
            "id": 8,
            "prompt": "Epic hero shot of the lotion bottle on a golden podium with light rays radiating from behind. 'TIMELESS EVOLUTION' theme. Luxurious atmosphere.",
        }
    ]

    print(f"Starting generation for {len(tasks)} images using Reference Image...")

    for task in tasks:
        i = task['id']
        prompt_text = task['prompt']
        print(f"\nGenerating Image {i}...")

        try:
            # Pass both the text prompt AND the reference image
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=[prompt_text, ref_image], # Multimodal input
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                    )
                )
            )
            
            # Save
            saved = False
            for part in response.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    filename = f"{ASIN}_0{i}_main.png" if i == 1 else f"{ASIN}_0{i}.png"
                    save_path = os.path.join(IMG_DIR, filename)
                    image.save(save_path)
                    print(f"Saved: {save_path}")
                    
                    # Thumbnail
                    thumb_size = (800, 800)
                    thumb = image.resize(thumb_size)
                    thumb_filename = f"thumb_{ASIN}_0{i}_main.jpg" if i == 1 else f"thumb_{ASIN}_0{i}.jpg"
                    thumb_path = os.path.join(IMG_DIR, thumb_filename)
                    thumb.save(thumb_path, "JPEG", quality=85)
                    print(f"Saved thumbnail")
                    saved = True
                    break
            
            if not saved:
                print(f"Warning: No image found in response for Image {i}")

        except Exception as e:
            print(f"Failed to generate Image {i}: {e}")
            if "429" in str(e):
                 print("Rate limit. Sleeping 60s...")
                 time.sleep(60)

        time.sleep(10) # Safety buffer

if __name__ == "__main__":
    main()
