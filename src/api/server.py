"""FastAPI server for streaming agent responses."""

import json
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from react_agent.context import Context
from react_agent.graph import graph
from .session_manager import session_manager, Session, SessionSummary

app = FastAPI(
    title="React Agent API",
    description="流式对话 API 服务",
    version="1.0.0"
)

# 配置 CORS，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请修改为具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """聊天请求模型."""
    
    message: str
    thread_id: Optional[str] = None
    session_id: Optional[str] = None  # 可以直接传递 session_id
    model: Optional[str] = "openai/gpt-4o-mini"
    system_prompt: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应模型."""
    
    thread_id: str
    message: str


class StartSessionRequest(BaseModel):
    """开启新会话请求模型."""
    title: Optional[str] = None


class SessionDetailRequest(BaseModel):
    """获取会话详情请求模型."""
    session_id: str


async def stream_agent_response(
    message: str,
    thread_id: str,
    session_id: Optional[str] = None,
    model: str = "openai/gpt-4o-mini",
    system_prompt: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    流式生成 agent 的响应.
    
    Args:
        message: 用户消息
        thread_id: 线程 ID，用于多轮对话
        session_id: 会话 ID（可选），用于保存消息
        model: 模型名称
        system_prompt: 系统提示词（可选）
    
    Yields:
        SSE 格式的流式数据
    """
    assistant_messages = {}  # 使用字典来收集 AI 消息，key 是 message_id
    
    try:
        # 创建 Context 实例
        context_kwargs: Dict[str, Any] = {"model": model}
        if system_prompt:
            context_kwargs["system_prompt"] = system_prompt
        context = Context(**context_kwargs)
        
        # 准备配置
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        # 准备输入
        input_data = {
            "messages": [HumanMessage(content=message)]
        }
        
        # 流式调用 graph（使用 context 参数）
        async for chunk in graph.astream(
            input_data,
            config,
            context=context,  # 直接传递 context
            stream_mode="messages"  # 流式返回消息
        ):
            # chunk 是一个元组 (message, metadata)
            if isinstance(chunk, tuple) and len(chunk) == 2:
                message_chunk, metadata = chunk
                
                # 只处理 AI 的响应消息
                if hasattr(message_chunk, 'content') and message_chunk.content:
                    # 收集 AI 回复内容（支持 AIMessage 和 AIMessageChunk）
                    msg_type_name = type(message_chunk).__name__
                    if msg_type_name in ('AIMessage', 'AIMessageChunk'):
                        msg_id = getattr(message_chunk, 'id', None)
                        if msg_id:
                            # 累加消息内容（流式输出时每次都是增量内容）
                            if msg_id not in assistant_messages:
                                assistant_messages[msg_id] = ""
                            assistant_messages[msg_id] += message_chunk.content
                    
                    # 发送数据块
                    data = {
                        "type": "content",
                        "content": message_chunk.content,
                        "metadata": {
                            "message_id": getattr(message_chunk, 'id', None),
                            "message_type": type(message_chunk).__name__
                        }
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                # 如果有工具调用
                if hasattr(message_chunk, 'tool_calls') and message_chunk.tool_calls:
                    for tool_call in message_chunk.tool_calls:
                        data = {
                            "type": "tool_call",
                            "tool_name": tool_call.get("name", "unknown"),
                            "tool_args": tool_call.get("args", {})
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        # 保存消息到会话
        if session_id or thread_id:
            # 优先使用 session_id，否则通过 thread_id 查找
            target_session_id = session_id
            if not target_session_id:
                session = session_manager.get_session_by_thread_id(thread_id)
                if session:
                    target_session_id = session.session_id
            
            # 保存用户消息和 AI 回复
            if target_session_id:
                session_manager.add_message(target_session_id, "user", message)
                
                # 合并所有 AI 消息
                if assistant_messages:
                    full_response = "\n".join(assistant_messages.values())
                    session_manager.add_message(target_session_id, "assistant", full_response)
        
        # 发送完成信号
        yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        # 记录详细错误日志
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ 流式响应错误: {e}")
        print(error_traceback)
        
        # 发送错误信息
        error_data = {
            "type": "error",
            "error": str(e),
            "traceback": error_traceback
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@app.get("/")
async def root():
    """根路径，返回 API 信息."""
    return {
        "name": "React Agent API",
        "version": "1.0.0",
        "endpoints": {
            "stream": "/api/generate/stream",
            "start_new_session": "/api/start_new_session",
            "history_list": "/api/history_list",
            "session_detail": "/api/session_detail/{session_id}",
            "docs": "/docs"
        }
    }


@app.post("/api/generate/stream")
async def generate_stream(request: ChatRequest):
    """
    流式生成对话响应.
    
    前端调用示例：
    ```javascript
    const response = await fetch('http://localhost:8000/api/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: '你好',
            thread_id: 'thread-123',  // 可选，用于多轮对话
            session_id: 'session-123'  // 可选，用于保存消息到会话
        })
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                console.log(data);
            }
        }
    }
    ```
    """
    # 如果没有提供 thread_id，生成一个新的
    thread_id = request.thread_id or f"thread-{uuid.uuid4()}"
    
    # 返回 SSE 流式响应
    return StreamingResponse(
        stream_agent_response(
            message=request.message,
            thread_id=thread_id,
            session_id=request.session_id,
            model=request.model or "openai/gpt-4o-mini",
            system_prompt=request.system_prompt
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )


@app.post("/api/start_new_session")
async def start_new_session(request: StartSessionRequest):
    """
    开启新对话会话.
    
    创建一个新的对话会话，并返回会话信息。
    前端可以将此信息存储到浏览器的 IndexedDB 中。
    
    Args:
        request: 包含可选的会话标题
    
    Returns:
        新创建的会话信息
    
    Example:
        POST /api/start_new_session
        {
            "title": "关于 Python 的问题"  // 可选
        }
        
        Response:
        {
            "session_id": "uuid-string",
            "thread_id": "thread-uuid-string",
            "title": "关于 Python 的问题",
            "created_at": "2025-10-11T15:30:00",
            "updated_at": "2025-10-11T15:30:00",
            "messages": [],
            "metadata": {}
        }
    """
    try:
        session = session_manager.create_session(title=request.title)
        return session.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@app.get("/api/history_list")
async def get_history_list():
    """
    获取历史会话列表（摘要信息）.
    
    返回所有历史会话的摘要列表，仅包含标题和预览信息，适合左侧列表渲染。
    按更新时间倒序排列。前端可以将此信息同步到浏览器的 IndexedDB 中。
    
    Returns:
        会话摘要列表
    
    Example:
        GET /api/history_list
        
        Response:
        [
            {
                "session_id": "uuid-1",
                "thread_id": "thread-uuid-1",
                "title": "第一个对话",
                "created_at": "2025-10-11T15:30:00",
                "updated_at": "2025-10-11T15:35:00",
                "message_count": 5,
                "preview": "最后一条消息的前100个字符...",
                "metadata": {}
            },
            {
                "session_id": "uuid-2",
                "thread_id": "thread-uuid-2",
                "title": "第二个对话",
                "created_at": "2025-10-11T14:00:00",
                "updated_at": "2025-10-11T14:10:00",
                "message_count": 3,
                "preview": "最后一条消息的前100个字符...",
                "metadata": {}
            }
        ]
    """
    try:
        summaries = session_manager.get_all_sessions_summary()
        return [summary.model_dump() for summary in summaries]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@app.get("/api/session_detail/{session_id}")
async def get_session_detail(session_id: str):
    """
    获取某个历史会话的详细信息.
    
    返回指定会话的完整信息，包括所有消息记录。
    
    Args:
        session_id: 会话 ID
    
    Returns:
        会话详细信息
    
    Example:
        GET /api/session_detail/uuid-string
        
        Response:
        {
            "session_id": "uuid-string",
            "thread_id": "thread-uuid-string",
            "title": "对话标题",
            "created_at": "2025-10-11T15:30:00",
            "updated_at": "2025-10-11T15:35:00",
            "messages": [
                {
                    "role": "user",
                    "content": "你好",
                    "timestamp": "2025-10-11T15:30:00",
                    "message_id": "msg-1"
                },
                {
                    "role": "assistant",
                    "content": "你好！有什么可以帮助你的吗？",
                    "timestamp": "2025-10-11T15:30:05",
                    "message_id": "msg-2"
                }
            ],
            "metadata": {}
        }
    """
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        return session.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查接口."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

