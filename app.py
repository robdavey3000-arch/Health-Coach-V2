# app.py - The main Streamlit Application Interface


import streamlit as st
import io
import openai
import datetime
import re
from gtts import gTTS


# --- NEW IMPORTS: Bring in the helper functions ---
# NOTE: Ensure these modules are saved in the same folder as app.py
from sheets import get_sheet, add_log_entry
from vision import analyze_meal_photo
from streamlit_mic_recorder import mic_recorder


# --- CONSTANTS ---
SHEET_NAME = "My Health Tracker" # Make sure this matches your actual sheet name!
HEALTH_PLAN = """
I want to reduce my belly circumference from 101cm to under 95cm.
My daily habits are: a) fasting from 5:30 pm to 9:30 am daily, b) eat meals with meat based protein plus vegetables, avoiding potatoes and other higher carb vegetables, c) avoid standard carbs, d) limit snacks to only those that are based on high fibre and gut healhty ingredients (e.g. nuts, seeds, fruti and youghurt).
"""


# --- HELPER FUNCTION (TTS) ---


def clean_for_tts(text):
   """Removes common Markdown characters and emojis for clean TTS playback."""
   # Remove headings, bold/italics markers
   text = re.sub(r'#+\s?', '', text)
   text = re.sub(r'[\*\-]\s?', '', text)
   text = re.sub(r'[\*\*|\*|_]', '', text)
   # Remove emojis (replace common ones if necessary, or use a more robust library)
   text = text.replace("🤖 Agent Assessment", "Agent Assessment")
   text = text.replace("✅", "")
   return text


def speak_output(text_to_speak):
   """
   Converts text to speech and RETURNS THE BYTESIO OBJECT.
   This is the cleanest file-like object for Streamlit's st.audio.
   """
   clean_text = clean_for_tts(text_to_speak)
   try:
       # 1. Generate the speech audio
       tts = gTTS(text=clean_text, lang='en')
      
       # 2. Save the audio to a BytesIO object (in-memory file)
       fp = io.BytesIO()
       tts.write_to_fp(fp)
       fp.seek(0) # Reset pointer to start of file
      
       # Return the BytesIO object itself, not raw bytes
       return fp
      
   except Exception as e:
       # We return None if TTS fails so the main logic can handle it
       print(f"TTS Warning: Could not generate voice feedback. Details: {e}")
       return None




# ----------------- UI FUNCTIONS -----------------


def transcribe_and_assess(audio_bytes):
   """Handles the Whisper transcription and the GPT-4o assessment."""
  
   # --- 1. SECURELY RETRIEVE AND SETUP SECRETS ---
   # Retrieve secrets from Streamlit Cloud
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


       # --- MOBILE AUDIO FIX IMPLEMENTATION ---
       audio_io_tts = speak_output(assessment)
      
       if audio_io_tts:
           # FIX: We pass the BytesIO object (audio_io_tts) directly to st.audio
           # It already has .seek(0) applied within speak_output.
          
           st.audio(audio_io_tts, format='audio/mp3', autoplay=False, start_time=0)
           st.warning("🔊 Tap the play button above to hear the full audio response.")
       # ---------------------------------------


       # 4. LOG TO GOOGLE SHEETS
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




