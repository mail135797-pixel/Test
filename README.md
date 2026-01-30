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
    - **Google Drive Upload (Optional)**:
      - Place your Google Service Account Key file in the project root directory.
      - Rename the file to `service_account.json`.
      - Ensure the service account has "Editor" access to the target Google Drive folder.

2.  **Run the analysis**:
    ```bash
    python analyze_video.py
    ```
    - This script will:
      1. Download the video.
      2. Extract frames and create a PDF.
      3. Generate the Excel file with product data.
      4. Automatically upload the Excel and PDF files to Google Drive if `service_account.json` is present.

## Security Note
- `service_account.json` is added to `.gitignore` to prevent accidental commit of credentials to the repository.

