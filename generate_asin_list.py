import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from io import BytesIO
from PIL import Image
import xlsxwriter

# ASIN List
asins = [
    "B071XYNR2Y", "B0CSDVJLXZ", "B0978HFG81", "B0DG5DVQMK",
    "B0DVGX6F7Q", "B0CZDBSLR3", "B0D2D1S6JM", "B0D4LNY4CW",
    "B0DQ15C2XW", "B0D4VD3HG3", "B0D6R3LYBG", "B01N7GB0KY"
]

def get_asin_info(asin):
    url = f"https://www.amazon.co.jp/dp/{asin}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    
    data = {
        "ASIN": asin,
        "Link": f"https://www.amazon.co.jp/dp/{asin}",
        "Title": "",
        "Bullets": "",
        "ImageURL": "",
        "ImageBytes": None
    }
    
    try:
        time.sleep(random.uniform(2, 5)) # Respectful delay
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Title
            title_elem = soup.select_one("#productTitle")
            if title_elem:
                data["Title"] = title_elem.get_text(strip=True)
            
            # Bullets
            bullets = []
            bullet_elems = soup.select("#feature-bullets ul li span.a-list-item")
            for b in bullet_elems:
                text = b.get_text(strip=True)
                if text:
                    bullets.append(text)
            data["Bullets"] = "\n".join(bullets)
            
            # Image
            img_elem = soup.select_one("#landingImage")
            if img_elem:
                # Try getting hi-res or src
                img_url = img_elem.get('data-old-hires') or img_elem.get('src')
                if img_url:
                    data["ImageURL"] = img_url
                    # Download image
                    try:
                        img_resp = requests.get(img_url, headers=headers, timeout=10)
                        if img_resp.status_code == 200:
                            data["ImageBytes"] = BytesIO(img_resp.content)
                    except Exception as e:
                        print(f"Failed to download image for {asin}: {e}")
            
    except Exception as e:
        print(f"Error scraping {asin}: {e}")
        
    return data

def create_combined_image(image_bytes_list):
    if not image_bytes_list:
        return None
    
    images = []
    for ib in image_bytes_list:
        if ib:
            try:
                img = Image.open(ib)
                images.append(img)
            except:
                pass
    
    if not images:
        return None
        
    # Create a composite image (horizontal)
    # Resize images to same height
    min_height = min(img.height for img in images)
    resized_images = []
    for img in images:
        aspect_ratio = img.width / img.height
        new_width = int(min_height * aspect_ratio)
        resized_images.append(img.resize((new_width, min_height)))
        
    total_width = sum(img.width for img in resized_images)
    combined_img = Image.new('RGB', (total_width, min_height), (255, 255, 255))
    
    x_offset = 0
    for img in resized_images:
        combined_img.paste(img, (x_offset, 0))
        x_offset += img.width
        
    output = BytesIO()
    combined_img.save(output, format='JPEG')
    output.seek(0)
    return output

def analyze_combinations(all_data):
    # This is a heuristic based on simple keyword matching since we don't have a semantic engine
    # In a real scenario, we'd use embeddings. Here we look for overlapping words in titles.
    
    combinations = []
    
    # Pre-process titles
    processed_items = []
    for item in all_data:
        # Simple tokenization
        tokens = set(item['Title'].replace('｜', ' ').replace('【', ' ').replace('】', ' ').split())
        processed_items.append({'asin': item['ASIN'], 'tokens': tokens, 'data': item})

    # Find pairs
    matches = {} # asin -> list of matched asins
    
    for i in range(len(processed_items)):
        item1 = processed_items[i]
        asin1 = item1['asin']
        matches[asin1] = []
        
        for j in range(len(processed_items)):
            if i == j: continue
            item2 = processed_items[j]
            
            # Simple score: intersection of tokens
            score = len(item1['tokens'].intersection(item2['tokens']))
            if score > 0:
                matches[asin1].append((item2['asin'], score))
        
        # Sort by score
        matches[asin1].sort(key=lambda x: x[1], reverse=True)

    # Format result for each ASIN
    results = {} # asin -> {comb_text, comb_bullets, comb_reason, comb_images}
    
    for item in all_data:
        asin = item['ASIN']
        top_matches = matches.get(asin, [])[:2] # Take top 2
        
        comb_text_lines = []
        comb_bullet_lines = []
        comb_reason_lines = []
        comb_images_list = [] # List of lists of image bytes
        
        if top_matches:
            for idx, (match_asin, score) in enumerate(top_matches):
                match_data = next(d for d in all_data if d['ASIN'] == match_asin)
                
                # Format: ・ 조합 1 : asin,asin
                comb_text_lines.append(f"・ 조합 {idx+1} : {asin},{match_asin}")
                
                # Format: ・ 조합 1의 箇条書き : ...
                # Combine first bullet of each
                b1 = item['Bullets'].split('\n')[0] if item['Bullets'] else ""
                b2 = match_data['Bullets'].split('\n')[0] if match_data['Bullets'] else ""
                comb_bullet_lines.append(f"・ 조합 {idx+1}의 箇条書き : {b1} + {b2}")
                
                # Reason
                reason = f"Keywords overlap score: {score}. Titles share similar terms."
                comb_reason_lines.append(f"・ 조합 {idx+1}의 이유 : {reason}")
                
                # Images for combination
                comb_images_list.append([item['ImageBytes'], match_data['ImageBytes']])
        else:
            # Fallback if no text matches (empty titles?), pick random different one
            other = next((d for d in all_data if d['ASIN'] != asin), None)
            if other:
                match_asin = other['ASIN']
                comb_text_lines.append(f"・ 조합 1 : {asin},{match_asin}")
                comb_bullet_lines.append(f"・ 조합 1의 箇条書き : Combined utility.")
                comb_reason_lines.append(f"・ 조합 1의 이유 : General pairing.")
                comb_images_list.append([item['ImageBytes'], other['ImageBytes']])

        # Create one merged image for the "Combination Image" column
        # The prompt asks for "Combination Image" in column I. 
        # "Make an image containing the main screens of each combination".
        # If there are multiple combinations, we probably need to stack them or just show the first one?
        # "각 조합의 메인 화면을 한 장의 메인 화면에 담기는 형태" -> "form that contains main screens of EACH combination in ONE main screen"
        # It sounds like: Image for Combination 1, Image for Combination 2... all in one cell? Or one image per combination?
        # The format example: "・ 조합 1의 메인 화면 : ・ 조합 2의 메인 화면 :" suggests text description?
        # But step 7 says "Create an image... and attach it".
        # I will create ONE image that vertically stacks the combined images of the combinations.
        
        final_comb_image_bytes = None
        if comb_images_list:
            # Create sub-images
            sub_images = []
            for img_pair in comb_images_list:
                comp = create_combined_image(img_pair)
                if comp:
                    sub_images.append(Image.open(comp))
            
            if sub_images:
                # Stack sub-images vertically
                max_width = max(img.width for img in sub_images)
                total_height = sum(img.height for img in sub_images) + (10 * (len(sub_images)-1)) # padding
                
                final_canvas = Image.new('RGB', (max_width, total_height), (255, 255, 255))
                y_off = 0
                for img in sub_images:
                    # Center align
                    x_off = (max_width - img.width) // 2
                    final_canvas.paste(img, (x_off, y_off))
                    y_off += img.height + 10
                
                out = BytesIO()
                final_canvas.save(out, format='JPEG')
                out.seek(0)
                final_comb_image_bytes = out

        results[asin] = {
            "Combinations": "\n".join(comb_text_lines),
            "CombBullets": "\n".join(comb_bullet_lines),
            "CombReasons": "\n".join(comb_reason_lines),
            "CombImage": final_comb_image_bytes
        }
        
    return results

def main():
    print("Scraping ASINs...")
    all_data = []
    for asin in asins:
        print(f"Processing {asin}...")
        info = get_asin_info(asin)
        all_data.append(info)
        
    print("Analyzing combinations...")
    comb_results = analyze_combinations(all_data)
    
    print("Generating Excel...")
    df_rows = []
    
    # Create Excel
    wb = xlsxwriter.Workbook('ASIN_List.xlsx')
    ws = wb.add_worksheet()
    
    # Headers
    headers = ["ASIN", "Link", "Title", "箇条書き", "조합", "조합의 箇条書き", "조합의 이유", "메인 화면", "조합의 메인 화면"]
    for col, h in enumerate(headers):
        ws.write(0, col, h)
        
    # Set column widths
    ws.set_column('A:A', 15)
    ws.set_column('B:B', 30)
    ws.set_column('C:C', 30)
    ws.set_column('D:D', 40)
    ws.set_column('E:G', 30)
    ws.set_column('H:I', 20)
    
    row = 1
    for data in all_data:
        asin = data['ASIN']
        comb = comb_results.get(asin, {})
        
        ws.write(row, 0, asin)
        ws.write(row, 1, data['Link'])
        ws.write(row, 2, data['Title'])
        ws.write(row, 3, data['Bullets'])
        ws.write(row, 4, comb.get('Combinations', ''))
        ws.write(row, 5, comb.get('CombBullets', ''))
        ws.write(row, 6, comb.get('CombReasons', ''))
        
        # Insert Main Image
        if data['ImageBytes']:
            ws.set_row(row, 100) # Set row height
            ws.insert_image(row, 7, f"{asin}.jpg", {'image_data': data['ImageBytes'], 'x_scale': 0.5, 'y_scale': 0.5, 'object_position': 1})
            
        # Insert Combined Image
        if comb.get('CombImage'):
            ws.insert_image(row, 8, f"{asin}_comb.jpg", {'image_data': comb['CombImage'], 'x_scale': 0.3, 'y_scale': 0.3, 'object_position': 1})
            
        row += 1
        
    wb.close()
    print("Done!")

if __name__ == "__main__":
    main()
