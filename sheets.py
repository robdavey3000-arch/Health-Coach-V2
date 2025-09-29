# sheets.py
import gspread
from google.oauth2.service_account import Credentials
import datetime # Keep datetime for the logging function if needed for testing

# NOTE: The function now takes the secrets dictionary directly.
def get_sheet(sheet_name, secrets):
    """
    Connects to Google Sheets using the secrets provided by st.secrets.
    """
    try:
        # Pull the 'gcp_service_account' dictionary from the Streamlit secrets
        creds_json = secrets["gcp_service_account"]
        
        # Load the credentials using the service account info
        creds = Credentials.from_service_account_info(creds_json, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).sheet1
        print("Connected to Google Sheet successfully.")
        return sheet
        
    except Exception as e:
        # Logging the error details to the terminal (visible in Streamlit logs)
        print(f"ERROR: Failed to connect to Google Sheets: {e}")
        return None

def add_log_entry(sheet, date, assessment, notes):
    """
    Adds a new row of data to the Google Sheet. (No change needed here)
    """
    try:
        row = [date, assessment, notes]
        sheet.append_row(row)
        print("Successfully added a new entry to the Google Sheet.")
        
    except Exception as e:
        print(f"An error occurred while adding data to the sheet: {e}")

# NOTE: Remove the 'if __name__ == "__main__":' block entirely before deployment.
# We no longer want these helper files to be runnable locally.