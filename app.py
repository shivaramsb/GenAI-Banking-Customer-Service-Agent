import streamlit as st
import os
import csv
from datetime import datetime
from dotenv import load_dotenv

# Import the agent core
from src.agent_core import process_query
from src.config import SUPPORTED_BANKS

# --- Page Configuration ---
st.set_page_config(
    page_title="BankWise - Your AI Banking Advisor",
    layout="wide",
    page_icon="💼",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Professional Look (Dark/Light Mode Compatible) ---
st.markdown("""
<style>
    /* Main container - compact */
    .main {
        padding: 1rem;
    }
    
    /* Chat message styling - COMPACT */
    .stChatMessage {
        border-radius: 12px;
        padding: 8px 12px !important;
        margin: 6px 0 !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        border: 1px solid rgba(0, 0, 0, 0.05);
    }
    
    /* User message - subtle blue tint */
    .stChatMessage[data-testid="user-message"] {
        background: rgba(79, 172, 254, 0.1);
        border-left: 3px solid #4facfe;
    }
    
    /* Assistant message - neutral background */
    .stChatMessage[data-testid="assistant-message"] {
        background: rgba(100, 100, 100, 0.05);
        border-left: 3px solid #00f2fe;
    }
    
    /* Message content compact */
    .stChatMessage p {
        margin-bottom: 0.3rem !important;
        line-height: 1.5 !important;
    }
    
    /* Header styling - compact */
    h1 {
        font-weight: 700;
        padding-bottom: 0.3rem;
        margin-bottom: 0.5rem;
    }
    
    /* Caption compact */
    .stCaption {
        margin-top: 0 !important;
        font-size: 0.85rem !important;
    }
    
    /* Input box styling */
    .stChatInputContainer {
        border-radius: 25px;
        padding: 5px;
    }
    
    /* Primary buttons - blue gradient */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 10px 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(79, 172, 254, 0.3);
    }
    
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
    }
    
    /* Regular buttons - COMPACT */
    .stButton > button {
        border-radius: 15px;
        padding: 4px 12px !important;
        font-weight: 500;
        font-size: 0.85rem;
        transition: all 0.2s ease;
        min-height: 30px !important;
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 1.8em;
        font-weight: bold;
        color: #4facfe;
    }
    
    /* Sidebar styling - STICKY */
    section[data-testid="stSidebar"] {
        position: sticky;
        top: 0;
        height: 100vh;
        overflow-y: auto;
        padding: 1.5rem 1rem;
    }
    
    /* Sidebar content wrapper */
    section[data-testid="stSidebar"] > div {
        position: sticky;
        top: 0;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        border-radius: 10px;
        font-weight: 600;
    }
    
    /* Divider line - compact */
    hr {
        margin: 1rem 0;
        opacity: 0.2;
    }
    
    /* Column layout - reduce gaps */
    [data-testid="column"] {
        gap: 0.5rem !important;
    }
    
    /* Success/Error messages - compact */
    .stSuccess, .stError {
        padding: 0.3rem 0.6rem !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def log_feedback(message_idx, feedback_type, message_content):
    """Log user feedback for analytics"""
    try:
        log_file = "feedback_log.csv"
        file_exists = os.path.isfile(log_file)
        
        with open(log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'message_idx', 'feedback_type', 'message_preview'])
            writer.writerow([
                datetime.now().isoformat(),
                message_idx,
                feedback_type,
                message_content[:100]  # First 100 chars
            ])
    except Exception as e:
        pass  # Silent fail for logging

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback" not in st.session_state:
    st.session_state.feedback = {}

# --- Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("💼 BankWise")
    st.caption("Your Intelligent Banking Advisor • Instant Answers • Smart Recommendations")

with col2:
    st.markdown("###")
    banks_count = len(SUPPORTED_BANKS)
    st.metric("🏦 Banks", banks_count)

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bank-building.png", width=80)
    st.markdown("## 📊 About BankWise")
    st.markdown(f"""
    **BankWise** is your AI-powered banking assistant, providing instant answers about:
    
    - 💳 Credit & Debit Cards
    - 🏠 Loans & Mortgages  
    - 💰 Savings & Investments
    - 🔒 Security & Support
    
    **Currently supporting {banks_count} major banks** with comprehensive product information.
    """)
    
    st.divider()
    
    st.markdown("### 🔧 Tools")
    
    if st.button("🔄 New Conversation", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.session_state.feedback = {}
        st.rerun()
    
    if st.button("📥 Export Chat", use_container_width=True):
        if st.session_state.messages:
            chat_text = "\n\n".join([
                f"{'User' if msg['role']=='user' else 'BankWise'}: {msg['content']}"
                for msg in st.session_state.messages
            ])
            st.download_button(
                "💾 Download as TXT",
                chat_text,
                file_name=f"bankwise_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                use_container_width=True
            )
    
    st.divider()
    
    st.markdown("### 📞 Need Human Help?")
    st.markdown("""
    **Contact Support:**
    - 📧 support@bankwise.ai
    - 🌐 www.bankwise.ai
    - ⏰ 24/7 Available
    """)

# --- Chat History Display ---
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])
        
        # Show inline feedback buttons for assistant messages
        if msg["role"] == "assistant":
            feedback_key = f"feedback_{idx}"
            
            # Check if feedback already given
            if idx not in st.session_state.feedback:
                # Show buttons inline
                col1, col2 = st.columns([1, 11])
                with col1:
                    if st.button("👍", key=f"up_{idx}", help="Helpful"):
                        st.session_state.feedback[idx] = "positive"
                        log_feedback(idx, "positive", msg["content"])
                        st.rerun()
                with col2:
                    if st.button("👎", key=f"down_{idx}", help="Not helpful"):
                        st.session_state.feedback[idx] = "negative"
                        log_feedback(idx, "negative", msg["content"])
                        st.rerun()
            else:
                # Show feedback status compactly
                status = "✅ Helpful" if st.session_state.feedback[idx] == "positive" else "❌ Not helpful"
                st.caption(f"*{status}*")

# --- Chat Input ---
if prompt := st.chat_input("💬 Ask me anything about banking products, loans, accounts, or services..."):
    # Add user message
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Generate response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🤔 Analyzing your question..."):
            try:
                response_obj = process_query(prompt, chat_history=st.session_state.messages, mode="auto")
                
                if isinstance(response_obj, dict):
                    ans = response_obj.get("text", "I apologize, but I couldn't generate a response.")
                    source = response_obj.get("source", "")
                    data = response_obj.get("data")
                    metadata = response_obj.get("metadata", {})
                    
                    # Display answer
                    st.markdown(ans)
                    
                    # Show sources
                    if metadata and metadata.get('sources_searched'):
                        sources_str = ", ".join(metadata.get('sources_searched', []))
                        st.caption(
                            f"📊 **Sources:** {sources_str} | "
                            f"**Results:** {metadata.get('sql_count', 0)} products, {metadata.get('faq_count', 0)} FAQs"
                        )
                    
                    # Show data table if available
                    if data:
                        with st.expander("📋 View Detailed Data", expanded=False):
                            st.dataframe(data, use_container_width=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": ans})
                    
                else:
                    st.markdown(response_obj)
                    st.session_state.messages.append({"role": "assistant", "content": response_obj})
                    
            except Exception as e:
                error_msg = "😔 I encountered an error. Please try rephrasing your question or contact support."
                st.error(error_msg)
                st.caption(f"*Error details: {str(e)}*")

# --- Welcome Message ---
if len(st.session_state.messages) == 0:
    with st.chat_message("assistant", avatar="🤖"):
        welcome_msg = """
        👋 **Welcome to BankWise!**
        
        I'm your intelligent banking advisor, ready to help you with:
        
        - 🔍 **Product Discovery**: Find the perfect credit card, loan, or account
        - 💡 **Smart Recommendations**: Get personalized suggestions based on your needs
        - 📊 **Detailed Comparisons**: Compare products side-by-side
        - ❓ **Instant Answers**: Get answers to common banking questions
        
        How can I assist you today?
        """
        st.markdown(welcome_msg)

