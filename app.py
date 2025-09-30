# app.py - Your main Streamlit Application File

import streamlit as st
import io
import openai
import datetime
import base64
import time
from gtts import gTTS

# --- NEW IMPORTS: Bring in the helper functions ---
from sheets import get_sheet, add_log_entry 
from vision import analyze_meal_photo 
from streamlit_mic_recorder import mic_recorder 

# --- CONSTANTS ---
SHEET_NAME = "My Health Tracker" # Make sure this matches your actual sheet name!
HEALTH_PLAN = """
I want to reduce my belly circumference from 101cm to under 95cm. 
My daily habits are: a) fasting from 5:30 pm to 9:30 am daily, 
b) eat meals with meat based protein plus vegetables, avoiding potatoes and other higher carb vegetables, 
c) avoid standard carbs, 
d) limit snacks to only those that are based on high fibre and gut healthy ingredients (e.g. nuts, seeds, fruit and yoghurt).
"""

# --- HELPER FUNCTION (TTS) ---
def speak_output(text_to_speak):
    """Generate speech from text and return Base64-encoded MP3 string."""
    try:
        tts = gTTS(text=text_to_speak, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_bytes = fp.read()

        # Encode in Base64 for embedding
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        return audio_base64
    except Exception as e:
        st.error(f"TTS Error: Could not generate voice feedback. {e}")
        return None

# ----------------- UI FUNCTIONS -----------------
def transcribe_and_assess(audio_bytes):
    """Handles the Whisper transcription and the GPT-4o assessment."""
    
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    openai.api_key = OPENAI_API_KEY
    
    # Create file object for Whisper
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice_log.wav" 

    try:
        # 1. Transcribe
        with st.spinner("Transcribing your voice..."):
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcript_text = transcript.text
        st.success("Transcription Complete!")
        st.caption(f"**Transcription:** *{transcript_text}*")

        # 2. Assess
        prompt = f"""
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

        # 3. Log to Google Sheets
        try:
            sheet = get_sheet(SHEET_NAME, st.secrets.to_dict()) 
            if sheet:
                today = datetime.date.today().strftime("%Y-%m-%d")
                add_log_entry(sheet, today, "Voice Summary", assessment)
        except Exception as e:
            st.warning(f"Logging Error: Could not connect to Google Sheets. Details: {e}")

        # 4. TTS Output
        audio_base64 = speak_output(assessment)
        if audio_base64:
            timestamp = int(time.time() * 1000)  # cache buster
            audio_html = f"""
            <audio controls>
                <source src="data:audio/mp3;base64,{audio_base64}?v={timestamp}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
            """
            st.markdown(audio_html, unsafe_allow_html=True)
            st.caption("🔊 Tap the play button above to hear the audio response.")

    except Exception as e:
        st.error(f"An error occurred during AI processing: {e}")

# ----------------- STREAMLIT LAYOUT -----------------
st.set_page_config(page_title="Personal Health Agent", layout="centered")
st.title("🎙️ Daily Progress Log")
st.markdown("Tap the button below to record your voice summary.")

audio_output = mic_recorder(
    start_prompt="Click to Start Recording",
    stop_prompt="Click to Stop & Analyze",
    key='recorder', 
)

if audio_output is not None and audio_output.get('bytes'):
    audio_bytes = audio_output.get('bytes')
    st.audio(audio_bytes, format='audio/wav') 
    transcribe_and_assess(audio_bytes)






