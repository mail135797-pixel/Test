import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin, quote
import os
import difflib

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
    """
    # Remove "Costco" or "コストコ"
    title = re.sub(r'Costco|コストコ', '', title, flags=re.IGNORECASE)
    
    # Reduce multiple spaces
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def calculate_similarity(s1, s2):
    """
    Calculate similarity ratio between two strings using SequenceMatcher.
    """
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def fetch_jan_from_yahoo_api(title, price_str):
    """
    Fetch JAN code from Yahoo! Shopping API.
    """
    if not YAHOO_APP_ID:
        return ""

    url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
    
    cleaned_title = clean_title_for_search(title)
    
    # Construct query: Title + "コストコ" to prioritize Costco items
    query = f"{cleaned_title} コストコ" 
    
    params = {
        "appid": YAHOO_APP_ID,
        "query": query,
        "results": 5, 
        "sort": "-score"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 429:
             print("Rate limited. Waiting...", flush=True)
             time.sleep(5)
             return ""
             
        response.raise_for_status()
        data = response.json()
        
        hits = data.get("hits", [])
        best_match_jan = ""
        highest_score = 0.0

        for hit in hits:
            item_name = hit.get("name", "")
            jan_code = hit.get("janCode", "")
            
            if not jan_code:
                continue
                
            # Filter by name similarity
            similarity = calculate_similarity(cleaned_title, item_name)
            
            if similarity > highest_score:
                highest_score = similarity
                best_match_jan = jan_code
        
        # Threshold for acceptance (0.3 is lenient)
        if highest_score > 0.3:
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
            
        count += 1
        
        # Rate Limiting (0.5s sleep = 2 requests/sec)
        time.sleep(0.5) 
        
        # Save periodically
        if count % 100 == 0:
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
