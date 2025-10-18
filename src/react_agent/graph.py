"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from react_agent.context import Context
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model
from react_agent.memory import MemoryManager
from react_agent.memory_checkpoint import FileCheckpointSaver

# Define the function that calls the model


async def call_model(
    state: State, runtime: Runtime[Context]
) -> Dict[str, List[AIMessage] | Dict]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message and updated memory.
    """
    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Inject memory context into the system prompt
    memory_context = state.memory.get_context(include_long_term=True)
    if memory_context:
        system_message = f"{system_message}\n\n{memory_context}"

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Add user's last message to short-term memory
    if state.messages:
        last_msg = state.messages[-1]
        if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
            state.memory.add_short_term(
                f"User: {last_msg.content}",
                tags=["user_input"],
                source="conversation"
            )

    # Add model's response to short-term memory
    if response.content:
        state.memory.add_short_term(
            f"Assistant: {response.content}",
            tags=["assistant_response"],
            source="conversation"
        )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ],
            "memory": state.memory  # Explicitly return memory to persist across turns
        }

    # Return the model's response as a list to be added to existing messages
    # Memory is explicitly returned to ensure it persists across conversation turns
    return {"messages": [response], "memory": state.memory}


# Define a new graph

builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "tools").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "__end__"
    # Otherwise we execute the requested actions
    return "tools"


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
    "call_model",
    # After call_model finishes running, the next node(s) are scheduled
    # based on the output from route_model_output
    route_model_output,
)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Create memory-based checkpoint saver for state persistence
# This global memory manager is used for cross-session long-term memory
_memory_manager = MemoryManager()
checkpointer = FileCheckpointSaver(
    memory_manager=_memory_manager,
    checkpoint_dir="checkpoints"
)

# Compile the builder into an executable graph with checkpointer
graph = builder.compile(
    name="ReAct Agent",
    checkpointer=checkpointer
)


def get_shared_memory_manager() -> MemoryManager:
    """Get the global memory manager instance for cross-session memory.

    This ensures long-term memory persists across different conversation threads.
    """
    return _memory_manager
