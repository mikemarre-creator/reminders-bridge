# OpenClaw Reminders Bridge

FastAPI service that bridges OpenClaw automation with iPhone Shortcuts for Apple Reminders.

## Features

- ✅ RESTful API for creating and retrieving reminders
- ✅ Support for Apple's urgent/time-sensitive reminders
- ✅ SQLite persistent storage
- ✅ Auto-mark reminders as retrieved when iPhone polls
- ✅ Docker containerized
- ✅ API key authentication
- ✅ Default "Automation" list for all reminders

## Quick Start

### 1. Deploy the Service

```bash
cd /home/node/.openclaw/workspace/reminders-bridge

# Set your API key (optional, defaults to openclaw-reminders-2026-secure-key)
export API_KEY="your-secure-api-key-here"

# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f
```

Service will be available at: `http://192.168.1.29:8888`

### 2. Test the Service

```bash
# Health check
curl http://192.168.1.29:8888/health

# Create a test reminder
curl -X POST http://192.168.1.29:8888/reminders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: openclaw-reminders-2026-secure-key" \
  -d '{
    "title": "Test Reminder",
    "due": "2026-05-02T20:00:00",
    "list": "Automation",
    "priority": 5,
    "urgent": true,
    "notes": "This is a test"
  }'

# Get pending reminders (marks as retrieved)
curl http://192.168.1.29:8888/reminders/pending \
  -H "X-API-Key: openclaw-reminders-2026-secure-key"

# Get stats
curl http://192.168.1.29:8888/stats \
  -H "X-API-Key: openclaw-reminders-2026-secure-key"
```

## API Endpoints

### `POST /reminders`
Create a new reminder (OpenClaw → Service)

**Headers:**
- `X-API-Key: your-api-key`
- `Content-Type: application/json`

**Body:**
```json
{
  "title": "Take out recycling",
  "due": "2026-05-02T20:00:00",
  "list": "Automation",
  "priority": 5,
  "urgent": true,
  "notes": "Blue bin pickup day"
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Take out recycling",
  "due": "2026-05-02T20:00:00",
  "list": "Automation",
  "priority": 5,
  "urgent": true,
  "notes": "Blue bin pickup day",
  "created_at": "2026-05-01T19:30:00",
  "status": "created"
}
```

### `GET /reminders/pending`
Get all pending reminders (iPhone → Service)

**Headers:**
- `X-API-Key: your-api-key`

**Response:**
```json
{
  "reminders": [
    {
      "id": 1,
      "title": "Take out recycling",
      "due": "2026-05-02T20:00:00",
      "list": "Automation",
      "priority": 5,
      "urgent": true,
      "notes": "Blue bin pickup day",
      "created_at": "2026-05-01T19:30:00",
      "retrieved_at": "2026-05-01T19:35:00"
    }
  ],
  "count": 1,
  "retrieved_at": "2026-05-01T19:35:00"
}
```

**Note:** Calling this endpoint automatically marks all pending reminders as "retrieved".

### `GET /stats`
Get reminder statistics

**Headers:**
- `X-API-Key: your-api-key`

**Response:**
```json
{
  "total": 10,
  "pending": 3,
  "retrieved": 7
}
```

### `GET /health`
Health check (no auth required)

**Response:**
```json
{
  "status": "healthy",
  "service": "openclaw-reminders-bridge"
}
```

## iPhone Shortcut Setup

### 1. Create Polling Shortcut

**Actions:**
1. **Get Contents of URL**
   - URL: `http://192.168.1.29:8888/reminders/pending`
   - Method: GET
   - Headers:
     - `X-API-Key`: `openclaw-reminders-2026-secure-key`

2. **Get Dictionary from Input**

3. **Get Value for "reminders" in Dictionary**

4. **Repeat with Each Item**
   - **Add New Reminder**
     - Title: `Repeat Item's title`
     - List: `Repeat Item's list`
     - Due Date: `Repeat Item's due`
     - Priority: `Repeat Item's priority`
     - Time Sensitive: `Repeat Item's urgent`
     - Notes: `Repeat Item's notes`

### 2. Automate the Shortcut

**Personal Automation:**
- Trigger: Time of Day (every hour or multiple times per day)
- Action: Run Shortcut "OpenClaw Reminders Poll"
- Turn OFF "Ask Before Running"

## OpenClaw Integration

### Create a Reminder from OpenClaw

```python
import requests

def create_reminder(title, due_datetime, urgent=False, notes=""):
    """Create a reminder via the bridge service"""
    url = "http://192.168.1.29:8888/reminders"
    headers = {
        "X-API-Key": "openclaw-reminders-2026-secure-key",
        "Content-Type": "application/json"
    }
    payload = {
        "title": title,
        "due": due_datetime,  # ISO 8601: "2026-05-02T20:00:00"
        "list": "Automation",
        "priority": 9 if urgent else 5,
        "urgent": urgent,
        "notes": notes
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# Example usage
create_reminder(
    title="Check server logs",
    due_datetime="2026-05-02T09:00:00",
    urgent=True,
    notes="vmagent restart issue"
)
```

### From Cron Jobs

Add this to your cron job scripts to create reminders:

```bash
curl -X POST http://192.168.1.29:8888/reminders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: openclaw-reminders-2026-secure-key" \
  -d "{
    \"title\": \"Disk space above 85%\",
    \"due\": \"$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%S)\",
    \"urgent\": true,
    \"notes\": \"Check /var/log cleanup\"
  }"
```

## Configuration

### Environment Variables

- `API_KEY` - API key for authentication (default: `openclaw-reminders-2026-secure-key`)
- `DB_PATH` - SQLite database path (default: `/data/reminders.db`)

### Changing the API Key

Edit `.env` file or `docker-compose.yml`:

```yaml
environment:
  - API_KEY=your-new-secure-key-here
```

Restart:
```bash
docker-compose down
docker-compose up -d
```

## Maintenance

### View Logs
```bash
docker-compose logs -f
```

### Backup Database
```bash
cp data/reminders.db data/reminders.db.backup
```

### Clear Retrieved Reminders (older than 7 days)
```bash
sqlite3 data/reminders.db "DELETE FROM reminders WHERE retrieved_at IS NOT NULL AND retrieved_at < datetime('now', '-7 days')"
```

### Reset Everything
```bash
docker-compose down
rm -rf data/
docker-compose up -d
```

## Troubleshooting

### Service won't start
```bash
docker-compose logs
```

### iPhone can't connect
- Check firewall: `sudo ufw status`
- Test from iPhone browser: `http://192.168.1.29:8888/health`
- Verify API key matches in both service and Shortcut

### Reminders not appearing
- Check Shortcut has correct URL and API key
- Verify "Ask Before Running" is OFF in automation
- Check service stats: `curl http://192.168.1.29:8888/stats -H "X-API-Key: ..."`

## API Documentation

Once running, visit: `http://192.168.1.29:8888/docs` for interactive API documentation (Swagger UI).

---

**Service Status:** Running at `http://192.168.1.29:8888`  
**API Key:** `openclaw-reminders-2026-secure-key` (change in production!)  
**Database:** `/home/node/.openclaw/workspace/reminders-bridge/data/reminders.db`
