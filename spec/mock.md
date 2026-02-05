# Mock Data Tool

CLI script that generates realistic Tradle mock data directly into SQLite.

## Usage

```bash
uv run tradle-mockdata --key=testgroup --players=8 --rounds=50
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--key` | `testgroup` | Tenant key for the mock data |
| `--players` | `8` | Number of players to generate |
| `--rounds` | `50` | Number of game rounds to generate |

## Players

Default player names (used in order up to `--players` count):
- `alice`, `bob`, `charlie`, `diana`, `eddie`, `fiona`, `george`, `hannah`

Each player participates in ~80% of rounds (realistic gaps).

## Score Distribution

Realistic Tradle score probabilities:

| Score | Probability | Description |
|-------|-------------|-------------|
| 1/6   | 2%          | Lucky first guess |
| 2/6   | 8%          | Very good |
| 3/6   | 25%         | Good |
| 4/6   | 35%         | Most common |
| 5/6   | 20%         | Below average |
| 6/6   | 8%          | Close call |
| X/6   | 2%          | Failure |

## Raw Text Generation

Generates authentic-looking Tradle results with emoji rows showing plausible progression to solution:

```
#Tradle #1415 4/6
🟩🟨⬜⬜⬜
🟩🟩🟨⬜⬜
🟩🟩🟩🟨⬜
🟩🟩🟩🟩🟩
https://oec.world/en/games/tradle
```

Emoji logic:
- Final row for solved games: `🟩🟩🟩🟩🟩`
- Earlier rows: progressive improvement toward solution
- Failed games (X/6): 6 rows, none fully green

## Implementation

**File:** `backend/mockdata.py`

**Entry point** (in `pyproject.toml`):
```toml
tradle-mockdata = "backend.mockdata:main"
```

**Dependencies:** None (uses stdlib `argparse`, `random`)

**Database interaction:**
- Reuses `get_db`, `init_db`, `get_or_create_tenant` from `backend.app`
- Calls `update_ratings_for_round` to populate Glicko-2 ratings
- Direct SQLite insertion (no HTTP overhead)

## Output

Prints summary when complete:
```
Created mock data for tenant 'testgroup':
  Players: 8
  Rounds: 1371-1420
  Total scores: 320
```
