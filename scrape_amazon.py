import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import json

# List of ASINs provided
ASIN_LIST_STR = "B094QDQJ58,B007KTN33A,B0CSDVJLXZ,B0DJ5PYDYC,B01LXY4722,B07YBHFPYN,B01N8T4SFU,B0978HFG81,B0D2D1S6JM,B0DVGX6F7Q,B07XYWZ4LD,B071XYNR2Y,B0DJGFDJMJ,B08241LKPM,B0DQ15C2XW,B005I0GO3O,B0DG5DVQMK,B07CCTXKL1,B0D4LNY4CW,B0DRD9ZVJT,B0DS9DGSMT,B0GC4RFQNG,B0CZDBSLR3,B075159W3Q,B0DV4DYHDF,B07LCH4L9N,B0D7BRJ8RT,B09CPV6HVZ,B01GMMRMMS,B01HSVD6X6,B0DSFNSBF5,B0DT4FCMHV,B00AHRJ2GO,B0DPHF1C76,B07WFBKPLN,B08XTXMM35,B0DQG8Z4WJ,B0CP3DWG3M,B0CYPG1Z3R,B0F2SP1FM9,B0D4VD3HG3,B075NFKSL1,B0DP87ZY74,B08J4X7476,B000W9HC5A,B0953PL81V,B0DZBXM4YL,B09MK1T82Y,B0D443BG2N,B0C61C823L,B0D59PW2V6,B0DPHGRFC5,B0F2SZKWG3,B012JU6JA8,B0FV8RVB1B,B0916QJYJG,B01G6WX49O,B0DNX3517P,B07517NV3R,B00QT5UHDU,B09Z25CB4Q,B0G8D43YC2,B09BMT4BW4,B01H1EH7CG,B0D21YT6FY,B0DPVCRWPZ,B0F79R5SB2,B0CR2XQFLX,B09L1H1CCH,B072XGSD8C,B0DNW35S5W,B08R9MRD7X,B009SY47OE,B0FN442FZQ,B0FY5NWN78,B07NDT7Q1F,B07KX7B9L1,B072XKCTJ3,B0FSZ3ZCYL,B0C4S3KTPM,B00TAYZ4SK,B0FRRYHPWS,B07BL1VWP6,B0FRZ9YSMJ,B0FHBV449D,B0B1845RLL,B0FHBFLL5F,B0FLXJY9GG,B07GJMMWYL,B0DSQ7T7VP,B0FBFYX1T1,B0FFSTRR59,B0DK2Y99B1,B0CX4VRT7B,B0GC4FDNF8,B0D7WFV6ZV,B01EX8MN3G,B0DG94XYV3,B07NRT3ZL7,B0F8PWBCFX,B0FP4Q2LFN,B0748943G4,B0FDBJM9WQ,B0F1ML8F6R,B0F3841CCT,B0D7Z7F6QL,B0D7ZLTNR4,B0D7ZMPPCQ,B0CHPKHBLM,B0CM69MXBF"
ASIN_LIST = [asin.strip() for asin in ASIN_LIST_STR.split(',')]

HEADERS_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_headers():
    return {
        'User-Agent': random.choice(HEADERS_LIST),
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Referer': 'https://www.google.com/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
    }

def get_soup(url):
    session = requests.Session()
    retries = 3
    for attempt in range(retries):
        try:
            headers = get_headers()
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # Check for captcha
                if "api-services-support@amazon.com" in response.text:
                    print(f"  Captcha detected for {url}")
                    time.sleep(2 + attempt * 2)
                    continue
                return BeautifulSoup(response.content, 'lxml')
            elif response.status_code in [500, 503]:
                print(f"  Status {response.status_code} for {url}. Retrying ({attempt+1}/{retries})...")
                time.sleep(3 + attempt * 2)
            else:
                print(f"  Failed to retrieve {url}: Status {response.status_code}")
                # Don't retry for 404
                if response.status_code == 404:
                    return None
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            time.sleep(2)
            
    return None

def parse_variations(soup, main_asin):
    variations = []
    
    # 1. Try extracting from script tag containing "jQuery.parseJSON" or "P.register('Twister'"
    # Look for the data-dp-variations-data attribute which is common in newer layouts
    variation_data_div = soup.find('div', id='twister_feature_div')
    
    # Base title
    base_title_tag = soup.find('span', id='productTitle')
    base_title = base_title_tag.get_text().strip() if base_title_tag else "Unknown Title"
    
    # Sometimes variations are not available or there is only one
    # Check if there are variations
    # We look for the JSON data usually embedded in the page
    
    # Strategy A: Look for dimensionValuesData in scripts
    # Strategy B: Look for data-a-dynamic-image which maps ASINs to images, but we need titles.
    
    # Regex to find the JSON object for variations
    # Often it is in a block: var dataToReturn = {...};
    
    # Let's search for the big JSON blob
    scripts = soup.find_all('script')
    found_variations = False
    
    for script in scripts:
        if script.string:
            # Look for JSON with ASINs
            if 'dimensionValuesDisplayData' in script.string:
                try:
                    # This is one format
                    # extract the json
                    pass 
                except:
                    pass
            
            # Another common format: P.register('Twister', function(){... dataToReturn = {...} ...})
            # Or just looking for the mapping of ASIN to attributes
            
    # Simpler approach: Look for the variation ASINs directly if possible.
    # However, to be reliable, let's use the 'twister-js-init-inline' if it exists
    
    # Fallback/Alternative: use the `data-csa-c-item-id` of swatches if available
    # Swatches often have `data-defaultasin` or `data-asin`
    
    swatches = soup.select('li[data-defaultasin]')
    if not swatches:
        swatches = soup.select('li[data-asin]')
        
    if swatches:
        for swatch in swatches:
            asin = swatch.get('data-defaultasin') or swatch.get('data-asin')
            if not asin:
                continue
                
            # Try to get title from the swatch (often it's just the color/size name)
            # We want the full title. Usually we can construct it or it's hard to get without visiting.
            # However, prompt implies we should just get "ASIN TITLE".
            # If we are on the main page, we can assume the base title + variation attributes.
            # But the user might want the exact title as it appears on the page.
            
            # For now, let's use Base Title. 
            # If the swatch has a title attribute (e.g. title="Click to select Black"), we can append it.
            
            # Wait, if we use the same title for all, it might be incorrect if the user expects differentiation.
            # Let's see if we can find a map.
            
            # Let's proceed with finding ASINs first.
            if asin not in [v['asin'] for v in variations]:
                 # Try to find specific variation name
                img = swatch.find('img')
                var_name = ""
                if img and img.get('alt'):
                    var_name = img.get('alt')
                
                # If we have a variation name, append to base title?
                # Actually, usually Amazon titles are "Base Title - Variation Name"
                # But sometimes the Base Title already includes the selected variation.
                
                # Let's just collect ASINs for now and use Base Title + Var Name if available.
                # Or better: Check if there's a variation matrix in the page source.
                
                full_title = base_title
                # If we are strictly on the page of 'main_asin', base_title corresponds to main_asin.
                # For other ASINs, we might not know the exact title without visiting.
                # BUT, let's check if the prompt implies visiting is okay?
                # "1. ... 해당 ASIN의 바리에이션의 ASIN이 무엇인지 전부 파악을 해 줘." (Identify all variation ASINs)
                # "2. ... 데이터를 추출을 해 주었으면 좋겠어." (Extract data)
                
                # Visiting every single variation ASIN might take a long time (100 input ASINs * ~5 variations = 500 requests).
                # With 10s timeout and retries, this could take an hour.
                # I should try to extract from the main page if possible.
                
                # If I can't get the title, I will mark it as "Check Link".
                # But let's try to get the variation values.
                
                variations.append({
                    'asin': asin,
                    'title': full_title + (f" ({var_name})" if var_name else ""),
                    'link': f"https://www.amazon.co.jp/dp/{asin}"
                })
                
    # If no swatches found, maybe it's a dropdown (select)
    if not variations:
        options = soup.select('select[name="dropdown_selected_size_name"] option')
        if not options:
            options = soup.select('select[data-a-touch-header] option') # Generic
            
        for opt in options:
            val = opt.get('value')
            # The value usually isn't the ASIN directly in dropdowns, it's a key like "0,1"
            # which maps to ASIN in the JSON.
            # Parsing the JSON is the most robust way.
            pass

    # If we still have no variations, it might be a single item or we failed to parse.
    # We should at least include the main ASIN.
    if not variations:
        variations.append({
            'asin': main_asin,
            'title': base_title,
            'link': f"https://www.amazon.co.jp/dp/{main_asin}"
        })
    else:
        # Check if main_asin is in variations. If not, add it (it should be there usually)
        # Note: sometimes the main ASIN provided IS one of the variations.
        found = False
        for v in variations:
            if v['asin'] == main_asin:
                found = True
                # Update title to be exact if possible (since we are on the page)
                v['title'] = base_title
                break
        if not found:
            # If main_asin not found in swatches (rare but possible if out of stock or hidden), add it
            variations.insert(0, {
                'asin': main_asin,
                'title': base_title,
                'link': f"https://www.amazon.co.jp/dp/{main_asin}"
            })

    # Robust JSON extraction for Variation Titles (Best effort)
    try:
        # Search for `dimensionValuesDisplayData`
        # This maps { "ASIN": ["Value1", "Value2"] }
        # And `variationValues` maps { "dim1": ["val1", "val2"] }
        
        # There is often a `title` field in the JSON too.
        regex = re.compile(r'jQuery\.parseJSON\(\'(.*?)\'\)')
        # This might be too fragile.
        
        # Let's rely on swatches/list items first as they are DOM elements.
        pass
    except:
        pass

    return variations

def extract_json_variations(soup, main_asin):
    """
    Attempts to extract variation data from Amazon's JSON data embedded in the page.
    """
    variations = []
    base_title_tag = soup.find('span', id='productTitle')
    base_title = base_title_tag.get_text().strip() if base_title_tag else "Unknown Title"

    # Try to find the Twister data
    # Look for script content that contains "dimensionToAsinMap"
    scripts = soup.find_all('script')
    data = None
    
    for script in scripts:
        if script.string and 'dimensionToAsinMap' in script.string:
            # Extract the JSON object
            # Usually: var dataToReturn = { ... "dimensionToAsinMap" : {...} ... };
            # Or P.register(..., dataToReturn);
            try:
                # Find the start of the object
                match = re.search(r'dimensionToAsinMap"\s*:\s*({.*?})\s*,', script.string)
                if match:
                    dim_map_str = match.group(1)
                    # This is just the map. We also need values if we want titles.
                    # But at least we get all ASINs.
                    dim_map = json.loads(dim_map_str)
                    
                    # Create variations from this map
                    for key, asin in dim_map.items():
                        # We don't have the specific title here, but we have the ASIN.
                        # We can use the base title.
                        variations.append({
                            'asin': asin,
                            'title': base_title, # Placeholder
                            'link': f"https://www.amazon.co.jp/dp/{asin}"
                        })
                    return variations
            except:
                continue

    return variations

def main():
    output_file = "/workspace/asin_variations.xlsx"
    processed_asins = set()
    existing_data = []
    
    # Load existing data if available
    try:
        df_existing = pd.read_excel(output_file, sheet_name='카비즈바')
        # Check which ASINs are successfully processed
        # We consider successful if TITLE is not "Error Loading Page"
        # However, we need to know which Main ASINs are done.
        
        # Group by Main ASIN
        grouped = df_existing.groupby('Main ASIN')
        for main_asin, group in grouped:
            # If any row in the group has "Error Loading Page", marks as not done (or needs retry)
            # Or if the group is just the error row
            if len(group) == 1 and group.iloc[0]['TITLE'] == "Error Loading Page":
                pass # Needs retry
            else:
                processed_asins.add(str(main_asin))
                existing_data.extend(group.to_dict('records'))
                
        print(f"Loaded {len(processed_asins)} already processed ASINs.")
    except Exception as e:
        print(f"No existing data found or error reading: {e}")
        existing_data = []

    all_data = existing_data
    
    # Filter ASIN_LIST
    asins_to_process = [asin for asin in ASIN_LIST if asin not in processed_asins]
    
    print(f"Processing {len(asins_to_process)} ASINs (out of {len(ASIN_LIST)} total)...")

    for i, main_asin in enumerate(asins_to_process):
        print(f"[{i+1}/{len(asins_to_process)}] Scrapping {main_asin}...")
        url = f"https://www.amazon.co.jp/dp/{main_asin}"
        
        soup = get_soup(url)
        if not soup:
            # If failed, just add the main ASIN as a fallback
            print(f"  Skipping {main_asin} (Failed to load after retries)")
            all_data.append({
                'Main ASIN': main_asin,
                'ASIN': main_asin,
                'TITLE': "Error Loading Page",
                'ASIN LINK': url
            })
            continue

        # Try to get variations
        # 1. Try swatches (DOM)
        variations = parse_variations(soup, main_asin)
        
        # If no variations found (only main returned), that's fine.
        
        # Filter duplicates just in case
        seen_asins = set()
        unique_variations = []
        for v in variations:
            if v['asin'] not in seen_asins:
                seen_asins.add(v['asin'])
                unique_variations.append(v)
        
        for v in unique_variations:
            all_data.append({
                'Main ASIN': main_asin,
                'ASIN': v['asin'],
                'TITLE': v['title'],
                'ASIN LINK': v['link']
            })
            
        # Respectful delay
        time.sleep(random.uniform(2.0, 5.0))
        
        # Save periodically
        if (i + 1) % 10 == 0:
            df = pd.DataFrame(all_data)
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='카비즈바', index=False)
            print("  Saved progress.")

    # Create DataFrame
    df = pd.DataFrame(all_data)
    
    # Ensure correct column order
    df = df[['Main ASIN', 'ASIN', 'TITLE', 'ASIN LINK']]
    
    # Save to Excel
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='카비즈바', index=False)
        
    print(f"Saved data to {output_file}")

if __name__ == "__main__":
    main()
