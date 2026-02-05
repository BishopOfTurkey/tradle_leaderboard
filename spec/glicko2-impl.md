# Glicko-2 Rating System Implementation Plan

## Overview

Add a Glicko-2 Elo rating system to the Tradle leaderboard. Players compete pairwise within each round - lower Tradle score = win.

## Database Migration

Add to `init_db()` in `backend/app.py` using existing `CREATE TABLE IF NOT EXISTS` pattern:

```sql
CREATE TABLE IF NOT EXISTS player_ratings (
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    rating REAL DEFAULT 1500.0,
    rd REAL DEFAULT 350.0,
    volatility REAL DEFAULT 0.06,
    last_played_at TIMESTAMP,
    PRIMARY KEY (tenant_id, player),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
)

CREATE TABLE IF NOT EXISTS rating_history (
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
)
```

## File Organization

```
backend/
  app.py          # Modify: add tables, routes, integrate ratings
  glicko2.py      # NEW: Pure Glicko-2 algorithm (~100 lines)
  ratings.py      # NEW: Rating DB operations & business logic
  recalculate.py  # NEW: CLI script to bootstrap from historical data
```

## Implementation Phases

### Phase 1: Core Algorithm & Database (COMPLETED)

1. Add new tables to `init_db()` in `backend/app.py:34-62`
2. Create `backend/glicko2.py`:
   - Scale conversions (Glicko ↔ Glicko-2)
   - g(φ), E(μ, μⱼ, φⱼ) functions
   - Variance and delta computation
   - Volatility update (Illinois algorithm)
   - Main `update_rating()` function
3. Create `backend/ratings.py`:
   - `decay_rd(rd, last_played_at, c=15)` - RD increases with inactivity
   - `get_or_create_rating(conn, tenant_id, player)` - fetch or default
   - `calculate_match_results(score, opponent_scores)` - win/loss/draw
   - `update_ratings_for_round(conn, tenant_id, player, round, score)` - main entry point

### Phase 2: Backend Integration (COMPLETED)

1. Modify `POST /api/scores` (`app.py:182-246`):
   - After successful insert, call `update_ratings_for_round()`
2. Modify `GET /api/scores` (`app.py:149-179`):
   - Add `ratings` object to response with all player ratings
3. Add `GET /api/ratings`:
   - Return all players sorted by conservative rating
4. Add `GET /api/ratings/<player>/history`:
   - Return rating history for graphing
5. Create `backend/recalculate.py`:
   - Clear ratings tables
   - Replay all scores in order: `ORDER BY round ASC, created_at ASC`
   - Add CLI entry point in `pyproject.toml`

### Phase 3: Frontend - Elo Column (COMPLETED)

1. Update `loadScores()` to store `this.ratings` from response
2. Add "Elo" column to standings table header (~line 656)
3. Add Elo cell to table body (~line 674)
4. Update `leaderboard` getter to include `elo: ratings[player]?.conservativeRating`
5. Add Elo to `sortBy()` options

### Phase 4: Frontend - Rating Graph

1. Download D3.js v7 to `vendor/d3.min.js`
2. Add `<script src="vendor/d3.min.js"></script>` to index.html
3. Add `ratingHistory` array to Alpine data
4. Add `loadRatingHistory(player)` method - fetch on modal open
5. Add `renderRatingChart()` using D3.js:
   - X-axis: round number
   - Y-axis: rating
   - Shaded band: rating ± 2×RD
   - Bold line: conservative rating (rating - 2×RD)
6. Add CSS for `.rating-graph` container

### Phase 5: Testing & Documentation

1. Run recalculate script on existing data
2. Test all API endpoints
3. Verify frontend display and sorting
4. Update `BACKEND.md` with new endpoints

## Key Files to Modify

| File | Changes |
|------|---------|
| `backend/app.py` | Add tables to `init_db()`, modify GET/POST /api/scores, add 2 new routes |
| `backend/glicko2.py` | NEW - Pure algorithm implementation |
| `backend/ratings.py` | NEW - Rating logic and DB operations |
| `backend/recalculate.py` | NEW - Historical recalculation script |
| `index.html` | Add Elo column, D3.js graph in modal |
| `vendor/d3.min.js` | NEW - D3.js library |
| `pyproject.toml` | Add `tradle-recalculate` CLI command |
| `BACKEND.md` | Document new API endpoints |

## Edge Cases

- **First score in tenant**: No opponents = no rating change, just create record
- **Solo round**: Defer update until opponent submits for same round
- **Late submission**: Player's rating updates; opponents who already played that round also get updated
- **Long inactivity**: Cap RD at 350 after decay

## Verification

1. **Unit tests**: Test Glicko-2 math with known inputs/outputs
2. **Manual test**: Submit scores, verify ratings update in API response
3. **Recalculation**: Run script, compare to live ratings (should match)
4. **Frontend**: Verify Elo column sorts correctly, graph renders in modal
