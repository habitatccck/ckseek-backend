#!/usr/bin/env python3
"""测试 checkpoint 加载功能"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from react_agent.memory_checkpoint import MemoryCheckpointSaver
from react_agent.memory import MemoryManager

def test_checkpoint_loading():
    """测试 checkpoint 加载功能"""
    print("🧪 测试 checkpoint 加载功能...")
    
    # 创建 checkpoint saver
    memory_manager = MemoryManager()
    checkpointer = MemoryCheckpointSaver(memory_manager)
    
    # 测试加载特定 thread_id
    thread_id = "thread-b11dd143-64ec-4f21-b101-06135b2e12d4"
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    print(f"📁 尝试加载 thread_id: {thread_id}")
    
    # 尝试加载 checkpoint
    checkpoint_tuple = checkpointer.get(config)
    
    if checkpoint_tuple:
        print("✅ 成功加载 checkpoint")
        print(f"📊 Checkpoint 信息:")
        print(f"   - Config: {checkpoint_tuple.config}")
        print(f"   - Metadata: {checkpoint_tuple.metadata}")
        print(f"   - Checkpoint keys: {list(checkpoint_tuple.checkpoint.keys())}")
        
        # 检查 channel_values
        if "channel_values" in checkpoint_tuple.checkpoint:
            channel_values = checkpoint_tuple.checkpoint["channel_values"]
            print(f"📝 Channel values 类型: {type(channel_values)}")
            
            if isinstance(channel_values, dict):
                print(f"📝 Channel values 内容:")
                for key, value in channel_values.items():
                    if key == "messages":
                        print(f"   - {key}: {len(value)} 条消息")
                        for i, msg in enumerate(value[:3]):  # 显示前3条
                            msg_type = type(msg).__name__
                            content = getattr(msg, 'content', '')[:50]
                            print(f"     {i+1}. {msg_type}: {content}...")
                    elif key == "memory":
                        print(f"   - {key}: {type(value)}")
                    else:
                        print(f"   - {key}: {type(value)}")
            else:
                print(f"📝 Channel values 是字符串: {str(channel_values)[:200]}...")
        else:
            print("❌ 没有找到 channel_values")
    else:
        print("❌ 无法加载 checkpoint")

if __name__ == "__main__":
    test_checkpoint_loading()
