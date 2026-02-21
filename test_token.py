
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def test_refresh():
    if not os.path.exists('token.json'):
        print("token.json not found")
        return
    
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    print(f"Current token expiry: {creds.expiry}")
    print(f"Is valid: {creds.valid}")
    print(f"Is expired: {creds.expired}")
    
    if creds.expired and creds.refresh_token:
        print("Attempting refresh...")
        try:
            creds.refresh(Request())
            print("Refresh successful!")
            print(f"New expiry: {creds.expiry}")
            with open('token_test_new.json', 'w') as token:
                token.write(creds.to_json())
            print("Saved refreshed token to token_test_new.json")
        except Exception as e:
            print(f"Refresh failed: {e}")
    else:
        print("No refresh needed or no refresh token available")

if __name__ == "__main__":
    test_refresh()
