# Glicko-2 Rating System Specification

## Overview

Implement a Glicko-2 Elo rating system for the Tradle leaderboard. Players compete pairwise within each daily round - if player A scores better than player B on the same puzzle, A "beats" B.

## Data Model

### New Tables

```sql
CREATE TABLE player_ratings (
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    rating REAL DEFAULT 1500.0,
    rd REAL DEFAULT 350.0,
    volatility REAL DEFAULT 0.06,
    last_played_at TIMESTAMP,
    PRIMARY KEY (tenant_id, player)
)

CREATE TABLE rating_history (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    player TEXT NOT NULL,
    round INTEGER NOT NULL,
    rating REAL NOT NULL,
    rd REAL NOT NULL,
    conservative_rating REAL NOT NULL,  -- rating - 2*RD (precomputed)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, player, round)
)
```

## Glicko-2 Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Rating (r) | 1500 | Skill estimate |
| RD | 350 | Rating deviation (uncertainty), range ~50-350 |
| Volatility (σ) | 0.06 | Player consistency measure |
| System constant (τ) | 0.5 | Controls volatility change rate |
| RD decay (c) | 15/day | How much RD increases per day of inactivity |

## Pairwise Match Logic

For each round, players are compared pairwise based on their scores:

| Comparison | Result for A |
|------------|--------------|
| A score < B score | Win (1.0) |
| A score = B score | Draw (0.5) |
| A score > B score | Loss (0.0) |

Note: Lower Tradle scores are better (fewer guesses).

## Algorithm Flow

### On Score Submission (player X, round N)

1. **RD time decay for X:** Apply decay based on days since `last_played_at`
   - Formula: `RD_new = min(sqrt(RD² + c² × days), 350)`
   - Where `c = 15`

2. **Get opponents:** Find all other players who played round N

3. **RD time decay for opponents:** Apply same decay formula to each

4. **Build match results:** For each opponent, determine win/loss/draw

5. **Update X's rating:** Run Glicko-2 algorithm with all opponents as a batch

6. **Update opponents:** Re-run Glicko-2 for each opponent (they now have a new result vs X)

7. **Record history:** Insert entry into `rating_history` for X

8. **Update timestamp:** Set `last_played_at` for X

### Historical Recalculation

To bootstrap ratings from existing data:

1. Clear all ratings (reset `player_ratings` to empty)
2. Clear `rating_history`
3. Fetch all scores ordered by `(round ASC, created_at ASC)`
4. For each score, execute the submission flow above

This simulates the ratings as if each score was submitted in real-time.

## Display

### Standings Table

- New column: **"Elo"**
- Value: `floor(rating - 2 × RD)` (conservative estimate)
- This rewards both skill (high rating) and consistency (low RD)

### Player Detail View - Rating Graph

A line graph showing rating history over time:

- **X-axis:** Round number
- **Y-axis:** Rating
- **Shaded band:** Rating ± 2×RD (uncertainty range)
- **Bottom line (bold):** Conservative rating (rating - 2×RD) - the "real" displayed rating
- **Top line (light):** Rating + 2×RD

### Visualization Library

Use **D3.js** for the rating graph.

## API Changes

### GET /api/scores Response

Add player ratings to response:

```json
{
  "scores": [...],
  "ratings": {
    "PlayerName": {
      "rating": 1523.4,
      "rd": 45.2,
      "volatility": 0.058,
      "conservativeRating": 1433
    }
  }
}
```

### GET /api/ratings (new endpoint)

Returns current ratings for all players:

```json
{
  "ratings": [
    {
      "player": "PlayerName",
      "rating": 1523.4,
      "rd": 45.2,
      "volatility": 0.058,
      "conservativeRating": 1433
    }
  ]
}
```

### GET /api/ratings/:player/history (new endpoint)

Returns rating history for graphing:

```json
{
  "player": "PlayerName",
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

## Glicko-2 Algorithm Reference

Implement from scratch following the standard Glicko-2 algorithm:

1. Convert rating and RD to Glicko-2 scale (μ, φ)
2. Compute estimated variance (v) based on opponents
3. Compute estimated improvement (Δ)
4. Update volatility (σ') using iterative algorithm
5. Update RD: φ' = 1 / sqrt(1/φ² + 1/v)
6. Update rating: μ' = μ + φ'² × Σ g(φⱼ)(sⱼ - E)
7. Convert back to rating scale

Reference: http://www.glicko.net/glicko/glicko2.pdf
