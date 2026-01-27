import subprocess
import time
import random
import urllib.parse

keyword = "コゲ落とし ジェル"
encoded_keyword = urllib.parse.quote(keyword)

base_url = "https://www.amazon.co.jp/s"

for page in range(1, 4):
    url = f"{base_url}?k={encoded_keyword}&page={page}"
    output_file = f"search_page_{page}.html"
    
    print(f"Fetching page {page}: {url}")
    
    # Use curl via subprocess
    cmd = [
        "curl",
        "-L",
        url,
        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "-o", output_file
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Saved {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error fetching page {page}: {e}")
    
    # Sleep to be polite
    time.sleep(random.uniform(5, 10))
