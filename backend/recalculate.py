#!/usr/bin/env python3
"""
Recalculate all ratings from historical data.

This script:
1. Clears all rating data (player_ratings, rating_history)
2. Replays all scores in chronological order
3. Recalculates ratings as if each score was submitted in real-time

Usage:
    uv run tradle-recalculate [--db PATH]
"""

import argparse
import os
import sqlite3

from .ratings import update_ratings_for_round, DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOLATILITY


def get_db(db_path):
    """Get a database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def clear_ratings(conn):
    """Clear all rating data."""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rating_history')
    cursor.execute('DELETE FROM player_ratings')
    conn.commit()
    print("Cleared rating tables")


def get_all_scores(conn):
    """Get all scores ordered by round ASC, created_at ASC."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT tenant_id, player, round, score, created_at
        FROM scores
        ORDER BY round ASC, created_at ASC
    ''')
    return cursor.fetchall()


def recalculate_ratings(db_path):
    """Recalculate all ratings from historical data."""
    conn = get_db(db_path)

    # Clear existing ratings
    clear_ratings(conn)

    # Get all scores in chronological order
    scores = get_all_scores(conn)
    total = len(scores)
    print(f"Found {total} scores to process")

    # Process each score
    for i, row in enumerate(scores):
        tenant_id = row['tenant_id']
        player = row['player']
        round_num = row['round']
        score = row['score']

        update_ratings_for_round(conn, tenant_id, player, round_num, score)

        if (i + 1) % 100 == 0 or i + 1 == total:
            print(f"Processed {i + 1}/{total} scores")

    conn.close()
    print("Rating recalculation complete")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Recalculate all Glicko-2 ratings from historical data'
    )
    parser.add_argument(
        '--db',
        default=os.environ.get('TRADLE_DB', 'tradle.db'),
        help='Path to SQLite database (default: TRADLE_DB env var or tradle.db)'
    )

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found at {args.db}")
        return 1

    print(f"Recalculating ratings from {args.db}")
    recalculate_ratings(args.db)
    return 0


if __name__ == '__main__':
    exit(main())
