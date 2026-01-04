import cv2
import pandas as pd
import easyocr
import re
import os
from tqdm import tqdm
from datetime import timedelta

class CostcoScanner:
    def __init__(self, video_path, output_path, use_gpu=True):
        self.video_path = video_path
        self.output_path = output_path
        # Initialize EasyOCR reader (English + likely Korean if Costco Korea, or just English)
        # Assuming English for standard Costco, but adding 'ko' just in case based on user language
        self.reader = easyocr.Reader(['en', 'ko'], gpu=use_gpu)
        self.data = []
        self.seen_items = set()

    def process_video(self, frame_interval_sec=1.0):
        if not os.path.exists(self.video_path):
            print(f"Error: Video file not found at {self.video_path}")
            return

        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        print(f"Video Info: {duration:.2f} seconds, {fps} FPS, {total_frames} frames")
        
        # Calculate frames to skip
        skip_frames = int(fps * frame_interval_sec)
        
        current_frame = 0
        pbar = tqdm(total=total_frames)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Process frame only at intervals
            if current_frame % skip_frames == 0:
                self.process_frame(frame, current_frame / fps)

            current_frame += 1
            pbar.update(1)
            
            # Fast forward to next interval to save read time (optional optimization)
            # cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame + skip_frames)
            # current_frame += skip_frames
            # pbar.update(skip_frames)

        cap.release()
        pbar.close()
        self.save_excel()

    def process_frame(self, frame, timestamp):
        # OCR the frame
        # detail=0 returns just the list of strings
        results = self.reader.readtext(frame, detail=0)
        
        # Parse the text results
        parsed_item = self.parse_text(results)
        
        if parsed_item and parsed_item['product_number']:
            # Deduplicate by Product Number
            if parsed_item['product_number'] not in self.seen_items:
                parsed_item['timestamp'] = str(timedelta(seconds=int(timestamp)))
                self.data.append(parsed_item)
                self.seen_items.add(parsed_item['product_number'])
                print(f"Found Item: {parsed_item['product_number']} - {parsed_item['title']}")

    def parse_text(self, text_list):
        # Combine text for regex search
        full_text = " ".join(text_list)
        
        # Initialize fields
        item = {
            'product_number': None,
            'title': '',
            'price': None,
            'final_price': None,
            'remarks': ''
        }

        # 1. Extract Product Number (A column)
        # Costco items are usually 5-7 digits. distinct from price.
        # Often preceded by "Item" or just standalone.
        # Strategy: Find 5-7 digit number that is NOT a price (no decimals nearby usually)
        # Strict regex for Item #
        item_match = re.search(r'\b(\d{5,7})\b', full_text)
        if item_match:
            item['product_number'] = item_match.group(1)
        else:
            return None # Skip if no item number found (essential field)

        # 2. Extract Prices (C & D columns)
        # Look for patterns like 12,345 or 12.99 or 12,990 (KRW)
        # Regex for currency: possibly starting with currency symbol, numbers, comma/dot
        # KRW prices are large integers (e.g. 29,990). USD are decimals.
        # Assuming KRW based on user using Korean, but handling both.
        
        # Find all numbers that look like prices
        prices = re.findall(r'[\$₩]?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', full_text)
        
        # Clean prices (remove commas) and convert to float
        clean_prices = []
        for p in prices:
            try:
                val = float(p.replace(',', ''))
                if val > 100: # heuristic: prices usually aren't tiny numbers like "1" or "50" (unless USD)
                    clean_prices.append(val)
            except:
                continue
        
        if clean_prices:
            # Heuristic: Largest number is usually the price? Or separate normal vs discount.
            # If "Discount" or "-" is in text, handle distinct logic.
            max_price = max(clean_prices)
            min_price = min(clean_prices)
            
            if len(clean_prices) > 1 and ("-" in full_text or "할인" in full_text or "Discount" in full_text):
                item['price'] = max_price # Original Price
                item['final_price'] = min_price # Final Price
            else:
                item['price'] = max_price
                item['final_price'] = max_price

        # 3. Extract Title (B column)
        # Title is usually the longest text string or detected via exclusion of numbers
        # This is hard with simple regex. taking the text list excluding numbers.
        title_parts = [t for t in text_list if not re.search(r'\d', t)]
        item['title'] = " ".join(title_parts[:3]) # Take first few non-number words
        
        # 4. Remarks (E column) - Dates, Discounts
        # Look for dates
        dates = re.findall(r'\d{1,2}/\d{1,2}(?:/\d{2,4})?', full_text)
        if dates:
            item['remarks'] = f"Date: {' ~ '.join(dates)}"
        
        if "할인" in full_text or "OFF" in full_text:
            item['remarks'] += " [Discounted]"

        return item

    def save_excel(self):
        if not self.data:
            print("No data extracted.")
            return

        df = pd.DataFrame(self.data)
        # Reorder columns
        df = df[['product_number', 'title', 'price', 'final_price', 'remarks', 'timestamp']]
        df.columns = ['상품 번호', '상품 제목', '상품 가격', '최종 가격', '비고', '타임스탬프']
        
        df.to_excel(self.output_path, index=False)
        print(f"Data saved to {self.output_path}")

if __name__ == "__main__":
    # Example Usage
    # Update these paths
    VIDEO_PATH = "path/to/your/video.mp4" 
    OUTPUT_FILE = "costco_prices.xlsx"
    
    scanner = CostcoScanner(VIDEO_PATH, OUTPUT_FILE, use_gpu=True) # Set use_gpu=False if no CUDA
    scanner.process_video(frame_interval_sec=2.0) # Process every 2 seconds
