# app.py - Your main Streamlit Application File

import streamlit as st
import io
import openai
import datetime
import re
import base64
import time


# --- Import Helper Functions (Assuming these are updated for secure secrets) ---
from sheets import get_sheet, add_log_entry
from vision import analyze_meal_photo
from streamlit_mic_recorder import mic_recorder
# NOTE: gTTS is no longer needed but kept for completeness of history
# from gtts import gTTS


# --- CONSTANTS ---
SHEET_NAME = "My Health Tracker" # Make sure this matches your actual sheet name!
HEALTH_PLAN = """
I want to reduce my belly circumference from 101cm to under 95cm.
My daily habits are: a) fasting from 5:30 pm to 9:30 am daily, b) eat meals with meat based protein plus vegetables, avoiding potatoes and other higher carb vegetables, c) avoid standard carbs, d) limit snacks to only those that are based on high fibre and gut healhty ingredients (e.g. nuts, seeds, fruti and youghurt).
"""


# --- HELPER FUNCTION (NEW CLIENT-SIDE TTS) ---


def clean_for_js(text):
   """Escapes text for use safely inside JavaScript strings."""
   # Replace single quotes, line breaks, and escape backslashes
   text = text.replace('\\', '\\\\')
   text = text.replace("'", "\\'")
   text = text.replace('\n', ' ')
   text = re.sub(r'#+\s?', '', text)
   text = re.sub(r'[\*\*|\*|_]', '', text)
   return text


def embed_js_tts(text_to_speak, element_id='tts_player'):
   """
   Creates a hidden HTML player and a visible button to trigger
   the browser's native SpeechSynthesis API.
   """
   cleaned_text = clean_for_js(text_to_speak)
  
   # 1. HTML/JS component
   # We use st.markdown to inject a button and the necessary JavaScript
   js_code = f"""
   <button id='{element_id}'
           style='background-color:#4CAF50;color:white;padding:10px 24px;border:none;border-radius:4px;cursor:pointer;'>
       🔊 Tap to Hear Response
   </button>
   <script>
       const btn = document.getElementById('{element_id}');
       const text = '{cleaned_text}';
      
       // This function speaks the text using the browser's native engine
       function speak() {{
           if ('speechSynthesis' in window) {{
               const utterance = new SpeechSynthesisUtterance(text);
               // Optional: set preferred voice (browser dependent)
               // utterance.voice = window.speechSynthesis.getVoices()[0];
               utterance.pitch = 1.0;
               utterance.rate = 1.0;
               window.speechSynthesis.speak(utterance);
           }} else {{
               alert("Your browser does not support native Text-to-Speech.");
           }}
       }}


       // Force the audio to play on button click
       btn.addEventListener('click', speak);
   </script>
   """
   st.markdown(js_code, unsafe_allow_html=True)




# ----------------- UI FUNCTIONS -----------------


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
       embed_js_tts(assessment)
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




# ----------------- STREAMLIT LAYOUT (No major changes needed here) -----------------


st.set_page_config(page_title="Personal Health Agent", layout="centered")
st.title("🎙️ Daily Progress Log")
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






