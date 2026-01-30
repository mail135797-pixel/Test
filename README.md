# Costco Video Analysis

## Results

### Video Analysis (Single Video Test)
- **Source**: `https://drive.google.com/file/d/1tkRQ3vm1u3XOhOk6HBBCQEjshqGd6C3J/view`
- **Duration**: 54.81 seconds
- **Frames Extracted**: 55 (1 per second)

### Output Files
1.  **Excel**: `cursor_output/products.xlsx` - Contains extracted product data (Title, Item #, Price, Final Price, Remarks).
2.  **PDF**: `cursor_output/frames.pdf` - Compiled frames from the video.

## Usage

1.  **Prerequisites**:
    - Install dependencies:
      ```bash
      pip install -r requirements.txt
      ```
    - **Google Drive Upload (OAuth 2.0)**:
      - This project uses OAuth 2.0 to upload files to Google Drive using your personal account quota.
      - **Step 1**: Download your OAuth 2.0 Client Secret JSON file from Google Cloud Console.
      - **Step 2**: Rename the file to `client_secret.json` and place it in the project root directory.
      - **Step 3**: The first time you run the script, a browser window will open asking you to authorize the app.
      - **Step 4**: After authorization, a `token.json` file will be created automatically for future runs.

2.  **Run the analysis**:
    ```bash
    python analyze_video.py
    ```
    - This script will:
      1. Download the video.
      2. Extract frames and create a PDF.
      3. Generate the Excel file with product data.
      4. Upload the Excel and PDF files to Google Drive folder `1_LafaOLXNuTjJPdgyCCnuw_J4UgZYzjD`.

## Security Note
- `client_secret.json` and `token.json` are added to `.gitignore` to prevent accidental commit of credentials to the repository.
