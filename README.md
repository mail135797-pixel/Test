## Search term / bulk metrics helper

This repo contains a small script to reproduce the metrics requested:

- **Nov search term report**: own product-targeting **CTR** and **CVR** (orders/clicks)
- **Dec search term report**: competitor product-targeting **sales**, **spend**, **ROAS**
- **Bulk file**: count of **enabled competitor product targets**

### Inputs

Place these files under `data/` (not committed; `data/` is gitignored):

- `data/asin_master.xlsx` (ASIN master list; column A = own ASINs)
- `data/search_terms_2025-11.xlsx`
- `data/search_terms_2025-12.xlsx`
- `data/bulk.xlsx`

### Run

```bash
python3 -m pip install -r requirements.txt
python3 scripts/compute_search_term_and_bulk_metrics.py
```

