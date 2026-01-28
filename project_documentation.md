# BankWise: Project Documentation

**An Intelligent, Context-Aware Banking Assistant**

## 1. Project Overview
**BankWise** is a production-grade Generative AI banking assistant designed to answer customer queries with **guaranteed accuracy** for factual data (like interest rates and fees) while maintaining a natural, conversational flow.

Unlike standard chatbots that hallucinate numbers, BankWise uses a **Hybrid Architecture** that combines:
1.  **Deterministic SQL Layer**: For strict facts (Count, List, Explain Product).
2.  **Vector Search (RAG)**: For procedural FAQs (How to apply, Eligibility).
3.  **LLM (ChatGPT)**: For conversational glue, comparison, and synthesis.

---

## 2. System Architecture

The system follows a **Router-Retriever-Generator** pattern:

### A. The Smart Router (`src/smart_router.py`)
This is the "Brain" of the system. It classifies user queries into intents using a waterfall approach:
1.  **Context Check**: Checks history (e.g., Are we talking about SBI?).
2.  **Strict Signals**: If query contains "list", "count" -> **SQL Handler**.
3.  **Smart Fork (Implicit List)**: If query is "Credit Cards" + Context(SBI) -> **SQL Handler**.
4.  **Evidence Check**: Queries DB and Vector Store in parallel to see where the answer lies.
5.  **Fallback**: Sends to LLM if ambiguous.

### B. The Truth Layer (`src/database.py`)
- **Technology**: SQLite (structured data).
- **Purpose**: Stores the "Product Catalog" (Credit Cards, Loans).
- **Why**: Ensures that when a user asks "Fees for SBI Card", they get the *exact* number from the database, not an LLM guess.

### C. The Knowledge Layer (`src/vector_db.py`)
- **Technology**: ChromaDB.
- **Purpose**: Stores unstructured FAQs ("How do I block my card?").
- **Ingestion**: Converts text FAQs into vectors for semantic search.

### D. The Application Layer (`app.py`)
- **Frontend**: Streamlit.
- **Features**:
    - **Session State**: Remembers conversation history.
    - **Dynamic UI**: Renders data tables for lists, markdown for chats.
    - **Feedback System**: Allows users to rate responses.

---

## 3. Core Features & Logic

### 1. Context-Aware "Smart Fork"
*Solved the "Vague Query" problem.*
- **Problem**: User says "Debit cards". Standard bots ask "Which bank?".
- **Solution**:
    - If user previously said "SBI", system **infers** "List SBI Debit Cards".
    - It promotes the intent to `LIST` and fetches real data.
    - If no context exists, it falls back to a clarification prompt.

### 2. Evidence-Based Routing
*Solved the "Hallucination" problem.*
- Before answering "How many cards...", the system runs a **Pre-computation**:
    - `SELECT COUNT(*) FROM products...`
- If count > 0, it routes to the **SQL Handler**.
- It decides based on *data existence*, not just keywords.

### 3. Deep Follow-up Handling (`src/followup_router.py`)
*Solved the "Drill-down" problem.*
- **User**: "List SBI Cards" -> **Bot**: Shows 10 cards.
- **User**: "Explain the first one" -> **Bot**: Explains Card #1.
- **Logic**: The system maps ordinal words ("first", "second") to the index of the previously displayed list in memory.

### 4. Dynamic Data Ingestion (`src/ingest_dynamic.py`)
*Solved the "Fragile Pipeline" problem.*
- **Zero-Code Ingestion**: You can drop *any* CSV/Excel file into `data/products`.
- **LLM-Powered Mapping**:
    - The system reads the header row.
    - Uses an LLM to map weird columns (e.g., "Annual Chrg") to standard schema (`fees`).
    - Automatically detects Bank Name and Product Category.

---

## 4. Workflows

### Ingestion Flow
1.  Drop file `sbi_cards.csv` into `data/`.
2.  Run `python src/ingest_dynamic.py`.
3.  System detects bank "SBI", maps columns, and inserts into SQLite.

### Query Flow (Example: "SBI Credit Cards")
1.  **User Input**: "SBI Credit Cards"
2.  **Smart Router**:
    - Detects Entity: `Bank=SBI`, `Category=Credit Card`.
    - Checks Evidence: `DB_Count > 0`.
    - Decision: **LIST Intent**.
3.  **Agent Core**:
    - Calls `handle_list_query`.
    - Fetches data from SQLite.
4.  **Response Formatter**:
    - Formats data into a clean Markdown table.
5.  **UI**: Displays table to user.

---

## 5. Folder Structure
- `src/`: Source code.
    - `agent_core.py`: Main controller.
    - `smart_router.py` & `evidence_router.py`: Classification logic.
    - `database.py`: SQL operations.
- `data/`: Raw input files (CSV/Excel).
- `chromadb_data/`: Valid Vector Indices (Do not delete).
- `app.py`: Streamlit frontend entry point.

---

## 6. Future Capabilities
- **Transaction Support**: Integration with mock APIs to perform actions (transfer money).
- **Voice Interface**: Adding Speech-to-Text.
- **Multi-Modal**: Analyzing images of bank statements.
