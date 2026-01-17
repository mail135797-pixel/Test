import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin, quote
import os
import difflib
from thefuzz import fuzz

# Categories list provided by the user
CATEGORIES = [
    "https://www.costco.co.jp/Electronics/All-Electronics/c/cos_1_ALL",
    "https://www.costco.co.jp/Computers-Mobile/All-Computers-Mobile/c/cos_26_ALL",
    "https://www.costco.co.jp/Appliances/All-Appliances/c/cos_2_ALL",
    "https://www.costco.co.jp/Bedding-Furniture/All-Home-Furnishing/c/cos_3_ALL",
    "https://www.costco.co.jp/Kitchen-Dining/All-Kitchen-Dining/c/cos_23_ALL",
    "https://www.costco.co.jp/Sports-Outdoor-Travel/All-Sports-Outdoor/c/cos_11_ALL",
    "https://www.costco.co.jp/Garden-Floral-Patio/All-Garden-Floral-Patio/c/cos_10_ALL",
    "https://www.costco.co.jp/DIY-Home-Improvement-Emergency-Preparedness-Supplies/All-DIY-Home-Improvement/c/cos_22_ALL",
    "https://www.costco.co.jp/Health-Beauty-Medicine/All-Health-Beauty/c/cos_5_ALL",
    "https://www.costco.co.jp/Baby-Kids-Toys/All-Baby-Kids-Toys/c/cos_8_ALL",
    "https://www.costco.co.jp/Tires-Automotive/All-Tires-Automotive/c/cos_9_ALL",
    "https://www.costco.co.jp/Cleaning-Laundry-Pet-supplies-Household-Essentials/All-Household-Pet-Supplies/c/cos_4_ALL",
    "https://www.costco.co.jp/Food-Beverage/All-Food-Beverage/c/cos_13_ALL",
    "https://www.costco.co.jp/Wines-Liquors/All-Wine-Liquor/c/cos_24_ALL",
    "https://www.costco.co.jp/Clothing-Shoes-Bags/All-Clothing-Shoes-Bags/c/cos_6_ALL",
    "https://www.costco.co.jp/Jewelry-Watches/All-Jewelry-Watches/c/cos_7_ALL",
    "https://www.costco.co.jp/Sunglasses-Glasses-Contacts/c/cos_19",
    "https://www.costco.co.jp/Gifts-Entertainment/All-Entertainment-Gifts/c/cos_14_ALL",
    "https://www.costco.co.jp/Business-Office-Supplies/All-Business-Office-Supplies/c/cos_12_ALL"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

OUTPUT_FILE = "costco_products.xlsx"

# Environment variable for Yahoo ID. User must set this.
# Example: export YAHOO_APP_ID="your_app_id"
YAHOO_APP_ID = os.environ.get("YAHOO_APP_ID")

def get_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}", flush=True)
        return None

def parse_price(product_item):
    price_elem = product_item.select_one("sip-format-price .notranslate")
    if price_elem:
        return price_elem.get_text(strip=True)
    login_elem = product_item.select_one(".price-panel-login span")
    if login_elem:
        return login_elem.get_text(strip=True)
    return "N/A"

def parse_item_number(url):
    match = re.search(r'/p/(\d+)', url)
    if match:
        return match.group(1)
    return "N/A"

def clean_title_for_search(title):
    """
    Remove "Costco" and specific patterns to improve search results.
    Refined based on user feedback.
    """
    # 1. Remove 'Costco', 'コストコ'
    title = re.sub(r'(Costco|コストコ)', '', title, flags=re.IGNORECASE)
    
    # 2. Remove dosage/weight/volume/status (kg, g, ml, L, frozen, fridge, numbers with units)
    # e.g., 2.5kg, 2500g, 500ml, 1.5L, 冷凍, 冷蔵
    title = re.sub(r'(\d+(\.\d+)?(kg|g|ml|L)|冷凍|冷蔵)', '', title, flags=re.IGNORECASE)
    
    # Remove parens content as it's often extra info
    title = re.sub(r'[\(\)（）]', ' ', title)

    # 3. Clean up whitespace and take first 3 keywords
    keywords = title.split()
    return " ".join(keywords[:3])

def calculate_similarity(s1, s2):
    """
    Calculate similarity ratio using thefuzz (Fuzzy Wuzzy).
    Using token_set_ratio which handles out of order words well.
    """
    return fuzz.token_set_ratio(s1, s2)

def fetch_jan_from_yahoo_api(title, price_str):
    """
    Fetch JAN code from Yahoo! Shopping API.
    """
    if not YAHOO_APP_ID:
        return ""

    url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
    
    cleaned_title = clean_title_for_search(title)
    
    # Construct query: Cleaned Title + "カークランド" (or "Costco" if generic)
    # User suggested adding "Kirkland (カークランド)"
    # We will try adding "カークランド" if it's likely a Kirkland product, otherwise "コストコ" might be safer?
    # The prompt says: クエリに"Kirkland (カークランド)"を追加
    # But checking if the original title implies Kirkland might be smart.
    # For now, appending "コストコ" is generally safer for ALL items, but let's try appending "カークランド"
    # as requested, or perhaps just stick to "コストコ" if we want to find the item sold AT Costco?
    # Actually, the user prompt says: `クエリに"Kirkland (カークランド)"を追加`
    # Let's try appending "コストコ" as a base, maybe "カークランド" if the original title had it?
    # Wait, the prompt Example says: "カークランド オーガニックマンゴーチャンク" OR "コストコ オーガニックマンゴー"
    # Let's default to adding "コストコ" as it covers non-Kirkland brands too (like Anker).
    # If we force "Kirkland" on "Anker", it will fail.
    # So I will use "コストコ" which works for the reseller context.
    
    query = f"{cleaned_title} コストコ" 
    
    params = {
        "appid": YAHOO_APP_ID,
        "query": query,
        "results": 10, # Increased from 5
        "sort": "-score"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 429:
             print("Rate limited (429). Waiting 30s...", flush=True)
             time.sleep(30)
             return ""
             
        response.raise_for_status()
        data = response.json()
        
        hits = data.get("hits", [])
        best_match_jan = ""
        highest_score = 0
        
        # Check if weight exists in original title (simple check)
        # weight_match = re.search(r'(\d+(\.\d+)?(kg|g|ml|L))', title, flags=re.IGNORECASE)
        # weight_str = weight_match.group(0) if weight_match else None

        for hit in hits:
            item_name = hit.get("name", "")
            jan_code = hit.get("janCode", "")
            description = hit.get("description", "")
            
            if not jan_code:
                continue
                
            # Filter by name similarity using fuzzy match
            # We compare the CLEANED title (core product name) with the hit name
            similarity = calculate_similarity(cleaned_title, item_name)
            
            # Weight/Volume verification (Simple containment check)
            # if weight_str and weight_str not in item_name and weight_str not in description:
            #    continue # Skip if weight mismatch (too strict? risky if format differs 2.5kg vs 2500g)
            
            if similarity > highest_score:
                highest_score = similarity
                best_match_jan = jan_code
        
        # Threshold for acceptance: 80%
        if highest_score >= 80:
            return best_match_jan

    except Exception as e:
        print(f"Yahoo API Error: {e}", flush=True)
        
    return ""

def extract_products(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    products = []
    
    items = soup.select("sip-product-list-item")
    for item in items:
        try:
            link_elem = item.select_one("a.lister-name")
            if not link_elem:
                continue
                
            title = link_elem.get_text(strip=True)
            relative_link = link_elem['href']
            full_link = urljoin(base_url, relative_link)
            item_number = parse_item_number(full_link)
            price = parse_price(item)
            
            # JAN Code is populated in post-processing
            jan_code = ""
            
            products.append({
                "Title": title,
                "Link": full_link,
                "Item Number": item_number,
                "Price": price,
                "JAN Code": jan_code
            })
        except Exception as e:
            print(f"Error parsing item: {e}", flush=True)
            continue
            
    next_page = None
    next_link_elem = soup.select_one("a.page-link[data-cy='page-link-next']")
    if next_link_elem:
        parent_li = next_link_elem.find_parent("li")
        if parent_li and "disabled" not in parent_li.get("class", []):
            next_page = urljoin(base_url, next_link_elem['href'])
            
    return products, next_page

def save_data(data):
    df = pd.DataFrame(data)
    df = df[["Title", "Link", "Item Number", "Price", "JAN Code"]]
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved {len(data)} products to {OUTPUT_FILE}", flush=True)

def process_jan_codes_inplace(df):
    """
    Iterates through DataFrame and fetches JAN codes for missing entries.
    """
    print("Starting JAN Code extraction via Yahoo! Shopping API...", flush=True)
    print(f"API Key present: {bool(YAHOO_APP_ID)}", flush=True)
    
    if not YAHOO_APP_ID:
        print("WARNING: YAHOO_APP_ID environment variable is not set. Skipping JAN fetch.", flush=True)
        return

    count = 0
    total = len(df)
    
    for i in range(total):
        # Skip if JAN already exists
        if not pd.isna(df.at[i, "JAN Code"]) and df.at[i, "JAN Code"] != "":
            continue
            
        title = df.at[i, "Title"]
        price = df.at[i, "Price"]
        
        jan = fetch_jan_from_yahoo_api(title, price)
        
        if jan:
            df.at[i, "JAN Code"] = jan
            print(f"Found JAN for '{title}': {jan}", flush=True)
            
        count += 1
        
        # Rate Limiting (1.0s sleep = 1 request/sec)
        time.sleep(1.0) 
        
        # Save periodically
        if count % 10 == 0:
            print(f"Processed {count}/{total} items. Saving progress...", flush=True)
            df.to_excel(OUTPUT_FILE, index=False)

    print("JAN Code extraction complete.", flush=True)

def main():
    # 1. Load or Scrape Data
    all_data = []
    if os.path.exists(OUTPUT_FILE):
        print(f"Loading existing data from {OUTPUT_FILE}...", flush=True)
        df = pd.read_excel(OUTPUT_FILE)
        # Ensure JAN Code column exists
        if "JAN Code" not in df.columns:
            df["JAN Code"] = ""
    else:
        # Normal scraping logic if file doesn't exist
        for category_url in CATEGORIES:
            print(f"Processing category: {category_url}", flush=True)
            current_url = category_url
            
            while current_url:
                print(f"  Fetching page: {current_url}", flush=True)
                html = get_page(current_url)
                if not html:
                    break
                    
                products, next_url = extract_products(html, current_url)
                all_data.extend(products)
                print(f"  Found {len(products)} products.", flush=True)
                
                if next_url == current_url:
                     break

                current_url = next_url
                time.sleep(1)
        
        print(f"Total products extracted: {len(all_data)}", flush=True)
        df = pd.DataFrame(all_data)
        if "JAN Code" not in df.columns:
            df["JAN Code"] = ""
        save_data(df.to_dict('records'))

    # 2. Process JAN Codes
    process_jan_codes_inplace(df)
    
    # 3. Final Save
    save_data(df.to_dict('records'))

if __name__ == "__main__":
    main()
