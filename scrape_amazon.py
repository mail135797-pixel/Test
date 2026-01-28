import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import json

asins = [
    "B005PL0NV0", "B005PL0O28", "B008HAMO1S", "B008HANX4A", "B00ABX592K",
    "B00P723FCQ", "B00S0O6WIC", "B00YBSQRJU", "B01AUORRAQ", "B01B4H5ZIO",
    "B01B4I3NZ0", "B01COW1GEK", "B075R1SW4W", "B078K67R7K", "B08N2FR9L4",
    "B0BKZTKKSW"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}

def get_soup(url):
    retries = 3
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return BeautifulSoup(response.content, "html.parser")
            elif response.status_code == 503:
                print(f"503 Service Unavailable for {url}. Retrying...")
                time.sleep(2 + random.random() * 2)
            else:
                print(f"Failed to fetch {url}. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            time.sleep(2)
    return None

def extract_variations(soup, main_asin):
    variations = []
    
    # Check for Twister data (JSON format in script)
    # Often found in: var dataToReturn = { ... }; or P.register('twister-js-init-dta-data')
    
    # Method 1: Look for swatches in the HTML
    # Updated selectors to include inline twister
    swatches = soup.select("""
        #twister li[data-asin],
        #variation_color_name li[data-asin],
        #variation_size_name li[data-asin],
        #variation_style_name li[data-asin],
        #variation_pattern_name li[data-asin],
        #variation_flavor_name li[data-asin],
        ul.dimension-values-list li[data-asin],
        .swatch-list-item-text[data-asin],
        .inline-twister-swatch[data-asin]
    """)
    
    found_asins = set()
    found_asins.add(main_asin) # Ensure we don't duplicate the main one if we scrape it as a variation
    
    # Add the Main ASIN itself first
    main_title_tag = soup.select_one("#productTitle")
    main_title = main_title_tag.get_text(strip=True) if main_title_tag else "Title Not Found"
    variations.append({
        "Main ASIN": main_asin,
        "ASIN": main_asin,
        "TITLE": main_title,
        "ASIN LINK": f"https://www.amazon.co.jp/dp/{main_asin}"
    })

    for swatch in swatches:
        asin = swatch.get("data-asin")
        if asin and asin not in found_asins:
            found_asins.add(asin)
            
            # Try to get title for variation
            # Sometimes it's in the img alt or text
            title = ""
            img = swatch.select_one("img")
            if img:
                title = img.get("alt", "")
            
            if not title:
                # If it's a dropdown, might be text
                title = swatch.get_text(strip=True)
            
            # Sometimes specific variation titles are hard to get without visiting the page.
            # We will use the main title + variation attribute name if possible, or leave generic.
            # Ideally we visit each variation page, but that takes time. 
            # The prompt implies getting the ASINs is key. 
            # "해당 ASIN의 바리에이션의 ASIN이 무엇인지 전부 파악을 해 줘." -> Identify all variation ASINs.
            # If we need the EXACT title of the variation, we might need to fetch that page or parse the JSON data.
            
            # Let's try to extract from JSON if possible for better titles
            pass

    # Method 2: Regex for Twister data to get all ASINs and maybe titles
    scripts = soup.find_all("script")
    twister_data = None
    for script in scripts:
        if script.string and "dimensionToAsinMap" in script.string:
            # try to parse the JSON object
            # usually: 
            #   var dimensionToAsinMap =  {"0_0":"B0...", ...};
            #   htmlToAsinMap 
            # This map links combination of dimensions to ASIN.
            pass

    # Actually, simpler approach for title of variations:
    # If we find ASINs, we can just list them.
    # The user asks: "ASIN2 TITLE".
    # If we rely on swatches, we might get "Red" or "Small".
    # If we want the full product title like "Product Name - Red", we might need to construct it or fetch it.
    # Given the constraint of a script, fetching every variation might be too heavy/blocked.
    # But let's try to grab as much as we can from the main page.
    
    # Regex search for dimensions display
    # data["variationValues"] = { ... }
    
    html_content = str(soup)
    
    # Strategy: Find all ASINs associated with variations.
    # Using regex to find all B0... patterns might be too noisy.
    # Better to stick to structured data.
    
    # Try to find 'dimensionValuesDisplayData' which maps ASINs to specific names
    # or 'variationValues'
    
    # Let's fallback to the simple list of variations found in the DOM (swatches/dropdowns).
    # Those usually have `data-asin`.
    
    # Re-iterate swatches to populate list
    # We need to be careful to link Main ASIN to these.
    
    for swatch in swatches:
        asin = swatch.get("data-asin")
        if asin and asin != main_asin: # Skip main asin here as we added it at top
             # Attempt to find a better title if possible.
             # The swatch usually contains the variation name (e.g. "Chocolate").
             # Full title is usually "Main Title" + " " + "Variation Name".
            
            var_name = swatch.get("data-defaultasins", "") # sometimes helps
            
            # Try to extract the variation value name
            # <img> alt text is often the variation name
            var_text = ""
            img = swatch.select_one("img")
            if img:
                var_text = img.get("alt", "")
            else:
                var_text = swatch.get_text(strip=True)
            
            full_var_title = f"{main_title} - {var_text}" if var_text else f"{main_title} (Variation {asin})"
            
            # Check if we already added this ASIN (swatches can be duplicated for dimensions)
            if not any(v['ASIN'] == asin for v in variations):
                variations.append({
                    "Main ASIN": main_asin,
                    "ASIN": asin,
                    "TITLE": full_var_title,
                    "ASIN LINK": f"https://www.amazon.co.jp/dp/{asin}"
                })

    return variations

def main():
    all_data = []
    
    for asin in asins:
        print(f"Processing {asin}...")
        url = f"https://www.amazon.co.jp/dp/{asin}"
        soup = get_soup(url)
        
        if soup:
            vars_data = extract_variations(soup, asin)
            all_data.extend(vars_data)
        else:
            # If failed, at least add the main one
            all_data.append({
                "Main ASIN": asin,
                "ASIN": asin,
                "TITLE": "Failed to Fetch",
                "ASIN LINK": url
            })
        
        time.sleep(1 + random.random() * 2) # Respectful delay

    df = pd.DataFrame(all_data, columns=["Main ASIN", "ASIN", "TITLE", "ASIN LINK"])
    
    # Ensure all provided ASINs are present (even if no data found) is handled by loop.
    
    # Write to Excel
    output_file = "Amazon_ASIN_List.xlsx"
    df.to_excel(output_file, index=False)
    print(f"Data saved to {output_file}")

if __name__ == "__main__":
    main()
