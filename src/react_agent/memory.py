"""Memory management for LangGraph agent - supporting short-term and long-term memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json


@dataclass
class MemoryEntry:
    """Represents a single memory entry with metadata."""

    content: str
    """The actual memory content."""

    timestamp: datetime
    """When this memory was created."""

    importance: float = 1.0
    """Importance score (0-10, higher = more important). Used for summarization."""

    tags: List[str] = field(default_factory=list)
    """Tags for categorizing and retrieving memories."""

    source: str = "conversation"
    """Source of the memory (e.g., 'conversation', 'tool_result', 'summary')."""


@dataclass
class ShortTermMemory:
    """Short-term memory: stores recent messages in current conversation session.

    This memory has a fixed capacity and auto-discards oldest entries when full.
    """

    max_size: int = 20
    """Maximum number of entries to keep in short-term memory."""

    entries: List[MemoryEntry] = field(default_factory=list)
    """List of memory entries, ordered by recency."""

    def add(self, content: str, importance: float = 1.0, tags: List[str] = None, source: str = "conversation") -> None:
        """Add a new memory entry."""
        if tags is None:
            tags = []

        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now(),
            importance=importance,
            tags=tags,
            source=source
        )

        self.entries.append(entry)

        # Auto-trim if exceeds max size
        if len(self.entries) > self.max_size:
            # Keep the most important entries
            self.entries = sorted(
                self.entries,
                key=lambda x: (x.importance, x.timestamp.timestamp()),
                reverse=True
            )[:self.max_size]

    def get_all(self) -> List[str]:
        """Get all memory entries as strings, ordered by recency."""
        return [entry.content for entry in sorted(self.entries, key=lambda x: x.timestamp, reverse=True)]

    def get_by_tags(self, tags: List[str]) -> List[str]:
        """Get memory entries that contain any of the specified tags."""
        results = []
        for entry in sorted(self.entries, key=lambda x: x.timestamp, reverse=True):
            if any(tag in entry.tags for tag in tags):
                results.append(entry.content)
        return results

    def clear(self) -> None:
        """Clear all entries."""
        self.entries = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_size": self.max_size,
            "entries": [
                {
                    "content": entry.content,
                    "timestamp": entry.timestamp.isoformat(),
                    "importance": entry.importance,
                    "tags": entry.tags,
                    "source": entry.source
                }
                for entry in self.entries
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShortTermMemory:
        """Create from dictionary (deserialization)."""
        memory = cls(max_size=data.get("max_size", 20))
        for entry_data in data.get("entries", []):
            entry = MemoryEntry(
                content=entry_data["content"],
                timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                importance=entry_data.get("importance", 1.0),
                tags=entry_data.get("tags", []),
                source=entry_data.get("source", "conversation")
            )
            memory.entries.append(entry)
        return memory


@dataclass
class LongTermMemory:
    """Long-term memory: stores summarized information across sessions.

    This memory persists across conversations and stores key facts and summaries.
    """

    max_summaries: int = 50
    """Maximum number of summary entries to keep."""

    entries: List[MemoryEntry] = field(default_factory=list)
    """List of memory entries."""

    ttl_days: int = 30
    """Time-to-live for entries in days (None = never expire)."""

    def add(self, content: str, importance: float = 1.0, tags: List[str] = None, source: str = "summary") -> None:
        """Add a new long-term memory entry."""
        if tags is None:
            tags = []

        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now(),
            importance=importance,
            tags=tags,
            source=source
        )

        self.entries.append(entry)

        # Clean expired entries
        self._remove_expired()

        # Keep most important entries
        if len(self.entries) > self.max_summaries:
            self.entries = sorted(
                self.entries,
                key=lambda x: x.importance,
                reverse=True
            )[:self.max_summaries]

    def _remove_expired(self) -> None:
        """Remove entries that have expired based on TTL."""
        if self.ttl_days is None:
            return

        cutoff_time = datetime.now() - timedelta(days=self.ttl_days)
        self.entries = [e for e in self.entries if e.timestamp > cutoff_time]

    def get_all(self) -> List[str]:
        """Get all non-expired memory entries."""
        self._remove_expired()
        return [entry.content for entry in sorted(self.entries, key=lambda x: x.importance, reverse=True)]

    def get_by_tags(self, tags: List[str]) -> List[str]:
        """Get memory entries that contain any of the specified tags."""
        self._remove_expired()
        results = []
        for entry in sorted(self.entries, key=lambda x: x.importance, reverse=True):
            if any(tag in entry.tags for tag in tags):
                results.append(entry.content)
        return results

    def clear(self) -> None:
        """Clear all entries."""
        self.entries = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        self._remove_expired()
        return {
            "max_summaries": self.max_summaries,
            "ttl_days": self.ttl_days,
            "entries": [
                {
                    "content": entry.content,
                    "timestamp": entry.timestamp.isoformat(),
                    "importance": entry.importance,
                    "tags": entry.tags,
                    "source": entry.source
                }
                for entry in self.entries
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LongTermMemory:
        """Create from dictionary (deserialization)."""
        memory = cls(
            max_summaries=data.get("max_summaries", 50),
            ttl_days=data.get("ttl_days", 30)
        )
        for entry_data in data.get("entries", []):
            entry = MemoryEntry(
                content=entry_data["content"],
                timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                importance=entry_data.get("importance", 1.0),
                tags=entry_data.get("tags", []),
                source=entry_data.get("source", "summary")
            )
            memory.entries.append(entry)
        return memory


@dataclass
class MemoryManager:
    """Main memory manager combining short-term and long-term memory."""

    short_term: ShortTermMemory = field(default_factory=ShortTermMemory)
    """Short-term memory for current conversation."""

    long_term: LongTermMemory = field(default_factory=LongTermMemory)
    """Long-term memory across conversations."""

    def add_short_term(self, content: str, importance: float = 1.0, tags: List[str] = None, source: str = "conversation") -> None:
        """Add to short-term memory."""
        self.short_term.add(content, importance, tags, source)

    def add_long_term(self, content: str, importance: float = 1.0, tags: List[str] = None, source: str = "summary") -> None:
        """Add to long-term memory."""
        self.long_term.add(content, importance, tags, source)

    def get_context(self, include_long_term: bool = True) -> str:
        """Get formatted memory context for system prompt injection.

        Args:
            include_long_term: Whether to include long-term memory in context.

        Returns:
            Formatted string with memory context for the AI model.
        """
        context_parts = []

        # Add short-term memory (always include)
        short_term_entries = self.short_term.get_all()
        if short_term_entries:
            context_parts.append("## Recent Conversation Context:")
            context_parts.extend([f"- {entry}" for entry in short_term_entries[:10]])  # Limit to last 10

        # Add long-term memory if requested
        if include_long_term:
            long_term_entries = self.long_term.get_all()
            if long_term_entries:
                context_parts.append("\n## Key Information from Previous Conversations:")
                context_parts.extend([f"- {entry}" for entry in long_term_entries[:5]])  # Limit to top 5

        return "\n".join(context_parts) if context_parts else ""

    def summarize_short_term(self, summary: str, tags: List[str] = None) -> None:
        """Summarize short-term memory and move to long-term.

        This is typically called at the end of a conversation session.
        """
        if tags is None:
            tags = []

        self.add_long_term(summary, importance=7.0, tags=tags, source="session_summary")
        self.short_term.clear()

    def clear_all(self) -> None:
        """Clear all memory entries."""
        self.short_term.clear()
        self.long_term.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire memory to dictionary for serialization."""
        return {
            "short_term": self.short_term.to_dict(),
            "long_term": self.long_term.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryManager:
        """Create from dictionary (deserialization)."""
        manager = cls()
        if "short_term" in data:
            manager.short_term = ShortTermMemory.from_dict(data["short_term"])
        if "long_term" in data:
            manager.long_term = LongTermMemory.from_dict(data["long_term"])
        return manager
