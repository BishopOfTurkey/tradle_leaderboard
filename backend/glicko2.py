"""
Glicko-2 Rating System Implementation

Reference: http://www.glicko.net/glicko/glicko2.pdf
"""

import math

# Constants
SCALE = 173.7178  # Glicko-2 scaling factor
TAU = 0.5  # System constant (controls volatility change rate)
EPSILON = 0.000001  # Convergence tolerance for volatility iteration


def rating_to_glicko2(rating, rd):
    """Convert from Glicko scale to Glicko-2 scale."""
    mu = (rating - 1500) / SCALE
    phi = rd / SCALE
    return mu, phi


def glicko2_to_rating(mu, phi):
    """Convert from Glicko-2 scale to Glicko scale."""
    rating = mu * SCALE + 1500
    rd = phi * SCALE
    return rating, rd


def g(phi):
    """
    Compute the g function.
    g(φ) = 1 / sqrt(1 + 3φ²/π²)
    """
    return 1 / math.sqrt(1 + 3 * phi * phi / (math.pi * math.pi))


def expected_score(mu, mu_j, phi_j):
    """
    Compute expected score E.
    E(μ, μⱼ, φⱼ) = 1 / (1 + exp(-g(φⱼ)(μ - μⱼ)))
    """
    return 1 / (1 + math.exp(-g(phi_j) * (mu - mu_j)))


def compute_variance(mu, opponents):
    """
    Compute the estimated variance v.

    opponents: list of (mu_j, phi_j, score_j)

    v = 1 / Σ(g(φⱼ)² × E × (1 - E))
    """
    if not opponents:
        return float('inf')

    total = 0
    for mu_j, phi_j, _ in opponents:
        g_j = g(phi_j)
        e_j = expected_score(mu, mu_j, phi_j)
        total += g_j * g_j * e_j * (1 - e_j)

    return 1 / total if total > 0 else float('inf')


def compute_delta(mu, opponents, v):
    """
    Compute the estimated improvement delta.

    Δ = v × Σ(g(φⱼ)(sⱼ - E))
    """
    if not opponents:
        return 0

    total = 0
    for mu_j, phi_j, score_j in opponents:
        g_j = g(phi_j)
        e_j = expected_score(mu, mu_j, phi_j)
        total += g_j * (score_j - e_j)

    return v * total


def update_volatility(sigma, phi, v, delta):
    """
    Update volatility using the Illinois algorithm.

    This is Step 5 of the Glicko-2 algorithm.
    Returns new volatility σ'.
    """
    a = math.log(sigma * sigma)
    delta_sq = delta * delta
    phi_sq = phi * phi

    def f(x):
        ex = math.exp(x)
        num1 = ex * (delta_sq - phi_sq - v - ex)
        den1 = 2 * (phi_sq + v + ex) ** 2
        return num1 / den1 - (x - a) / (TAU * TAU)

    # Initialize bounds
    A = a
    if delta_sq > phi_sq + v:
        B = math.log(delta_sq - phi_sq - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU

    # Ensure f(A) and f(B) have opposite signs
    f_A = f(A)
    f_B = f(B)

    # Illinois algorithm iteration
    while abs(B - A) > EPSILON:
        C = A + (A - B) * f_A / (f_B - f_A)
        f_C = f(C)

        if f_C * f_B <= 0:
            A = B
            f_A = f_B
        else:
            f_A = f_A / 2

        B = C
        f_B = f_C

    return math.exp(A / 2)


def update_rating(rating, rd, volatility, opponents):
    """
    Main Glicko-2 rating update function.

    Args:
        rating: Current rating (Glicko scale)
        rd: Current rating deviation (Glicko scale)
        volatility: Current volatility
        opponents: List of (opponent_rating, opponent_rd, score) tuples
                   where score is 1.0 (win), 0.5 (draw), or 0.0 (loss)

    Returns:
        (new_rating, new_rd, new_volatility)
    """
    # Step 1: Convert to Glicko-2 scale
    mu, phi = rating_to_glicko2(rating, rd)

    # Convert opponents to Glicko-2 scale
    opponents_g2 = []
    for opp_rating, opp_rd, score in opponents:
        mu_j, phi_j = rating_to_glicko2(opp_rating, opp_rd)
        opponents_g2.append((mu_j, phi_j, score))

    # Step 2: Compute variance
    v = compute_variance(mu, opponents_g2)

    # Handle case with no opponents
    if not opponents_g2 or v == float('inf'):
        new_rating, new_rd = glicko2_to_rating(mu, phi)
        return new_rating, new_rd, volatility

    # Step 3: Compute delta
    delta = compute_delta(mu, opponents_g2, v)

    # Step 4 & 5: Update volatility
    new_sigma = update_volatility(volatility, phi, v, delta)

    # Step 6: Update RD (phi*)
    phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)

    # Step 7: Calculate new phi
    new_phi = 1 / math.sqrt(1 / (phi_star * phi_star) + 1 / v)

    # Step 8: Calculate new mu
    total = 0
    for mu_j, phi_j, score_j in opponents_g2:
        g_j = g(phi_j)
        e_j = expected_score(mu, mu_j, phi_j)
        total += g_j * (score_j - e_j)
    new_mu = mu + new_phi * new_phi * total

    # Convert back to Glicko scale
    new_rating, new_rd = glicko2_to_rating(new_mu, new_phi)

    # Clamp RD to valid range
    new_rd = min(max(new_rd, 30), 350)

    return new_rating, new_rd, new_sigma


def conservative_rating(rating, rd):
    """
    Calculate conservative rating estimate.
    This is rating - 2*RD, which represents a lower bound on skill.
    """
    return int(rating - 2 * rd)
