import requests
from bs4 import BeautifulSoup
import time
import random

ASIN = "B0D2D1S6JM"
URL = f"https://www.amazon.co.jp/dp/{ASIN}"

# List of user agents to rotate
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def get_headers():
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

def get_product_details(url):
    max_retries = 3
    for i in range(max_retries):
        try:
            print(f"Attempt {i+1}...")
            response = requests.get(url, headers=get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Check for captcha
                if "api-services-support@amazon.com" in response.text or "Type the characters you see in this image" in response.text:
                    print("Captcha detected.")
                    time.sleep(random.uniform(2, 5))
                    continue

                # Title
                title_element = soup.find("span", {"id": "productTitle"})
                title = title_element.get_text(strip=True) if title_element else None
                
                if not title:
                     print("Title not found on page, dumping part of html for debug...")
                     # print(soup.prettify()[:1000]) 
                     # Sometimes layout is different
                     pass

                # Bullet points
                bullet_points = []
                feature_bullets = soup.find("div", {"id": "feature-bullets"})
                if feature_bullets:
                    for li in feature_bullets.find_all("li"):
                        span = li.find("span", {"class": "a-list-item"})
                        if span:
                            bullet_points.append(span.get_text(strip=True))
                
                if title:
                    return {
                        "ASIN": ASIN,
                        "Title": title,
                        "Bullets": bullet_points,
                        "URL": url
                    }
                else:
                    print("Could not parse title.")
            else:
                print(f"Status code: {response.status_code}")
            
            time.sleep(random.uniform(2, 5))
            
        except Exception as e:
            print(f"Error fetching product: {e}")
            time.sleep(random.uniform(2, 5))
            
    return None

if __name__ == "__main__":
    details = get_product_details(URL)
    if details:
        print("Successfully fetched product details:")
        print(f"Title: {details['Title']}")
        print("Bullets:")
        for bp in details['Bullets']:
            print(f"- {bp}")
        
        # Save to a temporary file to use in next steps
        with open("product_info.txt", "w", encoding="utf-8") as f:
            f.write(f"Title: {details['Title']}\n")
            f.write("Bullets:\n")
            for bp in details['Bullets']:
                f.write(f"- {bp}\n")
    else:
        print("Failed to fetch product details.")
