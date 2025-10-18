# Checkpoint 异步方法修复

## 问题

运行时报错：
```
NotImplementedError: aget_tuple
```

这是因为 LangGraph 在异步流式调用中需要异步的 checkpoint 方法。

## 解决方案

为 `MemoryCheckpointSaver` 添加了以下异步方法：

- `async aget_tuple()` - 异步获取 checkpoint 元组
- `async aput()` - 异步保存 checkpoint
- `async alist()` - 异步列出 checkpoints
- `async adelete()` - 异步删除 checkpoints

## 实现方式

所有异步方法都是同步方法的包装器。由于内存操作很快，这样做没有问题：

```python
async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
    """Async version of get_tuple."""
    return self.get_tuple(config)

async def aput(self, config, values, metadata, new_versions):
    """Async version of put."""
    return self.put(config, values, metadata, new_versions)

async def alist(self, config, **kwargs):
    """Async version of list."""
    return self.list(config, **kwargs)

async def adelete(self, config):
    """Async version of delete."""
    self.delete(config)
```

## 测试

新增 5 个异步测试（`test_checkpoint_async.py`）：
- ✅ test_aget_tuple
- ✅ test_aput
- ✅ test_alist
- ✅ test_adelete
- ✅ test_langgraph_streaming

总计 16 个测试全部通过。

## 现在可以使用

```python
# 现在 LangGraph 异步流式调用可以正常工作了！
async for chunk in graph.astream(
    input_data,
    config
):
    # 自动使用异步 checkpointer
    ...
```

## 文件修改

- `src/react_agent/memory_checkpoint.py` - 添加异步方法
- `tests/unit_tests/test_checkpoint_async.py` - 新增异步测试
