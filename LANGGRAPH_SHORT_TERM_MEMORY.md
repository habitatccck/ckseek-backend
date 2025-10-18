# LangGraph 内置短期记忆实现

## 问题诊断

之前短期记忆没有生效的原因是：**每次调用 graph 时，只传递了新的单条消息，而不是完整的对话历史**。

LangGraph 的 checkpoint 虽然会保存所有状态（包括历史消息），但在调用时需要**显式地将历史消息包含在 input_data 中**。

## 解决方案

### 核心改动

在 `server.py` 的 `stream_agent_response` 函数中修改了消息处理逻辑：

```python
# ❌ 之前（只有新消息）
input_data = {
    "messages": [HumanMessage(content=message)]
}

# ✅ 现在（历史消息 + 新消息）
# 1. 从 checkpoint 中获取历史消息
existing_state = checkpointer.get(config)
existing_messages = []
if existing_state and existing_state.checkpoint:
    existing_messages = existing_state.checkpoint.get("messages", [])

# 2. 将历史消息和新消息组合
input_data = {
    "messages": existing_messages + [HumanMessage(content=message)]
}

# 3. graph 现在能看到完整对话历史
async for chunk in graph.astream(input_data, config, ...):
    ...
```

## 工作流程

```
第一次对话：
  用户: "你好"
  ↓
  messages: [HumanMessage("你好")]
  ↓
  Graph 执行
  ↓
  Checkpoint 保存: {messages: [User(你好), AI(你好！...)]}

第二次对话（同一 thread_id）：
  用户: "告诉我你是谁"
  ↓
  读取 Checkpoint → existing_messages = [User(你好), AI(你好！...)]
  ↓
  messages: [User(你好), AI(你好！...), User(告诉我你是谁)]
  ↓
  Graph 执行（能看到完整对话上下文！）
  ↓
  Checkpoint 更新: {messages: [...完整历史...]}

第三次对话（同一 thread_id）：
  用户: "你记得我之前说什么了吗？"
  ↓
  模型能看到所有之前的消息，可以回答！
```

## 为什么这样做有效

### LangGraph State 的 `add_messages` 机制

在 `state.py` 中定义的 State：

```python
@dataclass
class InputState:
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(...)
```

`add_messages` 是一个特殊的 reducer，它会：
1. **合并** 传入的消息列表
2. **自动去重** 相同 ID 的消息
3. **追加** 新消息到历史中

所以当你传递 `[历史消息..., 新消息]` 时，State 会正确地合并它们。

### Checkpoint 的作用

Checkpoint 在每次执行后自动保存完整状态：
- ✅ 保存所有消息（包括历史）
- ✅ 保存内存状态
- ✅ 保存工具调用结果
- ✅ 按 `thread_id` 分组管理

## 现在的效果

✨ **短期记忆已启用！**

```python
# 使用相同的 thread_id 进行多轮对话
thread_id = "user-alice"

# 第 1 轮
POST /api/generate/stream
{
    "message": "我叫 Alice",
    "thread_id": "user-alice"
}
→ AI: "很高兴认识你，Alice！"

# 第 2 轮 - 使用相同 thread_id
POST /api/generate/stream
{
    "message": "我的名字是什么？",
    "thread_id": "user-alice"
}
→ AI: "你的名字是 Alice。"  # ← 记住了！

# 第 3 轮
POST /api/generate/stream
{
    "message": "我们之前聊了什么？",
    "thread_id": "user-alice"
}
→ AI: "你告诉我你叫 Alice，然后问我记不记得你的名字。"  # ← 完整回忆！
```

## 前端集成

关键是要**保持 `thread_id` 不变**：

```javascript
// 创建新会话时生成 thread_id（一次性）
const threadId = `user-${userId}-${Date.now()}`;

// 所有消息都使用这个 thread_id
async function sendMessage(userMessage) {
    const response = await fetch('http://localhost:8000/api/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: userMessage,
            thread_id: threadId  // ← 关键：保持一致
        })
    });

    // 流式处理响应...
}

// 用户在同一对话中继续问问题
await sendMessage("我叫什么名字？");  // 使用相同 threadId
await sendMessage("我们聊过什么？");  // 使用相同 threadId
```

## 技术细节

### 消息历史的获取

```python
# 从 checkpoint 获取最后保存的状态
checkpoint_tuple = checkpointer.get(config)

# 获取 checkpoint 中保存的消息列表
if checkpoint_tuple and checkpoint_tuple.checkpoint:
    messages = checkpoint_tuple.checkpoint.get("messages", [])
    # messages 现在包含完整的对话历史
```

### 自动合并机制

LangGraph 使用 reducer pattern：

```python
# 当你调用
graph.invoke(
    {"messages": [msg1, msg2, msg3]},
    config
)

# 如果 state 中已有 [prev_msg1, prev_msg2]
# add_messages reducer 会合并为：
# [prev_msg1, prev_msg2, msg1, msg2, msg3]
```

### Checkpoint 的持久化

所有消息自动保存到 `checkpoints/{thread_id}.json`：

```json
[
  {
    "checkpoint_id": 1,
    "values": {
      "messages": [
        {"type": "HumanMessage", "content": "你好"},
        {"type": "AIMessage", "content": "你好！..."}
      ]
    }
  },
  {
    "checkpoint_id": 2,
    "values": {
      "messages": [
        {"type": "HumanMessage", "content": "你好"},
        {"type": "AIMessage", "content": "你好！..."},
        {"type": "HumanMessage", "content": "你记得吗？"},
        {"type": "AIMessage", "content": "..."}
      ]
    }
  }
]
```

## 验证短期记忆是否工作

### 方法 1：查看 Checkpoint 文件

```bash
# 第一次对话后
cat checkpoints/thread-123.json

# 应该能看到保存的消息列表
```

### 方法 2：使用 Checkpoint API

```bash
# 获取线程的 checkpoint 历史
curl http://localhost:8000/api/checkpoint/history/thread-123

# 获取内存总结
curl http://localhost:8000/api/checkpoint/memory-summary/thread-123
```

### 方法 3：观察 AI 的回应

如果 AI 能：
- ✅ 记住用户的名字
- ✅ 引用之前的对话
- ✅ 保持对话上下文一致
- ✅ 记住用户的偏好

那么短期记忆就是工作的！

## 限制和配置

### 消息历史长度限制

如果需要限制历史消息数量，可以在 `call_model` 中修改：

```python
# graph.py 中的 call_model 函数
# 只发送最后 N 条消息给模型（但完整历史仍被保存）

recent_messages = state.messages[-10:]  # 只发送最后 10 条
```

### 内存大小管理

Checkpoint 会占用磁盘空间。如果需要清理：

```bash
# 清理旧的 checkpoint
curl -X POST http://localhost:8000/api/checkpoint/cleanup/thread-123

# 或在代码中
checkpointer.delete(config)
```

## 文件清单

修改的文件：
- ✅ `src/api/server.py` - 从 checkpoint 读取历史消息并组合

涉及的系统：
- ✅ Checkpoint 保存器 (`memory_checkpoint.py`) - 自动持久化
- ✅ State 定义 (`state.py`) - 包含 add_messages reducer
- ✅ Graph (`graph.py`) - 自动使用 checkpoint

## 总结

| 方面 | 说明 |
|------|------|
| **何时生效** | 使用相同的 `thread_id` 进行多轮对话 |
| **数据存储** | `checkpoints/{thread_id}.json` 文件 |
| **消息合并** | `add_messages` reducer 自动处理 |
| **API 恢复** | `/api/checkpoint/history` 等端点 |
| **前端集成** | 保持 `thread_id` 不变，继续发送消息 |

现在你的 LangGraph Agent 具有**完整的内置短期记忆能力**！🎉
