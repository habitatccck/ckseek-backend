"""Memory-based checkpoint saver for LangGraph state persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from langgraph.checkpoint.base import ChannelVersions

from .memory import MemoryManager


class MemoryCheckpointSaver(BaseCheckpointSaver):
    """Checkpoint saver that persists LangGraph state using our memory system.

    This saver:
    1. Saves graph state to memory after each node execution
    2. Allows recovery of state from previous checkpoints
    3. Supports both in-memory and file-based persistence
    4. Automatically saves conversation history to long-term memory
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        persist_to_file: bool = True,
        checkpoint_dir: str = "checkpoints"
    ):
        """Initialize the memory checkpoint saver.

        Args:
            memory_manager: The memory manager instance to use
            persist_to_file: Whether to also persist to disk
            checkpoint_dir: Directory to save checkpoint files
        """
        super().__init__()
        self.memory_manager = memory_manager
        self.persist_to_file = persist_to_file
        self.checkpoint_dir = Path(checkpoint_dir)

        if persist_to_file:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # In-memory checkpoint storage: thread_id -> list of checkpoints
        self._checkpoints: Dict[str, list[Dict[str, Any]]] = {}

    def put(
        self,
        config: Dict[str, Any],
        values: Dict[str, Any],
        metadata: Dict[str, Any],
        new_versions: ChannelVersions,
    ) -> Optional[str]:
        """Save a checkpoint to memory and optionally to disk.

        Args:
            config: Configuration including thread_id
            values: The state values to save
            metadata: Additional metadata about the checkpoint
            new_versions: Channel versions for this checkpoint

        Returns:
            The checkpoint ID
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = metadata.get("step", 0)

        # Extract messages from state
        messages = values.get("messages", [])
        memory = values.get("memory")

        # Create checkpoint data
        checkpoint_data = {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "timestamp": datetime.now().isoformat(),
            "values": self._serialize_values(values),
            "metadata": metadata,
            "new_versions": new_versions,
        }

        # Store in memory
        if thread_id not in self._checkpoints:
            self._checkpoints[thread_id] = []

        self._checkpoints[thread_id].append(checkpoint_data)

        # Store messages in short-term memory
        if messages:
            self._save_messages_to_memory(messages)

        # Persist memory manager state to long-term memory
        if memory:
            self._save_memory_state(thread_id, memory, checkpoint_id)

        # Optionally save to file
        if self.persist_to_file:
            self._save_to_file(thread_id, checkpoint_data)

        return str(checkpoint_id)

    def get(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Retrieve a checkpoint from memory.

        Args:
            config: Configuration including thread_id

        Returns:
            CheckpointTuple with the state and metadata
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")

        if thread_id not in self._checkpoints or not self._checkpoints[thread_id]:
            # Try to load from file if available
            if self.persist_to_file:
                checkpoint_data = self._load_from_file(thread_id)
                if checkpoint_data:
                    return self._create_checkpoint_tuple(checkpoint_data)
            return None

        # Get the latest checkpoint
        latest_checkpoint = self._checkpoints[thread_id][-1]
        return self._create_checkpoint_tuple(latest_checkpoint)

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Get checkpoint tuple (same as get for this implementation)."""
        return self.get(config)

    def list(self, config: Dict[str, Any], **kwargs) -> list[CheckpointTuple]:
        """List all checkpoints for a thread.

        Args:
            config: Configuration including thread_id

        Returns:
            List of all checkpoints for this thread
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")

        if thread_id not in self._checkpoints:
            return []

        return [
            self._create_checkpoint_tuple(cp)
            for cp in self._checkpoints[thread_id]
        ]

    def delete(self, config: Dict[str, Any]) -> None:
        """Delete all checkpoints for a thread.

        Args:
            config: Configuration including thread_id
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")

        if thread_id in self._checkpoints:
            del self._checkpoints[thread_id]

        # Delete from file if exists
        if self.persist_to_file:
            checkpoint_file = self.checkpoint_dir / f"{thread_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()

    def _serialize_values(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize state values for storage.

        Handles conversion of non-JSON-serializable objects.
        """
        serialized = {}

        for key, value in values.items():
            if key == "memory" and hasattr(value, "to_dict"):
                # Serialize MemoryManager
                serialized[key] = value.to_dict()
            elif key == "messages":
                # Serialize messages
                serialized[key] = [
                    {
                        "type": type(msg).__name__,
                        "content": getattr(msg, "content", ""),
                        "id": getattr(msg, "id", None),
                    }
                    for msg in value
                ]
            else:
                try:
                    # Try to serialize directly
                    json.dumps(value)
                    serialized[key] = value
                except (TypeError, ValueError):
                    # If not serializable, store as string representation
                    serialized[key] = str(value)

        return serialized

    def _deserialize_values(self, serialized: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize state values from storage."""
        from .state import State

        deserialized = {}

        for key, value in serialized.items():
            if key == "memory" and isinstance(value, dict):
                # Deserialize MemoryManager
                deserialized[key] = MemoryManager.from_dict(value)
            else:
                deserialized[key] = value

        return deserialized

    def _create_checkpoint_tuple(
        self, checkpoint_data: Dict[str, Any]
    ) -> CheckpointTuple:
        """Create a CheckpointTuple from checkpoint data."""
        values = self._deserialize_values(checkpoint_data["values"])

        # Create CheckpointMetadata
        from langgraph.checkpoint.base import CheckpointMetadata
        metadata = CheckpointMetadata(
            source=checkpoint_data.get("metadata", {}).get("source", "put"),
            step=checkpoint_data.get("metadata", {}).get("step", 0),
            writes=checkpoint_data.get("metadata", {}).get("writes")
        )

        config = {
            "configurable": {
                "thread_id": checkpoint_data["thread_id"],
                "checkpoint_id": checkpoint_data["checkpoint_id"],
            }
        }

        return CheckpointTuple(
            config=config,
            checkpoint=values,
            metadata=metadata,
            parent_config=None,
            pending_writes=None
        )

    def _save_messages_to_memory(self, messages: list) -> None:
        """Save messages to short-term memory."""
        for msg in messages:
            msg_type = type(msg).__name__
            content = getattr(msg, "content", "")

            if content:
                tag = "assistant_response" if "AI" in msg_type else "user_input"
                self.memory_manager.add_short_term(
                    f"{msg_type}: {content}",
                    tags=[tag],
                    source="checkpoint"
                )

    def _save_memory_state(
        self,
        thread_id: str,
        memory: MemoryManager,
        checkpoint_id: int
    ) -> None:
        """Save memory state to long-term memory."""
        # Summary of short-term memory
        short_term_entries = memory.short_term.get_all()

        if short_term_entries:
            summary = (
                f"Checkpoint {checkpoint_id} - Thread {thread_id}: "
                f"{len(short_term_entries)} messages"
            )

            self.memory_manager.add_long_term(
                summary,
                importance=6.0,
                tags=["checkpoint", f"thread_{thread_id}", f"checkpoint_{checkpoint_id}"],
                source="checkpoint"
            )

    def _save_to_file(self, thread_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Save checkpoint to file."""
        checkpoint_file = self.checkpoint_dir / f"{thread_id}.json"

        checkpoints = []
        if checkpoint_file.exists():
            with open(checkpoint_file, "r") as f:
                checkpoints = json.load(f)

        checkpoints.append(checkpoint_data)

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoints, f, indent=2, default=str)

    def _load_from_file(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint from file."""
        checkpoint_file = self.checkpoint_dir / f"{thread_id}.json"

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r") as f:
                checkpoints = json.load(f)
                return checkpoints[-1] if checkpoints else None
        except (json.JSONDecodeError, IOError):
            return None

    def get_checkpoint_history(
        self,
        thread_id: str,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """Get checkpoint history for a thread.

        Args:
            thread_id: The thread ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoints
        """
        checkpoints = self._checkpoints.get(thread_id, [])
        return checkpoints[-limit:]

    def export_memory_summary(self, thread_id: str) -> Dict[str, Any]:
        """Export a summary of memory state for a thread.

        Args:
            thread_id: The thread ID

        Returns:
            Summary of short-term and long-term memory
        """
        return {
            "thread_id": thread_id,
            "short_term": {
                "count": len(self.memory_manager.short_term.entries),
                "entries": self.memory_manager.short_term.get_all()[:5]
            },
            "long_term": {
                "count": len(self.memory_manager.long_term.entries),
                "entries": self.memory_manager.long_term.get_all()[:5]
            },
            "checkpoint_count": len(self._checkpoints.get(thread_id, []))
        }


class InMemoryCheckpointSaver(MemoryCheckpointSaver):
    """In-memory only checkpoint saver (no file persistence)."""

    def __init__(self, memory_manager: MemoryManager):
        """Initialize with in-memory only mode."""
        super().__init__(
            memory_manager=memory_manager,
            persist_to_file=False
        )


class FileCheckpointSaver(MemoryCheckpointSaver):
    """File-backed checkpoint saver with in-memory cache."""

    def __init__(
        self,
        memory_manager: MemoryManager,
        checkpoint_dir: str = "checkpoints"
    ):
        """Initialize with file persistence."""
        super().__init__(
            memory_manager=memory_manager,
            persist_to_file=True,
            checkpoint_dir=checkpoint_dir
        )
