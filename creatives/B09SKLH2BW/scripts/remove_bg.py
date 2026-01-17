from PIL import Image
import numpy as np

def remove_white_bg(input_path, output_path, tolerance=10):
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()
    
    newData = []
    for item in datas:
        # Check if pixel is close to white
        if item[0] > 255 - tolerance and item[1] > 255 - tolerance and item[2] > 255 - tolerance:
            newData.append((255, 255, 255, 0)) # Transparent
        else:
            newData.append(item)
            
    img.putdata(newData)
    
    # Trim empty space
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    img.save(output_path, "PNG")
    print(f"Saved to {output_path}")

input_p = "creatives/B09SKLH2BW/reference/reference_main.jpg"
output_p = "creatives/B09SKLH2BW/reference/product_cutout.png"

remove_white_bg(input_p, output_p)
