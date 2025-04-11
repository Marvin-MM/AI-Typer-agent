import os
from pathlib import Path
import re
import tempfile
import streamlit as st
from utils import (
    extract_file_content,
    is_valid_doc, 
    display_screenshots,
)
from typer import DocumentRetyper, extract_text_from_docx
from validation import (
    display_error_details
)
from pynput.mouse import Controller as MouseController
import asyncio
import logging
from analyzer import analyze_docx




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="VClass Typer Automation",
    layout="centered",
    initial_sidebar_state="expanded",
    page_icon="🚀",
)

if 'processing_status' not in st.session_state:
    st.session_state.processing_status = None
if 'result' not in st.session_state:
    st.session_state.result = None
if 'file_info' not in st.session_state:
    st.session_state.file_info = None
if 'screenshots' not in st.session_state:
    st.session_state.screenshots = []

# Sidebar 
with st.sidebar:
    st.header("Settings")
    st.markdown("### Keep Your Credentials Safe and also Don't Set what you don't know")
    st.markdown("Configure your preferences and automation reset settings here.")
    
    st.subheader("Anonymous Credentials")
    reg_number = st.text_input("Rank Number", help="Your are yet to reach for better")
    password = st.text_input("Hash Passcode", type="password", help="Your have to be ranked for the hash")
    
    st.subheader("Browser Settings")
    
    typing_speed = st.slider(
        "Typing Speed",
        min_value=10,
        max_value=200,
        value=50,
        help="Characters per second for typing"
    )
            
    chunk_size = st.slider(
        "Chunk Size for Large Documents",
        min_value=500,
        max_value=10000,
        value=2000,
        help="Characters per chunk when processing large documents"
    )
    
    with st.expander("More Options", expanded=False):
        st.markdown("### ⚙️ Additional Settings")
        st.markdown("""
        - **Headless Mode**: Run the browser in the background without a visible window.        
        - **Keep as Docx**: Retains the document in its original format for better compatibility.
        """)

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            headless_mode = st.checkbox(
                "Headless Mode🕶️ ",
                value=True,
                help="Run browser in background (no visible window)"
            )

        with col2:
            doc_type = st.selectbox(
                "📄 Document Type",
                options=["Docx / Word Document", "PDF", "TXT", "ODT"],
                help="Select the type of document you are uploading"
            )

    take_screenshots = st.checkbox(
        "Capture Screenshots",
        value=True,
        help="Take screenshots during the automation process"
    )

    st.markdown("---")
    st.write("📍 Powered by **Breakers** | Made with ❤️ in Uganda")
    st.write("📧 Contact: support@dontcall.com | 🌐 [anonymus.com](https://.com)")
    st.caption("© 2025 . No Data is Stored on this site. All data is processed locally.")

#Main Page 
col1, col2 = st.columns([8, 2])

with col1:
    st.title("VClass Typer Agent / JailBreaker")

with col2:
    if st.button("💬", help="Show Info Dialog"):
        st.session_state.show_dialog = not st.session_state.get("show_dialog", False)


if st.session_state.get("show_dialog", False):
    with st.container():
        st.markdown("### 🗨️ Read with caution")
        st.info("""
        This application automates the process of typing documents into the VClass online editor.
        Upload your document, provide your credentials, and let the automation handle the rest.
        """)

        if st.button("❌ Close"):
            st.session_state.show_dialog = False

st.markdown("\n \n \n")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["🔧 Typer Agent Document", "⚙️ Automation", "⭐ Support Us 💰💰", " ⚙️ Settings"])

with tab1:
    with st.expander("Learn To Use The Agent "):
        st.caption("""
        1. Upload a  .docx file using the file uploader
        2. Adjust typing speed if needed
        3. Open the target application where you want the text to be typed
        4. Click "Start AI Retyper"
        5. You'll have 5 seconds to position your cursor where typing should begin
        6. Stay still and let the typing complete
    """)
    st.markdown("### 📤 Upload Your Document")
    st.caption("""
    Drag and drop your document below or click **Browse Files**.  
    Supported formats: **.docx**, **.odt**, **.pdf**
    """)
    
    uploaded_file = st.file_uploader(
        label="",
        type=["docx", "odt", "pdf",],
        accept_multiple_files=False,
        help="Upload a document to process (Docx, ODT, PDF,C-Soon,)",
        label_visibility="collapsed"
    )
    
    st.caption("**Note:** Ensure your document is in a supported format and contains valid content.")

    if uploaded_file is not None:
        
        is_valid, validation_result = is_valid_doc(uploaded_file)
        
        if not is_valid:
            st.error(f"Invalid document: {validation_result}")
        else:
           
            st.session_state.file_info = validation_result
            
            try:
                file_content = extract_file_content(uploaded_file, validation_result)

                
                
                with st.expander("Prefernces (Don`t Change Anything) ", expanded=False):
                    st.caption("The the lower (.001) the slider the faster the agent and the higher the slider the slower the agent")
                    st.caption("Default : 0.003 (Human Typing With Accuray 85%)")
                    speed_options = {
                        "Ultra Fast (AI Speed)": 0.001,
                        "Very Fast": 0.005,
                        "Fast": 0.01,
                        "Medium (Human-like)": 0.03,
                        "Slow": 0.05
                    }

                    # typing_speed_option = st.selectbox(
                    #     "Typing Speed Preset",
                    #     options=list(speed_options.keys()),
                    #     index=0,  # Default to Ultra Fast
                    #     help="Choose a typing speed preset"
                    # )

                    # # Set the delay based on selection (overrides the slider)
                    # selected_delay = speed_options[typing_speed_option]
                    typing_delay = st.slider("Typing Speed (delay in seconds)", 0.001, 0.1, 0.03, 0.001,
                                            help="Lower values result in faster typing")

                    enable_error_correction = st.checkbox("Enable Error Correction", value=True,
                                                        help="Periodically check and correct errors during typing")
                

                col1, col2 = st.columns([1, 2])
                if st.button("Start AI Typer", key="process_btn", use_container_width=True):
                    st.session_state.processing_status = "started"
                    st.caption("Make sure the Agent is split to the browser on left or right beside your Editor for proper focus.")
                    
                    progress_bar = st.progress(1)
                    status_text = st.empty()
                    status_container = st.empty()
                    
                    def update_progress(message, progress):
                        status_text.info(message)
                        progress_bar.progress(progress)
                    
                    async def process_document(doc_path, delay, error_correction):
                        try:
                            retyper = DocumentRetyper(delay=delay)
                            await retyper.async_init()
                            
                            await retyper.display_document_info(doc_path)
                            
                            doc_info = await retyper.display_document_info(doc_path)
        
                            # Extract total character count for progress tracking
                            char_count_match = re.search(r'(\d+) characters', doc_info)
                            total_chars = int(char_count_match.group(1)) if char_count_match else 1000
                            
                            if doc_path.endswith('.docx'):
                                document_text = extract_text_from_docx(doc_path)
                            else:
                                with open(doc_path, 'r') as f:
                                    document_text = f.read()

                            for i in range(5, 0, -1):
                                status_container.info(f"Typing will begin in {i} seconds... Position your cursor where typing should start!")
                                await asyncio.sleep(1)
                            
                            mouse = MouseController()
                            cursor_position = mouse.position

                            
                            status_container.warning("After Positioning Your Cursor. Dont Touch Your Mouse, Mouse Pad.")
                            status_container.info(" Don't move the cursor! >>>> Typing in progress...")
                            
                        # Setup progress tracking
                            progress_bar.progress(0)
                            typed_chars = 0
                            last_update = 0

                            # Create a progress callback function
                            async def update_typing_progress(chars_typed):
                                nonlocal typed_chars, last_update
                                typed_chars = chars_typed
                                progress_percent = min(1.0, typed_chars / total_chars)
                                
                                # Update only if significant progress has been made (reduces UI updates)
                                if progress_percent - last_update >= 0.01:  # Update every 1% progress
                                    progress_bar.progress(progress_percent)
                                    status_text.info(f"Typing: {typed_chars}/{total_chars} characters ({int(progress_percent*100)}%)")
                                    last_update = progress_percent



                            retyped_content = await retyper.retype_document_with_real_typing(
                                document_text, 
                                cursor_position, 
                                error_correction,
                                progress_callback=update_typing_progress,
                            )
                            progress_bar.progress(1.0)
                            status_text.info(f"Typing: {typed_chars}/{total_chars} characters (100%)")
                            status_container.success("Document has been successfully Retyped !")
                            return retyped_content
                            
                        except Exception as e:
                            status_container.error(f"Error occurred: {str(e)}")
                            return None
                    
                    if uploaded_file is not None:

                        st.write(f"File name: {uploaded_file.name}")
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            temp_path = tmp_file.name
                        
                        try:
                            result = asyncio.run(process_document(temp_path, typing_delay, enable_error_correction))
                        finally:
                            if os.path.exists(temp_path):
                                os.unlink(temp_path)
                    else:
                        st.error("Please upload a file first.")
                
                with st.expander("📄 Document Preview", expanded=False):
                    st.markdown("#### 🧾 File Content:")

                    if validation_result['type'] == 'py':
                        st.code(file_content, language=validation_result['type'])
                    else:
                        st.text_area(
                            label="Content Preview",
                            value=file_content,
                            height=400,
                            disabled=True
                        )
                
                st.caption("The Document Formats and Stlyes analyis, ")
                
                with st.expander("🔑 Analyzer Formater", expanded=False):
                    file_analyzed = analyze_docx(uploaded_file)
                    st.markdown("#### 🧾 File Content:")

                    if validation_result['type'] == 'py':
                        st.code(file_analyzed, language=validation_result['type'])
                    else:
                        st.text_area(
                            label="Document Contains the following Formats as Word Document Provided:",
                            value=file_analyzed,
                            height=400,
                            disabled=True
                        )
                status_container = st.empty()

                st.caption("Please If your document contains images trick the box below to avoid persistent download")
                st.divider()
                st.success(f"🚨 Valid {validation_result['type'].upper()} file: {uploaded_file.name} Detected ({validation_result['size']/1024:.1f} KB)")
                st.checkbox("Images Inside🕶️ ", value=True, help="To avoid image download")

            except Exception as e:
                st.error(f"Error processing document: {str(e)}")
                logger.error(f"Processing error: {str(e)}")
    
    if st.session_state.processing_status == "completed" and st.session_state.result:
        st.divider()
        st.subheader("Processing Results")
        
        if not st.session_state.result.get("success", False):
            display_error_details(st.session_state.result)
        else:
            st.success("Document processed successfully!")
            
            st.info(st.session_state.result.get("message", "Document was processed"))
            
            if st.session_state.result.get("screenshots"):
                with st.expander("Process Screenshots", expanded=True):
                    display_screenshots(st.session_state.result["screenshots"])

with tab2:
    st.subheader("Automatic Typer")
    st.write("Here the agent will login to your vclass and submit your document")
    st.caption("For Faster Agent its for payment")

    st.subheader("🚧 Coming Soon 🚀")
    st.markdown("### 🔜 Stay Tuned! 🌟")
    st.markdown("""
    - 🛠️ We're working hard to bring this feature to life!  
    - 📅 Expected release: **TBD**  
    - 💡 Have suggestions? Let us know!  
    """)
    st.info("✨ Exciting updates are on the way. Keep an eye out! 👀")

    with st.expander("Advanced Options"):
        st.caption("Keep in mind to reset just refresh the page and Dont jst set and thing.")
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Override Timer", value="", help="Leave empty to use sidebar value")
            st.text_input("Ghost Typer", value="", help="Leave empty to use sidebar value")
            
        with col2:
            st.number_input("Override Typing Speed", value=0, min_value=0, max_value=100, 
                            help="Set to 0 to use sidebar value")
    


with tab3:
    st.subheader("Support Us")

    st.write("If you find this tool helpful, consider supporting us!")
    st.write("Support us on [Patreon](https://patreon.com/vclassjailbreaker)")
    st.write("Support us on [Binance](https://paypal.me/vclassjailbreaker)")
    st.write("Support us on [PayPal](https://paypal.me/vclassjailbreaker)")

with tab4:
    
    st.subheader("Settings Guide")
    st.write("The Automation process for the Agent to Login to your vclass and also to submit your document")
    st.caption("Coming Soon : But first support to try for Free and Remember we are not responsible for anything.")
    st.write("""
    - **Typing Speed**: Reduce this for more accurate typing (recommended: 20-25 chars/sec)
    - **Chunk Size**: For larger documents, smaller chunks are processed more reliably
    - **Headless Mode**: Run the browser invisibly in the background
    - **Screenshots**: Capture images to verify the document was typed correctly
    """)
    
    st.subheader("Troubleshooting")
    st.write("""
    If the automation is not working correctly:
    1. Try a slower typing speed (15-20 chars/sec)
    2. Use smaller chunk sizes (2000-3000 chars)
    3. Make sure your login credentials are correct
    4. Check that the document format is supported (.odt, .docx, .py, .md)
    5. For complex documents, consider simplifying the formatting
    """)


st.divider()
st.caption("We value your privacy. This application does not store any data. | Made with ❤️ at Victoria Uni")

