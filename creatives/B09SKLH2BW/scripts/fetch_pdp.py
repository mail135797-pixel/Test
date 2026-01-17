import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import sys
import json
import random

asin = "B09SKLH2BW"
url = f"https://amazon.co.jp/dp/{asin}"

ua = UserAgent()

def fetch_with_retry():
    for i in range(5):
        print(f"Attempt {i+1}...")
        headers = {
            'User-Agent': ua.random,
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                if "captcha" in soup.text.lower():
                    print("Captcha hit.")
                    time.sleep(2 + random.random() * 3)
                    continue
                
                title = soup.find(id="productTitle")
                if title:
                    return soup
                else:
                    print("Title ID not found.")
            else:
                print(f"Status {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(2 + random.random() * 3)
    return None

soup = fetch_with_retry()

if soup:
    title = soup.find(id="productTitle")
    title_text = title.get_text(strip=True) if title else "N/A"
    print(f"Title: {title_text}")

    brand = soup.find(id="bylineInfo")
    brand_text = brand.get_text(strip=True) if brand else "N/A"

    bullets = []
    bullet_div = soup.find(id="feature-bullets")
    if bullet_div:
        for li in bullet_div.find_all('li'):
            txt = li.get_text(strip=True)
            if txt:
                bullets.append(txt)
    
    desc_div = soup.find(id="productDescription")
    desc_text = desc_div.get_text(strip=True) if desc_div else "N/A"
    
    img_div = soup.find(id="imgTagWrapperId")
    img_url = ""
    if img_div and img_div.find('img'):
        img_url = img_div.find('img').get('src')
        img_tag = img_div.find('img')
        if img_tag.get('data-a-dynamic-image'):
            try:
                data = json.loads(img_tag.get('data-a-dynamic-image'))
                img_url = max(data.keys(), key=lambda k: data[k][0] * data[k][1])
            except:
                pass
    
    if img_url:
        img_data = requests.get(img_url).content
        with open(f"creatives/{asin}/reference/reference_main.jpg", 'wb') as f:
            f.write(img_data)
        print("Image downloaded.")
        
    with open(f"creatives/{asin}/00_pdp_snapshot.md", 'w', encoding='utf-8') as f:
        f.write(f"# PDP Snapshot for {asin}\n\n")
        f.write(f"## Basic Info\n")
        f.write(f"- **Title**: {title_text}\n")
        f.write(f"- **Brand**: {brand_text}\n")
        f.write(f"- **URL**: {url}\n")
        f.write(f"- **Main Image**: {img_url}\n\n")
        
        f.write(f"## Feature Bullets\n")
        for b in bullets:
            f.write(f"- {b}\n")
        f.write("\n")
        
        f.write(f"## Description\n")
        f.write(f"{desc_text}\n")
else:
    print("Failed to fetch page after retries.")
