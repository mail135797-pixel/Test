# Costco JP price-card extractor (video → cropped cards → PDF)

This repo contains a small script that scans a video and extracts **Costco Japan price cards** as cropped images, removes duplicates, and outputs a single PDF.

## Output (experiment: first 5 minutes)

- `deliverables/costco_price_cards_first_5min.pdf`

## How to run

```bash
pip3 install --upgrade gdown opencv-python-headless numpy pillow imagehash tqdm
python3 scripts/extract_price_cards.py \
  --video "/path/to/video.mp4" \
  --out-dir "./output/run_1" \
  --minutes 5 \
  --sample-interval 0.5
```

The script writes:
- `output/run_1/costco_price_cards_first_5min.pdf`
- `output/run_1/crops/*.png`
- `output/run_1/metadata.json`

