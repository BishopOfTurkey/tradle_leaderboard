# Tradle Leaderboard

A web app for tracking [Tradle](https://oec.world/en/games/tradle) scores among friends.

## Features

- **Score submission** - Paste your Tradle result to submit scores
- **Multi-tenant** - Each group gets their own leaderboard via unique access key
- **Leaderboard tabs**:
  - **Standings** - Sortable metrics: average score, total points, win rate, games played, streak
  - **Results** - Per-round breakdown showing each player's score
- **Player details** - Click a player to see their game history

## Technology Stack

**Frontend:**
- Alpine.js (reactive UI)
- Vendored assets (Inter font, Alpine.js)

**Backend:**
- Python 3.13+ with Bottle framework
- SQLite database with multi-tenant support
- Gunicorn (production server)

**Infrastructure:**
- Fly.io deployment
- Docker containerization
- Litestream for SQLite replication to Tigris (S3-compatible)

**Tooling:**
- uv for Python package management
- Git for version control

See [spec/BACKEND.md](spec/BACKEND.md) for API details.

## Running Locally

```bash
# Install dependencies
uv sync

# Run the backend (serves frontend too)
uv run tradle-backend
```

The app will be available at `http://localhost:8080?key=YOUR_KEY`

## Authentication

Access is controlled via tenant keys:
- Pass key via URL: `?key=abc123` or `?id=abc123`
- Or via header: `X-Tenant-Key: abc123`
- Key is stored in a cookie for future visits
- First use of a key creates a new tenant group

## Style

- Clean white background
- Sans-serif typography (Inter)
- Accent colors: teal, purple, green
- Card containers with subtle borders
- Minimal, data-focused aesthetic

## Score Format

Tradle results look like:
```
#Tradle #1419 5/6
🟩⬜⬜⬜⬜
🟩🟩🟨⬜⬜
🟩🟩🟩🟩⬜
🟩🟩🟩🟩🟨
🟩🟩🟩🟩🟩
https://oec.world/en/games/tradle
```

- `5/6` = solved in 5 guesses
- `X/6` = failed (counts as 7 for calculations)
- Points: 1/6=6pts, 2/6=5pts, ..., 6/6=1pt, X/6=0pts
