from bs4 import BeautifulSoup
import re

def parse_local_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    soup = BeautifulSoup(content, "html.parser")
    
    # Title
    title_element = soup.find("span", {"id": "productTitle"})
    title = title_element.get_text(strip=True) if title_element else "Title not found"
    
    # Bullet points
    bullet_points = []
    feature_bullets = soup.find("div", {"id": "feature-bullets"})
    if feature_bullets:
        for li in feature_bullets.find_all("li"):
            span = li.find("span", {"class": "a-list-item"})
            if span:
                text = span.get_text(strip=True)
                bullet_points.append(text)
    
    return {
        "Title": title,
        "Bullets": bullet_points
    }

if __name__ == "__main__":
    details = parse_local_file("page.html")
    print(f"Title: {details['Title']}")
    print("Bullets:")
    for bp in details['Bullets']:
        print(f"- {bp}")
    
    # Save info for next steps
    with open("product_info.txt", "w", encoding="utf-8") as f:
        f.write(f"Title: {details['Title']}\n")
        f.write("Bullets:\n")
        for bp in details['Bullets']:
            f.write(f"- {bp}\n")
