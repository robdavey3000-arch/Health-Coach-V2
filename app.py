# app.py - The main Streamlit Application Interface


import streamlit as st
import io
import openai
import datetime
from gtts import gTTS
import base64
import sys


# Add current directory to path to ensure Streamlit finds local modules (sheets.py, vision.py)
sys.path.append(".")


# --- Import Helper Functions ---
# NOTE: These functions must be defined in your sheets.py and vision.py files
from sheets import get_sheet, add_log_entry
from vision import analyze_meal_photo
from streamlit_mic_recorder import mic_recorder


# --- CONSTANTS ---
SHEET_NAME = "My Health Tracker" # Match your Google Sheet name
HEALTH_PLAN = """
I want to reduce my belly circumference from 101cm to under 95cm.
My daily habits are: a) fasting from 5:30 pm to 9:30 am daily, b) eat meals with meat based protein plus vegetables, avoiding potatoes and other higher carb vegetables, c) avoid standard carbs, d) limit snacks to only those that are based on high fibre and gut healhty ingredients (e.g. nuts, seeds, fruit and yogurt).
"""




# --- TTS HELPER FUNCTION ---
# This function converts text to speech and plays it back in the Streamlit app.
def speak_output(text_to_speak):
   """Converts text to speech, saves to an in-memory MP3, and plays it in Streamlit."""
  
   try:
       # 1. Generate the speech audio
       tts = gTTS(text=text_to_speak, lang='en')
      
       # 2. Save the audio to a BytesIO object (in-memory file)
       fp = io.BytesIO()
       tts.write_to_fp(fp)
       fp.seek(0)
      
       # 3. Play the audio in Streamlit
       st.audio(fp, format='audio/mp3', start_time=0)
      
   except Exception as e:
       # We don't want the app to crash if TTS fails
       st.warning(f"TTS Warning: Could not generate voice feedback. {e}")




# ----------------- CORE LOGIC FUNCTION -----------------


def transcribe_and_assess(audio_bytes):
   """Handles the Whisper transcription, GPT-4o assessment, and logging."""
  
   # --- 1. SECURELY RETRIEVE SECRETS ---
   try:
       OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
       openai.api_key = OPENAI_API_KEY
   except KeyError:
       st.error("Configuration Error: OpenAI API key not found. Please set 'OPENAI_API_KEY' in Streamlit Secrets.")
       return


   # Create file object for Whisper
   audio_file = io.BytesIO(audio_bytes)
   audio_file.name = "voice_log.wav"


   try:
       # 2. Transcribe the audio
       with st.spinner("Transcribing your voice..."):
           transcript = openai.audio.transcriptions.create(
               model="whisper-1",
               file=audio_file
           ).text


       # Display Transcription Result
       st.success("Transcription Complete!")
       st.caption(f"**Transcription:** *{transcript}*")


       # 3. Assess the transcription (GPT-4o)
       prompt = f"""
       I have logged the following daily activities and notes: "{transcript}".
       My overall health plan is: {HEALTH_PLAN}.
       Please assess my progress based on my notes, highlight key adherence points or areas for improvement, and provide a brief, encouraging summary.
       """


       with st.spinner("Getting AI assessment..."):
           response = openai.chat.completions.create(
               model="gpt-4o",
               messages=[{"role": "user", "content": prompt}]
           ).choices[0].message.content
      
       assessment = response
      
       st.subheader("🤖 Agent Assessment")
       st.info(assessment)


       # 4. SPEAK THE OUTPUT
       with st.spinner("Preparing voice feedback..."):
           speak_output(assessment)


       # 5. LOG TO GOOGLE SHEETS
       try:
           # Pass the full st.secrets object to the sheets module
           sheet = get_sheet(SHEET_NAME, st.secrets.to_dict())
           if sheet:
               today = datetime.date.today().strftime("%Y-%m-%d")
               add_log_entry(sheet, today, "Voice Summary", assessment)
               st.success("Successfully logged entry to Google Sheet!")
       except Exception as e:
           st.warning(f"Logging Error: Could not connect to Google Sheets. Check credentials. Details: {e}")


   except Exception as e:
       st.error(f"An error occurred during AI processing: {e}")




# ----------------- STREAMLIT LAYOUT -----------------


st.set_page_config(page_title="Personal Health Agent", layout="centered")
st.title("🎙️ Daily Progress Log")
st.markdown("Tap the button below to record your voice summary.")


# The mic_recorder component is the entry point
audio_output = mic_recorder(
   start_prompt="Click to Start Recording",
   stop_prompt="Click to Stop & Analyze",
   key='recorder',
)


# Check if audio has been recorded
if audio_output is not None and audio_output.get('bytes'):
   audio_bytes = audio_output.get('bytes')
   st.audio(audio_bytes, format='audio/wav')
  
   # Trigger the analysis function
   transcribe_and_assess(audio_bytes)
