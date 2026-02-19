"""
Phase 2 Memory System — Semantic memory with embeddings.

Every agent has a private Qdrant collection. Memories are embedded and
stored as vectors. When the brain needs context, it searches semantically —
not just "last 5 memories" but "most relevant memories to today's situation."

Memory types:
    - personal: things that happened to me
    - relationship: things I know about other agents
    - observation: things I witnessed
    - lesson: things I learned
    - secret: things I'm keeping hidden (only accessible by owner)
"""

import os
import json
import hashlib
from datetime import datetime
from loguru import logger
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue
)

# ─── Clients ──────────────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

VECTOR_SIZE = 1536  # text-embedding-3-small
CITY_COLLECTION = "city_knowledge"


# ─── Embedding ────────────────────────────────────────────────────────────────

def embed(text: str) -> list[float]:
    """Generate an embedding vector for any text."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def _make_point_id(text: str, agent_id: str) -> int:
    """Generate a deterministic integer ID from text + agent."""
    combined = f"{agent_id}:{text}:{datetime.utcnow().isoformat()}"
    return int(hashlib.md5(combined.encode()).hexdigest()[:15], 16)


# ─── Agent Memory ─────────────────────────────────────────────────────────────

class AgentMemory:
    """
    Per-agent semantic memory. Each agent has their own Qdrant collection.
    Memories are embedded and searchable by meaning, not just recency.
    """

    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.collection = f"agent_{agent_id.replace('-', '_')}"
        self._ensure_collection()

    def _ensure_collection(self):
        """Create the agent's private memory collection if it doesn't exist."""
        try:
            existing = [c.name for c in qdrant.get_collections().collections]
            if self.collection not in existing:
                qdrant.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
                )
                logger.info(f"🏠 Memory house created for {self.agent_name}")
        except Exception as e:
            logger.error(f"❌ Could not create memory for {self.agent_name}: {e}")

    def remember(self, content: str, memory_type: str = "personal", day: int = 0, tags: list[str] = None):
        """
        Store a memory. Embeds the content and stores in Qdrant.

        memory_type: personal | relationship | observation | lesson | secret
        """
        try:
            vector = embed(content)
            point_id = _make_point_id(content, self.agent_id)

            qdrant.upsert(
                collection_name=self.collection,
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "content": content,
                        "type": memory_type,
                        "day": day,
                        "tags": tags or [],
                        "agent_name": self.agent_name,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )]
            )
            logger.debug(f"💾 {self.agent_name} remembered: \"{content[:60]}\"")
        except Exception as e:
            logger.error(f"❌ Memory store failed for {self.agent_name}: {e}")

    def recall(self, query: str, top_k: int = 5, memory_type: str = None) -> list[str]:
        """
        Search memories semantically. Returns most relevant memories to the query.
        This is what makes agents smart — they remember what's RELEVANT, not just recent.
        """
        try:
            query_vector = embed(query)
            results = qdrant.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=top_k,
            ).points
            return [r.payload["content"] for r in results]
        except Exception as e:
            logger.error(f"❌ Memory recall failed for {self.agent_name}: {e}")
            return []

    def recall_recent(self, days: int = 3, limit: int = 10) -> list[str]:
        """Get recent memories by day number (not semantic — just recent)."""
        try:
            results = qdrant.scroll(
                collection_name=self.collection,
                limit=limit,
                with_payload=True,
            )[0]

            # Filter by day and sort
            recent = [
                r.payload for r in results
                if r.payload.get("day", 0) >= days
            ]
            recent.sort(key=lambda x: x.get("day", 0), reverse=True)
            return [r["content"] for r in recent[:limit]]
        except Exception as e:
            logger.error(f"❌ Recent recall failed for {self.agent_name}: {e}")
            return []

    def remember_relationship(self, other_name: str, observation: str, day: int):
        """Store what I know about another agent."""
        content = f"About {other_name}: {observation}"
        self.remember(content, memory_type="relationship", day=day, tags=[other_name])

    def recall_about(self, other_name: str, top_k: int = 3) -> list[str]:
        """What do I remember about a specific agent?"""
        return self.recall(f"memories about {other_name}", top_k=top_k, memory_type="relationship")

    def count_memories(self) -> int:
        """How many memories does this agent have?"""
        try:
            return qdrant.get_collection(self.collection).points_count
        except:
            return 0

    def delete_all(self):
        """Delete agent's memory on death (but city knowledge persists)."""
        try:
            qdrant.delete_collection(self.collection)
            logger.info(f"🪦 Memory of {self.agent_name} archived on death.")
        except Exception as e:
            logger.error(f"❌ Could not delete memory for {self.agent_name}: {e}")


# ─── City Knowledge (Shared) ─────────────────────────────────────────────────

class CityKnowledge:
    """
    Shared knowledge base for all of AIcity.
    Laws, news, discoveries, historical events — all searchable.
    """

    def __init__(self):
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            existing = [c.name for c in qdrant.get_collections().collections]
            if CITY_COLLECTION not in existing:
                qdrant.create_collection(
                    collection_name=CITY_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
                )
                logger.info("📚 City knowledge base initialized.")
        except Exception as e:
            logger.error(f"❌ City knowledge init failed: {e}")

    def publish(self, content: str, category: str, author: str, day: int):
        """
        Publish something to the shared city knowledge base.
        category: law | news | discovery | history | announcement
        """
        try:
            vector = embed(content)
            point_id = _make_point_id(content, author)

            qdrant.upsert(
                collection_name=CITY_COLLECTION,
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "content": content,
                        "category": category,
                        "author": author,
                        "day": day,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )]
            )
            logger.info(f"📰 City knowledge updated: [{category}] by {author}")
        except Exception as e:
            logger.error(f"❌ City publish failed: {e}")

    def query(self, question: str, top_k: int = 5, category: str = None) -> list[str]:
        """Search the city knowledge base semantically."""
        try:
            query_vector = embed(question)
            search_filter = None
            if category:
                search_filter = Filter(
                    must=[FieldCondition(key="category", match=MatchValue(value=category))]
                )
            results = qdrant.query_points(
                collection_name=CITY_COLLECTION,
                query_vector=query_vector,
                limit=top_k,
                query_filter=search_filter,
            ).points
            return [r.payload["content"] for r in results]
        except Exception as e:
            logger.error(f"❌ City query failed: {e}")
            return []

    def get_laws(self) -> list[str]:
        """Get all laws."""
        return self.query("laws rules constitution", category="law", top_k=10)

    def get_recent_news(self, top_k: int = 5) -> list[str]:
        """Get the most recent news entries."""
        try:
            results = qdrant.scroll(
                collection_name=CITY_COLLECTION,
                limit=top_k,
                with_payload=True,
            )[0]
            news = [r.payload for r in results if r.payload.get("category") == "news"]
            news.sort(key=lambda x: x.get("day", 0), reverse=True)
            return [n["content"] for n in news[:top_k]]
        except Exception as e:
            logger.error(f"❌ Recent news fetch failed: {e}")
            return []