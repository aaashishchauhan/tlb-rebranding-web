import imaplib
import sys
import email
import json
import os
import time
import logging
import re
import shutil
from typing import List, Tuple, Dict, Any
from email.header import decode_header

import queue_db
import pdfplumber
from name_extractor import extract_patient_name, extract_test_name, normalize_text

# ===========================
# 🔧 Configuration
# ===========================
CONFIG_PATH = "config.json"
STATE_FILE = "thyrocare_state.json"
TEMP_JOBS_DIR = "temp_jobs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PRODUCER] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Producer")

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"last_processed_uid": 0, "last_processed_time": 0}
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {"last_processed_uid": 0, "last_processed_time": 0}
            return data
    except Exception:
        return {"last_processed_uid": 0, "last_processed_time": 0}

def save_state(state: Dict[str, Any]):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def decode_str(s) -> str:
    if not s: return ""
    if isinstance(s, str): return s
    try:
        parts = decode_header(s)
        pieces = []
        for part, enc in parts:
            if isinstance(part, bytes):
                pieces.append(part.decode(enc or "utf-8", errors="ignore"))
            else:
                pieces.append(part)
        return "".join(pieces)
    except: return str(s)

def connect_imap(config: Dict[str, Any]):
    account = config["accounts"][0] # Correct key based on config.json
    imap = imaplib.IMAP4_SSL(account["imap_server"], account.get("imap_port", 993))
    imap.login(account["email"], account["password"])
    imap.select("INBOX")
    return imap

def extract_thyrocare_link(msg_obj) -> str:
    body_texts = []
    for part in msg_obj.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    body_texts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
            except: pass
    
    full_body = "\n".join(body_texts)
    m = re.search(r"https://thyro\.care/n/o/[^\s\"'<>]+", full_body)
    return m.group(0) if m else None

def process_email(imap, uid: int, config: Dict[str, Any]) -> bool:
    """
    Fetches email, extracts content, pushes to queue.
    Returns True if a job was added (or if we should assume it's processed).
    """
    try:
        res, data = imap.uid("fetch", str(uid), "(RFC822)")
        if res != "OK":
            logger.error(f"Failed to fetch UID {uid}")
            return False
            
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        
        # Check Sender/Subject filter
        sender = (msg.get("From") or "").lower()
        subject = (msg.get("Subject") or "").lower()
        
        allowed_labs = [l.lower() for l in config["accounts"][0].get("labs", [])]
        is_relevant = False
        if allowed_labs:
            if any(l in sender for l in allowed_labs): is_relevant = True
        elif "thyrocare" in sender or "thyrocare" in subject:
            is_relevant = True
            
        if not is_relevant:
            logger.info(f"Skipping UID {uid} (Irrelevant)")
            return True # Mark as processed so we don't check again
            
        # Create Temp Dir for this UID
        job_dir = os.path.join(TEMP_JOBS_DIR, str(uid))
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        os.makedirs(job_dir, exist_ok=True)
        
        jobs_added = 0
        
        # 1. Attachments
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart': continue
            fname = part.get_filename()
            if not fname: continue
            fname = decode_str(fname)
            
            if fname.lower().endswith(".pdf"):
                payload = part.get_payload(decode=True)
                if payload:
                    file_path = os.path.join(job_dir, fname)
                    with open(file_path, "wb") as f:
                        f.write(payload)
                    
                    # --- NEW: RENAME LOGIC ---
                    try:
                        # 1. Extract Patient Name
                        res_name = extract_patient_name(file_path, original_filename=fname)
                        if isinstance(res_name, tuple):
                            extracted_name, source = res_name
                        else:
                            extracted_name = res_name
                            source = "filename"

                        # 2. Extract Test Name
                        extracted_text = ""
                        try:
                            with pdfplumber.open(file_path) as pdf_obj:
                                for p_obj in pdf_obj.pages:
                                    extracted_text += (p_obj.extract_text() or "") + "\n"
                        except Exception as e:
                            logger.error(f"Error extracting text from PDF {fname}: {e}")
                        
                        test_name = extract_test_name(extracted_text)
                        
                        # 3. Sanitize and Rename
                        safe_patient = re.sub(r'[\\/*?:"<>|]', "", extracted_name).strip() or "Unknown"
                        safe_test = re.sub(r'[\\/*?:"<>|]', "", test_name).strip() or "REPORT"
                        
                        new_fname = f"{safe_patient}_{safe_test}.pdf"
                        new_file_path = os.path.join(job_dir, new_fname)
                        
                        # Handle collision if multiple files have same extracted name in same job
                        if os.path.exists(new_file_path):
                            timestamp = int(time.time())
                            new_fname = f"{safe_patient}_{safe_test}_{timestamp}.pdf"
                            new_file_path = os.path.join(job_dir, new_fname)
                            
                        os.rename(file_path, new_file_path)
                        logger.info(f"Renamed {fname} -> {new_fname} (Patient: {extracted_name}, Test: {test_name})")
                        
                        # Update variables for payload
                        file_path = new_file_path
                        fname = new_fname
                        
                    except Exception as e:
                        logger.error(f"Failed to rename {fname}: {e}")
                        # If renaming fails, we keep original file_path and fname
                    
                    job_payload = {
                        "type": "file",
                        "path": os.path.abspath(file_path),
                        "filename": fname,
                        "email_subject": subject,
                        "email_sender": sender
                    }
                    
                    if queue_db.add_job(uid, "file", job_payload):
                        jobs_added += 1
                        
        # 2. Links
        if jobs_added == 0:
            link = extract_thyrocare_link(msg)
            if link:
                job_payload = {
                    "type": "link",
                    "url": link,
                    "email_subject": subject,
                    "email_sender": sender
                }
                if queue_db.add_job(uid, "link", job_payload):
                    jobs_added += 1
        
        if jobs_added > 0:
            logger.info(f"✅ UID {uid} -> Enqueued {jobs_added} jobs.")
        else:
            logger.info(f"UID {uid} -> No relevant content found.")
            # Cleanup empty dir
            try: os.rmdir(job_dir) 
            except: pass
            
        return True

    except Exception as e:
        logger.error(f"Error processing UID {uid}: {e}")
        return False

def main():
    logger.info("🚀 Starting Producer...")
    
    # Initialize DB
    queue_db.init_db()
    
    config = load_config(CONFIG_PATH)
    state = load_state()
    
    while True:
        try:
            imap = connect_imap(config)
            logger.info("Connected to IMAP.")
            
            while True:
                last_uid = state["last_processed_uid"]
                logger.info(f"🔍 Searching for UIDs > {last_uid}...")
                
                # Fetch UIDs
                # SEARCH criteria: UID X:* ... but to get only NEW we must know the next valid one. 
                # Imaplib doesn't support "Greater Than" easily without range.
                # easiest is to fetch ALL or fetch range last_uid+1:*
                
                search_crit = f"UID {last_uid + 1}:*"
                res, data = imap.uid("search", None, search_crit)
                
                if res == "OK":
                    uids = [int(u) for u in data[0].split()]
                    uids = [u for u in uids if u > last_uid] # Double check
                    uids.sort()
                    
                    if uids:
                        logger.info(f"Found {len(uids)} new emails.")
                        
                        for uid in uids:
                            if process_email(imap, uid, config):
                                state["last_processed_uid"] = uid
                                save_state(state)
                            else:
                                # If processing failed drastically, stop loop to retry later?
                                # Or just skip and log error?
                                # Better to retry connection if it was a connection error.
                                pass 
                    else:
                        logger.info("No new emails.")
                
                logger.info("💤 Sleeping for 10 minutes...")
                time.sleep(600)
                # Keep Alive
                try: imap.noop()
                except: break # Reconnect
                
        except Exception as e:
            logger.error(f"IMAP Connection Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
