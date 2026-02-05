#!/usr/bin/env python3
"""
Tradle Leaderboard Backend
A simple Bottle app with SQLite for multi-tenant score storage.
"""

import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

from bottle import Bottle, request, response, run, static_file, HTTPResponse

from .ratings import update_ratings_for_round, get_all_ratings, get_rating_history, get_all_rating_histories

# Configuration
DB_PATH = os.environ.get('TRADLE_DB', 'tradle.db')
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 8080))
STATIC_ROOT = os.environ.get('STATIC_ROOT', '/app')

app = Bottle()

# Tradle score pattern: #Tradle #1419 3/6 or #Tradle #1419 X/6
TRADLE_PATTERN = re.compile(r'#Tradle #(\d+) (\d|X)/6')


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            player TEXT NOT NULL,
            round INTEGER NOT NULL,
            score INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            UNIQUE (tenant_id, player, round)
        )
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
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
    ''')

    conn.commit()
    conn.close()


def parse_tradle_score(text):
    """
    Parse a Tradle score from the pasted text.
    Returns (round_number, score) or None if invalid.
    Score is 1-6 for solved, 7 for X/failure.
    """
    match = TRADLE_PATTERN.search(text)
    if not match:
        return None

    round_number = int(match.group(1))
    score_raw = match.group(2)
    score = 7 if score_raw == 'X' else int(score_raw)

    return (round_number, score)


def get_or_create_tenant(key):
    """Get tenant ID for a key, creating the tenant if it doesn't exist."""
    conn = get_db()
    cursor = conn.cursor()

    # Try to find existing tenant
    cursor.execute('SELECT id FROM tenants WHERE key = ?', (key,))
    row = cursor.fetchone()

    if row:
        tenant_id = row['id']
    else:
        # Create new tenant
        cursor.execute('INSERT INTO tenants (key) VALUES (?)', (key,))
        tenant_id = cursor.lastrowid
        conn.commit()

    conn.close()
    return tenant_id


def get_tenant_key():
    """Extract tenant key from request header or query param."""
    # Check header first
    key = request.headers.get('X-Tenant-Key')
    if key:
        return key

    # Check query params
    key = request.query.get('key') or request.query.get('id')
    return key


def json_error(status, message):
    """Return a JSON error response."""
    return HTTPResponse(
        body={'error': message},
        status=status,
        headers={'Content-Type': 'application/json'}
    )


def require_tenant(func):
    """Decorator to require and inject tenant_id."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = get_tenant_key()
        if not key:
            return json_error(401, 'Access key required. Please use an invite link.')

        tenant_id = get_or_create_tenant(key)
        return func(tenant_id, *args, **kwargs)
    return wrapper


@app.route('/')
def serve_index():
    """Serve the main index.html page."""
    return static_file('index.html', root=STATIC_ROOT)


@app.route('/vendor/<filepath:path>')
def serve_vendor(filepath):
    """Serve vendored static files (JS, CSS, fonts)."""
    return static_file(filepath, root=os.path.join(STATIC_ROOT, 'vendor'))


@app.route('/api/scores', method='GET')
@require_tenant
def get_scores(tenant_id):
    """Get all scores for the authenticated tenant."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, player, round, score, raw_text, created_at
        FROM scores
        WHERE tenant_id = ?
        ORDER BY round DESC, created_at DESC
    ''', (tenant_id,))

    rows = cursor.fetchall()

    scores = []
    for row in rows:
        scores.append({
            'id': row['id'],
            'player': row['player'],
            'gameNumber': row['round'],
            'score': row['score'],
            'solved': row['score'] < 7,
            'raw': row['raw_text'],
            'timestamp': row['created_at']
        })

    # Get all player ratings
    ratings_list = get_all_ratings(conn, tenant_id)
    ratings = {r['player']: r for r in ratings_list}

    conn.close()

    response.content_type = 'application/json'
    return {'scores': scores, 'ratings': ratings}


@app.route('/api/scores', method='POST')
@require_tenant
def submit_score(tenant_id):
    """Submit a new Tradle score."""
    try:
        data = request.json
    except Exception:
        return json_error(400, 'Invalid request format.')

    if not data:
        return json_error(400, 'No data provided.')

    player = data.get('player', '').strip()
    score_text = data.get('score', '').strip()

    if not player:
        return json_error(400, 'Player name is required.')

    if not score_text:
        return json_error(400, 'Please paste your Tradle result.')

    # Parse the Tradle score
    parsed = parse_tradle_score(score_text)
    if not parsed:
        return json_error(400, 'Could not find a valid Tradle score. Make sure to copy the full result including "#Tradle #NNNN X/6".')

    round_number, score = parsed

    # Insert the score
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO scores (tenant_id, player, round, score, raw_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (tenant_id, player, round_number, score, score_text))

        score_id = cursor.lastrowid
        conn.commit()

        # Update ratings for this round
        player_rating = update_ratings_for_round(conn, tenant_id, player, round_number, score)

        # Fetch the created score
        cursor.execute('''
            SELECT id, player, round, score, raw_text, created_at
            FROM scores WHERE id = ?
        ''', (score_id,))

        row = cursor.fetchone()
        conn.close()

        response.content_type = 'application/json'
        response.status = 201
        return {
            'id': row['id'],
            'player': row['player'],
            'gameNumber': row['round'],
            'score': row['score'],
            'solved': row['score'] < 7,
            'raw': row['raw_text'],
            'timestamp': row['created_at'],
            'rating': player_rating
        }

    except sqlite3.IntegrityError:
        conn.close()
        return json_error(409, f'You already submitted a score for game #{round_number}.')


@app.route('/api/ratings', method='GET')
@require_tenant
def get_ratings(tenant_id):
    """Get all player ratings for the authenticated tenant."""
    conn = get_db()
    ratings = get_all_ratings(conn, tenant_id)
    conn.close()

    response.content_type = 'application/json'
    return {'ratings': ratings}


@app.route('/api/ratings/<player>/history', method='GET')
@require_tenant
def get_player_rating_history(tenant_id, player):
    """Get rating history for a specific player."""
    conn = get_db()
    history = get_rating_history(conn, tenant_id, player)
    conn.close()

    response.content_type = 'application/json'
    return {'player': player, 'history': history}


@app.route('/api/ratings/history', method='GET')
@require_tenant
def get_all_players_rating_history(tenant_id):
    """Get rating histories for all players."""
    conn = get_db()
    histories = get_all_rating_histories(conn, tenant_id)
    conn.close()

    response.content_type = 'application/json'
    return {'histories': histories}


@app.route('/health')
def health():
    """Health check endpoint."""
    return {'status': 'ok'}


def run_server():
    """Entry point for running the server."""
    init_db()
    print(f'Starting Tradle backend on {HOST}:{PORT}')
    print(f'Database: {DB_PATH}')
    print(f'Static root: {STATIC_ROOT}')
    run(app, host=HOST, port=PORT, debug=True)


# Initialize database on module load (for production WSGI servers)
init_db()

if __name__ == '__main__':
    run_server()
