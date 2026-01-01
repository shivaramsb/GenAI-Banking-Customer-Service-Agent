# GenAI Banking Customer Service Agent 🏦

A production-ready, intelligent multi-bank customer service chatbot powered by GPT-4, combining structured SQL queries with semantic search to provide accurate, fast responses about banking products and services.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.24.0-FF4B4B)](https://streamlit.io/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-412991)](https://openai.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ Key Features

- **🚀 43% Faster Performance** - Optimized from 3.5s to 2.0s average response time
- **🏦 Multi-Bank Support** - Currently supports SBI & HDFC, unlimited scalability
- **🔄 Zero-Code Bank Addition** - Add new banks with just CSV files, no coding required
- **📊 Flexible CSV Schemas** - Support any column names via configuration
- **🤖 Hybrid AI Architecture** - Combines SQL precision with vector semantic search
- **💬 Context-Aware** - Remembers conversation history for natural dialogue
- **📈 Smart Recommendations** - Pre-filters products by user persona (students, travelers, etc.)
- **✅ List Completeness** - Guarantees 100% completeness, no AI truncation

---

## 🎯 What It Can Do

| Query Type | Example | Response Time |
|------------|---------|---------------|
| **Count** | "How many SBI credit cards?" | ~2.0s |
| **List** | "List all HDFC loans" | ~2.5s |
| **Compare** | "HDFC Millennia vs Swiggy card" | ~3.0s |
| **Recommend** | "Best credit card for students" | ~3.2s |
| **Procedural** | "How to apply for home loan?" | ~1.8s |

**Current Database:**
- 📦 114+ Banking Products
- 💬 846 FAQ Entries
- 🏦 2 Banks (SBI, HDFC)
- 📂 4 Categories (Credit Cards, Debit Cards, Loans, Schemes)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API Key (GPT-4 access)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/genai_cust_agent.git
cd genai_cust_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Initial Data Ingestion

```bash
# Ingest product data and FAQs
python src/ingest_pipeline.py
```

### Run the Application

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.

---

## 💡 Usage Examples

### In the Streamlit Web Interface:

**Simple Queries:**
```
User: How many SBI credit cards?
Bot: SBI offers 15 credit cards.

User: List all HDFC debit cards
Bot: Here are ALL 10 products found:
     1. HDFC Millennia Debit
     2. HDFC Platinum Debit
     ...
```

**Comparisons:**
```
User: Compare HDFC Millennia vs HDFC Swiggy
Bot: [Shows detailed comparison table with features, fees, rewards]
```

**Recommendations:**
```
User: Best credit card for students
Bot: 🥇 Best Choice: SBI SimplySave
     💰 Budget Option: HDFC Bharat
     [Filtered for low-fee cards suitable for students]
```

**Procedural Questions:**
```
User: How do I apply for HDFC credit card?
Bot: You can apply online via HDFC website or visit any HDFC branch...
```

---

## 🏦 Adding a New Bank (No Code Required!)

### Step 1: Prepare Your Data Files

Create two CSV files in the `data/` directory:

**`icici_products.csv`** (Example):
```csv
bank_name,category,product_name,features,fees,interest_rate,eligibility
ICICI,Credit Card,ICICI Coral,Cashback on dining,Rs. 500,3.5% p.m.,Income > 30k/month
ICICI,Debit Card,ICICI Platinum,International usage,Rs. 200,N/A,Account Holder
ICICI,Loan,ICICI Home Loan,Quick approval,0.5%,8.5%-9.5%,Salaried
```

**`icici_faq.csv`** (Example):
```csv
bank_name,category,question,answer
ICICI,Credit Cards,How to apply for credit card?,Visit ICICI website or branch...
ICICI,Loans,Documents for home loan?,Income proof, ID proof, property documents...
```

### Step 2: (Optional) Custom Column Names

If your CSV has different column names, define mapping in `src/column_mappings.py`:

```python
CUSTOM_COLUMN_MAPPINGS = {
    'ICICI': {
        'Bank Name': 'bank_name',
        'Product Type': 'category',
        'Name': 'product_name',
        # ... map your columns
    }
}
```

### Step 3: Ingest Data

```bash
python src/ingest_pipeline.py
```

**That's it!** The new bank is now available in the chatbot immediately.

---

## 🏗️ Architecture

```
┌─────────────┐
│  Streamlit  │  (Web UI)
│   Frontend  │
└──────┬──────┘
       │
┌──────▼──────────────┐
│  agent_core.py      │  (Query Orchestrator)
└──────┬──────────────┘
       │
┌──────▼──────────────────────┐
│  multi_retriever.py         │  (Hybrid Search)
└──┬────────────────────────┬─┘
   │                        │
   ▼                        ▼
┌──────────┐          ┌──────────┐
│ sql_tool │          │ vector_db│
│ (SQLite) │          │(ChromaDB)│
└──────────┘          └──────────┘
   │                        │
   ▼                        ▼
Products DB            FAQ Embeddings
(114 items)            (846 entries)
```

**Tech Stack:**
- **Frontend:** Streamlit
- **LLM:** OpenAI GPT-4
- **Databases:** SQLite (products) + ChromaDB (FAQs)
- **Embeddings:** SentenceTransformers (all-MiniLM-L6-v2)

---

## ⚡ Performance Optimizations

### Quick Wins Implemented:

1. **Skip Redundant Synthesis** (-1.5s)
   - Eliminates duplicate GPT calls in retrieval pipeline
   
2. **Persistent DB Connection** (-50ms)
   - Single connection reused across queries
   
3. **Database Indexing** (-30ms)
   - Optimized WHERE clauses with composite indexes

### Results:
- **Before:** 3.5s average latency
- **After:** 2.0s average latency
- **Improvement:** 43% faster! 🚀

---

## 📊 Project Structure

```
genai_cust_agent/
├── app.py                    # Streamlit web interface
├── src/
│   ├── agent_core.py        # Main query orchestrator
│   ├── multi_retriever.py   # Hybrid retrieval engine
│   ├── sql_tool.py          # SQL query generation
│   ├── vector_db.py         # FAQ semantic search
│   ├── database.py          # Product catalog management
│   ├── ingest_pipeline.py   # Data ingestion
│   ├── column_mappings.py   # Flexible CSV schemas
│   └── config.py            # Configuration
├── data/
│   ├── *_products.csv       # Product catalogs
│   ├── *_faq.csv           # FAQ databases
│   └── docs/                # Optional markdown docs
├── banking_assistant.db     # SQLite database
├── chromadb_data/          # Vector embeddings
└── requirements.txt
```

---

## 🧪 Testing & Verification

### Run Performance Tests
```bash
python src/verify_optimizations.py
```

### Run Comprehensive Test Suite
```bash
python comprehensive_test.py
```

### Clean Database
```bash
python cleanup_database.py
```

---

## 🔮 Future Roadmap

### Phase 2 Optimizations (Planned)
- [ ] Rule-based SQL for simple queries (save 0.8s)
- [ ] GPT-3.5 routing for medium queries (60% cost reduction)
- [ ] Response caching with Redis (instant for repeats)
- [ ] Async LLM calls (save 0.3s)
- [ ] Streaming responses (better UX)

### Feature Enhancements
- [ ] Multi-language support (Hindi, regional languages)
- [ ] Voice interface integration
- [ ] Product comparison tables
- [ ] Admin dashboard with analytics
- [ ] Mobile app API

---

## 📝 Configuration

### Environment Variables (`.env`)
```bash
OPENAI_API_KEY=sk-xxx         # Required: OpenAI API key
GROQ_API_KEY=gsk-xxx          # Optional: Alternative LLM
LLM_MODEL=gpt-4o              # Model to use
```

### System Config (`src/config.py`)
```python
SUPPORTED_BANKS = ['SBI', 'HDFC']
PRODUCT_CATEGORIES = ['Credit Card', 'Debit Card', 'Loan', 'Scheme']
DATA_DIR = "data"
DB_PATH = "banking_assistant.db"
```

---

## 🐛 Known Issues

### Minor Count Discrepancy
- **Issue:** COUNT queries may show different numbers than LIST queries
- **Status:** Documented, low impact
- **Workaround:** Use `cleanup_database.py` to remove duplicates

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Add New Banks:** Submit your CSV files via PR
2. **Improve Performance:** Suggest optimizations
3. **Report Bugs:** Open issues with details
4. **Documentation:** Enhance guides and examples

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Shivaram SB**

---

## 📚 Documentation

- [Complete Project Analysis](docs/project_analysis.md)
- [Adding New Banks Guide](docs/adding_new_banks_guide.md)
- [Flexible CSV Schema Guide](docs/flexible_csv_schema_guide.md)
- [Performance Walkthrough](docs/walkthrough.md)

---

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Streamlit for the amazing web framework
- ChromaDB for vector similarity search
- SentenceTransformers for embeddings

---

## 📞 Support

For questions or issues:
- Open a GitHub Issue
- Check the [Documentation](docs/)
- Review the [FAQ](docs/faq.md)

---

**⭐ Star this repository if you find it useful!**

---

*Last Updated: January 1, 2026*  
*Version: 2.0 (Performance Optimized)*
