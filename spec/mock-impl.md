# Mock Data Tool - Implementation Plan

## Overview

Create `backend/mockdata.py` with CLI entry point `tradle-mockdata` that generates realistic Tradle mock data directly into SQLite.

## Step 1: Create the module structure

**File:** `backend/mockdata.py`

```python
import argparse
import random
from .app import get_db, init_db, get_or_create_tenant, DB_PATH
from .ratings import update_ratings_for_round
```

## Step 2: Define constants

```python
DEFAULT_PLAYERS = ['alice', 'bob', 'charlie', 'diana', 'eddie', 'fiona', 'george', 'hannah']

# Score distribution: (score, probability)
SCORE_DISTRIBUTION = [
    (1, 0.02),   # 2% - lucky first guess
    (2, 0.08),   # 8% - very good
    (3, 0.25),   # 25% - good
    (4, 0.35),   # 35% - most common
    (5, 0.20),   # 20% - below average
    (6, 0.08),   # 8% - close call
    (7, 0.02),   # 2% - failure (X/6)
]

PARTICIPATION_RATE = 0.80  # 80% chance each player plays each round
```

## Step 3: Implement score generation

```python
def generate_score():
    """Return a random score (1-7) based on realistic distribution."""
    r = random.random()
    cumulative = 0
    for score, prob in SCORE_DISTRIBUTION:
        cumulative += prob
        if r < cumulative:
            return score
    return 4  # fallback
```

## Step 4: Implement raw text generation

Generate authentic Tradle result strings with progressive emoji rows.

```python
def generate_raw_text(round_num, score):
    """Generate realistic Tradle result text with emoji grid."""
    # Header
    score_display = 'X' if score == 7 else str(score)
    lines = [f'#Tradle #{round_num} {score_display}/6']

    # Generate emoji rows
    num_rows = 6 if score == 7 else score
    for i in range(num_rows):
        if score < 7 and i == num_rows - 1:
            # Final row for solved: all green
            lines.append('🟩🟩🟩🟩🟩')
        else:
            # Progressive improvement row
            lines.append(generate_progress_row(i, num_rows, score == 7))

    lines.append('https://oec.world/en/games/tradle')
    return '\n'.join(lines)

def generate_progress_row(row_index, total_rows, is_failure):
    """Generate a single emoji row showing progress toward solution."""
    # More greens as rows progress
    if is_failure:
        green_count = min(4, row_index + random.randint(0, 2))
    else:
        green_count = min(4, (row_index * 5) // total_rows + random.randint(0, 1))

    yellow_count = random.randint(0, min(2, 5 - green_count))
    white_count = 5 - green_count - yellow_count

    emojis = ['🟩'] * green_count + ['🟨'] * yellow_count + ['⬜'] * white_count
    random.shuffle(emojis)
    return ''.join(emojis)
```

## Step 5: Implement main data generation

```python
def generate_mock_data(tenant_key, num_players, num_rounds):
    """Generate mock data for a tenant."""
    init_db()
    tenant_id = get_or_create_tenant(tenant_key)

    players = DEFAULT_PLAYERS[:num_players]

    # Determine round range (end at a recent round number)
    end_round = 1420  # approximate current Tradle round
    start_round = end_round - num_rounds + 1

    conn = get_db()
    cursor = conn.cursor()
    total_scores = 0

    for round_num in range(start_round, end_round + 1):
        round_scores = []  # Track scores for rating updates

        for player in players:
            # Skip ~20% of rounds per player
            if random.random() > PARTICIPATION_RATE:
                continue

            score = generate_score()
            raw_text = generate_raw_text(round_num, score)

            try:
                cursor.execute('''
                    INSERT INTO scores (tenant_id, player, round, score, raw_text)
                    VALUES (?, ?, ?, ?, ?)
                ''', (tenant_id, player, round_num, score, raw_text))
                round_scores.append((player, score))
                total_scores += 1
            except Exception:
                pass  # Skip duplicates

        conn.commit()

        # Update ratings for each player in this round
        for player, score in round_scores:
            update_ratings_for_round(conn, tenant_id, player, round_num, score)

    conn.close()

    return {
        'tenant_key': tenant_key,
        'players': num_players,
        'start_round': start_round,
        'end_round': end_round,
        'total_scores': total_scores
    }
```

## Step 6: Implement CLI entry point

```python
def main():
    parser = argparse.ArgumentParser(description='Generate Tradle mock data')
    parser.add_argument('--key', default='testgroup', help='Tenant key')
    parser.add_argument('--players', type=int, default=8, help='Number of players')
    parser.add_argument('--rounds', type=int, default=50, help='Number of rounds')

    args = parser.parse_args()

    result = generate_mock_data(args.key, args.players, args.rounds)

    print(f"Created mock data for tenant '{result['tenant_key']}':")
    print(f"  Players: {result['players']}")
    print(f"  Rounds: {result['start_round']}-{result['end_round']}")
    print(f"  Total scores: {result['total_scores']}")

if __name__ == '__main__':
    main()
```

## Step 7: Add entry point to pyproject.toml

Add to `[project.scripts]`:

```toml
tradle-mockdata = "backend.mockdata:main"
```

## Testing

After implementation, verify with:

```bash
# Generate test data
uv run tradle-mockdata --key=testgroup --players=4 --rounds=10

# Start server and view
uv run tradle-backend
# Open http://localhost:8080?key=testgroup
```

## Files to modify

| File | Change |
|------|--------|
| `backend/mockdata.py` | Create new file |
| `pyproject.toml` | Add script entry point |
