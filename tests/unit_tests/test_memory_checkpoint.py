"""Unit tests for memory-based checkpoint saver."""

import pytest
from datetime import datetime
from react_agent.memory import MemoryManager
from react_agent.memory_checkpoint import (
    MemoryCheckpointSaver,
    InMemoryCheckpointSaver,
    FileCheckpointSaver
)


@pytest.fixture
def memory_manager():
    """Create a fresh memory manager for each test."""
    return MemoryManager()


@pytest.fixture
def checkpoint_saver(memory_manager):
    """Create a checkpoint saver instance."""
    return MemoryCheckpointSaver(
        memory_manager=memory_manager,
        persist_to_file=False
    )


class TestMemoryCheckpointSaver:
    """Test MemoryCheckpointSaver class."""

    def test_put_checkpoint(self, checkpoint_saver):
        """Test saving a checkpoint."""
        config = {"configurable": {"thread_id": "thread-123"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }
        metadata = {"step": 1}
        new_versions = {}

        checkpoint_id = checkpoint_saver.put(
            config, values, metadata, new_versions
        )

        assert checkpoint_id is not None
        assert checkpoint_id == "1"

    def test_get_checkpoint(self, checkpoint_saver):
        """Test retrieving a checkpoint."""
        config = {"configurable": {"thread_id": "thread-456"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }
        metadata = {"step": 1}
        new_versions = {}

        # Save a checkpoint
        checkpoint_saver.put(config, values, metadata, new_versions)

        # Retrieve it
        checkpoint_tuple = checkpoint_saver.get(config)

        assert checkpoint_tuple is not None
        assert "memory" in checkpoint_tuple.checkpoint

    def test_list_checkpoints(self, checkpoint_saver):
        """Test listing all checkpoints for a thread."""
        config = {"configurable": {"thread_id": "thread-789"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }

        # Save multiple checkpoints
        for i in range(3):
            metadata = {"step": i + 1}
            checkpoint_saver.put(config, values, metadata, {})

        # List checkpoints
        checkpoints = checkpoint_saver.list(config)

        assert len(checkpoints) == 3

    def test_delete_checkpoints(self, checkpoint_saver):
        """Test deleting all checkpoints for a thread."""
        config = {"configurable": {"thread_id": "thread-delete"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }

        # Save a checkpoint
        checkpoint_saver.put(config, values, {"step": 1}, {})

        # Verify it exists
        assert checkpoint_saver.get(config) is not None

        # Delete it
        checkpoint_saver.delete(config)

        # Verify it's gone
        assert checkpoint_saver.get(config) is None

    def test_memory_serialization(self, checkpoint_saver):
        """Test that memory is properly serialized."""
        memory = MemoryManager()
        memory.add_short_term("Test message", tags=["test"])
        memory.add_long_term("Important fact", importance=8.0)

        config = {"configurable": {"thread_id": "thread-serial"}}
        values = {
            "messages": [],
            "memory": memory
        }
        metadata = {"step": 1}

        checkpoint_saver.put(config, values, metadata, {})

        # Retrieve and verify
        checkpoint_tuple = checkpoint_saver.get(config)
        restored_memory = checkpoint_tuple.checkpoint["memory"]

        assert len(restored_memory.short_term.entries) == 1
        assert len(restored_memory.long_term.entries) == 1

    def test_checkpoint_history(self, checkpoint_saver):
        """Test getting checkpoint history."""
        config = {"configurable": {"thread_id": "thread-history"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }

        # Save multiple checkpoints
        for i in range(5):
            checkpoint_saver.put(config, values, {"step": i + 1}, {})

        history = checkpoint_saver.get_checkpoint_history("thread-history", limit=3)

        assert len(history) == 3  # Should return only 3 (limit)

    def test_export_memory_summary(self, checkpoint_saver):
        """Test exporting memory summary."""
        memory = MemoryManager()
        memory.add_short_term("Short-term message")
        memory.add_long_term("Long-term fact", importance=7.0)

        checkpoint_saver.memory_manager = memory

        config = {"configurable": {"thread_id": "thread-summary"}}
        values = {
            "messages": [],
            "memory": memory
        }
        checkpoint_saver.put(config, values, {"step": 1}, {})

        summary = checkpoint_saver.export_memory_summary("thread-summary")

        assert summary["thread_id"] == "thread-summary"
        assert summary["short_term"]["count"] >= 0
        assert summary["long_term"]["count"] >= 0


class TestInMemoryCheckpointSaver:
    """Test in-memory only checkpoint saver."""

    def test_in_memory_mode(self):
        """Test that in-memory saver doesn't persist to file."""
        memory = MemoryManager()
        saver = InMemoryCheckpointSaver(memory)

        assert not saver.persist_to_file

    def test_basic_functionality(self):
        """Test basic in-memory functionality."""
        memory = MemoryManager()
        saver = InMemoryCheckpointSaver(memory)

        config = {"configurable": {"thread_id": "test-thread"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }

        checkpoint_id = saver.put(config, values, {"step": 1}, {})
        checkpoint_tuple = saver.get(config)

        assert checkpoint_tuple is not None


class TestFileCheckpointSaver:
    """Test file-backed checkpoint saver."""

    def test_file_mode(self, tmp_path):
        """Test that file saver persists to disk."""
        memory = MemoryManager()
        saver = FileCheckpointSaver(
            memory,
            checkpoint_dir=str(tmp_path)
        )

        assert saver.persist_to_file

    def test_file_persistence(self, tmp_path):
        """Test that checkpoints persist to file."""
        memory = MemoryManager()
        saver = FileCheckpointSaver(
            memory,
            checkpoint_dir=str(tmp_path)
        )

        config = {"configurable": {"thread_id": "file-test"}}
        values = {
            "messages": [],
            "memory": MemoryManager()
        }

        # Save checkpoint
        saver.put(config, values, {"step": 1}, {})

        # Verify file was created
        checkpoint_file = tmp_path / "file-test.json"
        assert checkpoint_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
