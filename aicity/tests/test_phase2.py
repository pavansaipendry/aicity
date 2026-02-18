"""
tests/test_phase2.py — Phase 2 tests

Tests the brain, messaging, memory, and behaviors.
Run: pytest tests/test_phase2.py -v
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from src.agents.brain import AgentBrain
from src.agents.messaging import send_message, get_inbox, clear_inbox, format_inbox_for_brain
from src.agents.behaviors import execute_action, ActionResult
from src.agents.newspaper import CityNewspaper


# ─── Brain Tests ─────────────────────────────────────────────────────────────

class TestAgentBrain:

    def test_brain_creation(self):
        brain = AgentBrain("test-id-123", "Test-Agent", "builder")
        assert brain.agent_id == "test-id-123"
        assert brain.name == "Test-Agent"
        assert brain.role == "builder"
        assert brain.model_type == "gpt4o"

    def test_police_uses_claude(self):
        brain = AgentBrain("test-id-456", "Cop-Agent", "police")
        assert brain.model_type == "claude"

    def test_default_decision_low_tokens(self):
        brain = AgentBrain("test-id-789", "Poor-Agent", "builder")
        result = brain._default_decision({"tokens": 100})
        assert result["mood"] == "anxious"
        assert "action" in result

    def test_default_decision_rich(self):
        brain = AgentBrain("test-id-abc", "Rich-Agent", "explorer")
        result = brain._default_decision({"tokens": 5000})
        assert result["mood"] == "confident"

    def test_prompt_building(self):
        brain = AgentBrain("test-id-def", "Prompt-Agent", "merchant")
        context = {
            "tokens": 500,
            "age_days": 10,
            "mood": "neutral",
            "recent_memories": ["Made a good trade yesterday"],
            "city_news": "The city is quiet today.",
            "other_agents": [{"name": "Other", "role": "builder", "tokens": 800}],
            "messages_received": ["From Builder-1: Want to trade?"],
        }
        prompt = brain._build_prompt(context)
        assert "500" in prompt
        assert "merchant" in prompt
        assert "STABLE" in prompt  # 500 tokens = stable

    def test_parse_valid_json(self):
        brain = AgentBrain("test-id-ghi", "Parse-Agent", "builder")
        valid_json = '{"action": "works hard", "reasoning": "need tokens", "message_to": null, "message": null, "mood": "focused"}'
        result = brain._parse_response(valid_json)
        assert result["action"] == "works hard"
        assert result["mood"] == "focused"

    def test_parse_markdown_wrapped_json(self):
        brain = AgentBrain("test-id-jkl", "Parse-Agent2", "explorer")
        wrapped = '```json\n{"action": "explores", "reasoning": "adventure", "message_to": null, "message": null, "mood": "excited"}\n```'
        result = brain._parse_response(wrapped)
        assert result["action"] == "explores"


# ─── Messaging Tests ──────────────────────────────────────────────────────────

class TestMessaging:

    def setup_method(self):
        """Clear test agent inboxes before each test."""
        clear_inbox("TestRecipient")
        clear_inbox("TestSender")

    def test_send_and_receive(self):
        success = send_message("TestSender", "builder", "TestRecipient", "Hello from test", day=1)
        assert success is True
        inbox = get_inbox("TestRecipient", mark_read=False)
        assert len(inbox) >= 1
        assert inbox[0]["content"] == "Hello from test"
        assert inbox[0]["from"] == "TestSender"

    def test_message_metadata(self):
        send_message("Alpha", "explorer", "Beta", "Test message content", day=5)
        inbox = get_inbox("Beta", mark_read=False)
        msg = inbox[0]
        assert msg["from"] == "Alpha"
        assert msg["from_role"] == "explorer"
        assert msg["to"] == "Beta"
        assert msg["day"] == 5

    def test_format_for_brain(self):
        send_message("Writer", "teacher", "Reader", "Learn from this", day=3)
        inbox = get_inbox("Reader", mark_read=False)
        formatted = format_inbox_for_brain(inbox)
        assert len(formatted) >= 1
        assert "Writer" in formatted[0]
        assert "teacher" in formatted[0]

    def test_empty_inbox(self):
        inbox = get_inbox("NobodyMessaged", mark_read=False)
        assert inbox == []

    def teardown_method(self):
        clear_inbox("TestRecipient")
        clear_inbox("TestSender")
        clear_inbox("Alpha")
        clear_inbox("Beta")
        clear_inbox("Reader")


# ─── Behavior Tests ───────────────────────────────────────────────────────────

class TestBehaviors:

    def _make_agent(self, role: str, tokens: int = 1000, name: str = None) -> dict:
        return {
            "id": f"test-{role}-001",
            "name": name or f"Test-{role.capitalize()}",
            "role": role,
            "tokens": tokens,
            "age_days": 10,
            "status": "alive",
            "mood": "neutral",
        }

    def _make_decision(self, action: str = "works steadily") -> dict:
        return {
            "action": action,
            "reasoning": "just testing",
            "message_to": None,
            "message": None,
            "mood": "neutral",
        }

    def test_builder_earns(self):
        agent = self._make_agent("builder")
        result = execute_action(agent, self._make_decision(), [], day=1)
        assert result.tokens_earned >= 0
        assert isinstance(result.memory, str)
        assert "Day 1" in result.memory

    def test_builder_hard_work_bonus(self):
        agent = self._make_agent("builder")
        decision = self._make_decision("works overtime desperately through the night")
        result = execute_action(agent, decision, [], day=1)
        # Hard work decision should generally earn more
        assert result.tokens_earned >= 50

    def test_explorer_high_variance(self):
        """Run explorer many times, verify high variance in earnings."""
        agent = self._make_agent("explorer")
        decision = self._make_decision("explores the unknown")
        earnings = [execute_action(agent, decision, [], day=i).tokens_earned for i in range(20)]
        assert max(earnings) > min(earnings)  # Should have variance

    def test_thief_doesnt_steal_from_newborns(self):
        """Thieves have a code — never steal from Newborns."""
        thief = self._make_agent("thief")
        newborn = self._make_agent("newborn", tokens=200, name="Baby-Agent")
        decision = self._make_decision("steals from the vulnerable")

        # Run many times
        results = [execute_action(thief, decision, [newborn], day=i) for i in range(10)]
        # Newborn should never be targeted (thief targets tokens > 500, newborn has 200)
        # All steals should be 0 since only target has < 500 tokens
        for r in results:
            assert r.tokens_earned == 0 or "Baby-Agent" not in r.memory

    def test_newborn_low_earnings(self):
        agent = self._make_agent("newborn", tokens=400)
        decision = self._make_decision("tries to learn from others")
        result = execute_action(agent, decision, [], day=1)
        assert result.tokens_earned <= 100  # Newborns earn very little

    def test_healer_earns_more_with_critical(self):
        healer = self._make_agent("healer")
        critical = self._make_agent("builder", tokens=150, name="Dying-Builder")
        decision = self._make_decision("heals the sick")

        result = execute_action(healer, decision, [critical], day=1)
        assert result.tokens_earned >= 40

    def test_action_result_structure(self):
        agent = self._make_agent("merchant")
        result = execute_action(agent, self._make_decision(), [], day=1)
        assert hasattr(result, "tokens_earned")
        assert hasattr(result, "tokens_lost")
        assert hasattr(result, "events")
        assert hasattr(result, "memory")
        assert hasattr(result, "success")
        assert isinstance(result.events, list)


# ─── Newspaper Tests ─────────────────────────────────────────────────────────

class TestNewspaper:

    def test_quiet_day(self):
        paper = CityNewspaper()
        result = paper._quiet_day(5, "Iota-Drift")
        assert "Day 5" in result
        assert "Iota-Drift" in result

    def test_format_events(self):
        paper = CityNewspaper()
        events = [
            {"type": "death", "agent": "Zeta-Spark", "role": "newborn", "detail": "starvation"},
            {"type": "heart_attack", "agent": "Echo-Node", "role": "police", "tokens": 300, "detail": "cardiac"},
            {"type": "windfall", "agent": "Omega-Pulse", "role": "explorer", "tokens": 450, "detail": "discovery"},
        ]
        formatted = paper._format_events(events)
        assert "DEATH" in formatted
        assert "Zeta-Spark" in formatted
        assert "HEART ATTACK" in formatted
        assert "WINDFALL" in formatted
        assert "Omega-Pulse" in formatted