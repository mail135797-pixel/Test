import os
import re
import time
from google import genai
from google.genai import types
from PIL import Image
import io

# Config
ASIN = "B099DLV8QN"
BASE_DIR = f"creatives/{ASIN}"
IMG_DIR = os.path.join(BASE_DIR, "images")
PROMPT_FILE = os.path.join(BASE_DIR, "04_nano_banana_prompts.md")

def parse_prompts(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract Common Settings
    common_match = re.search(r"## Common Settings\n(.*?)\n## Image", content, re.DOTALL)
    common_settings = common_match.group(1).strip() if common_match else ""
    # Clean up markdown
    common_settings = common_settings.replace('- **Style**:', 'Style:').replace('- **Negative Prompt**:', 'Negative Prompt:').replace('- **Dimensions**:', 'Dimensions:')

    prompts = {}
    
    # Split by images
    # Regex to find "## Image X:" headers
    sections = re.split(r"## Image (\d+):", content)
    
    # sections[0] is preamble. Then comes (index, content) pairs.
    for i in range(1, len(sections), 2):
        img_idx = int(sections[i])
        section_content = sections[i+1]
        
        # Extract Prompt block (lines starting with > after **Prompt**:)
        prompt_match = re.search(r"\*\*Prompt\*\*:\s*((?:> .*\n?)+)", section_content)
        if prompt_match:
            raw_prompt = prompt_match.group(1)
            # Remove > and strip
            clean_prompt = "\n".join([line.strip().lstrip('> ').strip() for line in raw_prompt.splitlines() if line.strip()])
            
            # Combine with common settings
            full_prompt = f"Settings:\n{common_settings}\n\nImage Request:\n{clean_prompt}"
            prompts[img_idx] = full_prompt
            
    return prompts

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    client = genai.Client(api_key=api_key)
    
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)

    prompts = parse_prompts(PROMPT_FILE)
    
    print(f"Found {len(prompts)} prompts. Starting generation...")

    for i in range(1, 9):
        if i not in prompts:
            print(f"Skipping Image {i} (No prompt found)")
            continue
            
        prompt = prompts[i]
        print(f"\nGenerating Image {i}...")
        print(f"Prompt preview: {prompt.splitlines()[-1][:50]}...")

        try:
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                        # Not supporting 'image_size' param in all versions yet, relying on model default or explicit prompting if needed.
                        # However, user example used it. Let's try to match user example exactly if possible.
                        # Note: SDK types might vary. If 'image_size' is not a valid kwarg for ImageConfig in the installed version, 
                        # we might need to remove it. But let's trust the user's snippet for "gemini-3-pro-image-preview".
                    )
                )
            )
            
            # Save Image
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
                    print(f"Saved thumbnail: {thumb_path}")
                    
                    saved = True
                    break
            
            if not saved:
                print(f"Warning: No image found in response for Image {i}")
                
        except Exception as e:
            print(f"Failed to generate Image {i}: {e}")
        
        # Avoid rate limits
        time.sleep(2)

if __name__ == "__main__":
    main()
