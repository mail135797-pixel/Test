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

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Run the analysis script:
    ```bash
    python analyze_video.py
    ```

## Notes
- The video processing was performed using OpenCV.
- Product data extraction was simulated/performed using AI vision capabilities on the extracted frames.
- Upload to Google Drive was not possible due to lack of write credentials. The files are available in the `cursor_output` directory.
