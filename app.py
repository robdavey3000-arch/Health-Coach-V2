import streamlit as st
import io
import openai
import datetime
import re
import os
from streamlit.components.v1 import html 
from streamlit_mic_recorder import mic_recorder 

# --- Import Helper Functions ---
from sheets import get_sheet, add_log_entry 
from vision import analyze_meal_photo 

# --- CONSTANTS ---
SHEET_NAME = "My Health Tracker" # Make sure this matches your actual sheet name!
# Note: To avoid reaching LLM limits, consider truncating the prompt if it becomes too long.
HEALTH_PLAN = """
I want to reduce my belly circumference from 101cm to under 95cm. 
My daily habits are: a) fasting from 5:30 pm to 9:30 am daily, b) eat meals with meat based protein plus vegetables, avoiding potatoes and other higher carb vegetables, c) avoid standard carbs, d) limit snacks to only those that are based on high fibre and gut healthy ingredients (e.g. nuts, seeds, fruti and youghurt).
"""
# Set a limit for the running log to prevent API context window issues
MAX_LOG_LENGTH = 2000

# --- SECRETS & CLIENT INITIALIZATION ---

# 1. Retrieve secrets securely
# NOTE: The Google Sheet secrets must be structured under a single key in secrets.toml, 
# for example, [google_service_account]
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    GOOGLE_SHEETS_SECRETS = st.secrets["google_service_account"]
except KeyError as e:
    # Display an error if critical secrets are missing
    st.error(f"Configuration Error: Missing required secret key: {e}. Please check your `.streamlit/secrets.toml` file.")
    st.stop() # Stop the app if secrets are not available

# 2. Initialize the OpenAI client globally (improved modularity)
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)


# --- SESSION STATE INITIALIZATION ---
if 'conversation_stage' not in st.session_state:
    st.session_state.conversation_stage = 'start'
if 'transcription_text' not in st.session_state:
    st.session_state.transcription_text = ''
if 'photo_analysis_complete' not in st.session_state:
    st.session_state.photo_analysis_complete = False
if 'detailed_log' not in st.session_state:
    st.session_state.detailed_log = ""
if 'carb_response' not in st.session_state:
    st.session_state.carb_response = ""
if 'detailed_assessment_text' not in st.session_state:
    st.session_state.detailed_assessment_text = ''


# --- HELPER FUNCTION (CLIENT-SIDE TTS) ---

def clean_for_js(text):
    """
    Escapes text for use safely inside JavaScript strings, 
    AND REMOVES ALL APOSTROPHES (due to the LLM constraint) to prevent entity decoding failures.
    """
    # LLM constraint makes the text apostrophe-free, but this ensures safety just in case.
    text = text.replace("'", "") 
    text = text.replace('\\', '\\\\')
    text = text.replace('\n', ' ')
    text = re.sub(r'#+\s?', '', text)
    text = re.sub(r'[\*\*|\*|_]', '', text)
    return text

def embed_js_tts(text_to_speak, element_id='tts_player'):
    """
    Creates a visible button to trigger the browser's native SpeechSynthesis API.
    """
    # Limit text length for TTS for performance/reliability
    text_to_speak = text_to_speak[:500] 
    cleaned_text = clean_for_js(text_to_speak)
    
    # 1. HTML/JS component
    js_code = f"""
    <button id='{element_id}' 
            data-text='{cleaned_text}'
            style='background-color:#4CAF50;color:white;padding:10px 24px;border:none;border-radius:4px;cursor:pointer;'>
        🔊 Tap to Hear Response
    </button>
    <script>
        setTimeout(function() {{
            const btn = document.getElementById('{element_id}');
            
            if (btn && !btn.hasAttribute('data-listener-added')) {{
                
                function decodeHTMLEntities(str) {{
                    const textarea = document.createElement('textarea');
                    textarea.innerHTML = str;
                    return textarea.value;
                }}

                function speak() {{
                    const encodedText = btn.getAttribute('data-text');
                    const decodedText = decodeHTMLEntities(encodedText);
                    
                    if ('speechSynthesis' in window) {{
                        window.speechSynthesis.cancel();
                        const utterance = new SpeechSynthesisUtterance(decodedText);
                        window.speechSynthesis.speak(utterance);
                    }} else {{
                        console.error("Browser does not support native Text-to-Speech.");
                    }}
                }}

                btn.addEventListener('click', speak);
                btn.setAttribute('data-listener-added', 'true');
            }}
        }}, 100); 
    </script>
    """
    
    html(js_code, height=50) 


# ----------------- IMAGE ANALYSIS FUNCTION -----------------

def run_image_analysis(uploaded_file):
    """
    Handles file reading and calls vision.py for analysis.
    Uses in-memory buffer if possible, or temporary file as fallback.
    """

    # 1. Use an in-memory buffer for safety and speed (recommended alternative to disk)
    try:
        # Write file to disk (necessary for current vision.py to read it by path)
        # NOTE: If vision.py were updated to accept bytes, this step could be skipped.
        temp_dir = "/tmp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.info("Image uploaded. Starting analysis...")

        # 2. Assess the image (calls updated vision.py)
        with st.spinner("Calling Vision AI..."):
            # Pass the API key explicitly
            assessment = analyze_meal_photo(file_path, HEALTH_PLAN, OPENAI_API_KEY) 

        # 3. Display and Speak Output
        st.subheader("🤖 Meal Assessment")
        st.info(assessment)

        # CRITICAL CHECK: Check for vision.py's internal error messages
        if assessment.startswith("Error:"):
            st.error("The image analysis failed. Please check the console for details.")
        else:
            embed_js_tts(assessment, element_id='image_tts_player')
            st.session_state.photo_analysis_complete = True # Mark photo analysis as done

        # 4. Clean up temporary file
        os.remove(file_path)

        st.rerun() 

    except Exception as e:
        # Better error logging for the Streamlit environment
        st.error(f"An unexpected error occurred during image processing: {e}")


# ----------------- CONVERSATIONAL VOICE ANALYSIS FUNCTIONS -----------------

def get_carb_check_response(carb_answer):
    """Generates the final response based on the carb check and moves to the final stage."""
    
    # Truncate log text before sending to LLM
    log_to_send = st.session_state.transcription_text[:MAX_LOG_LENGTH]
    
    # 1. Combine all previously gathered data for the final prompt
    full_log_text = (
        f"INITIAL LOG: {log_to_send}\n"
        f"PHOTO ANALYSIS RESULT: {st.session_state.detailed_log}\n"
        f"CARB CHECK RESPONSE: {carb_answer}"
    )
    
    prompt = f"""
    You are the health coach for Rob. Review the entire daily log provided below, paying special attention to the fasting goal (finish by 5:30 PM). 
    CRITICAL CONSTRAINT: DO NOT USE ANY APOSTROPHES OR CONTRACTIONS. Spell out contractions (e.g., 'you are' instead of 'youre').
    Your response should cover:
    1. A single, positive summary sentence on overall adherence.
    2. A quick check on the dinner goal/time remaining (5:30 PM).
    3. A clear instruction to log off and check in after dinner.
    
    HEALTH PLAN: {HEALTH_PLAN}
    FULL DAILY LOG: {full_log_text}
    """
    
    with st.spinner("Finalizing analysis and logging..."):
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
        
    return response


def analyze_initial_log(transcript):
    """Generates the response for the photo/detail check stage."""
    
    prompt = f"""
    You are a friendly health coach. Rob (the user) has provided an initial log: "{transcript}".
    CRITICAL CONSTRAINT: DO NOT USE ANY APOSTROPHES OR CONTRACTIONS. Use phrases like 'you are' instead of 'youre'.
    Your goal is to prepare Rob for the next step.
    1. Give a brief, positive acknowledgement ("Okay great. Sounds like you are doing well.").
    2. Ask the follow-up question exactly: "If you have some photos, I can take a look and check you are applying the success guidelines we set at the start. Or if you dont have photos, just tell me everything you can about the ingredients for your porridge and for your salad bowl."
    3. Output ONLY the coach's spoken dialogue.
    """
    
    with st.spinner("Analyzing initial log..."):
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
    return response


# --- FUNCTION FOR AUDIO TRANSCRIPTION ---
def transcribe_new_audio(audio_bytes):
    """Safely transcribes new audio input and returns the text."""

    # Create file object for Whisper
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice_log.wav" # Whisper requires a file name and correct format
    
    try:
        with st.spinner("Transcribing new details..."):
            transcript = openai_client.audio.transcriptions.create( # Use the global client
                model="whisper-1",
                file=audio_file
            ).text
        return transcript
    except Exception as e:
        st.error(f"Transcription Failed: {e}")
        return None
        

def handle_transcription_and_state(audio_bytes):
    """Handles Whisper transcription and state transition upon initial recording."""

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice_log.wav" 

    try:
        # 1. Transcribe the audio
        with st.spinner("Transcribing your voice..."):
            transcript = openai_client.audio.transcriptions.create( # Use the global client
                model="whisper-1",
                file=audio_file
            ).text
        
        st.session_state.transcription_text = transcript # Save transcript

        # 2. Generate Photo/Detail Check Prompt
        initial_response = analyze_initial_log(transcript)
        st.session_state.detailed_log = initial_response
        
        # 3. Transition state
        st.session_state.conversation_stage = 'photo_check' 
        
        st.rerun() 

    except Exception as e:
        # Catch the specific 400 error which occurs when the audio component returns non-audio data
        if "Unrecognized file format" in str(e):
             st.error("Audio recording failed or was empty. Please ensure you tap 'Start Recording' and speak before tapping 'Stop & Analyze'.")
        else:
             st.error(f"An unexpected error occurred during transcription/summary: {e}")


# ----------------- STREAMLIT LAYOUT MANAGER -----------------

def main_layout():
    
    st.set_page_config(page_title="Personal Health Agent", layout="centered")
    st.title("🎙️ Conversational Health Agent")

    # Create two tabs for the two different input methods
    voice_tab, photo_tab = st.tabs(["🎙️ Coach Chat", "📸 Photo Upload"])

    # --- VOICE LOG TAB LOGIC ---
    with voice_tab:
        
        # --- PHASE 1: START AND INITIAL RECORDING ---
        if st.session_state.conversation_stage == 'start':
            
            initial_prompt = "Hey Rob, glad you are checking in. Want to share todays food choices?" 
            
            # Proactive greeting
            st.markdown(f"**Coach:** {initial_prompt}")
            embed_js_tts(initial_prompt, element_id='initial_tts_player')
            st.markdown("---")
            
            # Mic recorder component
            audio_output = mic_recorder(
                start_prompt="Click to Start Recording",
                stop_prompt="Click to Stop & Analyze",
                key='recorder_start', 
            )

            if audio_output and audio_output.get('bytes'):
                st.audio(audio_output.get('bytes'), format='audio/wav') 
                
                # Immediately call handler to process and transition state
                handle_transcription_and_state(audio_output.get('bytes'))
        
        
        # --- PHASE 2: PHOTO / DETAIL CHECK ---
        elif st.session_state.conversation_stage == 'photo_check':
            
            st.markdown("---")
            st.markdown(f"**Your Initial Log:** *{st.session_state.transcription_text}*")
            
            # Agent's response from initial analysis (suggesting photo/details)
            st.markdown(f"**Coach:** {st.session_state.detailed_log}")
            embed_js_tts(st.session_state.detailed_log, element_id='photo_check_tts_player')

            st.markdown("---")
            st.markdown("##### Action Required:")

            # Prompt for new audio input (optional: to give details)
            audio_details = mic_recorder(
                start_prompt="Record Details/Carb Check",
                stop_prompt="Stop & Analyze Carb Intake",
                key='recorder_details', 
            )

            # Button to trigger the next phase (assuming photo analysis or details were given)
            if audio_details and audio_details.get('bytes'):
                
                # Save the new audio details to the log
                new_transcript = transcribe_new_audio(audio_details.get('bytes'))
                
                if new_transcript:
                    # Append new details and ensure the log doesn't grow indefinitely
                    current_log = st.session_state.transcription_text
                    new_log = f"{current_log} | USER DETAIL: {new_transcript}"
                    st.session_state.transcription_text = new_log[:MAX_LOG_LENGTH]
                    st.session_state.conversation_stage = 'carb_check_ask'
                    st.rerun() 
                
            st.caption("You can also switch to the 📸 Meal Photo tab to upload images.")


        # --- PHASE 3: CARB CHECK QUESTION ---
        elif st.session_state.conversation_stage == 'carb_check_ask':
            
            carb_check_prompt = "This is really good stuff. I can see you are sticking mostly to the guidelines. Maybe keep an eye on how much mayonnaise you are having with the salad. Can I check your carb intake? Any major carbs like bread, pasta, or rice? Or anything with sugar in it today?"
            
            st.markdown("---")
            st.markdown(f"**Coach:** {carb_check_prompt}")
            embed_js_tts(carb_check_prompt, element_id='carb_check_tts_player')
            
            # New Text Input for simple carb answer
            carb_answer = st.text_input("Answer the Coach's Carb Check:", key="carb_input")

            if st.button("Submit Carb Check", key='submit_carb_btn'):
                st.session_state.carb_response = carb_answer
                st.session_state.conversation_stage = 'final_summary'
                st.rerun() 


        # --- PHASE 4: FINAL SUMMARY AND LOGGING ---
        elif st.session_state.conversation_stage == 'final_summary':
            
            # Generate the final conversation summary and logging advice
            final_response = get_carb_check_response(st.session_state.carb_response)
            
            st.markdown("---")
            st.subheader("🎉 Final Check-in")
            st.markdown(f"**Coach:** {final_response}")
            embed_js_tts(final_response, element_id='final_tts_player')
            
            # LOG TO GOOGLE SHEETS (FINAL LOGGING STEP)
            try:
                # Pass the SHEET_NAME and the GOOGLE_SHEETS_SECRETS dict
                sheet = get_sheet(SHEET_NAME, GOOGLE_SHEETS_SECRETS) 
                if sheet:
                    today = datetime.date.today().strftime("%Y-%m-%d")
                    log_notes = (
                        f"SUMMARY: {final_response}\n"
                        f"CARB ANSWER: {st.session_state.carb_response}\n"
                        f"INITIAL LOG (TRUNCATED): {st.session_state.transcription_text}"
                    )
                    add_log_entry(sheet, today, "Full Conversational Log", log_notes)
                    st.success("Session complete and successfully recorded!")
            except Exception as e:
                # Catch specific connection/logging errors
                st.warning(f"Logging Error: Could not connect to Google Sheets or log data. Details: {e}")
                
            if st.button("Start New Session", key='reset_btn'):
                # Reset all state variables
                st.session_state.conversation_stage = 'start'
                st.session_state.transcription_text = ''
                st.session_state.photo_analysis_complete = False
                st.session_state.detailed_log = ""
                st.session_state.carb_response = ""
                st.rerun() 

    # --- MEAL PHOTO TAB LOGIC ---
    with photo_tab:
        
        st.markdown("Upload a photo of your meal/snack for nutritional analysis.")

        uploaded_file = st.file_uploader(
            "Choose an image...", 
            type=["jpg", "jpeg", "png"],
            key="image_uploader"
        )
        
        # Check if a photo was uploaded and we are in the 'photo_check' stage
        if uploaded_file is not None and st.session_state.conversation_stage == 'photo_check':
            
            # Display image in photo tab
            st.image(uploaded_file, caption='Meal to Analyze', use_column_width=True)
            
            # Run image analysis and automatically move back to the Chat Tab upon success
            run_image_analysis(uploaded_file)
        
        elif uploaded_file is not None:
             st.image(uploaded_file, caption='Meal to Analyze', use_column_width=True)
             st.info("Image ready. Please switch back to the '🎙️ Coach Chat' tab to run the analysis when prompted.")


if __name__ == '__main__':
    main_layout()


















