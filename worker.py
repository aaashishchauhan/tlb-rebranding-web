import time
import sys
import json
import os
import logging
import shutil
import queue_db
import requests
import traceback
import re
from typing import Dict, Any, Optional
import io
import pdfplumber

# PDF & Drive Imports
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Local imports (assumed to exist or need to be copied)
try:
    from name_extractor import extract_patient_name, extract_test_name
except ImportError:
    # Define dummy or copy implementation if file doesn't exist
    def extract_patient_name(path, original_filename): return "Unknown", "fallback"
    def extract_test_name(text): return "REPORT"

# ===========================
# 🔧 Configuration
# ===========================
CONFIG_PATH = "config.json"
API_UPLOAD_URL = "https://toplabsbazaardev-git-21-nov-issue-pratiks-projects-7c12a0c0.vercel.app/booking-services/upload-report"
LOG_FILE = "worker.log"

# Google Drive Check
SERVICE_ACCOUNT_FILE = "service_account.json"
GOOGLE_DRIVE_FOLDER_ID = "Reports"

# Branding Config
COVER_IMAGE = "firstpage.png"
LEFT_LOGO = "toplabslogo.png"
RIGHT_LOGO = "lab_thyrocare.png"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Worker")

# ===========================
# 🛠️ Helper Functions
# ===========================

def get_todays_download_dir() -> str:
    import datetime
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    base_dir = os.path.abspath("download_pdf")
    target_dir = os.path.join(base_dir, today_str)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

# --- Google Drive Logic ---
_drive_service = None
def get_drive_service():
    global _drive_service
    if _drive_service: return _drive_service
    
    if not os.path.exists(SERVICE_ACCOUNT_FILE) and not os.path.exists('token.json'):
         logger.warning("No Drive credentials found.")
         return None
         
    try:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing Google Drive token...")
                    creds.refresh(Request())
                    # Save the refreshed token
                    with open('token.json', 'w') as token:
                        token.write(creds.to_json())
                    logger.info("Token refreshed and saved.")
                except Exception as refresh_error:
                    logger.error(f"Failed to refresh token: {refresh_error}")
                    creds = None # Force re-auth or failure
            
        if not creds and os.path.exists(SERVICE_ACCOUNT_FILE):
             # Try service account if it's actually a service account file
             # (Wait, we know it's a client secret file, so this fallback is legacy)
             try:
                 creds = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                 logger.info("Using Service Account credentials.")
             except Exception:
                 # It's probably a client secrets file, main.py should handle it
                 pass

        if not creds or not creds.valid:
            logger.error("No valid credentials available for Google Drive.")
            return None

        _drive_service = build('drive', 'v3', credentials=creds)
        return _drive_service
    except Exception as e:
        logger.error(f"Drive Init Failed: {e}")
        return None

def get_or_create_drive_folder(service, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id: query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = results.get('files', [])
    if files: return files[0]['id']
    
    metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id: metadata['parents'] = [parent_id]
    folder = service.files().create(body=metadata, fields='id').execute()
    return folder.get('id')

def upload_to_drive(file_path):
    service = get_drive_service()
    if not service: return False
    try:
        import datetime
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        parent_id = get_or_create_drive_folder(service, "Reports")
        folder_id = get_or_create_drive_folder(service, today_str, parent_id)
        
        metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
        media = MediaFileUpload(file_path, mimetype='application/pdf')
        service.files().create(body=metadata, media_body=media).execute()
        logger.info(f"☁️ Uploaded to Drive: {os.path.basename(file_path)}")
        return True
    except Exception as e:
        logger.error(f"Drive Upload Failed: {e}")
        return False

# --- Branding Logic ---
def create_cover_page(image_path):
    try:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        c.drawImage(image_path, 0, 0, width=A4[0], height=A4[1])
        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    except: return None

def create_header_overlay(left, right):
    try:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        w, h = A4
        header_h = 100
        c.setFillColorRGB(1,1,1)
        c.rect(0, h-header_h, w, header_h, fill=1, stroke=0)
        
        if os.path.exists(left):
            img_l = ImageReader(left)
            iw, ih = img_l.getSize()
            aspect = ih/float(iw)
            th = header_h * 0.8
            tw = th / aspect
            c.drawImage(left, 20, h - (header_h/2) - (th/2), width=tw, height=th, mask='auto')
            
        if os.path.exists(right):
            img_r = ImageReader(right)
            iw, ih = img_r.getSize()
            aspect = ih/float(iw)
            th = header_h * 0.8
            tw = th / aspect
            c.drawImage(right, w - tw - 20, h - (header_h/2) - (th/2), width=tw, height=th, mask='auto')
            
        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    except: return None

def apply_branding(input_path, output_path):
    try:
        if not os.path.exists(COVER_IMAGE):
            shutil.copy(input_path, output_path)
            return

        writer = PdfWriter()
        reader = PdfReader(input_path)
        
        cover = create_cover_page(COVER_IMAGE)
        if cover: writer.add_page(cover)
        
        header = create_header_overlay(LEFT_LOGO, RIGHT_LOGO)
        
        for i in range(1, len(reader.pages)):
            page = reader.pages[i]
            if i < len(reader.pages) - 1 and header:
                page.merge_page(header)
            writer.add_page(page)
            
        with open(output_path, "wb") as f:
            writer.write(f)
        logger.info(f"✨ Branding applied to {output_path}")
        
    except Exception as e:
        logger.error(f"Branding failed: {e}")
        shutil.copy(input_path, output_path)

# --- API Logic ---
def upload_to_api(file_path, patient_name):
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/pdf")}
            data = {"patientName": patient_name}
            res = requests.post(API_UPLOAD_URL, files=files, data=data)
            if res.status_code == 200:
                logger.info(f"✅ API Upload Success: {patient_name}")
                return True
            else:
                logger.error(f"❌ API Upload Failed: {res.text}")
                return False
    except Exception as e:
        logger.error(f"❌ API Error: {e}")
        return False

# ===========================
# 🚀 Job Processor
# ===========================

def process_job(job):
    job_id = job["id"]
    payload = job["payload"]
    uid = job["uid"]
    
    logger.info(f"⚙️ Processing Job {job_id} (UID {uid})")
    
    temp_path = None
    final_path = None
    
    try:
        # Determine Source File
        if job["job_type"] == "file":
             temp_path = payload["path"]
             if not os.path.exists(temp_path):
                 raise FileNotFoundError(f"Source file missing: {temp_path}")
                 
        elif job["job_type"] == "link":
             # Fetch Link via Playwright/Subprocess
             url = payload["url"]
             # We reuse the fetch_url.py script or logic
             # Assuming we can run the subprocess just like in new_reports.py
             import subprocess
             import sys
             import tempfile
             
             fd, temp_path = tempfile.mkstemp(prefix="thyro_", suffix=".pdf")
             os.close(fd)
             
             script_path = "fetch_url.py" # Assumed in CWD
             res = subprocess.run([sys.executable, script_path, url, temp_path], capture_output=True)
             if res.returncode != 0 or os.path.getsize(temp_path) == 0:
                 error_details = f"Stdout: {res.stdout.decode('utf-8', errors='ignore')} | Stderr: {res.stderr.decode('utf-8', errors='ignore')}"
                 raise Exception(f"Failed to fetch URL: {url} | {error_details}")
                 
        # Extraction
        # Try to use imported extractors, fallback to defaults
        p_name, _ = extract_patient_name(temp_path, payload.get("filename", "report.pdf"))
        
        # Test Name Extraction
        extracted_text = ""
        try:
            with pdfplumber.open(temp_path) as pdf_obj:
                for p_obj in pdf_obj.pages:
                    extracted_text += (p_obj.extract_text() or "") + "\n"
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            
        t_name = extract_test_name(extracted_text)
        logger.info(f"Extracted: '{p_name}' | Test: '{t_name}'")
        
        # Determine Final Path
        safe_p = re.sub(r'[\\/*?:"<>|]', "", p_name).strip() or "Unknown"
        safe_t = re.sub(r'[\\/*?:"<>|]', "", t_name).strip() or "REPORT"
        
        todays_dir = get_todays_download_dir()
        final_fname = f"{safe_p}_{safe_t}.pdf"
        final_path = os.path.join(todays_dir, final_fname)
        
        # Branding
        apply_branding(temp_path, final_path)
        
        # Uploads
        drive_ok = upload_to_drive(final_path)
        api_ok = upload_to_api(final_path, p_name)
        
        if drive_ok or api_ok:
            queue_db.complete_job(job_id)
            # Cleanup
            try: 
                if os.path.exists(final_path): os.remove(final_path)
                # If it was a temp download (link), remove it
                if job["job_type"] == "link" and os.path.exists(temp_path): os.remove(temp_path)
                
                # Cleanup producer's temp file after success
                if job["job_type"] == "file" and os.path.exists(temp_path):
                    os.remove(temp_path)
                    # Also remove parent dir if empty
                    parent = os.path.dirname(temp_path)
                    try: os.rmdir(parent) 
                    except: pass
            except: pass
        else:
            raise Exception("Both Drive and API uploads failed")

    except Exception as e:
        queue_db.fail_job(job_id, str(e))
        logger.error(f"Job {job_id} Failed: {e}")
        traceback.print_exc()

def main():
    logger.info("👷 Worker Started...")
    queue_db.init_db()
    
    # Check dependencies
    if not os.path.exists(COVER_IMAGE):
        logger.warning(f"⚠️ Cover image {COVER_IMAGE} not found!")

    while True:
        try:
            # 1. Reset stuck jobs (Crash recovery)
            queue_db.reset_stuck_jobs()
            
            # 2. Get Job
            job = queue_db.get_next_job()
            
            if job:
                process_job(job)
            else:
                # logger.info("Waiting for jobs...") # Uncomment if needed, but silence is golden
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
