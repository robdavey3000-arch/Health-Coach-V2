# sheets.py

import gspread
from google.oauth2.service_account import Credentials
import json # New import needed for JSON handling

# CRITICAL UPDATE: Now accepts the secrets dictionary directly from Streamlit
def get_sheet(sheet_name, st_secrets_dict):
    """
    Connects to Google Sheets using the secrets dictionary and returns the worksheet.
    This eliminates the need for a local 'credentials.json' file.
    """
    try:
        # These are the required scopes for a service account to access Google Drive and Sheets.
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
                  'https://www.googleapis.com/auth/drive']
        
        # 1. Extract the credentials section from the secrets dictionary
        # Assuming the Google Service Account details are under a key like 'gcp_service_account'
        # in the st.secrets.toml file (or similar)
        
        # If the secrets are structured as in Streamlit docs (e.g., just the keys):
        # We need to build the dictionary from the secrets
        creds_info = {
            "type": st_secrets_dict["type"],
            "project_id": st_secrets_dict["project_id"],
            "private_key_id": st_secrets_dict["private_key_id"],
            "private_key": st_secrets_dict["private_key"].replace('\\n', '\n'), # Fix line endings
            "client_email": st_secrets_dict["client_email"],
            "client_id": st_secrets_dict["client_id"],
            "auth_uri": st_secrets_dict["auth_uri"],
            "token_uri": st_secrets_dict["token_uri"],
            "auth_provider_x509_cert_url": st_secrets_dict["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st_secrets_dict["client_x509_cert_url"],
            "universe_domain": st_secrets_dict["universe_domain"]
        }
        
        # Load the credentials from the dictionary directly.
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        
        # Authorize the gspread client.
        client = gspread.authorize(creds)
        
        # Open the specific Google Sheet by its name.
        sheet = client.open(sheet_name).sheet1
        print("Connected to Google Sheet successfully.")
        return sheet
        
    except KeyError as e:
        print(f"Configuration Error: Missing Google Sheets secret key: {e}. Check your st.secrets.")
        return None
    except Exception as e:
        print(f"An error occurred while connecting to Google Sheets: {e}")
        return None

def add_log_entry(sheet, date, assessment, notes):
    """
    Adds a new row of data to the Google Sheet.
    """
    try:
        # The row of data to be appended.
        # This should match the columns in your Google Sheet (e.g., Date, Assessment, Notes).
        row = [date, assessment, notes]
        
        # Append the row to the end of the sheet.
        sheet.append_row(row)
        print("Successfully added a new entry to the Google Sheet.")
        
    except Exception as e:
        print(f"An error occurred while adding data to the sheet: {e}")

# Removed the '__main__' testing block as it relied on a local 'credentials.json'
# and 'config.py', which are not part of the secure Streamlit environment.
