# app.py - The main Streamlit Application Interface


import streamlit as st
import io
import openai
import datetime
import re
import base64
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
   Converts text to speech, encodes it to Base64, and returns the Base64 string.
   This bypasses Streamlit's internal audio serving issues on mobile Safari.
   """
   clean_text = clean_for_tts(text_to_speak)
   try:
       # 1. Generate the speech audio into an in-memory file
       tts = gTTS(text=clean_text, lang='en')
       fp = io.BytesIO()
       tts.write_to_fp(fp)
       fp.seek(0)
      
       # 2. Encode the raw MP3 bytes to a Base64 string
       base64_audio = base64.b64encode(fp.read()).decode('utf-8')
      
       return base64_audio
      
   except Exception as e:
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


       # --- MOBILE AUDIO FIX IMPLEMENTATION (Base64 Embedding) ---
       base64_audio_str = speak_output(assessment)
      
       if base64_audio_str:
           # FIX: Append a unique timestamp to the data URI to force Safari to reload the audio stream.
           timestamp = int(time.time() * 1000)
          
           # The data URI format is: data:audio/mp3;base64,{BASE64_DATA}
           audio_html = f"""
           <audio controls autoplay style="width: 100%;">
               <source src="data:audio/mp3;base64,{base64_audio_str}?t={timestamp}" type="audio/mp3">
               Your browser does not support the audio element.
           </audio>
           """
           st.markdown(audio_html, unsafe_allow_html=True)
           st.warning("🔊 The audio should play automatically. If not, please press play on the bar above.")
       else:
           st.warning("Audio generation failed.")
       # -----------------------------------------------------------


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






