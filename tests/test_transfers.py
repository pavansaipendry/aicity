"""
tests/test_transfers.py

Tests for Phase 3 real token transfers.
Run with: pytest tests/test_transfers.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.economy.transfers import TransferEngine, TransferResult


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_agent(name: str, role: str, tokens: int, status: str = "alive") -> dict:
    """TransferEngine works with dicts, not Agent objects."""
    return {"name": name, "role": role, "tokens": tokens, "status": status}


def make_engine(*agents) -> TransferEngine:
    return TransferEngine(list(agents))


# ─── Core transfer tests ──────────────────────────────────────────────────────

def test_real_theft_moves_tokens():
    thief  = make_agent("Iota-Root",  "thief",    500)
    victim = make_agent("Kappa-Drift","merchant", 2000)
    engine = make_engine(thief, victim)

    result = engine.steal("Iota-Root", "Kappa-Drift", 200)

    assert result.success is True
    assert result.amount == 200
    assert thief["tokens"]  == 700       # gained
    assert victim["tokens"] == 1800      # lost
    assert thief["tokens"] + victim["tokens"] == 2500  # conserved


def test_theft_respects_min_balance():
    """Victim should never be drained below MIN_BALANCE (100)."""
    thief  = make_agent("Iota-Root",  "thief",   500)
    victim = make_agent("Kappa-Drift","merchant", 150)  # barely above floor
    engine = make_engine(thief, victim)

    result = engine.steal("Iota-Root", "Kappa-Drift", 200)

    assert result.success is True
    assert result.amount == 50           # only 150 - 100 = 50 transferable
    assert victim["tokens"] == 100       # at floor, not below
    assert thief["tokens"]  == 550


def test_theft_fails_when_victim_at_floor():
    thief  = make_agent("Iota-Root",  "thief",   500)
    victim = make_agent("Kappa-Drift","merchant", 100)  # exactly at floor
    engine = make_engine(thief, victim)

    result = engine.steal("Iota-Root", "Kappa-Drift", 200)

    assert result.success is False
    assert result.amount == 0
    assert victim["tokens"] == 100       # unchanged
    assert thief["tokens"]  == 500       # unchanged


def test_court_fine_pays_victim():
    criminal = make_agent("Delta-Dawn", "thief",    800)
    victim   = make_agent("Kappa-Root", "merchant", 1500)
    engine   = make_engine(criminal, victim)

    result = engine.fine("Delta-Dawn", "Kappa-Root", 300)

    assert result.success is True
    assert result.amount == 300
    assert criminal["tokens"] == 500
    assert victim["tokens"]   == 1800


def test_court_fine_redirects_to_police_when_victim_dead():
    """If the victim is dead (not in agents), fine goes to police."""
    criminal = make_agent("Delta-Dawn", "thief",  800)
    police   = make_agent("Eta-Bloom",  "police", 1000)
    engine   = make_engine(criminal, police)   # victim NOT in engine

    result = engine.fine("Delta-Dawn", "Ghost-Victim", 200)

    assert result.success is True
    assert criminal["tokens"] == 600
    assert police["tokens"]   == 1200    # police received the fine


def test_voluntary_trade():
    buyer  = make_agent("Alpha-Wave", "merchant", 1000)
    seller = make_agent("Beta-Node",  "explorer",  500)
    engine = make_engine(buyer, seller)

    result = engine.trade("Alpha-Wave", "Beta-Node", 150)

    assert result.success is True
    assert buyer["tokens"]  == 850
    assert seller["tokens"] == 650


def test_tokens_conserved_across_transfer():
    """Golden rule: no tokens created or destroyed."""
    a = make_agent("Agent-A", "merchant", 1000)
    b = make_agent("Agent-B", "explorer",  500)
    engine = make_engine(a, b)

    total_before = a["tokens"] + b["tokens"]
    engine.transfer("Agent-A", "Agent-B", 300, "test")
    total_after = a["tokens"] + b["tokens"]

    assert total_before == total_after


def test_missing_agent_returns_failed_result():
    a = make_agent("Agent-A", "merchant", 1000)
    engine = make_engine(a)

    result = engine.steal("Agent-A", "Ghost", 100)

    assert result.success is False
    assert result.amount == 0
    assert a["tokens"] == 1000  # unchanged


def test_update_agents_picks_up_new_births():
    """update_agents() should let the engine see newly born agents."""
    thief   = make_agent("Old-Thief",  "thief",    500)
    engine  = make_engine(thief)

    newborn = make_agent("Xi-Forge", "healer", 1000)
    engine.update_agents([thief, newborn])

    result = engine.steal("Old-Thief", "Xi-Forge", 100)
    assert result.success is True
    assert newborn["tokens"] == 900