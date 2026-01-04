import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import urllib.parse
import subprocess
import sys

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def is_lawyer(text):
    return "弁護士" in text

def is_worker_side_strict(text):
    text = text.lower()
    # Must mention worker-related terms
    if not any(k in text for k in ['労働者', '会社員', '未払い', '解雇', '退職', 'パワハラ', 'セクハラ', '残業']):
        return False
    
    # Must NOT be explicitly for companies
    # "Company side" "Management side" "Corporate legal"
    negative_terms = ['使用者側', '会社側', '経営者側', '企業法務', '顧問弁護士', '法人']
    
    # But "Not for companies" is okay. "Check if company..."
    # Simple check: if negative term exists, assume bad unless "Not" is near it (hard to parse).
    # Let's reject if "Corporate Legal" (企業法務) is in the title.
    
    if any(k in text for k in negative_terms):
        # Double check: "Employee side, not Company side"?
        # It's safer to reject if unsure.
        return False
        
    return True

def fetch_with_curl(url):
    try:
        result = subprocess.run(
            ['curl', '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', '-L', url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception:
        return None

def scrape_coconala():
    base_url = "https://coconala.com"
    # Broader keywords to find ANY lawyer first, then filter
    search_keywords = [
        "労働 弁護士",
        "労働トラブル 弁護士",
        "残業代 弁護士",
        "解雇 弁護士"
    ]
    
    seen_urls = set()
    results = []

    print("Starting Coconala scrape (Broad Search & Strict Filter)...")

    for keyword in search_keywords:
        print(f"Searching for: {keyword}")
        search_url = f"{base_url}/search?keyword={urllib.parse.quote(keyword)}"
        
        html_content = fetch_with_curl(search_url)
        if not html_content: continue
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        all_links = soup.find_all('a', href=True)
        potential_urls = []
        for link in all_links:
            href = link['href']
            if '/services/' in href:
                if '?' in href: href = href.split('?')[0]
                full_url = href if href.startswith('http') else f"{base_url}{href}" if href.startswith('/') else f"{base_url}/{href}"
                if full_url not in seen_urls and full_url not in potential_urls:
                    potential_urls.append(full_url)
        
        print(f"Found {len(potential_urls)} links for {keyword}")
        
        for full_url in potential_urls:
            if full_url in seen_urls: continue
            seen_urls.add(full_url)
            
            time.sleep(1.0)
            page_content = fetch_with_curl(full_url)
            if not page_content: continue
            
            item_soup = BeautifulSoup(page_content, 'html.parser')
            body_text = clean_text(item_soup.body.get_text()) if item_soup.body else ""
            
            # Metadata
            h1 = item_soup.find('h1')
            title = clean_text(h1.get_text()) if h1 else "No Title"
            
            provider_elem = item_soup.find(class_=re.compile(r'provider|UserSummary'))
            provider_name = clean_text(provider_elem.get_text()) if provider_elem else ""

            price_elem = item_soup.find(class_=re.compile(r'price|Price|amount'))
            price_text = clean_text(price_elem.get_text()) if price_elem else "상담 후 견적"

            # 1. Must be Lawyer
            # Check title or provider name or body for "弁護士"
            if "弁護士" not in title and "弁護士" not in provider_name and "法律事務所" not in body_text:
                # print(f"  Skipping {title}: Not identified as lawyer")
                continue

            # 2. Must be Worker Side
            if not is_worker_side_strict(title + " " + body_text):
                # print(f"  Skipping {title}: Likely company side")
                continue

            # 3. Must be Labor Tribunal related (or at least mentions it)
            if "労働審判" not in body_text:
                # print(f"  Skipping {title}: No mention of Labor Tribunal")
                continue

            # Generate Summary
            summary_points = []
            if "労働審判" in body_text: summary_points.append("노동심판 언급")
            if "交渉" in body_text: summary_points.append("교섭")
            if "訴訟" in body_text: summary_points.append("소송")
            
            snippet = ""
            try:
                idx = body_text.find("労働審判")
                snippet = body_text[idx:idx+80]
            except: pass

            summary_kr = f"[{' / '.join(summary_points)}] 근로자측. {snippet}..."
            
            results.append({
                "변호사 명": provider_name,
                "링크": full_url,
                "금액": price_text,
                "상세 정보(한국어 요약)": summary_kr
            })
            print(f"Added: {title}")
            
            if len(results) >= 30: break
        if len(results) >= 30: break

    # Fallback if empty
    if not results:
        results.append({
            "변호사 명": "데이터 없음",
            "링크": "-",
            "금액": "-",
            "상세 정보(한국어 요약)": "Coconala에서 '노동심판' 관련 근로자 측 변호사 서비스를 자동 수집하지 못했습니다. 검색어가 너무 구체적이거나 사이트 구조 변경으로 인한 문제일 수 있습니다."
        })

    df = pd.DataFrame(results)
    df.to_excel("labor_shimpan_coconala.xlsx", index=False)
    print(f"Saved {len(results)} items.")

if __name__ == "__main__":
    scrape_coconala()
