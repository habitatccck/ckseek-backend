"""会话管理模块，用于管理对话会话的创建、存储和检索."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel


class Message(BaseModel):
    """消息模型."""
    role: str  # 'user' 或 'assistant'
    content: str
    timestamp: str
    message_id: Optional[str] = None


class Session(BaseModel):
    """会话模型."""
    session_id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[Message] = []
    metadata: Dict = {}


class SessionSummary(BaseModel):
    """会话摘要模型（用于列表展示）."""
    session_id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    preview: str  # 最后一条消息的预览
    metadata: Dict = {}


class SessionManager:
    """会话管理器，负责会话的创建、存储和检索."""
    
    def __init__(self, storage_path: str = "data/sessions.json"):
        """初始化会话管理器."""
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions: Dict[str, Session] = {}
        self._load_sessions()
    
    def _load_sessions(self):
        """从文件加载会话数据."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sessions = {
                        sid: Session(**session_data) 
                        for sid, session_data in data.items()
                    }
            except Exception as e:
                print(f"加载会话数据失败: {e}")
                self.sessions = {}
    
    def _save_sessions(self):
        """保存会话数据到文件."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                data = {
                    sid: session.model_dump() 
                    for sid, session in self.sessions.items()
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存会话数据失败: {e}")
    
    def create_session(self, title: Optional[str] = None) -> Session:
        """创建新的会话."""
        session_id = str(uuid.uuid4())
        thread_id = f"thread-{session_id}"
        now = datetime.now().isoformat()
        
        session = Session(
            session_id=session_id,
            thread_id=thread_id,
            title=title or f"新对话 {now[:19]}",
            created_at=now,
            updated_at=now,
            messages=[],
            metadata={}
        )
        
        self.sessions[session_id] = session
        self._save_sessions()
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取指定的会话."""
        return self.sessions.get(session_id)
    
    def get_session_by_thread_id(self, thread_id: str) -> Optional[Session]:
        """根据 thread_id 获取会话."""
        for session in self.sessions.values():
            if session.thread_id == thread_id:
                return session
        return None
    
    def get_all_sessions(self) -> List[Session]:
        """获取所有会话列表，按更新时间倒序排列."""
        sessions = list(self.sessions.values())
        sessions.sort(key=lambda x: x.updated_at, reverse=True)
        return sessions
    
    def get_all_sessions_summary(self) -> List[SessionSummary]:
        """获取所有会话的摘要列表，用于左侧列表展示."""
        sessions = list(self.sessions.values())
        sessions.sort(key=lambda x: x.updated_at, reverse=True)
        
        summaries = []
        for session in sessions:
            # 获取最后一条消息作为预览
            preview = ""
            if session.messages:
                last_message = session.messages[-1]
                # 截取前100个字符作为预览
                preview = last_message.content[:100]
                if len(last_message.content) > 100:
                    preview += "..."
            
            summary = SessionSummary(
                session_id=session.session_id,
                thread_id=session.thread_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=len(session.messages),
                preview=preview,
                metadata=session.metadata
            )
            summaries.append(summary)
        
        return summaries
    
    def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        message_id: Optional[str] = None
    ) -> bool:
        """向会话中添加消息."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            message_id=message_id or str(uuid.uuid4())
        )
        
        session.messages.append(message)
        session.updated_at = datetime.now().isoformat()
        
        # 如果是第一条用户消息，可以用它作为标题
        if len(session.messages) == 1 and role == 'user':
            session.title = content[:50] + ('...' if len(content) > 50 else '')
        
        self._save_sessions()
        return True
    
    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.title = title
        session.updated_at = datetime.now().isoformat()
        self._save_sessions()
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定的会话."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_sessions()
            return True
        return False


# 全局会话管理器实例
session_manager = SessionManager()

