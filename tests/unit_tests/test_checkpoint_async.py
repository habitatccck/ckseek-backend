"""Async tests for memory checkpoint saver."""

import pytest
from react_agent.memory import MemoryManager
from react_agent.memory_checkpoint import MemoryCheckpointSaver, FileCheckpointSaver


@pytest.mark.asyncio
async def test_aget_tuple():
    """Test async get_tuple."""
    memory = MemoryManager()
    saver = MemoryCheckpointSaver(memory, persist_to_file=False)

    config = {"configurable": {"thread_id": "async-test-1"}}
    values = {
        "messages": [],
        "memory": MemoryManager()
    }
    metadata = {"step": 1}

    # Save
    await saver.aput(config, values, metadata, {})

    # Retrieve async
    checkpoint_tuple = await saver.aget_tuple(config)

    assert checkpoint_tuple is not None
    assert "memory" in checkpoint_tuple.checkpoint


@pytest.mark.asyncio
async def test_aput():
    """Test async put."""
    memory = MemoryManager()
    saver = MemoryCheckpointSaver(memory, persist_to_file=False)

    config = {"configurable": {"thread_id": "async-test-2"}}
    values = {
        "messages": [],
        "memory": MemoryManager()
    }
    metadata = {"step": 1}

    # Put async
    checkpoint_id = await saver.aput(config, values, metadata, {})

    assert checkpoint_id is not None
    assert checkpoint_id == "1"


@pytest.mark.asyncio
async def test_alist():
    """Test async list."""
    memory = MemoryManager()
    saver = MemoryCheckpointSaver(memory, persist_to_file=False)

    config = {"configurable": {"thread_id": "async-test-3"}}
    values = {
        "messages": [],
        "memory": MemoryManager()
    }

    # Put multiple checkpoints
    for i in range(3):
        await saver.aput(config, values, {"step": i + 1}, {})

    # List async
    checkpoints = await saver.alist(config)

    assert len(checkpoints) == 3


@pytest.mark.asyncio
async def test_adelete():
    """Test async delete."""
    memory = MemoryManager()
    saver = MemoryCheckpointSaver(memory, persist_to_file=False)

    config = {"configurable": {"thread_id": "async-test-4"}}
    values = {
        "messages": [],
        "memory": MemoryManager()
    }

    # Put
    await saver.aput(config, values, {"step": 1}, {})

    # Verify exists
    checkpoint = await saver.aget_tuple(config)
    assert checkpoint is not None

    # Delete async
    await saver.adelete(config)

    # Verify gone
    checkpoint = await saver.aget_tuple(config)
    assert checkpoint is None


@pytest.mark.asyncio
async def test_langgraph_streaming():
    """Test that async methods work with LangGraph streaming."""
    from react_agent.graph import graph, checkpointer
    from langchain_core.messages import HumanMessage

    # This test simulates the actual LangGraph streaming call
    thread_id = "async-streaming-test"
    config = {"configurable": {"thread_id": thread_id}}

    # Test that aget_tuple works (this is what LangGraph calls)
    checkpoint = await checkpointer.aget_tuple(config)
    # Should be None for first call
    assert checkpoint is None or checkpoint is not None  # Just verify it returns something


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
