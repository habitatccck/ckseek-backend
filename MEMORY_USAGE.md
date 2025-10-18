# LangGraph 内存系统使用指南

## 概述

我们为你的 LangGraph 项目添加了一个完整的内存管理系统，支持**短期内存**和**长期内存**两个层级，实现了跨会话的对话记忆功能。

## 系统架构

### 1. 内存管理模块 (`memory.py`)

主要包含以下类：

#### MemoryEntry
表示单个内存条目的数据结构：
```python
@dataclass
class MemoryEntry:
    content: str              # 内存内容
    timestamp: datetime       # 创建时间
    importance: float         # 重要性 (0-10)
    tags: List[str]          # 标签
    source: str              # 来源 ("conversation", "tool_result", "summary" 等)
```

#### ShortTermMemory
短期内存 - 存储当前会话的近期消息：
- **最大容量**: 20 条消息（可配置）
- **自动清理**: 超过容量时自动删除最不重要的条目
- **特点**: 最近的对话上下文，用于实时对话

```python
memory = ShortTermMemory(max_size=20)
memory.add("用户的问题", importance=3.0, tags=["question"])
entries = memory.get_all()  # 按最新顺序返回
```

#### LongTermMemory
长期内存 - 存储跨会话的总结和关键信息：
- **最大容量**: 50 条摘要（可配置）
- **过期管理**: 支持 TTL（默认 30 天）
- **特点**: 按重要性排序，用于跨会话记忆

```python
memory = LongTermMemory(max_summaries=50, ttl_days=30)
memory.add("重要的用户信息", importance=8.0, tags=["user_info"])
summaries = memory.get_all()  # 按重要性返回
```

#### MemoryManager
统一的内存管理器，协调短期和长期内存：

```python
manager = MemoryManager()

# 添加内存
manager.add_short_term("用户问了关于 Python 的问题", tags=["python"])
manager.add_long_term("用户喜欢 Python", importance=7.0, tags=["user_preference"])

# 获取上下文（用于 prompt 注入）
context = manager.get_context(include_long_term=True)

# 会话结束时总结
manager.summarize_short_term("今天讨论了 Python 编程")

# 清除内存
manager.clear_all()
```

## 集成点

### 1. State 集成 (`state.py`)

内存管理器已集成到 State 中：

```python
@dataclass
class State(InputState):
    memory: MemoryManager = field(default_factory=MemoryManager)
    # 其他字段...
```

### 2. Graph 集成 (`graph.py`)

在 `call_model` 函数中自动：
1. **注入内存上下文到系统提示** - 模型能访问相关的历史记忆
2. **自动保存对话到短期内存** - 每次模型调用时

```python
# 内存上下文被注入到系统提示中
memory_context = state.memory.get_context(include_long_term=True)
system_message = f"{system_message}\n\n{memory_context}"

# 对话被自动保存
state.memory.add_short_term(f"User: {user_message}", tags=["user_input"])
state.memory.add_short_term(f"Assistant: {response}", tags=["assistant_response"])
```

### 3. API 端点 (`server.py`)

新增 6 个内存管理 API 端点：

## API 文档

### 1. POST `/api/memory/add`
添加内存条目

**请求体**:
```json
{
  "content": "用户关于 Python 的重要信息",
  "importance": 8.0,
  "tags": ["python", "important"],
  "memory_type": "long_term"
}
```

**响应**:
```json
{
  "status": "success",
  "message": "已添加到long_term记忆"
}
```

**使用场景**:
- 手动保存重要用户信息
- 添加用户偏好信息
- 保存系统学到的知识

---

### 2. POST `/api/memory/get`
获取内存内容

**请求体**:
```json
{
  "memory_type": "short_term",
  "tags": ["python"]
}
```

**响应**:
```json
{
  "status": "success",
  "memory_type": "short_term",
  "count": 3,
  "entries": [
    "User: 如何学习 Python?",
    "Assistant: 推荐学习官方文档...",
    "User: 感谢提议"
  ]
}
```

**参数**:
- `memory_type`: `"short_term"` 或 `"long_term"`
- `tags`: 可选，用于过滤结果

---

### 3. POST `/api/memory/summarize`
总结短期记忆并转移到长期记忆

**请求体**:
```json
{}
```

**响应**:
```json
{
  "status": "success",
  "message": "已将短期记忆总结到长期记忆",
  "short_term_entries_count": 15
}
```

**使用场景**:
- 会话结束时调用
- 保存关键信息到长期内存
- 清除当前短期内存

---

### 4. POST `/api/memory/clear`
清除指定类型的内存

**请求参数**:
- `memory_type`: `"short_term"` / `"long_term"` / `"all"`

**示例**:
```bash
POST /api/memory/clear?memory_type=short_term
```

**响应**:
```json
{
  "status": "success",
  "message": "已清除short_term记忆"
}
```

---

### 5. GET `/api/memory/context`
获取格式化的内存上下文

**响应**:
```json
{
  "status": "success",
  "context": "## Recent Conversation Context:\n- User: 如何学习 Python?\n- Assistant: 推荐...\n\n## Key Information from Previous Conversations:\n- 用户对 Python 感兴趣"
}
```

**用途**: 用于前端展示或调试内存内容

---

### 6. GET `/api/memory/stats`
获取内存统计信息

**响应**:
```json
{
  "status": "success",
  "short_term": {
    "count": 8,
    "max_size": 20
  },
  "long_term": {
    "count": 5,
    "max_summaries": 50,
    "ttl_days": 30
  }
}
```

## 使用示例

### 完整工作流示例

```python
# 1. 创建内存管理器
manager = MemoryManager()

# 2. 在对话期间，系统自动添加到短期内存（在 graph.py 中）
# graph.py 自动处理:
#   - 注入内存上下文到系统提示
#   - 保存用户输入到短期内存
#   - 保存 AI 响应到短期内存

# 3. 手动添加重要信息（可选）
manager.add_long_term(
    "用户喜欢 Python 和数据科学",
    importance=9.0,
    tags=["user_preference", "python"]
)

# 4. 会话结束时总结
manager.summarize_short_term(
    "用户询问了 Python 的最佳实践",
    tags=["session_1"]
)

# 5. 下一个会话开始时，AI 能够访问历史记忆
context = manager.get_context(include_long_term=True)
# 上下文包含了用户偏好和历史信息
```

### 前端集成示例

```javascript
// 1. 添加内存
async function addMemory(content, importance = 5.0) {
  const response = await fetch('http://localhost:8000/api/memory/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: content,
      importance: importance,
      tags: ['user_info'],
      memory_type: 'long_term'
    })
  });
  return response.json();
}

// 2. 获取内存
async function getMemory(type = 'short_term') {
  const response = await fetch('http://localhost:8000/api/memory/get', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      memory_type: type,
      tags: []
    })
  });
  return response.json();
}

// 3. 会话结束时总结
async function endSession() {
  await fetch('http://localhost:8000/api/memory/summarize', {
    method: 'POST'
  });
}

// 4. 获取统计信息
async function getMemoryStats() {
  const response = await fetch('http://localhost:8000/api/memory/stats');
  return response.json();
}

// 5. 获取内存上下文用于展示
async function displayMemoryContext() {
  const response = await fetch('http://localhost:8000/api/memory/context');
  const data = await response.json();
  console.log(data.context);
}
```

## 配置选项

### ShortTermMemory 配置

```python
# 修改最大容量（默认 20）
memory = ShortTermMemory(max_size=30)
```

### LongTermMemory 配置

```python
# 修改最大摘要数（默认 50）和 TTL（默认 30 天）
memory = LongTermMemory(max_summaries=100, ttl_days=60)
```

### 在 State 中使用自定义配置

```python
# 在创建 State 时
state = State(
    messages=[],
    memory=MemoryManager(
        short_term=ShortTermMemory(max_size=30),
        long_term=LongTermMemory(max_summaries=100, ttl_days=60)
    )
)
```

## 最佳实践

1. **标签管理**: 使用一致的标签分类内存
   ```python
   # 好的标签例子
   tags = ["user_preference", "python", "important"]
   tags = ["session_1", "summary"]
   tags = ["tool_result", "search"]
   ```

2. **重要性评分**: 根据内容相关性调整
   - 1-3: 低重要性（临时信息）
   - 4-6: 中等重要性
   - 7-10: 高重要性（核心用户信息）

3. **定期总结**: 在会话结束时调用总结函数
   ```python
   POST /api/memory/summarize
   ```

4. **定期清理**: 监控内存大小，必要时清除过期数据
   ```bash
   GET /api/memory/stats
   POST /api/memory/clear?memory_type=short_term
   ```

5. **序列化持久化**: 将内存保存到数据库
   ```python
   # 导出内存为字典
   data = memory.to_dict()
   # 保存到数据库...

   # 从字典恢复
   memory = MemoryManager.from_dict(data)
   ```

## 测试

运行单元测试验证内存功能：

```bash
python -m pytest tests/unit_tests/test_memory.py -v
```

所有 17 个测试都应该通过 ✅

## 故障排除

### 问题：内存无法自动注入到 prompt 中
**解决方案**: 确保 `graph.py` 中的 `call_model` 函数被正确调用，检查内存上下文是否为空

### 问题：短期内存快速满满
**解决方案**: 增加 `ShortTermMemory` 的 `max_size`，或更频繁地调用 `summarize_short_term`

### 问题：长期内存条目过期了
**解决方案**: 调整 `LongTermMemory` 的 `ttl_days` 参数或在保存时设置更高的重要性分数

## 文件清单

新增/修改的文件：
- ✅ `src/react_agent/memory.py` - 内存管理模块（新建）
- ✅ `src/react_agent/state.py` - 添加内存字段
- ✅ `src/react_agent/graph.py` - 集成内存注入和自动保存
- ✅ `src/api/server.py` - 添加 6 个内存 API 端点
- ✅ `tests/unit_tests/test_memory.py` - 内存模块单元测试（新建）

## 后续改进方向

1. **持久化存储**: 将内存保存到 MongoDB 或 PostgreSQL
2. **向量化搜索**: 使用向量数据库进行语义搜索
3. **自动总结**: 使用 LLM 自动生成高质量的会话总结
4. **分布式内存**: 支持多个 Agent 共享内存
5. **隐私控制**: 添加内存访问权限管理

---

祝你使用愉快！如有问题，请查看测试用例或代码注释。
