"""
CrowdSense Auth Database (src/auth/db.py)

Handles password hashing (scrypt) and database connection/schema setup.
Includes account lockout logic for security.
"""

import sqlite3
import hashlib
import hmac
import os
import base64
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_DIR = ROOT_DIR / "data"
DB_PATH = DB_DIR / "crowdsense.db"

# scrypt cost parameters (OWASP minimum for interactive logins)
SCRYPT_N = 2 ** 14 # CPU Cost
SCRYPT_R = 8 # Memory Cost
SCRYPT_P = 1 # Parallelism Cost
SCRYPT_DKLEN = 32 # Length of the desired key

# Lockout policy
MAX_ATTEMPTS = 5 # Maximum number of failed attempts before lockout
LOCKOUT_MINUTES = 15 # Duration of lockout in minutes


# Password hashing helpers

def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN
    )
    return (base64.b64encode(salt).decode("ascii") + "$" +
            base64.b64encode(key).decode("ascii"))


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, key_b64 = stored.split("$", 1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# Database connection

def get_db_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# Database Schema & Initialization

def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT    UNIQUE NOT NULL,
                password_hash   TEXT    NOT NULL,
                role            TEXT    NOT NULL DEFAULT 'user'
                                        CHECK(role IN ('admin', 'user')),
                created_at      TEXT    NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until    TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT NOT NULL,
                action    TEXT NOT NULL,
                details   TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                entry_hash TEXT
            );
        """)

        # Migrate existing databases that predate the lockout columns
        existing_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "failed_attempts" not in existing_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"
            )
        if "locked_until" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")

        # Migrate existing audit_log to include entry_hash column and backfill hashes
        existing_audit_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()
        }
        if "entry_hash" not in existing_audit_cols:
            conn.execute("ALTER TABLE audit_log ADD COLUMN entry_hash TEXT")
            rows = conn.execute("SELECT id, username, action, details, timestamp FROM audit_log ORDER BY id ASC").fetchall()
            prev_hash = "GENESIS"
            for row in rows:
                row_id = row["id"]
                hash_data = f"{prev_hash}|{row['username']}|{row['action']}|{row['details']}|{row['timestamp']}"
                curr_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()
                conn.execute("UPDATE audit_log SET entry_hash=? WHERE id=?", (curr_hash, row_id))
                prev_hash = curr_hash

        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            insert_user(conn, "admin",  "Admin@123",  "admin")
            insert_user(conn, "viewer", "Viewer@123", "user")


def insert_user(conn: sqlite3.Connection, username: str,
                 password: str, role: str) -> None:
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), role, datetime.now().isoformat())
    )


# User Authentication & Management API

def authenticate(username: str, password: str) -> dict | None:
    """
    Verify credentials.

    Returns:
      {'id', 'username', 'role'}  - success
      {'locked': True}            - account is locked (too many failures)
      None                        - invalid credentials
    """
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT id, password_hash, role, failed_attempts, locked_until "
                "FROM users WHERE username = ?",
                (username,)
            ).fetchone()

        if row is None:
            verify_password("_dummy_", hash_password("_dummy_"))
            return None

        # Check persistent lockout
        locked_until = row["locked_until"]
        if locked_until:
            if datetime.now().isoformat() < locked_until:
                return {"locked": True}
            # Lock period expired — reset counter
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?",
                    (username,)
                )

        if verify_password(password, row["password_hash"]):
            # Success — clear any previous failure counts
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?",
                    (username,)
                )
            return {"id": row["id"], "username": username, "role": row["role"]}

        # Wrong password — increment counter, lock if threshold reached
        new_attempts = (row["failed_attempts"] or 0) + 1
        new_lock     = None
        if new_attempts >= MAX_ATTEMPTS:
            new_lock = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET failed_attempts=?, locked_until=? WHERE username=?",
                (new_attempts, new_lock, username)
            )
        return None

    except Exception:
        return None


def reset_lockout(username: str) -> bool:
    """Unlock an account and reset its failed-attempt counter."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?",
                (username,)
            )
        return True
    except Exception:
        return False


def lock_user(username: str) -> bool:
    """Manually lock an account for LOCKOUT_MINUTES."""
    try:
        lock_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET locked_until=? WHERE username=?",
                (lock_until, username)
            )
        return True
    except Exception:
        return False


def update_role(username: str, new_role: str) -> bool:
    """Change a user's role (admin/user)."""
    if new_role not in ("admin", "user"):
        return False
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET role=? WHERE username=?",
                (new_role, username)
            )
        return True
    except Exception:
        return False


def delete_user(username: str) -> bool:
    """Permanently remove a user account."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM users WHERE username=?", (username,))
        return True
    except Exception:
        return False


def change_password(username: str, new_password: str) -> bool:
    """Set a new password for a user account."""
    try:
        new_hash = hash_password(new_password)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash=?, failed_attempts=0, locked_until=NULL WHERE username=?",
                (new_hash, username)
            )
        return True
    except Exception:
        return False


def create_user(username: str, password: str, role: str = "user") -> str | None:
    """
    Create a new user. Returns None on success, or an error string on failure.
    """
    try:
        with get_db_connection() as conn:
            insert_user(conn, username, password, role)
        return None
    except sqlite3.IntegrityError:
        return "username_taken"
    except Exception as e:
        return str(e)


def log_event(username: str, action: str, details: str = "") -> None:
    try:
        # Fetch previous hash from database
        try:
            with get_db_connection() as conn:
                row = conn.execute(
                    "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev_hash = row["entry_hash"] if row and row["entry_hash"] else "GENESIS"
        except Exception:
            prev_hash = "GENESIS"

        # Compute the hash chain for the new entry
        timestamp = datetime.now().isoformat()
        hash_data = f"{prev_hash}|{username}|{action}|{str(details)[:500]}|{timestamp}"
        entry_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()

        # Save to database
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO audit_log (username, action, details, timestamp, entry_hash) VALUES (?, ?, ?, ?, ?)",
                (username, action, str(details)[:500], timestamp, entry_hash)
            )
    except Exception:
        pass


def verify_audit_log_integrity() -> bool:
    """
    Crawls through the entire audit log from oldest to newest
    and recalculates the hash chain to check for tampering.
    Returns True if valid, False if tampered/broken.
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT username, action, details, timestamp, entry_hash "
                "FROM audit_log ORDER BY id ASC"
            ).fetchall()
        
        prev_hash = "GENESIS"
        for row in rows:
            username = row["username"]
            action = row["action"]
            details = row["details"]
            timestamp = row["timestamp"]
            stored_hash = row["entry_hash"]
            
            # Recalculate hash
            hash_data = f"{prev_hash}|{username}|{action}|{details}|{timestamp}"
            calc_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()
            
            if calc_hash != stored_hash:
                return False  # Chain broken
            prev_hash = calc_hash
            
        return True # All checks passed
    except Exception:
        return False


def get_audit_log(limit: int | None = 500, username: str | None = None, search_query: str | None = None) -> list[dict]:
    try:
        with get_db_connection() as conn:
            sql = "SELECT username, action, details, timestamp, entry_hash FROM audit_log"
            conditions = []
            params = []
            
            if username and username != "[All Users]":
                conditions.append("username = ?")
                params.append(username)
                
            if search_query:
                conditions.append("(username LIKE ? OR action LIKE ? OR details LIKE ?)")
                q = f"%{search_query}%"
                params.extend([q, q, q])
                
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
                
            sql += " ORDER BY id DESC"
            
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
                
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_users() -> list[dict]:
    """Return all user accounts with lockout status. No password hashes."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, username, role, created_at, failed_attempts, locked_until "
                "FROM users ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
