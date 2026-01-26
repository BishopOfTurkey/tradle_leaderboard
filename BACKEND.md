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

Returns all scores for the authenticated tenant.

### Submit Score

```
POST /api/scores
```

Submit a new Tradle score. Request body should include:
- `player` - player name (required)
- `score` - the pasted Tradle result text (required)

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
```
