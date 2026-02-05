# Tradle Leaderboard - Technical Implementation

## Architecture Overview

| Layer | Technology | Details |
|-------|------------|---------|
| Frontend | Alpine.js SPA | Single `index.html`, reactive UI, vendored assets |
| Backend | Python/Bottle | REST API, SQLite storage, multi-tenant |
| Hosting | Fly.io (unified) | Frontend and backend served together via Gunicorn |
| Auth | Tenant Keys | First-claim system via `X-Tenant-Key` header |

## Frontend

### Framework
- **Alpine.js 3.x** (44KB vendored in `/vendor/alpine.min.js`)
- No build step required - runs directly in browser

### Styling
- IEA-inspired design system
- **Inter font** (vendored in `/vendor/`)
- Color accents: teal, purple, green
- Responsive layout

### State Management
Single `tradleApp()` component with:
- `scores` - raw score data from API
- `leaderboard` - computed player rankings
- `roundsTable` - computed results matrix

### Features
- Score submission with paste detection
- Sortable leaderboard (by various metrics)
- Results matrix showing all rounds
- Player detail modal with statistics

### Data Flow
```
Cookie-based auth → GET /api/scores → reactive UI
User submission → POST /api/scores → refresh → UI update
```

## Backend

### Framework
- **Bottle 0.13.4** - micro web framework
- Single-file application structure

### Database
- **SQLite** for persistent storage
- Default location: `tradle.db` (configurable)

### Score Parsing
Regex pattern for Tradle results:
```
#Tradle #(\d+) (\d|X)/6
```
Extracts round number and score (1-6 or X for failure).

### Multi-tenancy
- Each tenant identified by unique key
- First request with new key auto-creates tenant
- `UNIQUE(tenant_id, player, round)` prevents duplicate submissions

## Configuration

### Python Environment
- **Python 3.13+** required
- **uv** package manager

### Entry Point
```bash
tradle-backend  # → run_server()
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRADLE_DB` | SQLite database path | `tradle.db` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8080` |
| `STATIC_ROOT` | Root directory for static files | `/app` |

### Git Workflow
- Rebase workflow
- Main branch: `main`
- Hosted on GitHub

### Domain
- `tradle.fly.dev` (Fly.io)

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `bottle` | >=0.12 | Web framework |
| `gunicorn` | >=21.0 | Production WSGI server |

## Database Schema

### tenants
```sql
CREATE TABLE tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### scores
```sql
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    round INTEGER NOT NULL,
    score INTEGER NOT NULL,
    raw_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, player, round),
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
```

## API Reference

**Note:** The API transforms database column names for the response:
| Database Column | API Field |
|-----------------|-----------|
| `round` | `gameNumber` |
| `raw_text` | `raw` |
| `created_at` | `timestamp` |
| *(computed)* | `solved` (true if score < 7) |

### GET /api/scores

Retrieve all scores for a tenant.

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `X-Tenant-Key` | Yes | Tenant identifier |

**Response:** `200 OK`
```json
{
  "scores": [
    {
      "id": 1,
      "player": "alice",
      "gameNumber": 123,
      "score": 3,
      "solved": true,
      "raw": "#Tradle #123 3/6\n🟩🟩🟩⬜⬜\n...",
      "timestamp": "2024-01-15 10:30:00"
    }
  ]
}
```

### POST /api/scores

Submit a new score.

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `X-Tenant-Key` | Yes | Tenant identifier |
| `Content-Type` | Yes | `application/json` |

**Request Body:**
```json
{
  "player": "alice",
  "score": "#Tradle #123 3/6\n🟩🟩🟩⬜⬜\n..."
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "player": "alice",
  "gameNumber": 123,
  "score": 3,
  "solved": true,
  "raw": "#Tradle #123 3/6\n🟩🟩🟩⬜⬜\n...",
  "timestamp": "2024-01-15 10:30:00"
}
```

**Error Responses:**

| Code | Description |
|------|-------------|
| `400 Bad Request` | Invalid/missing data or unparseable score text |
| `401 Unauthorized` | Missing `X-Tenant-Key` header |
| `409 Conflict` | Duplicate entry (player + round already exists) |

### GET /health

Health check endpoint.

**Response:** `200 OK`
```json
{
  "status": "ok"
}
```

### Static File Serving

- Frontend served from same origin as API (no CORS needed)
- Routes: `/` serves `index.html`, `/vendor/*` serves static assets

## Scoring System

### Raw Score Values
| Result | Internal Score |
|--------|----------------|
| 1/6 | 1 |
| 2/6 | 2 |
| 3/6 | 3 |
| 4/6 | 4 |
| 5/6 | 5 |
| 6/6 | 6 |
| X/6 | 7 |

### Points Calculation
```
points = max(0, 7 - score)
```

| Result | Points |
|--------|--------|
| 1/6 | 6 pts |
| 2/6 | 5 pts |
| 3/6 | 4 pts |
| 4/6 | 3 pts |
| 5/6 | 2 pts |
| 6/6 | 1 pt |
| X/6 | 0 pts |

### Leaderboard Metrics

| Metric | Description |
|--------|-------------|
| Average Score | Mean of raw scores (lower is better) |
| Total Points | Sum of all points earned |
| Win Rate | Percentage of games solved (score < 7, i.e. not X/6) |
| Games Played | Total submissions |
| Streak | Consecutive solved games from most recent game backward |
