import streamlit as st
import asyncio
import os
import tempfile
from pynput.mouse import Controller as MouseController
from typer import DocumentRetyper, extract_text_from_docx

st.set_page_config(page_title="Document Retyper", page_icon="📝", layout="wide")

st.title("Document Retyper")
st.write("Upload a document to retype it with real keyboard inputs")

# Create a file uploader widget
uploaded_file = st.file_uploader("Choose a document file", type=["txt", "docx"])

# Create a delay selector
typing_delay = st.slider("Typing Speed (delay in seconds)", 0.01, 0.1, 0.03, 0.01, 
                         help="Lower values result in faster typing")

# Create a checkbox for error correction
enable_error_correction = st.checkbox("Enable Error Correction", value=True,
                                     help="Periodically check and correct errors during typing")

# Create a start button
start_typing = st.button("Start Retyping (5s countdown)")

# Status display
status_container = st.empty()

async def process_document(doc_path, delay, error_correction):
    # Create and initialize the processor
    retyper = DocumentRetyper(delay=delay)
    await retyper.async_init()
    
    # Show basic info about the document
    await retyper.display_document_info(doc_path)
    
    # Get document text from file
    if doc_path.endswith('.docx'):
        document_text = extract_text_from_docx(doc_path)
    else:
        with open(doc_path, 'r') as f:
            document_text = f.read()
    
    # Countdown
    for i in range(5, 0, -1):
        status_container.info(f"Typing will begin in {i} seconds... Position your cursor where typing should start!")
        await asyncio.sleep(1)
    
    # Current mouse position will be used as the focus point
    mouse = MouseController()
    cursor_position = mouse.position
    
    # Run the retyping
    status_container.info("Typing in progress... Don't move the cursor!")
    try:
        retyped_content = await retyper.retype_document_with_real_typing(
            document_text, 
            cursor_position, 
            enable_error_correction
        )
        status_container.success("Document has been successfully retyped!")
        return retyped_content
    except Exception as e:
        status_container.error(f"Error occurred: {str(e)}")
        return None

# Main app logic
if uploaded_file is not None:
    # Display file info
    st.write(f"File name: {uploaded_file.name}")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        temp_path = tmp_file.name
    
    if start_typing:
        # Display instructions
        st.info("Please open a text editor where you want the typing to occur and position your cursor.")
        
        # Create a placeholder for status updates
        result = asyncio.run(process_document(temp_path, typing_delay, enable_error_correction))
        
        # Clean up temp file
        os.unlink(temp_path)

# Instructions
with st.expander("How to use"):
    st.markdown("""
    1. Upload a .txt or .docx file using the file uploader
    2. Adjust typing speed if needed
    3. Open the target application where you want the text to be typed
    4. Click "Start Retyping"
    5. You'll have 5 seconds to position your cursor where typing should begin
    6. Stay still and let the typing complete
    """)