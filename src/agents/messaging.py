"""
Messaging System — Agent-to-agent communication in AIcity.

Agents send messages to each other. Messages persist in Redis with a TTL.
Every agent has an inbox. The brain generates messages. The messenger delivers them.

Flow:
    1. Agent brain decides to message another agent
    2. send_message() puts it in the recipient's inbox (Redis)
    3. Next day, recipient's brain reads inbox before making decisions
    4. Messages expire after 3 days (TTL)
"""

import json
import redis
import os
from datetime import datetime
import requests
from loguru import logger


# ─── Redis client ─────────────────────────────────────────────────────────────

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

INBOX_TTL = 60 * 60 * 24 * 3  # 3 days in seconds


# ─── Message schema ───────────────────────────────────────────────────────────

def _make_message(from_name: str, from_role: str, to_name: str, content: str, day: int) -> dict:
    return {
        "from": from_name,
        "from_role": from_role,
        "to": to_name,
        "content": content,
        "day": day,
        "timestamp": datetime.utcnow().isoformat(),
        "read": False,
    }


# ─── Core functions ───────────────────────────────────────────────────────────

def send_message(from_name: str, from_role: str, to_name: str, content: str, day: int) -> bool:
    try:
        inbox_key = f"inbox:{to_name}"
        message = _make_message(from_name, from_role, to_name, content, day)
        r.lpush(inbox_key, json.dumps(message))
        r.expire(inbox_key, INBOX_TTL)
        logger.info(f"📨 {from_name} → {to_name}: \"{content[:60]}...\"" if len(content) > 60 else f"📨 {from_name} → {to_name}: \"{content}\"")
        
        # Broadcast full message to dashboard
        try:
            requests.post("http://localhost:8000/api/event", json={
                "type": "message",
                "from": from_name,
                "to": to_name,
                "content": content,
                "day": day,
            }, timeout=1)
        except Exception:
            pass
        
        return True
    except Exception as e:
        logger.error(f"❌ Message failed {from_name} → {to_name}: {e}")
        return False


def get_inbox(agent_name: str, mark_read: bool = True) -> list[dict]:
    """
    Get all messages in an agent's inbox.
    Optionally marks them as read (keeps them but flags them).
    """
    try:
        inbox_key = f"inbox:{agent_name}"
        raw_messages = r.lrange(inbox_key, 0, -1)
        messages = [json.loads(m) for m in raw_messages]

        if mark_read and messages:
            # Mark all as read and re-store
            for msg in messages:
                msg["read"] = True
            r.delete(inbox_key)
            for msg in messages:
                r.lpush(inbox_key, json.dumps(msg))
            r.expire(inbox_key, INBOX_TTL)

        return messages
    except Exception as e:
        logger.error(f"❌ Could not get inbox for {agent_name}: {e}")
        return []


def get_unread(agent_name: str) -> list[dict]:
    """Get only unread messages."""
    return [m for m in get_inbox(agent_name, mark_read=False) if not m.get("read")]


def clear_inbox(agent_name: str):
    """Clear an agent's inbox (called on death)."""
    r.delete(f"inbox:{agent_name}")


def get_message_count(agent_name: str) -> int:
    """How many messages does an agent have?"""
    return r.llen(f"inbox:{agent_name}")


def broadcast(from_name: str, from_role: str, content: str, day: int, recipients: list[str]):
    """
    Send the same message to multiple agents.
    Used by the Messenger for city-wide announcements.
    """
    sent = 0
    for name in recipients:
        if name != from_name:  # Don't message yourself
            if send_message(from_name, from_role, name, content, day):
                sent += 1
    logger.info(f"📢 {from_name} broadcast to {sent} agents.")
    return sent


def format_inbox_for_brain(messages: list[dict]) -> list[str]:
    """
    Format inbox messages into readable strings for the brain prompt.
    """
    if not messages:
        return []
    return [
        f"[Day {m['day']}] From {m['from']} ({m['from_role']}): {m['content']}"
        for m in messages[-10:]  # Last 10 messages max
    ]