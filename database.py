"""SQLite Persistent Memory for Conversations and Support Tickets.

Provides storage and retrieval for:
- Chat session conversation history (demonstrating agent memory)
- Customer support ticket creation and lookups
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "ecommerce_memory.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get an SQLite connection with Row factory enabled."""
    path = db_path or os.getenv("DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables if they do not exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Conversations Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_query TEXT NOT NULL,
                category TEXT,
                tool_used TEXT,
                response TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )

        # Support Tickets Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id TEXT PRIMARY KEY,
                issue TEXT NOT NULL,
                category TEXT,
                order_id TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'Open',
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_conversation(
    session_id: str,
    user_query: str,
    category: Optional[str],
    tool_used: Optional[str],
    response: str,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Save an interaction into the conversations table."""
    init_db(db_path)
    ts = timestamp or datetime.now().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conversations (session_id, user_query, category, tool_used, response, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_query, category, tool_used, response, ts),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_recent_conversations(
    session_id: Optional[str] = None,
    limit: int = 5,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve recent conversations, optionally filtered by session_id."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute(
                """
                SELECT session_id, user_query, category, tool_used, response, timestamp
                FROM conversations
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT session_id, user_query, category, tool_used, response, timestamp
                FROM conversations
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def create_ticket(
    issue: str,
    category: str = "General",
    order_id: Optional[str] = None,
    priority: str = "medium",
    db_path: Optional[str] = None,
) -> str:
    """Create a new support ticket and return generated ticket_id."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Find highest ticket number to increment
        cursor.execute("SELECT ticket_id FROM support_tickets ORDER BY ticket_id DESC LIMIT 1")
        last = cursor.fetchone()
        if last and last["ticket_id"].startswith("TKT"):
            try:
                num = int(last["ticket_id"].replace("TKT", "")) + 1
            except ValueError:
                num = 1001
        else:
            num = 1001
        ticket_id = f"TKT{num:04d}"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO support_tickets (ticket_id, issue, category, order_id, priority, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, issue, category, order_id, priority.lower(), "Open", ts),
        )
        conn.commit()
        return ticket_id


def get_ticket(ticket_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a specific ticket by ticket_id."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ticket_id, issue, category, order_id, priority, status, timestamp
            FROM support_tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_recent_tickets(limit: int = 5, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent support tickets."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ticket_id, issue, category, order_id, priority, status, timestamp
            FROM support_tickets
            ORDER BY ticket_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
