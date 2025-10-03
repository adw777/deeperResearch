import streamlit as st
import requests
import json
from typing import Generator

st.set_page_config(
    page_title="Legal Research Agent",
    page_icon="⚖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    .stChatMessage {
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-radius: 8px;
    }
    h1 {
        font-size: 2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #1a1a1a;
    }
    .subtitle {
        color: #666;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .status-step {
        padding: 0.75rem 1rem;
        background: #f8f9fa;
        border-left: 3px solid #0066cc;
        border-radius: 4px;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
        color: #333;
        font-family: monospace;
    }
    .response-text {
        line-height: 1.8;
        color: #1a1a1a;
        font-size: 1rem;
    }
    .response-text h1, .response-text h2, .response-text h3 {
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        color: #1a1a1a;
    }
    .response-text ul, .response-text ol {
        margin-left: 1.5rem;
        margin-bottom: 1rem;
    }
    .response-text li {
        margin-bottom: 0.5rem;
    }
    .cursor {
        display: inline-block;
        width: 2px;
        height: 1em;
        background: #0066cc;
        animation: blink 1s step-end infinite;
        margin-left: 2px;
    }
    @keyframes blink {
        50% { opacity: 0; }
    }
    .research-doc {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 1rem;
        margin-top: 1rem;
    }
    .doc-title {
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
    }
    .doc-content {
        background: white;
        border-radius: 4px;
        padding: 1rem;
        font-size: 0.85rem;
        line-height: 1.6;
        max-height: 400px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

API_URL = "http://localhost:8000"

if "messages" not in st.session_state:
    st.session_state.messages = []


def stream_research(query: str) -> Generator[dict, None, None]:
    """Stream research results from the API"""
    endpoint = f"{API_URL}/research/stream"
    
    try:
        response = requests.post(
            endpoint,
            json={"query": query},
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=300
        )
        
        if response.status_code != 200:
            yield {"type": "error", "content": f"API Error: {response.status_code}"}
            return
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        yield data
                    except json.JSONDecodeError:
                        continue
    
    except requests.exceptions.RequestException as e:
        yield {"type": "error", "content": f"Connection error: {str(e)}"}


def format_step(event_type: str, data: dict) -> str:
    """Format step messages"""
    if event_type == "status":
        return data.get("content", "")
    elif event_type == "node_completed":
        node = data.get('node', '').replace('_', ' ').replace('.', ' > ')
        return f"Completed: {node}"
    elif event_type == "streaming_node":
        node = data.get('node', '').replace('_', ' ')
        return f"Generating response from: {node}"
    return ""


# Header
st.title("Legal Research Agent")
st.markdown('<p class="subtitle">Advanced research for Indian legal queries</p>', unsafe_allow_html=True)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(f'<div class="response-text">{message["content"]}</div>', unsafe_allow_html=True)
        
        if message.get("files"):
            for filename, content in message["files"].items():
                st.markdown(f"""
                <div class="research-doc">
                    <div class="doc-title">{filename}</div>
                    <div class="doc-content">{content}</div>
                </div>
                """, unsafe_allow_html=True)

# Chat input
query = st.chat_input("Enter your legal question...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    
    with st.chat_message("user"):
        st.markdown(query)
    
    with st.chat_message("assistant"):
        steps_container = st.container()
        response_container = st.container()
        
        full_response = ""
        research_files = {}
        should_render_response = False
        steps = []
        
        with steps_container:
            steps_placeholder = st.empty()
        
        with response_container:
            response_placeholder = st.empty()
        
        try:
            for event in stream_research(query):
                event_type = event.get("type")
                
                # Only show steps before streaming_node
                if not should_render_response:
                    if event_type in ["status", "node_completed"]:
                        step_msg = format_step(event_type, event)
                        if step_msg:
                            steps.append(step_msg)
                            steps_html = "".join([f'<div class="status-step">{step}</div>' for step in steps])
                            steps_placeholder.markdown(steps_html, unsafe_allow_html=True)
                    
                    elif event_type == "streaming_node":
                        should_render_response = True
                        step_msg = format_step(event_type, event)
                        if step_msg:
                            steps.append(step_msg)
                            steps_html = "".join([f'<div class="status-step">{step}</div>' for step in steps])
                            steps_placeholder.markdown(steps_html, unsafe_allow_html=True)
                
                # After streaming_node, render tokens
                if should_render_response:
                    if event_type == "token":
                        full_response += event.get("content", "")
                        response_placeholder.markdown(
                            f'<div class="response-text">{full_response}<span class="cursor"></span></div>',
                            unsafe_allow_html=True
                        )
                    
                    elif event_type == "complete":
                        research_files = event.get("files", {})
                        final_content = event.get("final_response", "")
                        if final_content:
                            full_response = final_content
                        
                        steps_placeholder.empty()
                        response_placeholder.markdown(
                            f'<div class="response-text">{full_response}</div>',
                            unsafe_allow_html=True
                        )
                        
                        if research_files:
                            for filename, content in research_files.items():
                                st.markdown(f"""
                                <div class="research-doc">
                                    <div class="doc-title">{filename}</div>
                                    <div class="doc-content">{content}</div>
                                </div>
                                """, unsafe_allow_html=True)
                    
                    elif event_type == "error":
                        steps_placeholder.empty()
                        error_msg = event.get('content', 'Unknown error')
                        response_placeholder.error(f"Error: {error_msg}")
                        full_response = error_msg
        
        except Exception as e:
            steps_placeholder.empty()
            error_msg = f"Failed to complete research: {str(e)}"
            response_placeholder.error(error_msg)
            full_response = error_msg
    
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "files": research_files
    })
    
    st.rerun()


# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown("""
    Advanced research agent for Indian legal queries.
    
    **Capabilities:**
    - Case law research
    - Statutory analysis
    - Legal precedents
    - Comparative analysis
    
    **Usage:**
    1. Enter your legal question
    2. Wait for research completion
    3. Review analysis and citations
    """)
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown(f"**API:** {API_URL}")

st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #666; font-size: 0.85rem;">Legal Research Agent v0.1</p>',
    unsafe_allow_html=True
)