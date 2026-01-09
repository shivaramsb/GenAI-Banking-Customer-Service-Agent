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

# --- Custom CSS for Professional Look ---
st.markdown("""
<style>
    /* Main container */
    .main {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        background-attachment: fixed;
    }
    
    /* Chat container */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    /* Header styling */
    h1 {
        color: #ffffff;
        font-weight: 700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95);
    }
    
    /* Input box */
    .stChatInputContainer {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 25px;
        padding: 10px;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 10px 25px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    
    /* Feedback buttons */
    .feedback-container {
        display: flex;
        gap: 10px;
        margin-top: 10px;
        justify-content: flex-end;
    }
    
    /* Caption text */
    .caption-text {
        color: #ffffff;
        font-size: 1.1em;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback" not in st.session_state:
    st.session_state.feedback = {}

# --- Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("💼 BankWise")
    st.markdown('<p class="caption-text">Your Intelligent Banking Advisor • Instant Answers • Smart Recommendations</p>', unsafe_allow_html=True)

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
        
        # Show feedback buttons for assistant messages
        if msg["role"] == "assistant":
            feedback_key = f"feedback_{idx}"
            
            col1, col2, col3 = st.columns([10, 1, 1])
            with col2:
                if st.button("👍", key=f"thumbs_up_{idx}", help="Helpful answer"):
                    st.session_state.feedback[idx] = "positive"
                    # Log feedback (could save to database)
                    log_feedback(idx, "positive", msg["content"])
                    st.success("Thanks for your feedback!")
                    
            with col3:
                if st.button("👎", key=f"thumbs_down_{idx}", help="Not helpful"):
                    st.session_state.feedback[idx] = "negative"
                    log_feedback(idx, "negative", msg["content"])
                    st.error("Thanks! We'll improve our answers.")
            
            # Show if feedback was given
            if idx in st.session_state.feedback:
                feedback_icon = "✅ Helpful" if st.session_state.feedback[idx] == "positive" else "❌ Not helpful"
                st.caption(f"*{feedback_icon}*")

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
        
        **Try asking:**
        - "What are the best travel credit cards?"
        - "Compare home loan options"
        - "How do I apply for a personal loan?"
        
        How can I assist you today?
        """
        st.markdown(welcome_msg)

