#!/usr/bin/env python3
"""测试记忆功能"""

import requests
import json
import time

def test_memory():
    """测试 AI 是否能记住之前的对话"""
    print("🧪 测试 AI 记忆功能...")
    
    thread_id = "thread-b11dd143-64ec-4f21-b101-06135b2e12d4"
    session_id = "b11dd143-64ec-4f21-b101-06135b2e12d4"
    
    # 发送问题
    question = "你还记得我们之前聊了什么吗？请详细告诉我。"
    
    print(f"📤 发送问题: {question}")
    
    response = requests.post(
        'http://localhost:8000/api/generate/stream',
        headers={'Content-Type': 'application/json'},
        json={
            "message": question,
            "thread_id": thread_id,
            "session_id": session_id
        },
        stream=True
    )
    
    if response.status_code == 200:
        print("✅ 收到响应，内容如下:")
        print("-" * 50)
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])  # 去掉 'data: ' 前缀
                        if data.get('type') == 'content':
                            content = data.get('content', '')
                            print(content, end='', flush=True)
                            full_response += content
                    except json.JSONDecodeError:
                        continue
        
        print("\n" + "-" * 50)
        print(f"📝 完整响应长度: {len(full_response)} 字符")
        
        # 检查是否提到了之前的对话内容
        if "生日" in full_response or "4月" in full_response or "50日" in full_response:
            print("✅ AI 记住了之前的对话内容！")
        else:
            print("❌ AI 似乎没有记住之前的对话内容")
            
    else:
        print(f"❌ 请求失败: {response.status_code}")

if __name__ == "__main__":
    test_memory()
