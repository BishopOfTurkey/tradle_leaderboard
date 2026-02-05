# Backend Design

A simple Python backend to replace npoint.io for self-hosted score storage with multi-tenancy support.

## Technology

- **Framework:** Bottle (single-file, minimal)
- **Database:** SQLite (single file, tenant_id column for multi-tenancy)
- **Validation:** Parse and validate Tradle score format

## Multi-tenancy Model

Single database with a `tenant_id` column on all tables. The tenant key serves as both authentication and tenant identification.

### Auth Flow

1. Request includes a tenant key (header or query param)
2. Look up the key in the database
3. If found → operate on that tenant's data
4. If not found → create a new tenant with that key

The first person to use a key "claims" it and creates the tenant group.

### Key Location

The tenant key can be provided via:
- Header: `X-Tenant-Key: abc123`
- Query param: `?key=abc123`

## API

All endpoints require a valid tenant key.

### Get Scores

```
GET /api/scores
```

Returns all scores and player ratings for the authenticated tenant.

**Response:**
```json
{
  "scores": [
    {
      "id": 1,
      "player": "Alice",
      "round": 1419,
      "score": 3,
      "raw_text": "#Tradle #1419 3/6\n...",
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "ratings": {
    "Alice": {
      "rating": 1523.4,
      "rd": 45.2,
      "volatility": 0.058,
      "conservativeRating": 1433
    }
  }
}
```

### Submit Score

```
POST /api/scores
```

Submit a new Tradle score. Request body should include:
- `player` - player name (required)
- `score` - the pasted Tradle result text (required)

On success, player ratings are automatically updated using Glicko-2.

### Get Ratings

```
GET /api/ratings
```

Returns current ratings for all players, sorted by conservative rating (descending).

**Response:**
```json
{
  "ratings": [
    {
      "player": "Alice",
      "rating": 1523.4,
      "rd": 45.2,
      "volatility": 0.058,
      "conservativeRating": 1433
    }
  ]
}
```

### Get Rating History

```
GET /api/ratings/<player>/history
```

Returns rating history for a specific player (for graphing).

**Response:**
```json
{
  "player": "Alice",
  "history": [
    {
      "round": 1400,
      "rating": 1500.0,
      "rd": 320.0,
      "conservativeRating": 860
    },
    {
      "round": 1401,
      "rating": 1534.2,
      "rd": 290.5,
      "conservativeRating": 953
    }
  ]
}
```

## Data Validation

Score submissions are validated:
- Must match Tradle format: `#Tradle #NNNN X/6` followed by emoji grid
- Round number extracted from `#NNNN`
- Score extracted (1-6 or X for failure)
- Reject malformed submissions
- Reject duplicate submissions (same player + same round)

## Database Schema

```sql
CREATE TABLE tenants (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scores (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    round INTEGER NOT NULL,
    score INTEGER NOT NULL,  -- 1-6, or 7 for X/failure
    raw_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    UNIQUE (tenant_id, player, round)
);

CREATE TABLE player_ratings (
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    rating REAL DEFAULT 1500.0,
    rd REAL DEFAULT 350.0,
    volatility REAL DEFAULT 0.06,
    last_played_at TIMESTAMP,
    PRIMARY KEY (tenant_id, player),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE rating_history (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    round INTEGER NOT NULL,
    rating REAL NOT NULL,
    rd REAL NOT NULL,
    conservative_rating REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, player, round),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
```

## Rating System

The backend implements a Glicko-2 rating system for player rankings:

- **Rating**: Skill estimate (default 1500)
- **RD (Rating Deviation)**: Uncertainty (50-350, default 350)
- **Volatility**: Player consistency measure (default 0.06)
- **Conservative Rating**: `rating - 2×RD` (displayed Elo)

Players compete pairwise within each round - lower Tradle score = win.

### CLI Tools

```bash
# Recalculate all ratings from historical data
uv run tradle-recalculate [--db PATH]
```
