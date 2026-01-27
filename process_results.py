import pandas as pd
from bs4 import BeautifulSoup
import glob
import re

PROVIDED_ASIN = "B0D2D1S6JM"
SHEET_NAME = PROVIDED_ASIN

keywords_list = [
    "コゲ落とし ジェル",
    "コゲ取り 洗剤",
    "焦げ落とし 強力",
    "五徳 コゲ落とし",
    "フライパン 焦げ落とし",
    "キッチン 掃除 洗剤 コゲ",
    "油汚れ コゲ落とし",
    "焦げ付き 洗剤",
    "ステンレス コゲ落とし",
    "錫村商店 コゲ"
]

data = []

# Process each search page
search_files = sorted(glob.glob("search_page_*.html"))

for file_path in search_files:
    print(f"Processing {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    soup = BeautifulSoup(content, "html.parser")
    
    # Amazon search results usually have data-asin attribute
    items = soup.find_all("div", {"data-asin": True})
    
    for item in items:
        asin = item.get("data-asin")
        if not asin:
            continue
            
        # Skip if it's an ad or empty asin (though data-asin usually implies it has one)
        
        # Find Title
        # Title is usually in an h2 -> a -> span or just h2 -> span
        title_tag = item.find("span", {"class": "a-text-normal"})
        title = title_tag.get_text(strip=True) if title_tag else None
        
        if not title:
            # Try h2
            h2 = item.find("h2")
            if h2:
                title = h2.get_text(strip=True)
        
        # Find Link
        # Link is usually the href of the 'a' tag inside h2 or near title
        link_tag = item.find("a", {"class": "a-link-normal"})
        link_suffix = link_tag.get("href") if link_tag else None
        
        if link_suffix:
            # Amazon links can be relative or absolute. usually relative /dp/ASIN...
            if link_suffix.startswith("/"):
                link = f"https://www.amazon.co.jp{link_suffix}"
            else:
                link = link_suffix
        else:
            link = f"https://www.amazon.co.jp/dp/{asin}"
            
        if title:
            data.append({
                "ASIN": asin,
                "Title": title,
                "ASIN Link": link
            })

# Remove duplicates if any (based on ASIN)
unique_data = []
seen_asins = set()
for item in data:
    if item["ASIN"] not in seen_asins:
        seen_asins.add(item["ASIN"])
        unique_data.append(item)

# Create DataFrame
df = pd.DataFrame(unique_data)

# Add Keywords to Column D
# We can just fill the first 10 rows with keywords
df["検索キーワード"] = ""
for i, kw in enumerate(keywords_list):
    if i < len(df):
        df.at[i, "検索キーワード"] = kw

# Save to Excel
output_file = f"{PROVIDED_ASIN}.xlsx"
try:
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=SHEET_NAME, index=False)
    print(f"Successfully created {output_file}")
except Exception as e:
    print(f"Error creating Excel: {e}")
