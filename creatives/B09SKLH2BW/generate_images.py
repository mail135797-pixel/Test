import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
import io
import sys

# Load Env
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY or API_KEY.startswith("<"):
    print("Error: GEMINI_API_KEY is missing or invalid in .env")
    print("Please replace the placeholder in .env with your actual API key.")
    # For now, we exit. User needs to fix this manually.
    sys.exit(1)

# Config
# We are running from creatives/B09SKLH2BW/
BASE_DIR = "."
REF_IMG_PATH = f"{BASE_DIR}/reference/product_cutout.png"
OUTPUT_DIR = f"{BASE_DIR}/images"

PROMPTS = {
    1: "Nano Banana Pro: A professional product shot of a peeling gel bottle on a pure white background. The lighting is soft and studio-quality. The product is centered. High resolution, 4k.",
    2: "Nano Banana Pro: A peeling gel bottle placed on a surface with a soft, bright, fresh skin-toned gradient background. Subtle water ripples or abstract clean texture in the background. Bright lighting, clean aesthetic.",
    3: "Nano Banana Pro: A peeling gel bottle with three abstract golden droplets floating near it, representing 3GF ingredients. The background is a scientific yet elegant gradient of soft gold and white.",
    4: "Nano Banana Pro: A peeling gel bottle next to a smear of clear, transparent gel texture. The gel looks hydrating and smooth. Soft focus background.",
    5: "Nano Banana Pro: A peeling gel bottle sitting on a clean, modern white bathroom sink counter. Morning light, bright and airy atmosphere. Defocused mirror and faucet in the background.",
    6: "Nano Banana Pro: A peeling gel bottle standing on a simple white table. Minimalist composition. Soft natural lighting from the side.",
    7: "Nano Banana Pro: A peeling gel bottle with a soft white feather resting nearby. The background is a soft, blurry pastel color to imply gentleness.",
    8: "Nano Banana Pro: A peeling gel bottle on a clean white retail shelf or podium. Professional lighting."
}

def generate_image(prompt, idx):
    print(f"Generating Image {idx}...")
    
    try:
        client = genai.Client(api_key=API_KEY)
        
        # Try gemini-3-pro-image-preview
        try:
            response = client.models.generate_images(
                model='gemini-3-pro-image-preview',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1"
                )
            )
            if response.generated_images:
                return Image.open(io.BytesIO(response.generated_images[0].image.image_bytes))
        except Exception as e:
            # Fallback to nano-banana-pro-preview
            try:
                response = client.models.generate_images(
                    model='nano-banana-pro-preview',
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="1:1"
                    )
                )
                if response.generated_images:
                    return Image.open(io.BytesIO(response.generated_images[0].image.image_bytes))
            except Exception as e2:
                print("Trying imagen-3.0-generate-001...")
                response = client.models.generate_images(
                    model='imagen-3.0-generate-001',
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="1:1"
                    )
                )
                if response.generated_images:
                    return Image.open(io.BytesIO(response.generated_images[0].image.image_bytes))

        return None

    except Exception as e:
        print(f"Generation error: {e}")
        return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    from PIL import ImageDraw

    for idx, prompt in PROMPTS.items():
        target_path = f"{OUTPUT_DIR}/B09SKLH2BW_{idx:02d}.png"
        
        # Skip if already exists and good (Image 1)
        if idx == 1 and os.path.exists(target_path):
            continue

        # Try generation
        img_result = generate_image(prompt, idx)
        
        if img_result:
            img_result.save(target_path)
            print(f"Saved {target_path}")
        else:
            print(f"Failed to generate {target_path}. Using placeholder.")
            if not os.path.exists(target_path):
                img = Image.new('RGB', (2000, 2000), color=(200, 200, 200))
                d = ImageDraw.Draw(img)
                d.text((100,100), f"Image {idx}\n{prompt[:50]}...", fill=(0,0,0))
                img.save(target_path)

if __name__ == "__main__":
    main()
