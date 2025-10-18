"""Unit tests for memory management system."""

import pytest
from datetime import datetime
from react_agent.memory import (
    MemoryEntry,
    ShortTermMemory,
    LongTermMemory,
    MemoryManager
)


class TestMemoryEntry:
    """Test MemoryEntry dataclass."""

    def test_memory_entry_creation(self):
        """Test creating a memory entry."""
        entry = MemoryEntry(
            content="Test content",
            timestamp=datetime.now(),
            importance=5.0,
            tags=["test"],
            source="conversation"
        )
        assert entry.content == "Test content"
        assert entry.importance == 5.0
        assert "test" in entry.tags
        assert entry.source == "conversation"


class TestShortTermMemory:
    """Test ShortTermMemory class."""

    def test_add_entry(self):
        """Test adding an entry to short-term memory."""
        memory = ShortTermMemory(max_size=5)
        memory.add("Test message", importance=2.0, tags=["test"])

        assert len(memory.entries) == 1
        assert memory.entries[0].content == "Test message"

    def test_max_size_enforcement(self):
        """Test that max_size is enforced."""
        memory = ShortTermMemory(max_size=3)

        # Add 5 entries (more than max_size)
        for i in range(5):
            memory.add(f"Message {i}", importance=float(i))

        # Should only keep max_size (3) entries, prioritizing by importance
        assert len(memory.entries) <= memory.max_size

    def test_get_all(self):
        """Test retrieving all entries."""
        memory = ShortTermMemory()
        memory.add("Message 1")
        memory.add("Message 2")
        memory.add("Message 3")

        entries = memory.get_all()
        assert len(entries) == 3
        assert "Message 1" in entries
        assert "Message 2" in entries
        assert "Message 3" in entries

    def test_get_by_tags(self):
        """Test retrieving entries by tags."""
        memory = ShortTermMemory()
        memory.add("Python info", tags=["python"])
        memory.add("JavaScript info", tags=["javascript"])
        memory.add("Python advanced", tags=["python", "advanced"])

        python_entries = memory.get_by_tags(["python"])
        assert len(python_entries) == 2
        assert any("Python" in e for e in python_entries)

    def test_clear(self):
        """Test clearing memory."""
        memory = ShortTermMemory()
        memory.add("Message 1")
        memory.add("Message 2")

        assert len(memory.entries) == 2
        memory.clear()
        assert len(memory.entries) == 0


class TestLongTermMemory:
    """Test LongTermMemory class."""

    def test_add_entry(self):
        """Test adding an entry to long-term memory."""
        memory = LongTermMemory(max_summaries=10)
        memory.add("Summary of conversation", importance=8.0, tags=["summary"])

        assert len(memory.entries) == 1
        assert memory.entries[0].content == "Summary of conversation"

    def test_max_summaries_enforcement(self):
        """Test that max_summaries is enforced."""
        memory = LongTermMemory(max_summaries=3)

        # Add 5 entries (more than max_summaries)
        for i in range(5):
            memory.add(f"Summary {i}", importance=float(i))

        # Should only keep max_summaries (3) entries, prioritizing by importance
        assert len(memory.entries) <= memory.max_summaries

    def test_get_all(self):
        """Test retrieving all entries."""
        memory = LongTermMemory()
        memory.add("Summary 1", importance=5.0)
        memory.add("Summary 2", importance=8.0)
        memory.add("Summary 3", importance=3.0)

        entries = memory.get_all()
        assert len(entries) == 3

    def test_get_by_tags(self):
        """Test retrieving entries by tags."""
        memory = LongTermMemory()
        memory.add("Python knowledge", tags=["python", "knowledge"])
        memory.add("JavaScript knowledge", tags=["javascript", "knowledge"])

        knowledge_entries = memory.get_by_tags(["knowledge"])
        assert len(knowledge_entries) == 2


class TestMemoryManager:
    """Test MemoryManager class."""

    def test_add_short_term(self):
        """Test adding to short-term memory via manager."""
        manager = MemoryManager()
        manager.add_short_term("User asked about Python", tags=["python"])

        entries = manager.short_term.get_all()
        assert len(entries) == 1
        assert "Python" in entries[0]

    def test_add_long_term(self):
        """Test adding to long-term memory via manager."""
        manager = MemoryManager()
        manager.add_long_term("Important fact about Python", importance=9.0, tags=["python"])

        entries = manager.long_term.get_all()
        assert len(entries) == 1
        assert "Python" in entries[0]

    def test_get_context(self):
        """Test generating memory context for prompt injection."""
        manager = MemoryManager()
        manager.add_short_term("Recent message 1", tags=["recent"])
        manager.add_short_term("Recent message 2", tags=["recent"])
        manager.add_long_term("Important fact", tags=["knowledge"])

        context = manager.get_context(include_long_term=True)
        assert "Recent Conversation Context" in context
        assert "Key Information from Previous Conversations" in context
        assert len(context) > 0

    def test_get_context_short_term_only(self):
        """Test generating memory context with short-term only."""
        manager = MemoryManager()
        manager.add_short_term("Recent message", tags=["recent"])
        manager.add_long_term("Important fact", tags=["knowledge"])

        context = manager.get_context(include_long_term=False)
        assert "Recent Conversation Context" in context
        assert "Key Information from Previous Conversations" not in context

    def test_summarize_short_term(self):
        """Test summarizing short-term memory to long-term."""
        manager = MemoryManager()
        manager.add_short_term("Message 1")
        manager.add_short_term("Message 2")

        assert len(manager.short_term.entries) == 2
        assert len(manager.long_term.entries) == 0

        manager.summarize_short_term("Session summary", tags=["session"])

        assert len(manager.short_term.entries) == 0
        assert len(manager.long_term.entries) == 1

    def test_clear_all(self):
        """Test clearing all memory."""
        manager = MemoryManager()
        manager.add_short_term("Short-term memory")
        manager.add_long_term("Long-term memory")

        assert len(manager.short_term.entries) == 1
        assert len(manager.long_term.entries) == 1

        manager.clear_all()

        assert len(manager.short_term.entries) == 0
        assert len(manager.long_term.entries) == 0

    def test_serialization(self):
        """Test serializing and deserializing memory."""
        manager = MemoryManager()
        manager.add_short_term("Short-term", importance=3.0, tags=["short"])
        manager.add_long_term("Long-term", importance=8.0, tags=["long"])

        # Serialize
        data = manager.to_dict()

        # Deserialize
        manager2 = MemoryManager.from_dict(data)

        assert len(manager2.short_term.entries) == 1
        assert len(manager2.long_term.entries) == 1
        assert manager2.short_term.entries[0].content == "Short-term"
        assert manager2.long_term.entries[0].content == "Long-term"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
