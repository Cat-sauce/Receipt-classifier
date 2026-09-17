import sqlite3
import os
import glob

DB_PATH = "receipts.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            merchant TEXT,
            date TEXT,
            total REAL,
            category TEXT,
            english_summary TEXT,
            hindi_summary TEXT,
            contact_info TEXT,
            return_policy TEXT,
            raw_text TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_receipt(data: dict):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO receipts (
            filename, merchant, date, total, category,
            english_summary, hindi_summary, contact_info, return_policy, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("filename", "Unknown"),
        data.get("merchant", "Unknown"),
        data.get("date", "N/A"),
        data.get("total", 0.0),
        data.get("category", "Other"),
        data.get("english_summary", ""),
        data.get("hindi_summary", ""),
        data.get("contact_info", "N/A"),
        data.get("return_policy", "Not stated"),
        data.get("raw_text", "")
    ))
    conn.commit()
    conn.close()

def fetch_records(search_term="", category="All"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = """
        SELECT id, filename, merchant, date, total, category, 
               english_summary, hindi_summary, contact_info, return_policy, raw_text 
        FROM receipts WHERE 1=1
    """
    params = []

    if category != "All":
        query += " AND category = ?"
        params.append(category)

    if search_term.strip():
        query += " AND (merchant LIKE ? OR raw_text LIKE ?)"
        term = f"%{search_term.strip()}%"
        params.extend([term, term])

    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def clear_all_records():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM receipts")
    conn.commit()
    conn.close()

    # Clear stale audio files
    audio_dir = "static_audio"
    if os.path.exists(audio_dir):
        for f in glob.glob(os.path.join(audio_dir, "*.*")):
            try:
                os.remove(f)
            except OSError:
                pass
