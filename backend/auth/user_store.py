"""
User store using SQLite.
DB path: data/users.db (created automatically).
Tables: users, user_sessions, favorites
"""
import sqlite3, secrets, time
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).parent.parent.parent / "data" / "users.db"

def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            );
            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                market TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                added_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                UNIQUE(user_id, market, code)
            );
        """)

def register_user(email: str, password: str) -> dict | None:
    """Returns user dict on success, raises ValueError on conflict."""
    pw_hash = generate_password_hash(password)
    try:
        with _conn() as con:
            cur = con.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?) RETURNING id, email, created_at",
                (email.strip().lower(), pw_hash)
            )
            row = cur.fetchone()
            return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}
    except sqlite3.IntegrityError:
        raise ValueError("Email already registered")

def login_user(email: str, password: str) -> str | None:
    """Returns session token on success, None on failure."""
    with _conn() as con:
        row = con.execute("SELECT id, password_hash FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            return None
        token = secrets.token_hex(32)
        expires = int(time.time()) + 30 * 24 * 3600  # 30 days
        con.execute("INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?,?,?)", (token, row["id"], expires))
        return token

def get_user_by_token(token: str) -> dict | None:
    """Validate session token, return user dict or None."""
    if not token:
        return None
    with _conn() as con:
        row = con.execute(
            """SELECT u.id, u.email, u.created_at FROM users u
               JOIN user_sessions s ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > strftime('%s','now')""",
            (token,)
        ).fetchone()
        return dict(row) if row else None

def logout_token(token: str):
    with _conn() as con:
        con.execute("DELETE FROM user_sessions WHERE token = ?", (token,))

def get_favorites(user_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT market, code, name, added_at FROM favorites WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def add_favorite(user_id: int, market: str, code: str, name: str) -> bool:
    try:
        with _conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO favorites (user_id, market, code, name) VALUES (?,?,?,?)",
                (user_id, market.upper(), code, name)
            )
        return True
    except Exception:
        return False

def remove_favorite(user_id: int, market: str, code: str) -> bool:
    with _conn() as con:
        con.execute("DELETE FROM favorites WHERE user_id=? AND market=? AND code=?", (user_id, market.upper(), code))
    return True
