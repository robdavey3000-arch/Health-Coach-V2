import streamlit as st
import io
import openai
import datetime
import re
import base64
import time 
# CRITICAL IMPORT FOR HTML EMBEDDING
from streamlit.components.v1 import html 


# --- Import Helper Functions (Assuming these are updated for secure secrets) ---
from sheets import get_sheet, add_log_entry 
from vision import analyze_meal_photo 
from streamlit_mic_recorder import mic_recorder 
# NOTE: gTTS is no longer needed but kept for completeness of history
# The problem is resolved by switching to native JS SpeechSynthesis

# --- CONSTANTS ---
SHEET_NAME = "My Health Tracker" # Make sure this matches your actual sheet name!
HEALTH_PLAN = """
I want to reduce my belly circumference from 101cm to under 95cm. 
My daily habits are: a) fasting from 5:30 pm to 9:30 am daily, b) eat meals with meat based protein plus vegetables, avoiding potatoes and other higher carb vegetables, c) avoid standard carbs, d) limit snacks to only those that are based on high fibre and gut healhty ingredients (e.g. nuts, seeds, fruti and youghurt).
"""

# --- HELPER FUNCTION (NEW CLIENT-SIDE TTS) ---

def clean_for_js(text):
    """
    Escapes text for use safely inside JavaScript strings, 
    specifically neutralizing the apostrophe and other escape sequences.
    """
    # 1. Neutralize the apostrophe/single quote (CRITICAL FIX)
    text = text.replace("'", "\\'") 
    
    # 2. Escape backslashes for safety
    text = text.replace('\\', '\\\\')
    
    # 3. Clean up Markdown/formatting junk (remains the same)
    text = text.replace('\n', ' ')
    text = re.sub(r'#+\s?', '', text)
    text = re.sub(r'[\*\*|\*|_]', '', text)
    return text

def embed_js_tts(text_to_speak, element_id='tts_player'):
    """
    Creates a visible button to trigger the browser's native SpeechSynthesis API 
    using the more stable st.components.v1.html method.
    """
    # NOTE: The text is cleaned BEFORE it is passed into the data attribute.
    cleaned_text = clean_for_js(text_to_speak)
    
    # 1. HTML/JS component
    # The text is now passed as a data attribute, and the JS handles the simple click event.
    js_code = f"""
    <button id='{element_id}' 
            data-text='{cleaned_text}'
            style='background-color:#4CAF50;color:white;padding:10px 24px;border:none;border-radius:4px;cursor:pointer;'>
        🔊 Tap to Hear Response
    </button>
    <script>
        // CRITICAL FIX: Use simple selector logic within a short timeout.
        setTimeout(function() {{
            const btn = document.getElementById('{element_id}');
            
            if (btn && !btn.hasAttribute('data-listener-added')) {{
                
                function speak() {{
                    // Get text safely from the data attribute
                    const text = btn.getAttribute('data-text'); 
                    
                    if ('speechSynthesis' in window) {{
                        window.speechSynthesis.cancel();
                        const utterance = new SpeechSynthesisUtterance(text);
                        // CRITICAL: We also set the language to ensure the correct voice profile is used
                        // utterance.lang = 'en-US'; 
                        window.speechSynthesis.speak(utterance);
                    }} else {{
                        console.error("Browser does not support native Text-to-Speech.");
                    }}
                }}

                btn.addEventListener('click', speak);
                btn.setAttribute('data-listener-added', 'true');
            }}
        }}, 100); // Very short delay
    </script>
    """
    
    # Using st.html to render the button.
    html(js_code, height=50) 

# ----------------- IMAGE ANALYSIS FUNCTION -----------------

def run_image_analysis(uploaded_file):
    """Handles file reading and calls vision.py for analysis and logs the result."""

    # 1. SECURELY RETRIEVE AND SETUP SECRETS 
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    openai.api_key = OPENAI_API_KEY

    try:
        # Create a temporary file path needed by the vision.py helper
        # Since the helper function expects a path, we must write the uploaded file
        # to the local disk inside the Streamlit container.
        import os
        temp_dir = "/tmp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success("Image uploaded. Analyzing...")

        # 2. Assess the image (calls vision.py)
        with st.spinner("Calling Vision AI..."):
            assessment = analyze_meal_photo(file_path, HEALTH_PLAN, OPENAI_API_KEY)

        # 3. Display and Speak Output
        st.subheader("🤖 Meal Assessment")
        st.info(assessment)

        embed_js_tts(assessment, element_id='image_tts_player')
        
        # 4. LOG TO GOOGLE SHEETS
        try:
            sheet = get_sheet(SHEET_NAME, st.secrets.to_dict()) 
            if sheet:
                today = datetime.date.today().strftime("%Y-%m-%d")
                add_log_entry(sheet, today, "Image Meal Log", assessment)
                st.success("Analysis successfully logged to Google Sheets!")
        except Exception as e:
            st.warning(f"Logging Error: Could not connect to Google Sheets. Details: {e}")

        # 5. Clean up temporary file
        os.remove(file_path)

    except Exception as e:
        st.error(f"An error occurred during image processing: {e}")


# ----------------- VOICE ANALYSIS FUNCTION (Remains the same) -----------------

def transcribe_and_assess(audio_bytes):
    """Handles the Whisper transcription and the GPT-4o assessment."""
    
    # --- 1. SECURELY RETRIEVE AND SETUP SECRETS ---
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    openai.api_key = OPENAI_API_KEY
    
    # Create file object for Whisper
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice_log.wav" 

    try:
        # 2. Transcribe the audio
        with st.spinner("Transcribing your voice..."):
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        transcript_text = transcript.text
        st.success("Transcription Complete!")
        st.caption(f"**Transcription:** *{transcript_text}*")

        # 3. Assess the transcription (GPT-4o)
        prompt = f"""
        INSTRUCTIONS: You are a concise health coach. Review the user's notes and assess their adherence to the plan. 
        1. Keep the response to a maximum of 3 sentences (40-60 words). 
        2. Focus on one success point and one area for immediate improvement. 
        3. Your response must be clean text with no Markdown formatting (no **, #, or *). 
        
        I have logged the following daily activities and notes: "{transcript_text}".
        My overall health plan is: {HEALTH_PLAN}.
        Please assess my progress based on my notes, highlight key adherence points or areas for improvement, and provide a brief, encouraging summary.
        """

        with st.spinner("Getting AI assessment..."):
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )

        assessment = response.choices[0].message.content
        st.subheader("🤖 Agent Assessment")
        st.info(assessment)

        # --- MOBILE AUDIO FIX IMPLEMENTATION (Client-Side JS) ---
        # 4. EMBED CLIENT-SIDE TTS BUTTON
        embed_js_tts(assessment, element_id='voice_tts_player')
        # -----------------------------------------------------------

        # 5. LOG TO GOOGLE SHEETS
        try:
            # Pass the full st.secrets object to the sheets module
            sheet = get_sheet(SHEET_NAME, st.secrets.to_dict()) 
            if sheet:
                today = datetime.date.today().strftime("%Y-%m-%d")
                add_log_entry(sheet, today, "Voice Summary", assessment)
        except Exception as e:
            st.warning(f"Logging Error: Could not connect to Google Sheets. Check credentials in Streamlit Secrets. Details: {e}")

    except Exception as e:
        st.error(f"An error occurred during AI processing: {e}")


# ----------------- STREAMLIT LAYOUT MANAGER -----------------

st.set_page_config(page_title="Personal Health Agent", layout="centered")
st.title("🎙️ Daily Progress Log")

# Create two tabs for the two different input methods
voice_tab, photo_tab = st.tabs(["🎙️ Voice Log", "📸 Meal Photo"])

with voice_tab:
    st.markdown("Tap the button below to record your voice summary.")

    # The mic_recorder component
    audio_output = mic_recorder(
        start_prompt="Click to Start Recording",
        stop_prompt="Click to Stop & Analyze",
        key='recorder', 
    )

    # Check if audio has been recorded
    if audio_output is not None and audio_output.get('bytes'):
        # 'audio_output' contains a dictionary with the raw audio bytes
        audio_bytes = audio_output.get('bytes')
        st.audio(audio_bytes, format='audio/wav') 
        
        # Trigger the analysis function
        transcribe_and_assess(audio_bytes)

with photo_tab:
    st.markdown("Upload a photo of your meal/snack for nutritional analysis.")

    uploaded_file = st.file_uploader(
        "Choose an image...", 
        type=["jpg", "jpeg", "png"],
        key="image_uploader"
    )

    if uploaded_file is not None:
        st.image(uploaded_file, caption='Meal to Analyze', use_column_width=True)
        if st.button("Analyze Meal Photo", key="analyze_btn"):
            run_image_analysis(uploaded_file)












