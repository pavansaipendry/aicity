# Phase 1 — Step 4: Memory System

**Date:** February 2026
**Status:** ⏳ To Do
**Goal:** Give every agent a private house of memory, and the city a shared knowledge base.

---

## Two Types of Memory

| Type | Storage | Accessible By | Description |
|------|---------|--------------|-------------|
| Private (House) | Qdrant — per agent collection | Agent only | Personal history, relationships, secrets |
| Shared (City) | Qdrant — city collection | All agents | Laws, news, discoveries, public knowledge |
| Working (Mind) | Redis | Agent only | What the agent is thinking RIGHT NOW |

---

## The Code

Create `src/memory/memory_system.py`:

```python
import os
import json
from datetime import datetime
from typing import Optional
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue
)
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

VECTOR_SIZE = 1536  # OpenAI/Claude embedding size


class MemorySystem:
    """
    Every agent's house. Every city's library.
    Private thoughts stay private. City knowledge is shared.
    """

    def __init__(self):
        self.qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        self.redis = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        self._init_city_collection()
        logger.info("🧠 Memory system initialized.")

    def _init_city_collection(self):
        """Create the shared city knowledge collection"""
        collections = [c.name for c in self.qdrant.get_collections().collections]
        if "city_knowledge" not in collections:
            self.qdrant.create_collection(
                collection_name="city_knowledge",
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            logger.info("📚 City knowledge base created.")

    def create_agent_memory(self, agent_id: str) -> str:
        """
        Create a private memory collection for a new agent.
        This is their house — only they can write to it.
        """
        collection_name = f"agent_{agent_id.replace('-', '_')}"
        collections = [c.name for c in self.qdrant.get_collections().collections]

        if collection_name not in collections:
            self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            logger.info(f"🏠 Private memory created for agent {agent_id[:8]}.")

        return collection_name

    def remember(self, agent_id: str, memory: str, memory_type: str,
                 embedding: list[float], metadata: dict = None) -> None:
        """
        Store a memory in the agent's private house.
        memory_type: experience, relationship, discovery, emotion
        """
        collection = f"agent_{agent_id.replace('-', '_')}"
        import uuid as _uuid
        point_id = str(_uuid.uuid4()).replace("-", "")[:16]

        payload = {
            "content": memory,
            "type": memory_type,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
        }
        if metadata:
            payload.update(metadata)

        self.qdrant.upsert(
            collection_name=collection,
            points=[PointStruct(
                id=int(point_id, 16) % (2**63),
                vector=embedding,
                payload=payload
            )]
        )

    def recall(self, agent_id: str, query_embedding: list[float],
               limit: int = 5) -> list[dict]:
        """
        Search an agent's private memory.
        Returns the most relevant memories.
        """
        collection = f"agent_{agent_id.replace('-', '_')}"
        results = self.qdrant.search(
            collection_name=collection,
            query_vector=query_embedding,
            limit=limit
        )
        return [hit.payload for hit in results]

    def publish_to_city(self, content: str, content_type: str,
                        embedding: list[float], author_id: str = None) -> None:
        """
        Add knowledge to the shared city library.
        content_type: law, news, discovery, announcement
        """
        import uuid as _uuid
        point_id = str(_uuid.uuid4()).replace("-", "")[:16]

        self.qdrant.upsert(
            collection_name="city_knowledge",
            points=[PointStruct(
                id=int(point_id, 16) % (2**63),
                vector=embedding,
                payload={
                    "content": content,
                    "type": content_type,
                    "timestamp": datetime.now().isoformat(),
                    "author_id": author_id,
                }
            )]
        )

    def query_city_knowledge(self, query_embedding: list[float],
                             limit: int = 5) -> list[dict]:
        """Search the shared city knowledge base"""
        results = self.qdrant.search(
            collection_name="city_knowledge",
            query_vector=query_embedding,
            limit=limit
        )
        return [hit.payload for hit in results]

    # ── Working Memory (Redis) ─────────────────────────────────

    def set_working_memory(self, agent_id: str, key: str, value: any,
                           ttl_seconds: int = 3600) -> None:
        """
        Store something in the agent's working memory (Redis).
        This is what they're thinking RIGHT NOW.
        Expires after ttl_seconds.
        """
        redis_key = f"agent:{agent_id}:{key}"
        self.redis.setex(redis_key, ttl_seconds, json.dumps(value))

    def get_working_memory(self, agent_id: str, key: str) -> Optional[any]:
        """Retrieve something from working memory"""
        redis_key = f"agent:{agent_id}:{key}"
        value = self.redis.get(redis_key)
        return json.loads(value) if value else None

    def clear_working_memory(self, agent_id: str) -> None:
        """Clear all working memory for an agent — called on death"""
        pattern = f"agent:{agent_id}:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
        logger.info(f"🧹 Working memory cleared for agent {agent_id[:8]}.")

    def delete_agent_memory(self, agent_id: str) -> None:
        """
        Called when an agent dies.
        Private memory is preserved (for history/graveyard).
        Working memory is cleared.
        """
        self.clear_working_memory(agent_id)
        logger.info(
            f"📦 Agent {agent_id[:8]} memory archived. "
            f"Their story is preserved in the graveyard."
        )
```

---

## Next Step

→ [05_PHASE1_DEATH.md](./05_PHASE1_DEATH.md) — Build the Death Mechanism