import streamlit as st
import os
import csv
from datetime import datetime
from dotenv import load_dotenv

# Import the new Brain
from src.agent_core import process_query

# --- Config & Setup ---
st.set_page_config(page_title="Enterprise Banking Agent", layout="wide", page_icon="🏦")

# --- UI Layout ---
st.title("🏦 Enterprise Banking Agent")
st.caption("💬 Your Intelligent Banking Assistant | Instant answers on products, policies, and services from SBI & HDFC")

# Sidebar
with st.sidebar:
    st.header("ℹ️ Need More Help?")
    st.markdown("""
    **For detailed assistance:**
    - 🌐 Visit your bank's website
    - 📞 Contact Customer Support:
      - **SBI**: 1800 425 3800
      - **HDFC**: 1800 266 4332
    - 🏢 Visit nearest branch
    """)
    
    st.divider()
    
    st.subheader("🔧 Session Controls")
    if st.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# Always use AUTO mode (intelligent routing)
selected_mode = "auto"

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Type your question here... e.g., 'How many SBI Cards?' or 'HDFC Biz Black benefits'"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking..."):
            # CALL THE NEW AGENT CORE WITH MODE PARAMETER
            try:
                response_obj = process_query(prompt, chat_history=st.session_state.messages, mode=selected_mode)
                
                # Check format
                if isinstance(response_obj, dict):
                    ans = response_obj.get("text", "No response text.")
                    source = response_obj.get("source", "")
                    data = response_obj.get("data")
                    metadata = response_obj.get("metadata", {})
                    
                    st.markdown(ans)
                    
                    # Show retrieval statistics
                    if metadata and metadata.get('sources_searched'):
                        sources_str = ", ".join(metadata.get('sources_searched', []))
                        st.caption(
                            f"📊 **Sources searched:** {sources_str} | "
                            f"**Found:** {metadata.get('sql_count', 0)} products, {metadata.get('faq_count', 0)} FAQs"
                        )
                    elif source:
                        st.caption(f"ℹ️ Source: {source}")
                        
                    if data:
                        with st.expander("📊 View Data Table"):
                            st.dataframe(data)
                            
                    # Add to session history
                    # We store just the text for history context, or maybe text + [Data Table Shown]
                    st.session_state.messages.append({"role": "assistant", "content": ans})

                else:
                    # Fallback for string
                    st.markdown(response_obj)
                    st.session_state.messages.append({"role": "assistant", "content": response_obj})

            except Exception as e:
                err_msg = f"⚠️ Agent Error: {str(e)}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})