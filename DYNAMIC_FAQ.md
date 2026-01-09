# Dynamic FAQ Handling

## Now FAQs Support Extra Columns Too! ✅

### What Changed

**Before:**
- FAQs **required** exactly 4 columns: `bank_name`, `category`, `question`, `answer`
- Extra columns caused errors
- Different column names not supported

**After:**
- FAQs **intelligently map** columns (like products)
- **Extra columns automatically preserved** in metadata
- **Different column names supported** via fuzzy matching

---

## FAQ Column Mapping

### Standard Column Names

The system recognizes these variations:

| System Field | Recognized Names |
|--------------|------------------|
| `bank_name` | bank, bank_name, bankname, institution |
| `category` | category, type, topic, subject |
| `question` | question, q, query, ask |
| `answer` | answer, a, response, reply, solution |

### Examples

**Example 1: Different Column Names**
```csv
Bank,Topic,Q,A
HDFC,Loans,How to apply?,Visit website...
```
✅ **Auto-mapped**: Bank→bank_name, Topic→category, Q→question, A→answer

**Example 2: Extra Columns**
```csv
bank_name,category,question,answer,priority,tags,updated_date
HDFC,Loans,How to apply?,Visit...,High,loan;apply,2024-01-09
```
✅ **Result**: 
- Core fields: bank_name, category, question, answer → Used normally
- Extra fields: priority, tags, updated_date → Stored in metadata

---

## Extra Fields Use Cases

### 1. Priority FAQs
```csv
bank_name,category,question,answer,priority
HDFC,Cards,Lost my card?,Call 1800...,HIGH
SBI,Loans,Interest rate?,Check website,MEDIUM
```

**Benefit**: Can filter by priority in future

### 2. Multi-Language FAQs
```csv
bank_name,category,question,answer,language,translated_question
HDFC,Cards,How to apply?,Visit...,Hindi,आवेदन कैसे करें?
```

**Benefit**: Store translations for future multi-lingual support

### 3. Tagged FAQs
```csv
bank_name,category,question,answer,tags,related_products
HDFC,Loans,Home loan documents?,ID proof...,documents;requirements,Home Loan
```

**Benefit**: Better search and filtering

### 4. Metadata
```csv
bank_name,category,question,answer,author,updated_date,verified
HDFC,Cards,Apply online?,Visit...,Support Team,2024-01-09,TRUE
```

**Benefit**: Track FAQ quality and freshness

---

## How It Works

### Ingestion Process

1. **Load CSV**
   ```
   Columns: Bank, Topic, Query, Reply, Priority, Tags
   ```

2. **Fuzzy Mapping**
   ```
   Bank → bank_name (80% match)
   Topic → category (90% match)
   Query → question (75% match)
   Reply → answer (85% match)
   ```

3. **Extract Extra**
   ```
   Priority → metadata
   Tags → metadata
   ```

4. **Store in ChromaDB**
   ```json
   {
     "question": "...",
     "answer": "...",
     "bank_name": "HDFC",
     "category": "Cards",
     "priority": "HIGH",
     "tags": "apply;online"
   }
   ```

---

## Testing

### Create Test FAQ with Extra Columns

`data/faqs/test_extra_faq.csv`:
```csv
Bank,Topic,Q,A,Priority,Tags
ICICI,Cards,How to block card?,Call 1800-200-3344,HIGH,security;block
ICICI,Loans,Document needed?,ID and income proof,MEDIUM,documents;requirements
```

### Run Ingestion
```bash
python src/ingest_dynamic.py
```

### Expected Output
```
📚 Processing 4 FAQ files...

  📄 test_extra_faq.csv
     Loaded 2 FAQs, 6 columns
     FAQ Mapped: 'Bank' → 'bank_name' (confidence: 80%)
     FAQ Mapped: 'Topic' → 'category' (confidence: 90%)
     FAQ Mapped: 'Q' → 'question' (confidence: 100%)
     FAQ Mapped: 'A' → 'answer' (confidence: 100%)
     Mapping confidence: 100%
  ✅ test_extra_faq.csv: 2 FAQs ingested
```

---

## Summary

**FAQs are now as dynamic as products!**

✅ **Required**: question, answer (minimum)
✅ **Optional**: bank_name, category
✅ **Unlimited**: Any extra columns you want!

**No code changes needed** - just add columns to your CSV! 🎉
