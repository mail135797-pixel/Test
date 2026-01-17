import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin
import os

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

def get_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}", flush=True)
        return None

def parse_price(product_item):
    # Try to find visible price
    price_elem = product_item.select_one("sip-format-price .notranslate")
    if price_elem:
        return price_elem.get_text(strip=True)
    
    # Try to find login message
    login_elem = product_item.select_one(".price-panel-login span")
    if login_elem:
        return login_elem.get_text(strip=True)
    
    return "N/A"

def parse_item_number(url):
    match = re.search(r'/p/(\d+)', url)
    if match:
        return match.group(1)
    return "N/A"

def extract_products(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    products = []
    
    items = soup.select("sip-product-list-item")
    for item in items:
        try:
            # Title and Link
            link_elem = item.select_one("a.lister-name")
            if not link_elem:
                continue
                
            title = link_elem.get_text(strip=True)
            relative_link = link_elem['href']
            full_link = urljoin(base_url, relative_link)
            
            # Item Number
            item_number = parse_item_number(full_link)
            
            # Price
            price = parse_price(item)
            
            products.append({
                "Title": title,
                "Link": full_link,
                "Item Number": item_number,
                "Price": price
            })
        except Exception as e:
            print(f"Error parsing item: {e}", flush=True)
            continue
            
    # Pagination
    next_page = None
    next_link_elem = soup.select_one("a.page-link[data-cy='page-link-next']")
    if next_link_elem:
        # Check if parent li is disabled
        parent_li = next_link_elem.find_parent("li")
        if parent_li and "disabled" not in parent_li.get("class", []):
            next_page = urljoin(base_url, next_link_elem['href'])
            
    return products, next_page

def save_data(data):
    df = pd.DataFrame(data)
    # Reorder columns to match request: A: Title, B: Link, C: Item Number, D: Price
    df = df[["Title", "Link", "Item Number", "Price"]]
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved {len(data)} products to {OUTPUT_FILE}", flush=True)

def main():
    all_data = []
    
    for category_url in CATEGORIES:
        print(f"Processing category: {category_url}", flush=True)
        current_url = category_url
        page_count = 0
        
        while current_url:
            print(f"  Fetching page: {current_url}", flush=True)
            html = get_page(current_url)
            if not html:
                break
                
            products, next_url = extract_products(html, current_url)
            all_data.extend(products)
            print(f"  Found {len(products)} products.", flush=True)
            
            # Save progress after each page (or could do after each category)
            # Saving after each page is safer if it crashes
            save_data(all_data)

            if next_url == current_url:
                 break

            current_url = next_url
            page_count += 1
            
            # Polite delay
            time.sleep(1)
            
    print(f"Total products extracted: {len(all_data)}", flush=True)
    save_data(all_data)

if __name__ == "__main__":
    main()
