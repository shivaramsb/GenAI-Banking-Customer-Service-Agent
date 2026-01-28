You are a Senior Solution Architect + Lead AI Engineer. Build an enterprise-style Proof-of-Concept (PoC) “Banking Customer Chatbot” that supports multiple banks and uses a dynamic, ingestion-based architecture.

========================
1) PROJECT GOAL
========================
Build a conversational chatbot "BankWise" that reduces call center workload by answering banking product + FAQ queries.

It must support:
- COUNT queries (Exact numbers)
- LIST queries (Complete lists)
- EXPLAIN queries (Single product details)
- EXPLAIN ALL (All products in a category)
- COMPARE (Between products)
- RECOMMEND (Best product for need)
- FAQ (Procedures, policies)
- GREETING + Small talk
- CONTEXT SWITCHING (Changing banks mid-conversation)

Primary Requirement:
- **Accuracy-Critical Routing**: COUNT/LIST/EXPLAIN_ALL must be handled by deterministic Python logic (SQL-based), NEVER by the LLM alone.
- **Smart Fork Logic**: If a user has established a bank context (e.g., "SBI"), a vague query like "debit cards" must be automatically promoted to a strict "LIST SBI Debit Cards" intent.
- **Dynamic Config**: No hardcoded bank names in code. Using a database to discover available banks.

========================
2) DATA SOURCES & INGESTION
========================
Input data is located in:
- `data/products/`: Flat folder containing CSV/Excel/JSON files.
- `data/faqs/`: Flat folder containing CSV files.

**Ingestion Pipeline (`src/ingest_dynamic.py`)**:
- Must support **Zero-Code Ingestion**. Placing a new file (e.g., `axis_loans.csv`) should automatically make it available after running the script.
- **Smart Detection**:
  - Detect Bank Name and Category from file content/filename.
  - Map various column names (e.g., "Ann. Fee", "Annual Charges") to a standard schema using LLM-based inference.
- **Storage**:
  - **Structured Data**: SQLite (`banking_assistant.db`) -> Table `products`.
  - **Unstructured Data**: ChromaDB (`chromadb_data/`) -> Collection `bank_faqs`.

========================
3) SYSTEM ARCHITECTURE (Hybrid Router)
========================
Implement a robust **Router-Retriever-Generator** pattern:

**Layer 1: Smart Router (`src/smart_router.py`)**
- Acts as the entry point.
- **Step 1: Entity Extraction**: Uses DB to identify Bank/Category entities (0ms latency).
- **Step 2: Context Management**: Checks `HistoryStateManager` for active bank context.
- **Step 3: Accuracy Check**: If intent is COUNT/LIST/EXPLAIN_ALL, bypass LLM and route to `src/agent_core.py` handlers.
- **Step 4: Evidence Check (`src/evidence_router.py`)**:
    - Parallel query to DB `SELECT COUNT(*)` and Vector Store.
    - If `db_count > 0` and query implies a list, force LIST intent.
    - If `faq_score > 0.6`, force FAQ intent.
- **Step 5: Fallback**: If ambiguous, send to ChatGPT.

**Layer 2: Agent Core (`src/agent_core.py`)**
- Orchestrates the response.
- **Handlers**:
  - `handle_count_query`: Returns exact count.
  - `handle_list_query`: Returns Markdown table.
  - `handle_explain_query`: Returns detailed breakdown.
  - `chatgpt_query`: Handles natural conversation (FAQ/Compare/Recommend).

========================
4) FUNCTIONAL REQUIREMENTS
========================
**A. Deterministic Intents (SQL-Backed)**
1.  **COUNT**: "How many SBI cards?" -> `SELECT COUNT(*)...` (Pure Python).
2.  **LIST**: "List HDFC loans" -> Render Markdown Table (Pure Python).
3.  **IMPLICIT LIST (Smart Fork)**: "SBI" (Context) + "Credit Cards" -> Treat as LIST.

**B. Conversational Intents (LLM-Backed)**
1.  **EXPLAIN**: "Tell me about SBI Aurum" -> Retrieve SQL row -> LLM formats text.
2.  **COMPARE**: Retrieval -> Context -> LLM Comparison.
3.  **FAQ**: Retrieval (ChromaDB) -> LLM Synthesis.

**C. Follow-up Logic (`src/followup_router.py`)**
- Support "Virtual Query Rewriting".
- **Ordinal Selection**: "Explain the first one" -> Maps "first" to Index 0 of `last_product_list` in session state.
- **Context Retention**: "Why?" -> Uses `last_intent` and `last_response` to generate a relevant answer.

========================
5) USER INTERFACE
========================
**Frontend**: Streamlit (`app.py`)
- **Features**:
  - Chat interface (User/Bot).
  - Sidebar with "About" and "Tools" (Export Chat, New Conversation).
  - **Visual Feedback**: Buttons for Thumbs Up/Down.
  - **Data Display**: Expandable "View Detailed Data" section for LIST/COUNT queries.
  - **Session State**: Persist chat history and feedback.

========================
6) KEY FILES & STRUCTURE
========================
- `src/config.py`: Central config, reads environment variables and DB paths.
- `src/database.py`: SQLite wrapper for upserts and queries.
- `src/vector_db.py`: ChromaDB wrapper.
- `src/response_formatters.py`: dedicated module for standardizing output (Markdown tables).
- `project_documentation.md`: Detailed architecture docs.

========================
7) NON-FUNCTIONAL
========================
- **Logging**: Dual logging (Console + `app_debug.log`).
- **Error Handling**: Graceful degradation (LLM fallback if DB fails).
- **Environment**: `.env` file for API keys (`OPENAI_API_KEY`).
