import chromadb
from typing import List, Dict, Any
import uuid
from datetime import datetime
import logging

logger = logging.getLogger("vector_store")

class KnowledgeVectorStore:
    """知识向量存储"""
    
    def __init__(self, persist_directory: str = "./data/vector_store"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection("elderly_knowledge")
    
    def add_knowledge(self, text: str, metadata: Dict = None, category: str = "general"):
        """添加知识到向量存储"""
        doc_id = str(uuid.uuid4())
        
        self.collection.add(
            documents=[text],
            metadatas=[{
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "source": "conversation",
                **(metadata or {})
            }],
            ids=[doc_id]
        )
        
        logger.info(f"添加知识到向量存储，类别: {category}, 长度: {len(text)}")
    
    def search_knowledge(self, query: str, n_results: int = 3, category: str = None) -> List[Dict]:
        """搜索相关知识"""
        where_clause = {"category": category} if category else None
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        return [
            {
                "document": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )
        ]
    
    def get_conversation_patterns(self, session_id: str) -> List[Dict]:
        """获取对话模式"""
        results = self.collection.query(
            query_texts=["conversation pattern"],
            n_results=5,
            where={"source": "conversation", "session_id": session_id}
        )
        
        return [
            {
                "pattern": doc,
                "metadata": meta
            }
            for doc, meta in zip(results['documents'][0], results['metadatas'][0])
        ]