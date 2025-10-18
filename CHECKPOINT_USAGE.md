# LangGraph 内存 Checkpoint 系统使用指南

## 概述

我们为你的 LangGraph 项目实现了一个**内存驱动的 Checkpoint 系统**，用于持久化和恢复 Agent 状态。这个系统：

1. ✅ 自动保存每次 graph 执行的状态
2. ✅ 支持状态恢复和重放
3. ✅ 将对话历史持久化到内存和文件
4. ✅ 提供完整的 API 接口进行状态管理

## 系统架构

### 核心组件

#### 1. MemoryCheckpointSaver (`memory_checkpoint.py`)

主要的 Checkpoint 保存器类：

```python
class MemoryCheckpointSaver(BaseCheckpointSaver):
    """内存驱动的 Checkpoint 保存器"""

    def __init__(
        self,
        memory_manager: MemoryManager,
        persist_to_file: bool = True,
        checkpoint_dir: str = "checkpoints"
    ):
        # 初始化
```

**主要方法**:
- `put()` - 保存一个 checkpoint
- `get()` - 获取最新的 checkpoint
- `get_tuple()` - 获取 CheckpointTuple
- `list()` - 列出所有 checkpoint
- `delete()` - 删除 checkpoint
- `get_checkpoint_history()` - 获取历史记录
- `export_memory_summary()` - 导出内存总结

#### 2. InMemoryCheckpointSaver

内存模式（无文件持久化）:

```python
saver = InMemoryCheckpointSaver(memory_manager)
```

#### 3. FileCheckpointSaver

文件模式（带持久化）:

```python
saver = FileCheckpointSaver(
    memory_manager,
    checkpoint_dir="checkpoints"
)
```

## 工作流程

### 1. Graph 编译时

```python
# graph.py 中的配置
_memory_manager = MemoryManager()
checkpointer = FileCheckpointSaver(
    memory_manager=_memory_manager,
    checkpoint_dir="checkpoints"
)

graph = builder.compile(
    name="ReAct Agent",
    checkpointer=checkpointer  # 传递 checkpointer
)
```

### 2. 执行时自动 Checkpoint

```python
# 每次调用都会自动保存 checkpoint
config = {"configurable": {"thread_id": "user-123"}}
result = await graph.ainvoke(
    input_data,
    config  # thread_id 用于分组 checkpoint
)
```

### 3. 数据流

```
用户输入
  ↓
Graph 执行
  ↓
保存到内存（ShortTermMemory）
  ↓
序列化状态
  ↓
保存 Checkpoint 到内存和文件
  ↓
模型响应
```

## API 文档

### 新增 5 个 Checkpoint API 端点

#### 1. GET `/api/checkpoint/history/{thread_id}`
获取线程的 checkpoint 历史

**参数**:
- `thread_id` (必需) - 线程 ID
- `limit` (可选) - 返回数量，默认 10

**响应**:
```json
{
  "status": "success",
  "thread_id": "thread-123",
  "count": 5,
  "checkpoints": [
    {
      "checkpoint_id": 1,
      "timestamp": "2025-10-18T10:30:00",
      "step": 1
    },
    ...
  ]
}
```

**使用场景**:
- 查看会话的执行历史
- 调试 graph 执行过程
- 监控状态变化

---

#### 2. GET `/api/checkpoint/memory-summary/{thread_id}`
获取线程的内存总结

**参数**:
- `thread_id` (必需) - 线程 ID

**响应**:
```json
{
  "status": "success",
  "data": {
    "thread_id": "thread-123",
    "short_term": {
      "count": 10,
      "entries": [
        "User: 你好",
        "Assistant: 你好！有什么可以帮助你的吗？",
        ...
      ]
    },
    "long_term": {
      "count": 3,
      "entries": [
        "用户对 Python 感兴趣",
        ...
      ]
    },
    "checkpoint_count": 5
  }
}
```

**使用场景**:
- 查看用户交互历史
- 分析对话内容
- 内存使用情况统计

---

#### 3. GET `/api/checkpoint/restore/{thread_id}`
从 checkpoint 恢复状态

**参数**:
- `thread_id` (必需) - 线程 ID

**响应**:
```json
{
  "status": "success",
  "thread_id": "thread-123",
  "checkpoint": {
    "config": {
      "configurable": {
        "thread_id": "thread-123",
        "checkpoint_id": 5
      }
    },
    "metadata": {
      "source": "put",
      "step": 5
    },
    "state_keys": ["messages", "memory", "is_last_step"]
  }
}
```

**使用场景**:
- 恢复中断的会话
- 重新加载上一个状态
- 状态验证

---

#### 4. POST `/api/checkpoint/cleanup/{thread_id}`
清理线程的 checkpoint

**参数**:
- `thread_id` (必需) - 线程 ID

**响应**:
```json
{
  "status": "success",
  "message": "已清理线程 thread-123 的所有 checkpoint"
}
```

**使用场景**:
- 清理旧会话
- 释放存储空间
- 会话结束处理

---

#### 5. GET `/api/checkpoint/stats`
获取全局 checkpoint 统计

**响应**:
```json
{
  "status": "success",
  "total_threads": 42,
  "total_checkpoints": 256,
  "checkpoint_dir": "/path/to/checkpoints",
  "persist_to_file": true
}
```

**使用场景**:
- 系统监控
- 存储空间管理
- 性能分析

## 前端集成示例

### JavaScript 客户端

```javascript
// 1. 获取 checkpoint 历史
async function getCheckpointHistory(threadId, limit = 10) {
  const response = await fetch(
    `http://localhost:8000/api/checkpoint/history/${threadId}?limit=${limit}`
  );
  return response.json();
}

// 2. 获取内存总结
async function getMemorySummary(threadId) {
  const response = await fetch(
    `http://localhost:8000/api/checkpoint/memory-summary/${threadId}`
  );
  return response.json();
}

// 3. 恢复状态
async function restoreSession(threadId) {
  const response = await fetch(
    `http://localhost:8000/api/checkpoint/restore/${threadId}`
  );
  return response.json();
}

// 4. 清理会话
async function cleanupSession(threadId) {
  const response = await fetch(
    `http://localhost:8000/api/checkpoint/cleanup/${threadId}`,
    { method: 'POST' }
  );
  return response.json();
}

// 5. 获取统计
async function getCheckpointStats() {
  const response = await fetch(
    'http://localhost:8000/api/checkpoint/stats'
  );
  return response.json();
}

// 使用示例
async function displaySessionHistory(threadId) {
  const history = await getCheckpointHistory(threadId, 5);
  console.log('Checkpoint 历史:', history.checkpoints);

  const summary = await getMemorySummary(threadId);
  console.log('对话历史:', summary.data.short_term.entries);
  console.log('关键信息:', summary.data.long_term.entries);
}
```

## Python 使用示例

### 直接访问 Checkpointer

```python
from react_agent.graph import graph, checkpointer
from react_agent.memory import MemoryManager

# 1. 获取 checkpoint 历史
history = checkpointer.get_checkpoint_history("thread-123", limit=5)
for cp in history:
    print(f"Checkpoint {cp['checkpoint_id']}: {cp['timestamp']}")

# 2. 恢复状态
config = {"configurable": {"thread_id": "thread-123"}}
checkpoint_tuple = checkpointer.get(config)
if checkpoint_tuple:
    print("恢复的状态:", checkpoint_tuple.checkpoint)

# 3. 导出内存总结
summary = checkpointer.export_memory_summary("thread-123")
print(f"短期内存条数: {summary['short_term']['count']}")
print(f"长期内存条数: {summary['long_term']['count']}")

# 4. 清理 checkpoint
checkpointer.delete(config)
```

### 集成到自定义处理流程

```python
from react_agent.graph import graph, checkpointer
from react_agent.memory import MemoryManager

async def handle_user_input(thread_id: str, user_message: str):
    # 配置
    config = {"configurable": {"thread_id": thread_id}}

    # 执行 graph（会自动保存 checkpoint）
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=user_message)]},
        config
    )

    # 获取 checkpoint 历史
    history = checkpointer.get_checkpoint_history(thread_id, limit=1)
    print(f"第 {history[0]['metadata']['step']} 步执行完成")

    # 获取内存摘要
    summary = checkpointer.export_memory_summary(thread_id)
    print(f"保存了 {summary['short_term']['count']} 条短期记忆")

    return result
```

## Checkpoint 数据结构

### 文件格式

Checkpoint 保存在 `checkpoints/{thread_id}.json`:

```json
[
  {
    "thread_id": "thread-123",
    "checkpoint_id": 1,
    "timestamp": "2025-10-18T10:30:00.123456",
    "values": {
      "messages": [
        {
          "type": "HumanMessage",
          "content": "你好",
          "id": "msg-1"
        }
      ],
      "memory": {
        "short_term": {
          "max_size": 20,
          "entries": [...]
        },
        "long_term": {
          "max_summaries": 50,
          "entries": [...]
        }
      }
    },
    "metadata": {
      "step": 1,
      "source": "put"
    }
  }
]
```

## 最佳实践

### 1. 线程 ID 管理

```python
# 为每个用户会话生成唯一 ID
import uuid
thread_id = f"user-{user_id}-{uuid.uuid4()}"

config = {"configurable": {"thread_id": thread_id}}
```

### 2. 定期清理

```python
# 定期清理老旧会话
import os
from pathlib import Path

def cleanup_old_checkpoints(days: int = 30):
    import time
    checkpoint_dir = Path("checkpoints")
    cutoff = time.time() - (days * 24 * 3600)

    for f in checkpoint_dir.glob("*.json"):
        if os.path.getmtime(f) < cutoff:
            f.unlink()
```

### 3. 监控 Checkpoint 大小

```python
async def monitor_checkpoint_size():
    stats = await get_checkpoint_stats()

    if stats['total_checkpoints'] > 1000:
        print("警告：checkpoint 数量过多，需要清理")

    # 计算磁盘占用
    import os
    checkpoint_dir = stats['checkpoint_dir']
    size = sum(
        os.path.getsize(f)
        for f in Path(checkpoint_dir).glob("*.json")
    ) / (1024 * 1024)  # MB

    print(f"Checkpoint 总大小: {size:.2f} MB")
```

### 4. 集成到会话管理

```python
async def end_session(thread_id: str):
    # 导出最终总结
    summary = checkpointer.export_memory_summary(thread_id)

    # 保存到数据库
    await save_session_summary({
        "thread_id": thread_id,
        "short_term_count": summary['short_term']['count'],
        "long_term_count": summary['long_term']['count']
    })

    # 清理 checkpoint
    config = {"configurable": {"thread_id": thread_id}}
    checkpointer.delete(config)
```

## 配置选项

### 在 graph.py 中修改

```python
# 修改 checkpoint 目录
checkpointer = FileCheckpointSaver(
    memory_manager=_memory_manager,
    checkpoint_dir="/path/to/custom/checkpoints"
)

# 只使用内存（不持久化到文件）
checkpointer = InMemoryCheckpointSaver(memory_manager=_memory_manager)
```

## 故障排除

### 问题：Checkpoint 文件很大

**解决方案**:
1. 定期清理旧 checkpoint
2. 调整内存容量
3. 使用 InMemoryCheckpointSaver 而不是 FileCheckpointSaver

### 问题：无法恢复状态

**排查步骤**:
1. 验证 thread_id 是否正确
2. 检查 checkpoint 文件是否存在
3. 查看 API 返回的错误信息

### 问题：内存持续增长

**可能原因**:
1. 没有定期清理 checkpoint
2. 内存配置过大

**解决方案**:
```python
# 定期执行清理
checkpointer.delete(config)
```

## 测试

运行 checkpoint 单元测试：

```bash
python -m pytest tests/unit_tests/test_memory_checkpoint.py -v
```

所有 11 个测试应该通过 ✅

## 文件清单

新增文件：
- ✅ `src/react_agent/memory_checkpoint.py` - Checkpoint 保存器实现
- ✅ `tests/unit_tests/test_memory_checkpoint.py` - Checkpoint 单元测试

修改的文件：
- ✅ `src/react_agent/graph.py` - 集成 checkpointer
- ✅ `src/api/server.py` - 添加 5 个 API 端点

## 完整工作流示例

```python
from react_agent.graph import graph, checkpointer
from langchain_core.messages import HumanMessage

async def complete_workflow():
    # 1. 配置会话
    thread_id = "demo-user-123"
    config = {"configurable": {"thread_id": thread_id}}

    # 2. 首次对话
    result1 = await graph.ainvoke(
        {"messages": [HumanMessage(content="什么是 Python?")]},
        config
    )
    print("AI:", result1["messages"][-1].content)

    # 3. 后续对话（自动恢复上下文）
    result2 = await graph.ainvoke(
        {"messages": [HumanMessage(content="教我如何使用它")]},
        config
    )
    print("AI:", result2["messages"][-1].content)

    # 4. 查看历史
    history = checkpointer.get_checkpoint_history(thread_id)
    print(f"共执行了 {len(history)} 个步骤")

    # 5. 查看内存
    summary = checkpointer.export_memory_summary(thread_id)
    print(f"短期内存: {summary['short_term']['count']}")
    print(f"长期内存: {summary['long_term']['count']}")

    # 6. 恢复状态
    checkpoint_tuple = checkpointer.get(config)
    print(f"最后一步: {checkpoint_tuple.metadata.step}")

    # 7. 会话结束
    checkpointer.delete(config)
```

## 后续改进方向

1. **数据库后端** - 支持 PostgreSQL/MongoDB 存储
2. **云存储** - 支持 S3/GCS
3. **增量 Checkpoint** - 只保存变化的部分
4. **版本管理** - 支持 checkpoint 版本控制
5. **分布式** - 支持多机部署共享状态

---

现在你的 LangGraph Agent 具有完整的状态持久化和恢复能力！🚀
