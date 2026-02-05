"""
Rating system database operations and business logic.

This module handles:
- RD decay over time
- Getting/creating player ratings
- Calculating match results from scores
- Updating ratings after score submission
"""

import math
from datetime import datetime

from .glicko2 import update_rating, conservative_rating

# Constants
DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOLATILITY = 0.06
RD_DECAY_PER_DAY = 15  # How much RD increases per day of inactivity
MAX_RD = 350.0


def decay_rd(rd, last_played_at, now=None):
    """
    Apply RD time decay based on days since last played.

    Formula: RD_new = min(sqrt(RD² + c² × days), 350)
    Where c = 15 (RD_DECAY_PER_DAY)

    Args:
        rd: Current rating deviation
        last_played_at: Timestamp of last game (string or None)
        now: Current time (for testing), defaults to datetime.now()

    Returns:
        New RD value after decay
    """
    if last_played_at is None:
        return MAX_RD

    if now is None:
        now = datetime.now()

    # Parse timestamp if string
    if isinstance(last_played_at, str):
        last_played_at = datetime.fromisoformat(last_played_at.replace('Z', '+00:00'))

    # Make both timezone-naive for comparison
    if hasattr(last_played_at, 'tzinfo') and last_played_at.tzinfo is not None:
        last_played_at = last_played_at.replace(tzinfo=None)
    if hasattr(now, 'tzinfo') and now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    days = (now - last_played_at).total_seconds() / 86400
    if days <= 0:
        return rd

    new_rd = math.sqrt(rd * rd + RD_DECAY_PER_DAY * RD_DECAY_PER_DAY * days)
    return min(new_rd, MAX_RD)


def get_or_create_rating(conn, tenant_id, player):
    """
    Get player's current rating or create with defaults.

    Args:
        conn: Database connection
        tenant_id: Tenant ID
        player: Player name

    Returns:
        dict with keys: rating, rd, volatility, last_played_at
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rating, rd, volatility, last_played_at
        FROM player_ratings
        WHERE tenant_id = ? AND player = ?
    ''', (tenant_id, player))

    row = cursor.fetchone()
    if row:
        return {
            'rating': row['rating'],
            'rd': row['rd'],
            'volatility': row['volatility'],
            'last_played_at': row['last_played_at']
        }

    # Create new record with defaults
    cursor.execute('''
        INSERT INTO player_ratings (tenant_id, player, rating, rd, volatility)
        VALUES (?, ?, ?, ?, ?)
    ''', (tenant_id, player, DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOLATILITY))
    conn.commit()

    return {
        'rating': DEFAULT_RATING,
        'rd': DEFAULT_RD,
        'volatility': DEFAULT_VOLATILITY,
        'last_played_at': None
    }


def calculate_match_results(player_score, opponent_scores):
    """
    Calculate match results against all opponents.

    In Tradle, lower score = better (fewer guesses).

    Args:
        player_score: The player's score (1-7)
        opponent_scores: List of (opponent_name, opponent_score) tuples

    Returns:
        List of (opponent_name, result) tuples where result is:
        - 1.0 for win (player scored lower)
        - 0.5 for draw (same score)
        - 0.0 for loss (player scored higher)
    """
    results = []
    for opponent_name, opponent_score in opponent_scores:
        if player_score < opponent_score:
            result = 1.0  # Win
        elif player_score == opponent_score:
            result = 0.5  # Draw
        else:
            result = 0.0  # Loss
        results.append((opponent_name, result))
    return results


def get_round_scores(conn, tenant_id, round_num, exclude_player=None):
    """
    Get all scores for a specific round.

    Args:
        conn: Database connection
        tenant_id: Tenant ID
        round_num: Round number
        exclude_player: Optional player to exclude

    Returns:
        List of (player, score) tuples
    """
    cursor = conn.cursor()
    if exclude_player:
        cursor.execute('''
            SELECT player, score FROM scores
            WHERE tenant_id = ? AND round = ? AND player != ?
        ''', (tenant_id, round_num, exclude_player))
    else:
        cursor.execute('''
            SELECT player, score FROM scores
            WHERE tenant_id = ? AND round = ?
        ''', (tenant_id, round_num))

    return [(row['player'], row['score']) for row in cursor.fetchall()]


def save_rating(conn, tenant_id, player, rating, rd, volatility, last_played_at):
    """
    Save or update player's rating in the database.
    """
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO player_ratings
        (tenant_id, player, rating, rd, volatility, last_played_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tenant_id, player, rating, rd, volatility, last_played_at))
    conn.commit()


def save_rating_history(conn, tenant_id, player, round_num, rating, rd):
    """
    Record rating snapshot in history for graphing.
    """
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO rating_history
        (tenant_id, player, round, rating, rd, conservative_rating)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tenant_id, player, round_num, rating, rd, conservative_rating(rating, rd)))
    conn.commit()


def update_player_rating(conn, tenant_id, player, round_num, player_score, now=None):
    """
    Update a single player's rating after they submit a score.

    Args:
        conn: Database connection
        tenant_id: Tenant ID
        player: Player name
        round_num: Round number
        player_score: The player's score
        now: Current timestamp (for testing)

    Returns:
        dict with new rating info
    """
    if now is None:
        now = datetime.now()

    # Get player's current rating
    player_rating = get_or_create_rating(conn, tenant_id, player)

    # Apply RD decay
    decayed_rd = decay_rd(
        player_rating['rd'],
        player_rating['last_played_at'],
        now
    )

    # Get opponents for this round
    opponent_scores = get_round_scores(conn, tenant_id, round_num, exclude_player=player)

    if not opponent_scores:
        # No opponents yet - just save initial rating with updated timestamp
        save_rating(conn, tenant_id, player,
                   player_rating['rating'], decayed_rd,
                   player_rating['volatility'], now.isoformat())
        save_rating_history(conn, tenant_id, player, round_num,
                           player_rating['rating'], decayed_rd)
        return {
            'rating': player_rating['rating'],
            'rd': decayed_rd,
            'volatility': player_rating['volatility'],
            'conservativeRating': conservative_rating(player_rating['rating'], decayed_rd)
        }

    # Calculate match results
    match_results = calculate_match_results(player_score, opponent_scores)

    # Build opponents list for Glicko-2
    opponents = []
    for opponent_name, result in match_results:
        opp_rating = get_or_create_rating(conn, tenant_id, opponent_name)
        opp_decayed_rd = decay_rd(opp_rating['rd'], opp_rating['last_played_at'], now)
        opponents.append((opp_rating['rating'], opp_decayed_rd, result))

    # Run Glicko-2 update
    new_rating, new_rd, new_volatility = update_rating(
        player_rating['rating'],
        decayed_rd,
        player_rating['volatility'],
        opponents
    )

    # Save new rating
    save_rating(conn, tenant_id, player, new_rating, new_rd, new_volatility, now.isoformat())
    save_rating_history(conn, tenant_id, player, round_num, new_rating, new_rd)

    return {
        'rating': new_rating,
        'rd': new_rd,
        'volatility': new_volatility,
        'conservativeRating': conservative_rating(new_rating, new_rd)
    }


def update_opponent_ratings(conn, tenant_id, new_player, round_num, new_player_score, now=None):
    """
    Update ratings for all opponents who already played this round.

    When a new player submits a score, existing players for that round
    get an additional match result.
    """
    if now is None:
        now = datetime.now()

    # Get all other players who played this round
    opponent_scores = get_round_scores(conn, tenant_id, round_num, exclude_player=new_player)

    for opponent_name, opponent_score in opponent_scores:
        # Determine result from opponent's perspective
        if opponent_score < new_player_score:
            result = 1.0  # Opponent wins
        elif opponent_score == new_player_score:
            result = 0.5  # Draw
        else:
            result = 0.0  # Opponent loses

        # Get opponent's current rating
        opp_rating = get_or_create_rating(conn, tenant_id, opponent_name)
        opp_decayed_rd = decay_rd(opp_rating['rd'], opp_rating['last_played_at'], now)

        # Get new player's rating
        new_player_rating = get_or_create_rating(conn, tenant_id, new_player)

        # Run Glicko-2 update for just this one new match
        new_opp_rating, new_opp_rd, new_opp_volatility = update_rating(
            opp_rating['rating'],
            opp_decayed_rd,
            opp_rating['volatility'],
            [(new_player_rating['rating'], new_player_rating['rd'], result)]
        )

        # Save updated rating (keep original last_played_at since this is a retroactive update)
        save_rating(conn, tenant_id, opponent_name,
                   new_opp_rating, new_opp_rd, new_opp_volatility,
                   opp_rating['last_played_at'])
        save_rating_history(conn, tenant_id, opponent_name, round_num,
                           new_opp_rating, new_opp_rd)


def update_ratings_for_round(conn, tenant_id, player, round_num, score, now=None):
    """
    Main entry point: Update ratings when a player submits a score.

    1. Update the submitting player's rating
    2. Update opponents' ratings (they now have a new match result)

    Args:
        conn: Database connection
        tenant_id: Tenant ID
        player: Player name who submitted
        round_num: Round number
        score: Player's score (1-7)
        now: Current timestamp (for testing)

    Returns:
        The player's new rating info
    """
    if now is None:
        now = datetime.now()

    # Update the player who just submitted
    player_rating = update_player_rating(conn, tenant_id, player, round_num, score, now)

    # Update all opponents for this round
    update_opponent_ratings(conn, tenant_id, player, round_num, score, now)

    return player_rating


def get_all_ratings(conn, tenant_id):
    """
    Get all player ratings for a tenant.

    Returns:
        List of dicts with player, rating, rd, volatility, conservativeRating
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT player, rating, rd, volatility
        FROM player_ratings
        WHERE tenant_id = ?
        ORDER BY (rating - 2 * rd) DESC
    ''', (tenant_id,))

    ratings = []
    for row in cursor.fetchall():
        ratings.append({
            'player': row['player'],
            'rating': row['rating'],
            'rd': row['rd'],
            'volatility': row['volatility'],
            'conservativeRating': conservative_rating(row['rating'], row['rd'])
        })
    return ratings


def get_rating_history(conn, tenant_id, player):
    """
    Get rating history for a player (for graphing).

    Returns:
        List of dicts with round, rating, rd, conservativeRating
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT round, rating, rd, conservative_rating
        FROM rating_history
        WHERE tenant_id = ? AND player = ?
        ORDER BY round ASC
    ''', (tenant_id, player))

    history = []
    for row in cursor.fetchall():
        history.append({
            'round': row['round'],
            'rating': row['rating'],
            'rd': row['rd'],
            'conservativeRating': row['conservative_rating']
        })
    return history
