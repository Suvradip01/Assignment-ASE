"""SQLite persistence for decisions and simulator messages."""

import sqlite3
from pathlib import Path
from typing import Any


def connect(path: str = "data/app.db") -> sqlite3.Connection:
    """Open database and create the initial tables."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE IF NOT EXISTS decisions (order_id TEXT PRIMARY KEY, action TEXT, risk REAL, reason TEXT, discount_inr REAL, est_saved REAL, est_lost REAL, est_discount_cost REAL, est_msg_cost REAL, order_date TEXT, is_first_time INTEGER, order_value REAL, state TEXT, city TEXT, llm_source TEXT, decided_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS conversations (order_id TEXT PRIMARY KEY, state TEXT, risk REAL, updated_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, direction TEXT, msg_id TEXT UNIQUE, body TEXT, created_at TEXT)"
    )
    return db


def save_conversation(conversation: Any, path: str = "data/app.db") -> None:
    """Persist the current simulator state with its injected update time."""
    db = connect(path)
    db.execute(
        "INSERT INTO conversations (order_id,state,risk,updated_at) VALUES (?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET state=excluded.state,risk=excluded.risk,updated_at=excluded.updated_at",
        (
            conversation.order_id,
            conversation.state,
            conversation.risk,
            conversation.last_at.isoformat(),
        ),
    )
    db.commit()
    db.close()


def record_message(
    order_id: str,
    direction: str,
    msg_id: str | None,
    body: str,
    created_at: str,
    path: str = "data/app.db",
) -> None:
    """Store a mock conversation message and ignore duplicate inbound IDs."""
    db = connect(path)
    db.execute(
        "INSERT OR IGNORE INTO messages (order_id,direction,msg_id,body,created_at) VALUES (?,?,?,?,?)",
        (order_id, direction, msg_id, body, created_at),
    )
    db.commit()
    db.close()
