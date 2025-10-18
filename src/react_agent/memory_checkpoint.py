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

        # Always try to load from file first to get complete history
        if self.persist_to_file:
            checkpoint_data = self._load_from_file(thread_id)
            if checkpoint_data:
                print(f"✅ 从文件加载了完整的 checkpoint 历史")
                return self._create_checkpoint_tuple(checkpoint_data)

        # Fallback to memory if no file data
        if thread_id not in self._checkpoints or not self._checkpoints[thread_id]:
            return None

        # Get the latest checkpoint
        latest_checkpoint = self._checkpoints[thread_id][-1]
        return self._create_checkpoint_tuple(latest_checkpoint)

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Get checkpoint tuple (same as get for this implementation)."""
        return self.get(config)

    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Async version of get_tuple."""
        return self.get_tuple(config)

    async def aput(
        self,
        config: Dict[str, Any],
        values: Dict[str, Any],
        metadata: Dict[str, Any],
        new_versions: ChannelVersions,
    ) -> Optional[str]:
        """Async version of put."""
        return self.put(config, values, metadata, new_versions)

    async def alist(self, config: Dict[str, Any], **kwargs) -> list[CheckpointTuple]:
        """Async version of list."""
        return self.list(config, **kwargs)

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

    async def adelete(self, config: Dict[str, Any]) -> None:
        """Async version of delete."""
        self.delete(config)

    async def aput_writes(
        self,
        config: Dict[str, Any],
        writes: list,
        task_id: str,
        task_path: str = ""
    ) -> None:
        """Async version of put_writes.
        
        This method is required by LangGraph for async streaming operations.
        For our memory-based implementation, we don't need to do anything special
        as writes are handled by the regular aput method.
        """
        # For memory-based checkpointing, writes are handled by the regular put method
        # This is a no-op implementation as our checkpoint system doesn't need
        # special handling for writes during async streaming
        pass

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
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        import ast

        deserialized = {}

        for key, value in serialized.items():
            if key == "channel_values" and isinstance(value, str):
                # Parse the string representation of channel_values
                try:
                    # Import necessary classes for eval
                    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
                    from .memory import MemoryManager, ShortTermMemory, LongTermMemory, MemoryEntry
                    import datetime
                    
                    # Use eval to parse the string (contains complex objects)
                    # This is safe because we control the data source
                    channel_values = eval(value)
                    deserialized.update(channel_values)
                    print(f"✅ 成功解析 channel_values，包含 {len(channel_values)} 个键")
                except Exception as e:
                    print(f"⚠️ 无法解析 channel_values: {e}")
                    print(f"⚠️ 原始值: {value[:200]}...")
                    # Fallback: try to extract messages from the string
                    if "messages" in value:
                        # This is a fallback - in practice, we should fix the serialization
                        deserialized["messages"] = []
                        print("⚠️ 使用空消息列表作为后备")
            elif key == "memory" and isinstance(value, dict):
                # Deserialize MemoryManager
                deserialized[key] = MemoryManager.from_dict(value)
            elif key == "messages" and isinstance(value, list):
                # Deserialize messages back to proper message objects
                messages = []
                for msg_dict in value:
                    msg_type = msg_dict.get("type", "HumanMessage")
                    content = msg_dict.get("content", "")
                    msg_id = msg_dict.get("id")
                    
                    if msg_type == "HumanMessage":
                        msg = HumanMessage(content=content, id=msg_id)
                    elif msg_type == "AIMessage":
                        msg = AIMessage(content=content, id=msg_id)
                    elif msg_type == "SystemMessage":
                        msg = SystemMessage(content=content, id=msg_id)
                    else:
                        # Default to HumanMessage for unknown types
                        msg = HumanMessage(content=content, id=msg_id)
                    
                    messages.append(msg)
                deserialized[key] = messages
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

        # Ensure checkpoint has the structure LangGraph expects
        import uuid
        checkpoint = {
            "v": 1,  # Version field required by LangGraph
            "id": str(uuid.uuid4()).replace("-", ""),  # UUID format checkpoint ID
            "channel_values": values,
            "channel_versions": {},  # Empty dict for channel versions
            "versions_seen": {},  # Empty dict for versions seen
            "pending_sends": []
        }

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
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
        """Load checkpoint from file and rebuild complete conversation history."""
        checkpoint_file = self.checkpoint_dir / f"{thread_id}.json"

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r") as f:
                checkpoints = json.load(f)
                if not checkpoints:
                    return None
                
                # Get the latest checkpoint
                latest_checkpoint = checkpoints[-1]
                
                # Rebuild complete conversation history from all checkpoints
                all_messages = []
                all_memory = None
                
                for checkpoint in checkpoints:
                    values = checkpoint.get("values", {})
                    channel_values_str = values.get("channel_values", "")
                    
                    if channel_values_str:
                        try:
                            # Import necessary classes for eval
                            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
                            from .memory import MemoryManager, ShortTermMemory, LongTermMemory, MemoryEntry
                            import datetime
                            
                            # Parse the channel_values string
                            channel_values = eval(channel_values_str)
                            
                            # Extract messages from this checkpoint
                            messages = channel_values.get("messages", [])
                            if messages:
                                # Add messages to our complete history
                                all_messages.extend(messages)
                            
                            # Get the latest memory state
                            memory = channel_values.get("memory")
                            if memory:
                                all_memory = memory
                                
                        except Exception as e:
                            print(f"⚠️ 解析 checkpoint 失败: {e}")
                            continue
                
                # Create a reconstructed checkpoint with complete history
                reconstructed_checkpoint = latest_checkpoint.copy()
                reconstructed_checkpoint["values"] = latest_checkpoint["values"].copy()
                
                # Update channel_values with complete message history
                if all_messages:
                    # Remove duplicates while preserving order
                    seen_ids = set()
                    unique_messages = []
                    for msg in all_messages:
                        msg_id = getattr(msg, 'id', None)
                        if msg_id not in seen_ids:
                            unique_messages.append(msg)
                            seen_ids.add(msg_id)
                    
                    # Create new channel_values with complete history
                    new_channel_values = {
                        'messages': unique_messages,
                        'memory': all_memory
                    }
                    
                    # Update the checkpoint
                    reconstructed_checkpoint["values"]["channel_values"] = str(new_channel_values)
                    print(f"✅ 重建了包含 {len(unique_messages)} 条消息的完整对话历史")
                
                return reconstructed_checkpoint
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 加载 checkpoint 文件失败: {e}")
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
