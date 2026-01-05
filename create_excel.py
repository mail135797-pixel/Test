import pandas as pd
import json
import sys

def create_excel(json_file, output_file):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Ensure data is a list of dictionaries
        if not isinstance(data, list):
            print("Error: JSON data must be a list of objects.")
            return

        # Prepare data for DataFrame
        # A: Product Title, B: Product Number, C: Product Price, D: Final Price, E: Remarks
        df_data = []
        for item in data:
            df_data.append({
                '상품 제목': item.get('title', ''),
                '상품 번호': item.get('number', ''),
                '상품 가격': item.get('price', ''),
                '최종 가격': item.get('final_price', ''),
                '비고': item.get('remarks', '')
            })

        df = pd.DataFrame(df_data)
        
        # Reorder columns to match requirements
        columns = ['상품 제목', '상품 번호', '상품 가격', '최종 가격', '비고']
        # Add missing columns if any
        for col in columns:
            if col not in df.columns:
                df[col] = ''
        
        df = df[columns]
        
        df.to_excel(output_file, index=False)
        print(f"Excel file created: {output_file}")
        
    except Exception as e:
        print(f"Error creating Excel file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_excel.py <json_file> <output_file>")
    else:
        create_excel(sys.argv[1], sys.argv[2])
