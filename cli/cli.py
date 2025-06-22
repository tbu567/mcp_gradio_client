import sqlite3
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime


class ConversationManager:
    """Manages conversation storage and retrieval using SQLite database"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        # Create directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT,
                    metadata TEXT
                )
            ''')
            
            # Create messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''')
            
            # Create index for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_conversation_id 
                ON messages(conversation_id)
            ''')
            
            conn.commit()
    
    async def save_id(self, conversation_id: str, title: Optional[str] = None):
        """Save or update a conversation ID"""
        def _save():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if conversation exists
                cursor.execute(
                    'SELECT id FROM conversations WHERE id = ?', 
                    (conversation_id,)
                )
                
                if cursor.fetchone():
                    # Update existing conversation
                    cursor.execute('''
                        UPDATE conversations 
                        SET updated_at = CURRENT_TIMESTAMP, title = COALESCE(?, title)
                        WHERE id = ?
                    ''', (title, conversation_id))
                else:
                    # Insert new conversation
                    cursor.execute('''
                        INSERT INTO conversations (id, title)
                        VALUES (?, ?)
                    ''', (conversation_id, title))
                
                conn.commit()
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _save)
    
    async def get_last_id(self) -> Optional[str]:
        """Get the most recently updated conversation ID"""
        def _get_last():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id FROM conversations 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                ''')
                result = cursor.fetchone()
                return result[0] if result else None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_last)
    
    async def save_message(self, conversation_id: str, role: str, content: str):
        """Save a message to the database"""
        def _save_message():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (?, ?, ?)
                ''', (conversation_id, role, content))
                conn.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _save_message)
    
    async def get_conversation_messages(self, conversation_id: str) -> list:
        """Get all messages for a conversation"""
        def _get_messages():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT role, content, timestamp
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                ''', (conversation_id,))
                return cursor.fetchall()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_messages)
    
    async def list_conversations(self, limit: int = 50) -> list:
        """List recent conversations"""
        def _list_conversations():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, created_at, updated_at
                    FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list_conversations)
    
    async def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its messages"""
        def _delete():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete messages first (foreign key constraint)
                cursor.execute(
                    'DELETE FROM messages WHERE conversation_id = ?', 
                    (conversation_id,)
                )
                
                # Delete conversation
                cursor.execute(
                    'DELETE FROM conversations WHERE id = ?', 
                    (conversation_id,)
                )
                
                conn.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _delete)
    
    def get_db_stats(self) -> dict:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get conversation count
            cursor.execute('SELECT COUNT(*) FROM conversations')
            conversation_count = cursor.fetchone()[0]
            
            # Get message count
            cursor.execute('SELECT COUNT(*) FROM messages')
            message_count = cursor.fetchone()[0]
            
            # Get database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return {
                'conversations': conversation_count,
                'messages': message_count,
                'db_size_bytes': db_size,
                'db_path': str(self.db_path)
            }
