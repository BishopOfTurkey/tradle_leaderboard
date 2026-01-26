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

from bottle import Bottle, request, response, run, abort

# Configuration
DB_PATH = os.environ.get('TRADLE_DB', 'tradle.db')
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 8080))
CORS_ORIGIN = os.environ.get('CORS_ORIGIN', '*')

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


def require_tenant(func):
    """Decorator to require and inject tenant_id."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = get_tenant_key()
        if not key:
            abort(401, 'Tenant key required (X-Tenant-Key header or ?key= param)')

        tenant_id = get_or_create_tenant(key)
        return func(tenant_id, *args, **kwargs)
    return wrapper


@app.hook('after_request')
def enable_cors():
    """Add CORS headers to all responses."""
    response.headers['Access-Control-Allow-Origin'] = CORS_ORIGIN
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Tenant-Key'


@app.route('/api/scores', method='OPTIONS')
def cors_preflight():
    """Handle CORS preflight requests."""
    return ''


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
    conn.close()

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

    response.content_type = 'application/json'
    return {'scores': scores}


@app.route('/api/scores', method='POST')
@require_tenant
def submit_score(tenant_id):
    """Submit a new Tradle score."""
    try:
        data = request.json
    except Exception:
        abort(400, 'Invalid JSON')

    if not data:
        abort(400, 'Request body required')

    player = data.get('player', '').strip()
    score_text = data.get('score', '').strip()

    if not player:
        abort(400, 'Player name required')

    if not score_text:
        abort(400, 'Score text required')

    # Parse the Tradle score
    parsed = parse_tradle_score(score_text)
    if not parsed:
        abort(400, 'Invalid Tradle score format. Expected: #Tradle #NNNN X/6')

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
            'timestamp': row['created_at']
        }

    except sqlite3.IntegrityError:
        conn.close()
        abort(409, f'Duplicate score: {player} already submitted for round #{round_number}')


@app.route('/health')
def health():
    """Health check endpoint."""
    return {'status': 'ok'}


def run_server():
    """Entry point for running the server."""
    init_db()
    print(f'Starting Tradle backend on {HOST}:{PORT}')
    print(f'Database: {DB_PATH}')
    print(f'CORS Origin: {CORS_ORIGIN}')
    run(app, host=HOST, port=PORT, debug=True)


if __name__ == '__main__':
    run_server()
