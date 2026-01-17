import pandas as pd
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import time
import os
import re
import sys

# ==========================================
# Configuration
# ==========================================
# Try to get API KEY from environment variable, otherwise ask user
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("\n[알림] Gemini API Key가 환경 변수에 설정되지 않았습니다.")
    GEMINI_API_KEY = input("Google AI Studio에서 발급받은 API Key를 입력해주세요: ").strip()
    if not GEMINI_API_KEY:
        print("API Key가 입력되지 않아 종료합니다.")
        sys.exit(1)

# Initialize the client with the new SDK
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    sys.exit(1)

# Model to use
MODEL_ID = 'gemini-2.0-flash-exp'

def get_video_id(url):
    """Extract video ID from URL"""
    match = re.search(r'(?:v=|\/shorts\/)([\w-]+)', url)
    return match.group(1) if match else None

def get_transcript(video_id):
    """Fetch transcript with robust fallback strategy"""
    try:
        # 1. List all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        transcript = None
        
        # 2. Try Manual transcripts in preference order
        try:
            transcript = transcript_list.find_manually_created_transcript(['ko', 'en', 'ja'])
        except:
            pass
            
        # 3. If no manual, try Auto-generated in preference order
        if not transcript:
            try:
                transcript = transcript_list.find_generated_transcript(['ko', 'en', 'ja'])
            except:
                pass
        
        # 4. If still nothing, try ANY available transcript
        if not transcript:
            try:
                transcript = next(iter(transcript_list))
            except:
                return None
                
        if transcript:
            formatter = TextFormatter()
            return formatter.format_transcript(transcript.fetch())
            
    except Exception as e:
        # print(f"Transcript fetch error: {e}")
        return None
    return None

def summarize_text(text):
    """Summarize full transcript using new SDK"""
    if not text:
        return None
    
    # Gemini 2.0 Flash has a large context window, but being safe with 30k chars is fine for summaries
    truncated_text = text[:50000] 
    prompt = f"""
    아래는 유튜브 동영상의 자막 스크립트입니다. 
    이 내용을 바탕으로 동영상의 핵심 내용을 한국어로 1000자 내외로 요약 정리해주세요.
    
    [자막 내용]
    {truncated_text}
    
    [요약]
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"요약 생성 실패: {str(e)}"

def summarize_metadata_only(title, link):
    """Fallback: Generate description based on title only using new SDK"""
    prompt = f"""
    나는 유튜브 동영상 리스트를 정리하고 있는데, 이 영상의 자막을 구할 수 없어.
    
    제목: '{title}'
    링크: {link}
    
    이 제목을 보고 어떤 내용일지 유추해서 3~5문장으로 설명해줘.
    (반드시 "자막이 없어 제목을 기반으로 추측한 내용입니다"라고 명시할 것)
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"메타데이터 요약 실패: {str(e)}"

# ==========================================
# Main Process
# ==========================================

input_filename = 'JennyJeon_Videos.xlsx'
output_filename = 'JennyJeon_Videos_Summarized_Final.xlsx'

# Check if input file exists in current directory
if not os.path.exists(input_filename):
    print(f"Error: '{input_filename}' 파일을 찾을 수 없습니다.")
    print("스크립트와 같은 폴더에 엑셀 파일이 있는지 확인해주세요.")
    sys.exit(1)

print(f"Reading {input_filename}...")
try:
    df = pd.read_excel(input_filename)
    print(f"Loaded {len(df)} videos.")
except Exception as e:
    print(f"Error reading Excel file: {e}")
    sys.exit(1)

# Ensure columns exist
if '동영상 내용 정리' not in df.columns:
    df['동영상 내용 정리'] = ""

print(f"Starting processing using {MODEL_ID}...")
print("Press Ctrl+C to stop safely.")

save_interval = 5

try:
    for index, row in df.iterrows():
        link = row['링크']
        title = row['동영상 제목']
        
        # Skip if link is empty
        if pd.isna(link):
            continue

        video_id = get_video_id(link)
        if not video_id:
            continue
            
        print(f"[{index+1}/{len(df)}] Processing: {title[:30]}...")
        
        # 1. Try Transcript
        transcript = get_transcript(video_id)
        
        if transcript:
            print("  -> Transcript found! Generating summary...")
            summary = summarize_text(transcript)
            df.at[index, '동영상 내용 정리'] = summary
        else:
            print("  -> No transcript found. Generating metadata summary...")
            summary = summarize_metadata_only(title, link)
            df.at[index, '동영상 내용 정리'] = summary

        # Delay to prevent API rate limits
        time.sleep(2) 

        if (index + 1) % save_interval == 0:
            df.to_excel(output_filename, index=False)
            print(f"  -> Progress saved to {output_filename}")

except KeyboardInterrupt:
    print("\nStopped by user. Saving current progress...")

# Final save
try:
    df.to_excel(output_filename, index=False)
    print(f"\nDone! Successfully saved to {output_filename}")
except Exception as e:
    print(f"Error saving final file: {e}")
