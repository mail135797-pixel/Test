# QC Report: B09SKLH2BW

## Status: FAILURE (Model Not Found)

### 1. Workflow Check
- [x] Step 1: PDP Snapshot (Manual verification due to anti-bot)
- [x] Step 2: Research (Completed)
- [x] Step 3: Storyboard (Completed)
- [x] Step 4: JP Copy (Completed)
- [x] Step 5: Prompts (Completed)
- [x] Step 6: Image Generation 
    - **Image 1**: Previously generated (Imagen 4.0).
    - **Image 2-8**: Failed. User requested `imagen-3.0-generate-001`, but API returned `404 NOT_FOUND` (Model not found).
- [x] Step 7: Text Overlay Script (Completed on placeholders)

### 2. Compliance Check (Copy)
- **Medical Claims**: Checked. No "cure" claims. "Pore Care" used as per title.
- **Safety**: "Gentle", "Moisturizing" used.
- **Brand**: "cos:mura" verified.

### 3. Image Plan Check
- **Main Image**: AI generated (Imagen 4.0 - kept from previous successful run).
- **Text on Image 1**: None.
- **Resolution**: 2000x2000.

### 4. Issues & Next Steps
- **Issue**: `imagen-3.0-generate-001` is not available for this API key/version, despite user instruction. Previous successful run used `imagen-4.0-generate-001`.
- **Action**: Check available models using `list_models.py` or revert to `imagen-4.0-generate-001` if acceptable.
- **Result**: 
    - `B09SKLH2BW_01.png`: AI Generated (Imagen 4.0).
    - `B09SKLH2BW_02`...`08`: Placeholder with text overlay.
