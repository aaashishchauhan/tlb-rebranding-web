import subprocess
import sys
import time
import os
import signal
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = "service_account.json" # This is actually client_secrets.json

def ensure_google_creds():
    """Checks if token.json is valid, refreshes it, or triggers a new login flow."""
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            print(f"⚠️ Error loading token.json: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("🔄 Refreshing expired Google Drive token...")
                creds.refresh(Request())
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                print("✅ Token refreshed successfully.")
            except Exception as e:
                print(f"❌ Refresh failed: {e}. A new login is required.")
                creds = None
        
        if not creds:
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                print(f"❌ Error: {SERVICE_ACCOUNT_FILE} not found. Cannot perform authentication.")
                return False
            
            print("🔑 Starting new Google Drive login flow...")
            # Load config and potentially flip 'web' to 'installed' for local flow compatibility
            with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                config = json.load(f)
            
            if 'web' in config:
                flow = InstalledAppFlow.from_client_config(config, SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(SERVICE_ACCOUNT_FILE, SCOPES)

            # Droplet/Headless support:
            # If we can't open a browser, run_local_server might fail or wait forever.
            # We add a small helper message.
            print("🌐 If you are on a remote server (Droplet), you might need to:")
            print("   1. Run this locally first to generate token.json")
            print("   2. Copy token.json to the server.")
            
            try:
                # Flow with local server (works if user is SSH-ing with port forwarding or on local machine)
                creds = flow.run_local_server(port=8080, prompt='consent', timeout_seconds=120)
            except Exception as e:
                print(f"⚠️ Could not start local server or browser: {e}")
                print("🔄 Attempting manual console flow...")
                # Note: Newer versions of google-auth-oauthlib don't support run_console()
                # The best way is to run locally and copy token.json.
                return False
            
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
            print("✅ New token saved to token.json")
    
    return True

def main():
    print("🚀 Starting Report Automation System (Producer + Worker)...")
    
    # 0. Ensure Google Drive Credentials are valid
    if not ensure_google_creds():
        print("❌ Could not verify Google Drive credentials. Exiting.")
        sys.exit(1)

    # Paths to scripts
    base_dir = os.path.dirname(os.path.abspath(__file__))
    producer_script = os.path.join(base_dir, "producer.py")
    worker_script = os.path.join(base_dir, "worker.py")
    
    processes = []
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # Start Producer
        print(f"Starting Producer...")
        # We pass stdout/stderr to sys.stdout/stderr to stream logs to this console
        p_producer = subprocess.Popen([sys.executable, "-u", producer_script], cwd=base_dir, env=env)
        processes.append(p_producer)
        
        # Start Worker
        print(f"Starting Worker...")
        p_worker = subprocess.Popen([sys.executable, "-u", worker_script], cwd=base_dir, env=env)
        processes.append(p_worker)
        
        print("✅ System Running! Press Ctrl+C to stop both.")
        
        # Monitor Loop
        while True:
            time.sleep(1)
            if p_producer.poll() is not None:
                print("⚠️ Producer has exited unexpectedly!")
                break
            if p_worker.poll() is not None:
                print("⚠️ Worker has exited unexpectedly!")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping system...")
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("👋 Shutdown complete.")

if __name__ == "__main__":
    main()
