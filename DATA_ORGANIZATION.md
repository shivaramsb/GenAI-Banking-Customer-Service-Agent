# Organized Data Folder Structure

## New Structure

```
data/
├── products/          ← All product files go here
│   ├── hdfc_products.csv
│   ├── sbi_products.csv
│   ├── test.csv (ICICI)
│   └── [any new bank products]
│
├── faqs/             ← All FAQ files go here
│   ├── hdfc_faq.csv
│   ├── sbi_faq.csv
│   ├── icici_faq.csv
│   └── [any new bank FAQs]
│
└── docs/             ← Unstructured documents (if any)
```

## Benefits

✅ **Better Organization**: Clearly separated products and FAQs
✅ **Easier to Navigate**: Find files quickly
✅ **Scalable**: Add 100 banks without clutter
✅ **Zero Name Conflicts**: No more filtering by `*_faq.csv` pattern

## How to Add New Data

### Adding Products
```bash
# Drop CSV/Excel/JSON files into data/products/
data/products/axis_products.csv
data/products/kotak_products.xlsx
data/products/newbank.json
```

### Adding FAQs
```bash
# Drop FAQ CSV files into data/faqs/
data/faqs/axis_faq.csv
data/faqs/kotak_faq.csv
```

### Run Ingestion
```bash
python src/ingest_dynamic.py
```

## What Changed in Code

**Updated Files:**
1. ✅ `config.py` - Added `PRODUCTS_DIR` and `FAQS_DIR` paths
2. ✅ `ingest_dynamic.py` - Updated to search in new folders
3. ✅ `icici_faq.csv` - Fixed CSV quoting issue

**No Breaking Changes:**
- Old ingestion pipeline still works
- Database schema unchanged
- All existing queries work

## File Naming

### Products
**Any name works!** System auto-detects bank:
- ✅ `bankname_products.csv`
- ✅ `products_january.csv`
- ✅ `mydata.xlsx`
- ✅ `data.json`

### FAQs
**Any name works!** Just put in `faqs/` folder:
- ✅ `bankname_faq.csv`
- ✅ `faqs.csv`
- ✅ `questions.csv`

**Required columns**: `bank_name`, `category`, `question`, `answer`

## Migration Complete ✅

All files moved to organized structure!
System now uses subfolder-based organization.
