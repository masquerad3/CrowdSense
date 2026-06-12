"""
CrowdSense Database Interface (src/auth/db.py)

Handles SQLite connections, database migrations, cryptographic audit logging,
persistent settings, session analytics, and database retention/purging.
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_DIR = ROOT_DIR / "data"
DB_PATH = DB_DIR / "crowdsense.db"


def get_db_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize the SQLite database schema and run structural migrations."""
    # Temporarily disable foreign keys during potential structural alterations
    with get_db_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")

        # ── Drop Obsolete Users Table ──────────────────────────────────────────
        conn.execute("DROP TABLE IF EXISTS users")

        # ── Migration: audit_log (Remove username column) ──────────────────────
        cursor = conn.execute("PRAGMA table_info(audit_log)")
        cols = [r[1] for r in cursor.fetchall()]
        if cols and "username" in cols:
            conn.execute("ALTER TABLE audit_log RENAME TO audit_log_old")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    action     TEXT NOT NULL,
                    details    TEXT DEFAULT '',
                    timestamp  TEXT NOT NULL,
                    entry_hash TEXT
                );
            """)
            conn.execute("""
                INSERT INTO audit_log (id, action, details, timestamp, entry_hash)
                SELECT id, action, details, timestamp, entry_hash FROM audit_log_old
            """)
            conn.execute("DROP TABLE audit_log_old")

        # ── Migration: sessions (Remove operator column) ───────────────────────
        cursor = conn.execute("PRAGMA table_info(sessions)")
        cols = [r[1] for r in cursor.fetchall()]
        if cols and "operator" in cols:
            # Drop child table first to prevent broken foreign key references
            conn.execute("DROP TABLE IF EXISTS session_readings")
            conn.execute("ALTER TABLE sessions RENAME TO sessions_old")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_label  TEXT,
                    started_at    TEXT NOT NULL,
                    ended_at      TEXT,
                    peak_count    INTEGER DEFAULT 0,
                    avg_count     REAL DEFAULT 0,
                    total_samples INTEGER DEFAULT 0,
                    alert_events  INTEGER DEFAULT 0
                );
            """)
            conn.execute("""
                INSERT INTO sessions (id, source_label, started_at, ended_at, peak_count, avg_count, total_samples, alert_events)
                SELECT id, source_label, started_at, ended_at, peak_count, avg_count, total_samples, alert_events FROM sessions_old
            """)
            conn.execute("DROP TABLE sessions_old")

        # ── Migration: sessions (Add safety_limit column if missing) ───────────
        cursor = conn.execute("PRAGMA table_info(sessions)")
        cols = [r[1] for r in cursor.fetchall()]
        if cols and "safety_limit" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN safety_limit INTEGER DEFAULT 30")

        # ── Schema Creation (If tables don't exist) ──────────────────────────
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                action     TEXT NOT NULL,
                details    TEXT DEFAULT '',
                timestamp  TEXT NOT NULL,
                entry_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                source_label  TEXT,
                started_at    TEXT NOT NULL,
                ended_at      TEXT,
                peak_count    INTEGER DEFAULT 0,
                avg_count     REAL DEFAULT 0,
                total_samples INTEGER DEFAULT 0,
                alert_events  INTEGER DEFAULT 0,
                safety_limit  INTEGER DEFAULT 30
            );

            CREATE TABLE IF NOT EXISTS session_readings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                sampled_at   TEXT NOT NULL,
                count        INTEGER,
                density      TEXT,
                alert_active INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.execute("PRAGMA foreign_keys=ON")


# ── Cryptographic Audit Logging API ───────────────────────────────────────────

def log_event(action: str, details: str = "") -> None:
    """Log an audit event bound by a cryptographic hash chain."""
    try:
        # Fetch previous hash
        try:
            with get_db_connection() as conn:
                row = conn.execute(
                    "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev_hash = row["entry_hash"] if row and row["entry_hash"] else "GENESIS"
        except Exception:
            prev_hash = "GENESIS"

        # Compute hash chain signature
        timestamp = datetime.now().isoformat()
        hash_data = f"{prev_hash}|{action}|{str(details)[:500]}|{timestamp}"
        entry_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()

        # Save to database
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO audit_log (action, details, timestamp, entry_hash) VALUES (?, ?, ?, ?)",
                (action, str(details)[:500], timestamp, entry_hash)
            )
    except Exception:
        pass


def verify_audit_log_integrity() -> bool:
    """
    Crawls the entire audit log from oldest to newest and recalculates the SHA-256
    hash chain. Returns True if all signatures match, False if tampered or broken.
    """
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT action, details, timestamp, entry_hash FROM audit_log ORDER BY id ASC"
            ).fetchall()

        prev_hash = "GENESIS"
        for row in rows:
            action = row["action"]
            details = row["details"]
            timestamp = row["timestamp"]
            stored_hash = row["entry_hash"]

            # Recalculate hash
            hash_data = f"{prev_hash}|{action}|{details}|{timestamp}"
            calc_hash = hashlib.sha256(hash_data.encode("utf-8")).hexdigest()

            if calc_hash != stored_hash:
                return False
            prev_hash = calc_hash

        return True
    except Exception:
        return False


def get_audit_log(limit: int | None = 500, search_query: str | None = None,
                  alerts_only: bool = False) -> list[dict]:
    """Retrieve audit log entries matching search and filter parameters."""
    try:
        with get_db_connection() as conn:
            sql = "SELECT action, details, timestamp, entry_hash FROM audit_log"
            conditions = []
            params = []

            if search_query:
                conditions.append("(action LIKE ? OR details LIKE ?)")
                q = f"%{search_query}%"
                params.extend([q, q])

            if alerts_only:
                conditions.append("action LIKE ?")
                params.append("ALERT%")

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


# ── Settings Persistence API ──────────────────────────────────────────────────

def save_setting(key: str, value) -> None:
    """Upsert a key-value setting."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value))
            )
    except Exception:
        pass


def get_setting(key: str, default=None):
    """Retrieve a setting value by key, returning default if not found."""
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row else default
    except Exception:
        return default


# ── Session Analytics & Pruning API ───────────────────────────────────────────

def create_session(source_label: str = "", safety_limit: int = 30) -> int | None:
    """Create a new session record and return its ID."""
    try:
        with get_db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (source_label, started_at, safety_limit) VALUES (?, ?, ?)",
                (source_label, datetime.now().isoformat(), safety_limit)
            )
            return cur.lastrowid
    except Exception:
        return None


def close_session(session_id: int, peak_count: int, avg_count: float,
                  total_samples: int, alert_events: int) -> None:
    """Finalize a session with aggregates."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at=?, peak_count=?, avg_count=?, "
                "total_samples=?, alert_events=? WHERE id=?",
                (datetime.now().isoformat(), peak_count, avg_count,
                 total_samples, alert_events, session_id)
            )
    except Exception:
        pass


def insert_reading(session_id: int, count: int,
                   density: str, alert_active: bool) -> None:
    """Insert a 1-Hz sensor reading for a session."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO session_readings (session_id, sampled_at, count, density, alert_active) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, datetime.now().isoformat(), count, density, int(alert_active))
            )
    except Exception:
        pass


def get_sessions(limit: int = 200) -> list[dict]:
    """Retrieve recent completed or active sessions, newest first."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, source_label, started_at, ended_at, "
                "peak_count, avg_count, total_samples, alert_events, safety_limit "
                "FROM sessions ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_session_readings(session_id: int) -> list[dict]:
    """Retrieve 1-Hz readings of a specific session, oldest first."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT sampled_at, count, density, alert_active "
                "FROM session_readings WHERE session_id=? ORDER BY id ASC",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def delete_session(session_id: int) -> bool:
    """Delete a session. CASCADE deletes associated readings."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return True
    except Exception:
        return False


def delete_all_sessions() -> bool:
    """Delete all sessions from the database. CASCADE deletes associated readings."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM sessions")
        log_event("DATABASE_CLEARED", "Permanently deleted all sessions and readings.")
        return True
    except Exception as exc:
        log_event("CLEAR_ERROR", str(exc))
        return False


def prune_database(retention_days: int) -> int:
    """Delete sessions and readings older than retention_days. Return number of deleted sessions."""
    if retention_days <= 0:
        return 0
    try:
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        with get_db_connection() as conn:
            # Get list of expired session IDs
            cur = conn.execute("SELECT id FROM sessions WHERE started_at < ?", (cutoff,))
            session_ids = [row["id"] for row in cur.fetchall()]
            if not session_ids:
                return 0

            # Delete them (cascading automatically deletes readings)
            placeholders = ",".join("?" for _ in session_ids)
            conn.execute(
                f"DELETE FROM sessions WHERE id IN ({placeholders})",
                session_ids
            )
            # Log prune event
            log_event("DATABASE_PRUNED", f"Purged {len(session_ids)} sessions older than {retention_days} days.")
            return len(session_ids)
    except Exception as exc:
        log_event("PRUNE_ERROR", str(exc))
        return 0
