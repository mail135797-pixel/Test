# Seller data processing and export

This repo contains a small script that aggregates the provided seller reports into two Excel outputs:

- `first_data.xlsx`: Before/After summary table (with diff and ratio)
- `second_data.xlsx`: Before/After sales totals for specific targeting buckets

## How to regenerate

Source files are expected under `data/raw/` (downloaded from the shared Google Drive/Sheets links).

Run:

```bash
python3 /workspace/generate_reports.py
```

It will write/overwrite:

- `/workspace/first_data.xlsx`
- `/workspace/second_data.xlsx`

