"""
OpenClaw Reminders Bridge - FastAPI service for iPhone Shortcuts integration
Allows OpenClaw to push reminders that iPhone can poll and retrieve
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import sqlite3
import os
import json

# Configuration
API_KEY = os.getenv("API_KEY", "openclaw-reminders-bridge-default-key")
DB_PATH = os.getenv("DB_PATH", "/data/reminders.db")

app = FastAPI(
    title="OpenClaw Reminders Bridge",
    description="Bridge service for OpenClaw → iPhone Shortcuts reminders",
    version="1.0.0"
)

# Models
class Reminder(BaseModel):
    title: str = Field(..., description="Reminder title/text")
    due: str = Field(..., description="ISO 8601 datetime when reminder is due")
    list: str = Field(default="Automation", description="Apple Reminders list name")
    priority: Optional[int] = Field(default=0, description="Priority (0=none, 1=low, 5=medium, 9=high)")
    urgent: Optional[bool] = Field(default=False, description="Urgent/time-sensitive flag")
    notes: Optional[str] = Field(default="", description="Additional notes/description")

class ReminderResponse(BaseModel):
    id: int
    title: str
    due: str
    list: str
    priority: int
    urgent: bool
    notes: str
    created_at: str
    retrieved_at: Optional[str] = None

# Database initialization
def init_db():
    """Initialize SQLite database with reminders table"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due TEXT NOT NULL,
            list TEXT NOT NULL DEFAULT 'Automation',
            priority INTEGER DEFAULT 0,
            urgent INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            retrieved_at TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            acknowledged_delete_at TEXT,
            UNIQUE(title, due)
        )
    """)
    
    # Add new columns if they don't exist (migration for existing databases)
    cursor.execute("PRAGMA table_info(reminders)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'resolved' not in columns:
        cursor.execute("ALTER TABLE reminders ADD COLUMN resolved INTEGER DEFAULT 0")
    if 'resolved_at' not in columns:
        cursor.execute("ALTER TABLE reminders ADD COLUMN resolved_at TEXT")
    if 'acknowledged_delete_at' not in columns:
        cursor.execute("ALTER TABLE reminders ADD COLUMN acknowledged_delete_at TEXT")
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_retrieved 
        ON reminders(retrieved_at)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_created 
        ON reminders(created_at DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_resolved 
        ON reminders(resolved)
    """)
    
    conn.commit()
    conn.close()

# Auth dependency
def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Routes
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "openclaw-reminders-bridge"}

@app.get("/stats", dependencies=[Depends(verify_api_key)])
async def get_stats():
    """Get reminder statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM reminders")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE retrieved_at IS NULL AND resolved = 0")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE retrieved_at IS NOT NULL AND resolved = 0")
    retrieved = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE resolved = 1")
    resolved = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total": total,
        "pending": pending,
        "retrieved": retrieved,
        "resolved": resolved
    }

@app.post("/reminders", dependencies=[Depends(verify_api_key)])
async def create_reminder(reminder: Reminder):
    """
    Create a new reminder (OpenClaw → Service)
    Returns created reminder with ID
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    created_at = datetime.utcnow().isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO reminders (title, due, list, priority, urgent, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            reminder.title,
            reminder.due,
            reminder.list,
            reminder.priority,
            1 if reminder.urgent else 0,
            reminder.notes or "",
            created_at
        ))
        
        reminder_id = cursor.lastrowid
        conn.commit()
        
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=409, 
            detail="Reminder with same title and due date already exists"
        )
    
    conn.close()
    
    return {
        "id": reminder_id,
        "title": reminder.title,
        "due": reminder.due,
        "list": reminder.list,
        "priority": reminder.priority,
        "urgent": reminder.urgent,
        "notes": reminder.notes,
        "created_at": created_at,
        "status": "created"
    }

@app.get("/reminders/pending", dependencies=[Depends(verify_api_key)])
async def get_pending_reminders():
    """
    Get all active (non-resolved) reminders and mark them as retrieved
    (iPhone Shortcuts → Service)
    Returns list of pending reminders, marks all as retrieved immediately
    Only returns reminders where resolved=false
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all active reminders (not resolved)
    cursor.execute("""
        SELECT id, title, due, list, priority, urgent, notes, created_at
        FROM reminders
        WHERE retrieved_at IS NULL AND resolved = 0
        ORDER BY due ASC, priority DESC
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        return {"reminders": [], "count": 0, "to_delete": []}
    
    # Mark all as retrieved
    retrieved_at = datetime.utcnow().isoformat()
    reminder_ids = [row[0] for row in rows]
    
    placeholders = ','.join('?' * len(reminder_ids))
    cursor.execute(f"""
        UPDATE reminders
        SET retrieved_at = ?
        WHERE id IN ({placeholders})
    """, [retrieved_at] + reminder_ids)
    
    # Get resolved reminders (to tell iPhone to delete them)
    # Only return those that haven't been acknowledged yet
    cursor.execute("""
        SELECT id, title
        FROM reminders
        WHERE resolved = 1 AND retrieved_at IS NOT NULL AND acknowledged_delete_at IS NULL
    """)
    
    resolved_rows = cursor.fetchall()
    
    conn.commit()
    conn.close()
    
    # Format response
    reminders = []
    for row in rows:
        reminders.append({
            "id": row[0],
            "title": row[1],
            "due": row[2],
            "list": row[3],
            "priority": row[4],
            "urgent": bool(row[5]),
            "notes": row[6],
            "created_at": row[7],
            "retrieved_at": retrieved_at
        })
    
    # Format resolved reminders (iPhone should delete these)
    to_delete = []
    for row in resolved_rows:
        to_delete.append({
            "id": row[0],
            "title": row[1],
            "action": "delete_from_device"
        })
    
    return {
        "reminders": reminders,
        "count": len(reminders),
        "to_delete": to_delete,
        "retrieved_at": retrieved_at
    }

@app.patch("/reminders/{reminder_id}/resolve", dependencies=[Depends(verify_api_key)])
async def resolve_reminder(reminder_id: int):
    """Mark a reminder as resolved (will be deleted from iPhone on next sync)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    resolved_at = datetime.utcnow().isoformat()
    
    cursor.execute(
        "UPDATE reminders SET resolved = 1, resolved_at = ? WHERE id = ?",
        (resolved_at, reminder_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    conn.commit()
    conn.close()
    
    return {"status": "resolved", "id": reminder_id, "resolved_at": resolved_at}

@app.patch("/reminders/{reminder_id}/acknowledge-delete", dependencies=[Depends(verify_api_key)])
async def acknowledge_delete(reminder_id: int):
    """iPhone acknowledges it has deleted the reminder from the device
    After this, the reminder won't appear in to_delete on future syncs
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    acknowledged_at = datetime.utcnow().isoformat()
    
    cursor.execute(
        "UPDATE reminders SET acknowledged_delete_at = ? WHERE id = ?",
        (acknowledged_at, reminder_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    conn.commit()
    conn.close()
    
    return {"status": "acknowledged", "id": reminder_id, "acknowledged_at": acknowledged_at}

@app.delete("/reminders/{reminder_id}", dependencies=[Depends(verify_api_key)])
async def delete_reminder(reminder_id: int):
    """Permanently delete a specific reminder by ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    conn.commit()
    conn.close()
    
    return {"status": "deleted", "id": reminder_id}

@app.get("/reminders", dependencies=[Depends(verify_api_key)])
async def list_all_reminders(limit: int = 50, show_resolved: bool = False):
    """List all reminders (for debugging/admin)
    
    Args:
        limit: Maximum number of reminders to return
        show_resolved: If true, include resolved reminders; if false, only active ones
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if show_resolved:
        query = """
            SELECT id, title, due, list, priority, urgent, notes, created_at, retrieved_at, resolved, resolved_at, acknowledged_delete_at
            FROM reminders
            ORDER BY created_at DESC
            LIMIT ?
        """
    else:
        query = """
            SELECT id, title, due, list, priority, urgent, notes, created_at, retrieved_at, resolved, resolved_at, acknowledged_delete_at
            FROM reminders
            WHERE resolved = 0
            ORDER BY created_at DESC
            LIMIT ?
        """
    
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    reminders = []
    for row in rows:
        reminders.append({
            "id": row[0],
            "title": row[1],
            "due": row[2],
            "list": row[3],
            "priority": row[4],
            "urgent": bool(row[5]),
            "notes": row[6],
            "created_at": row[7],
            "retrieved_at": row[8],
            "resolved": bool(row[9]),
            "resolved_at": row[10],
            "acknowledged_delete_at": row[11]
        })
    
    return {"reminders": reminders, "count": len(reminders)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
