import sqlite3
import json
import time
import logging
from typing import Dict, Any, Optional

DB_FILE = "jobs.db"

# Configure logging for the Queue module
logger = logging.getLogger("QueueDB")
logger.setLevel(logging.INFO)

def get_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10) # 10s timeout to wait for locks
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return None

def init_db():
    """Initializes the database table and indices."""
    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        
        # Create Jobs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid INTEGER NOT NULL,
                tenant_id TEXT,
                job_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT DEFAULT 'pending', 
                retry_count INTEGER DEFAULT 0,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create Indicies for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_created ON jobs(status, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uid ON jobs(uid)")
        
        conn.commit()
        logger.info("✅ Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    finally:
        conn.close()

def add_job(uid: int, job_type: str, payload: Dict[str, Any], tenant_id: str = None) -> bool:
    """Adds a new job to the queue."""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (uid, tenant_id, job_type, payload, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (uid, tenant_id, job_type, json.dumps(payload)))
        conn.commit()
        logger.info(f"📥 Job added: UID={uid}, Type={job_type}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add job: {e}")
        return False
    finally:
        conn.close()

def get_next_job() -> Optional[Dict[str, Any]]:
    """
    Fetches the next pending job atomically using exclusive locking.
    Returns the job dict or None.
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        # Start an immediate transaction to lock the DB for writing
        conn.execute("BEGIN IMMEDIATE") 
        cursor = conn.cursor()
        
        # Select oldest pending job
        cursor.execute("""
            SELECT id, uid, job_type, payload, retry_count 
            FROM jobs 
            WHERE status = 'pending' 
            AND (retry_count = 0 OR updated_at < datetime('now', '-2 minutes'))
            ORDER BY created_at ASC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row:
            job_id = row["id"]
            # Mark as processing
            cursor.execute("""
                UPDATE jobs 
                SET status = 'processing', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (job_id,))
            
            conn.commit()
            
            return {
                "id": row["id"],
                "uid": row["uid"],
                "job_type": row["job_type"],
                "payload": json.loads(row["payload"]),
                "retry_count": row["retry_count"]
            }
        else:
            conn.rollback() # Nothing to do
            return None

    except Exception as e:
        logger.error(f"❌ Error fetching next job: {e}")
        try:
            conn.rollback()
        except:
            pass
        return None
    finally:
        conn.close()

def complete_job(job_id: int):
    """Marks a job as successfully completed."""
    conn = get_connection()
    if not conn:
        return
    
    try:
        conn.execute("""
            UPDATE jobs 
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (job_id,))
        conn.commit()
        logger.info(f"✅ Job {job_id} marked COMPLETED.")
    except Exception as e:
        logger.error(f"❌ Failed to complete job {job_id}: {e}")
    finally:
        conn.close()

def fail_job(job_id: int, error_msg: str):
    """
    Marks a job as failed. Increments retry_count. 
    If retry_count > 3, status becomes 'failed' (permanent).
    Else status becomes 'pending' (for retry).
    """
    conn = get_connection()
    if not conn:
        return

    MAX_RETRIES = 3

    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        
        # Get current retry count
        cursor.execute("SELECT retry_count FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        if row:
            current_retries = row["retry_count"]
            new_retries = current_retries + 1
            
            if new_retries > MAX_RETRIES:
                new_status = 'failed'
                logger.error(f"⛔ Job {job_id} PERMANENTLY FAILED after {new_retries} retries. Error: {error_msg}")
            else:
                new_status = 'pending'
                logger.warning(f"⚠️ Job {job_id} failed. Retrying ({new_retries}/{MAX_RETRIES}). Error: {error_msg}")
            
            cursor.execute("""
                UPDATE jobs 
                SET status = ?, retry_count = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_status, new_retries, error_msg, job_id))
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ Failed to mark job {job_id} as failed: {e}")
        try:
            conn.rollback()
        except:
            pass
    finally:
        conn.close()

def reset_stuck_jobs(timeout_minutes=10):
    """
    Resets jobs that have been stuck in 'processing' for too long.
    This handles worker crashes.
    """
    conn = get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        # SQLite's datetime function modifiers: '-10 minutes'
        cursor.execute(f"""
            UPDATE jobs 
            SET status = 'pending', error = 'Reset from stuck state', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'processing' 
            AND updated_at < datetime('now', '-{timeout_minutes} minutes')
        """)
        
        if cursor.rowcount > 0:
            logger.warning(f"🔄 Reset {cursor.rowcount} STUCK jobs to pending.")
            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ Failed to reset stuck jobs: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Test initialization
    logging.basicConfig(level=logging.INFO)
    init_db()
    
