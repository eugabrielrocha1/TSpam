"""
CyberTG – SQLite Database Manager
Stores accounts, scraped users, and app settings.
"""
import sqlite3
import os
import threading
from datetime import datetime

DB_NAME = "cybertg.db"

_lock = threading.Lock()


def _db_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DB_NAME)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            phone       TEXT UNIQUE NOT NULL,
            api_id      TEXT NOT NULL,
            api_hash    TEXT NOT NULL,
            proxy_type  TEXT DEFAULT '',
            proxy_addr  TEXT DEFAULT '',
            proxy_port  INTEGER DEFAULT 0,
            proxy_user  TEXT DEFAULT '',
            proxy_pass  TEXT DEFAULT '',
            session_file TEXT DEFAULT '',
            status      TEXT DEFAULT 'disconnected',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scraped_users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            username     TEXT DEFAULT '',
            first_name   TEXT DEFAULT '',
            last_name    TEXT DEFAULT '',
            phone        TEXT DEFAULT '',
            has_photo    INTEGER DEFAULT 0,
            last_seen    TEXT DEFAULT '',
            source_group TEXT DEFAULT '',
            scraped_at   TEXT DEFAULT (datetime('now')),
            added_status TEXT DEFAULT 'pending',
            UNIQUE(user_id, source_group)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS farmed_accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            phone       TEXT UNIQUE NOT NULL,
            api_id      TEXT NOT NULL,
            api_hash    TEXT NOT NULL,
            sms_provider TEXT DEFAULT '',
            country     TEXT DEFAULT 'US',
            cost        REAL DEFAULT 0.0,
            status      TEXT DEFAULT 'creating',
            farm_stage  TEXT DEFAULT 'new',
            created_at  TEXT DEFAULT (datetime('now')),
            aged_days   INTEGER DEFAULT 0,
            last_activity TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()


# ─── Account helpers ────────────────────────────────────────────────
def add_account(phone, api_id, api_hash, proxy_type="", proxy_addr="",
                proxy_port=0, proxy_user="", proxy_pass=""):
    with _lock:
        conn = get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO accounts
                    (phone, api_id, api_hash, proxy_type, proxy_addr,
                     proxy_port, proxy_user, proxy_pass, session_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (phone, api_id, api_hash, proxy_type, proxy_addr,
                  proxy_port, proxy_user, proxy_pass, f"sessions/{phone}"))
            conn.commit()
        finally:
            conn.close()


def get_all_accounts():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_account_status(phone, status):
    with _lock:
        conn = get_connection()
        conn.execute("UPDATE accounts SET status=? WHERE phone=?", (status, phone))
        conn.commit()
        conn.close()


def delete_account(phone):
    with _lock:
        conn = get_connection()
        conn.execute("DELETE FROM accounts WHERE phone=?", (phone,))
        conn.commit()
        conn.close()


# ─── Scraped users helpers ─────────────────────────────────────────
def insert_scraped_user(user_id, username, first_name, last_name,
                        phone, has_photo, last_seen, source_group):
    with _lock:
        conn = get_connection()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO scraped_users
                    (user_id, username, first_name, last_name, phone,
                     has_photo, last_seen, source_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name,
                  phone, 1 if has_photo else 0, last_seen, source_group))
            conn.commit()
        finally:
            conn.close()


def insert_scraped_users_batch(users_list: list):
    """Insert multiple scraped users in a single transaction."""
    if not users_list:
        return
    with _lock:
        conn = get_connection()
        try:
            conn.executemany("""
                INSERT OR IGNORE INTO scraped_users
                    (user_id, username, first_name, last_name, phone,
                     has_photo, last_seen, source_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, users_list)
            conn.commit()
        finally:
            conn.close()


def get_scraped_users(source_group=None, status="pending"):
    conn = get_connection()
    if source_group:
        rows = conn.execute(
            "SELECT * FROM scraped_users WHERE source_group=? AND added_status=? ORDER BY id",
            (source_group, status)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM scraped_users WHERE added_status=? ORDER BY id",
            (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_scraped_users():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM scraped_users ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_source_groups():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT source_group FROM scraped_users ORDER BY source_group"
    ).fetchall()
    conn.close()
    return [r["source_group"] for r in rows]


def update_user_added_status(user_id, status):
    with _lock:
        conn = get_connection()
        conn.execute(
            "UPDATE scraped_users SET added_status=? WHERE user_id=?",
            (status, user_id))
        conn.commit()
        conn.close()


def get_scraped_count(source_group=None):
    conn = get_connection()
    if source_group:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM scraped_users WHERE source_group=?",
            (source_group,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) as cnt FROM scraped_users").fetchone()
    conn.close()
    return row["cnt"]


def clear_scraped_users():
    with _lock:
        conn = get_connection()
        conn.execute("DELETE FROM scraped_users")
        conn.commit()
        conn.close()


# ─── Settings helpers ──────────────────────────────────────────────
def get_setting(key, default=""):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    with _lock:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value)))
        conn.commit()
        conn.close()


# ─── Self-Farm helpers ─────────────────────────────────────────────
def add_farmed_account(phone, api_id, api_hash, sms_provider="",
                       country="US", cost=0.0):
    """Insert a new farmed account and also add it to the main accounts table."""
    with _lock:
        conn = get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO farmed_accounts
                    (phone, api_id, api_hash, sms_provider, country, cost, status)
                VALUES (?, ?, ?, ?, ?, ?, 'created')
            """, (phone, api_id, api_hash, sms_provider, country, cost))
            # Also add to main accounts table for adder round-robin
            conn.execute("""
                INSERT OR REPLACE INTO accounts
                    (phone, api_id, api_hash, session_file, status)
                VALUES (?, ?, ?, ?, 'farmed')
            """, (phone, api_id, api_hash, f"sessions/{phone}"))
            conn.commit()
        finally:
            conn.close()


def get_farmed_accounts(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM farmed_accounts WHERE status=? ORDER BY id DESC",
            (status,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM farmed_accounts ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_farm_status(phone, status, farm_stage=None):
    with _lock:
        conn = get_connection()
        if farm_stage:
            conn.execute(
                "UPDATE farmed_accounts SET status=?, farm_stage=? WHERE phone=?",
                (status, farm_stage, phone))
        else:
            conn.execute(
                "UPDATE farmed_accounts SET status=? WHERE phone=?",
                (status, phone))
        conn.commit()
        conn.close()


def update_farm_activity(phone):
    """Update last_activity timestamp and increment aged_days."""
    with _lock:
        conn = get_connection()
        conn.execute("""
            UPDATE farmed_accounts
            SET last_activity = datetime('now'),
                aged_days = CAST((julianday('now') - julianday(created_at)) AS INTEGER)
            WHERE phone = ?
        """, (phone,))
        conn.commit()
        conn.close()


def get_farm_stats():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM farmed_accounts").fetchone()["c"]
    created = conn.execute(
        "SELECT COUNT(*) as c FROM farmed_accounts WHERE status='created'").fetchone()["c"]
    aged = conn.execute(
        "SELECT COUNT(*) as c FROM farmed_accounts WHERE aged_days >= 30").fetchone()["c"]
    failed = conn.execute(
        "SELECT COUNT(*) as c FROM farmed_accounts WHERE status='failed'").fetchone()["c"]
    cost = conn.execute(
        "SELECT COALESCE(SUM(cost), 0) as c FROM farmed_accounts").fetchone()["c"]
    conn.close()
    return {"total": total, "created": created, "aged": aged, "failed": failed, "total_cost": cost}
