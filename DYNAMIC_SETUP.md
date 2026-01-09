# Dynamic Ingestion Setup

## Quick Start

### 1. Install New Dependencies

```bash
pip install fuzzywuzzy python-Levenshtein openpyxl
```

### 2. Test with Sample Data

Create a test file `data/test_bank.csv`:

```csv
Bank,Product,Type,Fee,Benefits
TestBank,Test Card,Credit Card,Rs. 500,5% cashback
TestBank,Test Loan,Loan,Rs. 1000,Low interest
```

### 3. Run Dynamic Ingestion

```bash
python src/ingest_dynamic.py
```

### 4. Check Results

```bash
python -c "from src.config import SUPPORTED_BANKS, PRODUCT_CATEGORIES; print('Banks:', SUPPORTED_BANKS); print('Categories:', PRODUCT_CATEGORIES)"
```

You should see `TestBank` in the list!

---

## What's New

### Files Created
- ✅ `src/dynamic_utils.py` - Intelligent detection utilities
- ✅ `src/ingest_dynamic.py` - Enhanced ingestion pipeline

### Files Modified
- ✅ `requirements.txt` - Added fuzzy matching libraries
- ✅ `src/config.py` - Dynamic bank/category registries

### Old Files (Still Work)
- ⏸️ `src/ingest_pipeline.py` - Original ingestion (backup)
- ⏸️ `src/column_mappings.py` - Manual mappings (fallback)

---

## Migration Path

**Option A: Keep Both**
- Use `ingest_dynamic.py` for new banks
- Use `ingest_pipeline.py` for existing HDFC/SBI

**Option B: Full Migration**
- Switch all ingestion to `ingest_dynamic.py`
- Keep `ingest_pipeline.py` as backup

---

## Features Implemented

✅ **Bank Detection**
- Filename pattern matching
- Content keyword search
- LLM analysis

✅ **Column Mapping**
- Fuzzy matching (70%+ similarity)
- LLM fallback for unknown columns
- Confidence scoring

✅ **Unlimited Columns**
- Dynamic JSON `attributes` storage
- Preserves all data (100+ columns supported)

✅ **Edge Cases**
- Headerless CSV (LLM infers headers)
- Duplicate products (upsert logic)
- Non-CSV formats (Excel, JSON)

✅ **Dynamic Registries**
- Banks auto-discovered from database
- Categories auto-discovered from database
- No hardcoded lists!

---

## Testing Checklist

- [ ] Install dependencies
- [ ] Run on existing HDFC/SBI data (verify compatibility)
- [ ] Add test file with different column names
- [ ] Add test file with unknown bank
- [ ] Check logs for mapping confidence
- [ ] Verify database has new bank/products
- [ ] Test chatbot with new bank queries

---

## Rollback Plan

If issues occur:

1. Use original ingestion:
   ```bash
   python src/ingest_pipeline.py
   ```

2. Revert config.py:
   ```python
   SUPPORTED_BANKS = ['SBI', 'HDFC']  # Back to hardcoded
   ```

---

## Next Steps

1. **Test with real Axis/ICICI data**
2. **Monitor logs for mapping accuracy**
3. **Add more bank display names** in `config.py` if needed
4. **Consider building admin UI** for manual column mapping override
