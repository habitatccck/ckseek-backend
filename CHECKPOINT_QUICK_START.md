# Checkpoint 快速开始指南

## 5 分钟快速上手

### 1️⃣ 系统已自动配置

你的 Graph 已经自动配置了 checkpointer，无需额外设置！

```python
# graph.py 中已经配置好了
checkpointer = FileCheckpointSaver(
    memory_manager=_memory_manager,
    checkpoint_dir="checkpoints"
)

graph = builder.compile(
    name="ReAct Agent",
    checkpointer=checkpointer
)
```

### 2️⃣ 使用 Thread ID 执行 Graph

每次调用时，传递 `thread_id` 用于状态跟踪：

```python
from react_agent.graph import graph
from langchain_core.messages import HumanMessage

# 为用户创建唯一的 thread_id
thread_id = "user-123-session-1"
config = {"configurable": {"thread_id": thread_id}}

# 第一个请求
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="你好")]},
    config
)

# 第二个请求 - 自动恢复上下文
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="请继续")]},
    config
)
```

**✨ 优点**:
- ✅ 自动保存每次执行的状态
- ✅ 自动恢复对话上下文
- ✅ 状态持久化到文件

### 3️⃣ 通过 API 查询 Checkpoint

```bash
# 查看执行历史
curl http://localhost:8000/api/checkpoint/history/user-123-session-1

# 查看内存总结
curl http://localhost:8000/api/checkpoint/memory-summary/user-123-session-1

# 获取统计信息
curl http://localhost:8000/api/checkpoint/stats

# 清理会话
curl -X POST http://localhost:8000/api/checkpoint/cleanup/user-123-session-1
```

## API 端点参考

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/api/checkpoint/history/{thread_id}` | 查看执行历史 |
| GET | `/api/checkpoint/memory-summary/{thread_id}` | 查看对话内存 |
| GET | `/api/checkpoint/restore/{thread_id}` | 恢复最新状态 |
| POST | `/api/checkpoint/cleanup/{thread_id}` | 清理 checkpoint |
| GET | `/api/checkpoint/stats` | 全局统计 |

## 文件位置

```
backend/
├── src/react_agent/
│   ├── memory_checkpoint.py       # ← Checkpoint 实现
│   ├── graph.py                   # ← 已集成 checkpointer
│   └── memory.py                  # ← 内存管理
├── checkpoints/                   # ← 自动创建的 checkpoint 目录
│   └── user-123-session-1.json
└── CHECKPOINT_USAGE.md            # ← 详细文档
```

## 工作原理（5 步）

```
1️⃣ 用户输入
        ↓
2️⃣ Graph 执行（call_model → tools → ...）
        ↓
3️⃣ 状态自动保存到内存 + 内存对话保存
        ↓
4️⃣ 序列化并写入 checkpoint 文件
        ↓
5️⃣ 返回结果给用户
        ↓
6️⃣ 下次同一线程的请求自动加载上次状态
```

## 前端集成示例

### React 中使用

```jsx
// 创建 unique thread ID
const threadId = `user-${userId}-${sessionId}`;

// 发送消息（会自动保存 checkpoint）
async function sendMessage(message) {
  const response = await fetch('http://localhost:8000/api/generate/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      thread_id: threadId  // ← 关键！用于恢复状态
    })
  });

  return response.body.getReader();
}

// 查看对话历史
async function showHistory() {
  const res = await fetch(
    `http://localhost:8000/api/checkpoint/memory-summary/${threadId}`
  );
  const data = await res.json();
  console.log('短期内存:', data.data.short_term.entries);
}
```

## 测试 Checkpoint

### 方法 1：命令行测试

```bash
# 查看 checkpoint 统计
curl http://localhost:8000/api/checkpoint/stats

# 查看特定线程的历史（需要先有数据）
curl http://localhost:8000/api/checkpoint/history/thread-123

# 查看内存总结
curl http://localhost:8000/api/checkpoint/memory-summary/thread-123
```

### 方法 2：运行单元测试

```bash
python -m pytest tests/unit_tests/test_memory_checkpoint.py -v
```

### 方法 3：Python 脚本测试

```python
from react_agent.graph import checkpointer

# 查看所有 checkpoint 统计
stats = {
    "threads": len(checkpointer._checkpoints),
    "total_checkpoints": sum(
        len(cps) for cps in checkpointer._checkpoints.values()
    )
}
print(f"正在追踪 {stats['threads']} 个线程")
print(f"总共 {stats['total_checkpoints']} 个 checkpoint")

# 查看特定线程的 checkpoint 历史
history = checkpointer.get_checkpoint_history("your-thread-id")
print(f"线程有 {len(history)} 个 checkpoint")
```

## 常见场景

### 场景 1：同一用户的多轮对话

```python
# 所有消息使用同一 thread_id
thread_id = "user-alice-001"
config = {"configurable": {"thread_id": thread_id}}

# 第 1 轮
await graph.ainvoke({"messages": [HumanMessage(content="你好")]}, config)

# 第 2 轮 - 自动记得第 1 轮的内容
await graph.ainvoke({"messages": [HumanMessage(content="我之前说什么了？")]}, config)
# 模型能看到整个对话历史！
```

### 场景 2：会话暂停和恢复

```python
# 会话 1 - 早上
await graph.ainvoke({...}, {"configurable": {"thread_id": "user-bob-day1"}})

# 几小时后...

# 会话 1 恢复 - 自动恢复之前的状态
checkpoint = checkpointer.get({"configurable": {"thread_id": "user-bob-day1"}})
print(f"恢复状态，共有 {len(checkpoint.checkpoint['messages'])} 条消息")
```

### 场景 3：多用户并发

```python
# 每个用户独立的 thread_id
for user_id in [1, 2, 3, 4, 5]:
    thread_id = f"user-{user_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # 并发执行 - 完全隔离
    await graph.ainvoke({...}, config)
```

### 场景 4：清理旧会话

```python
# 用户登出时清理
user_thread_ids = [f"user-{user_id}-session-{i}" for i in range(10)]

for thread_id in user_thread_ids:
    config = {"configurable": {"thread_id": thread_id}}
    checkpointer.delete(config)
```

## 性能提示

### ✅ 推荐做法

- 为每个用户/会话使用唯一的 `thread_id`
- 定期清理不活跃的会话
- 监控 `checkpoints/` 目录大小

### ❌ 避免做法

- 所有用户使用同一个 `thread_id`
- 无限增长的 thread_id 列表
- 忘记清理旧的 checkpoint

## 监控仪表板

```python
# 创建一个监控端点
from react_agent.graph import checkpointer

def get_dashboard_stats():
    stats = {
        "total_threads": len(checkpointer._checkpoints),
        "total_checkpoints": sum(
            len(cps) for cps in checkpointer._checkpoints.values()
        ),
        "avg_checkpoints_per_thread": round(
            sum(len(cps) for cps in checkpointer._checkpoints.values())
            / max(len(checkpointer._checkpoints), 1)
        ),
        "checkpoint_directory": str(checkpointer.checkpoint_dir),
        "persist_to_file": checkpointer.persist_to_file
    }
    return stats

# 使用
print(get_dashboard_stats())
# 输出:
# {
#   'total_threads': 5,
#   'total_checkpoints': 23,
#   'avg_checkpoints_per_thread': 5,
#   'checkpoint_directory': 'checkpoints',
#   'persist_to_file': True
# }
```

## 故障排除 Quick Tips

| 问题 | 原因 | 解决方案 |
|------|------|--------|
| 无法找到 checkpoint | thread_id 拼写错误 | 检查 `/api/checkpoint/stats` 中的活动 thread |
| 状态没有被保存 | 没有使用 `configurable` config | 必须传递 `{"configurable": {"thread_id": "..."}}` |
| 文件过大 | 太多 checkpoint | 调用 `/api/checkpoint/cleanup/{thread_id}` |
| 内存使用过多 | 使用了 `InMemoryCheckpointSaver` | 改用 `FileCheckpointSaver` |

## 下一步

1. ✅ 在前端集成 `thread_id`
2. ✅ 测试多轮对话是否保存状态
3. ✅ 查看 `CHECKPOINT_USAGE.md` 了解更多高级功能
4. ✅ 根据需要配置 checkpoint 目录和策略

## 文档链接

- 📖 [详细使用指南](CHECKPOINT_USAGE.md)
- 📖 [内存系统指南](MEMORY_USAGE.md)
- 🧪 [单元测试代码](tests/unit_tests/test_memory_checkpoint.py)

---

现在你已经有了完整的状态持久化系统！🎉

**关键点**:
- 传递 `thread_id` 即可自动保存状态
- 同一 thread 的后续请求会自动恢复上下文
- 提供了完整的 API 接口管理 checkpoint
