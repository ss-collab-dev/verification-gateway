#!/usr/bin/env python3
"""
Receipt Database - SQLite storage for verification receipts.

Provides persistent storage with indexing by:
- receipt_id (primary key)
- intent_hash
- timestamp
- verification_status

Supports search and query operations for audit trails.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


class ReceiptDatabase:
    """SQLite database for receipt storage and retrieval."""
    
    VERSION = "1.0.0"
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize receipt database.
        
        Args:
            db_path: Path to SQLite database file.
                    Defaults to receipts.db in module directory.
        """
        if db_path is None:
            db_dir = Path(__file__).parent
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / 'receipts.db')
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create receipts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                intent_hash TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT,
                executor_id TEXT,
                verification_status TEXT NOT NULL,
                confidence REAL,
                signature_algorithm TEXT,
                signature_value TEXT NOT NULL,
                full_receipt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Create indexes for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_intent_hash 
            ON receipts(intent_hash)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON receipts(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_verification_status 
            ON receipts(verification_status)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_executor_id 
            ON receipts(executor_id)
        ''')
        
        # Create metadata table for schema versioning
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS db_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # Store schema version
        cursor.execute('''
            INSERT OR REPLACE INTO db_metadata (key, value)
            VALUES ('schema_version', ?)
        ''', ('1.0.0',))
        
        conn.commit()
        conn.close()
    
    def store_receipt(self, receipt: Any) -> str:
        """
        Store a receipt in the database.
        
        Args:
            receipt: Receipt object from ReceiptGenerator
            
        Returns:
            receipt_id of stored receipt
        """
        from dataclasses import asdict
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        receipt_dict = asdict(receipt)
        
        # Extract fields for indexed columns
        receipt_id = receipt_dict['receipt_id']
        timestamp = receipt_dict['timestamp']
        intent_hash = receipt_dict['intent_hash']
        
        action_type = receipt_dict['action_taken'].get('action_type', 'unknown')
        target = receipt_dict['action_taken'].get('target', '')
        executor_id = receipt_dict['action_taken'].get('executor_id', 'unknown')
        
        verification_status = receipt_dict['verification_result'].get('status', 'UNVERIFIED')
        confidence = receipt_dict['verification_result'].get('confidence', 0.0)
        
        signature_algorithm = receipt_dict['signature'].get('algorithm', 'unknown')
        signature_value = receipt_dict['signature'].get('value', '')
        
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Store full receipt as JSON
        full_receipt_json = json.dumps(receipt_dict)
        
        cursor.execute('''
            INSERT OR REPLACE INTO receipts 
            (receipt_id, version, timestamp, intent_hash, action_type, target,
             executor_id, verification_status, confidence, signature_algorithm,
             signature_value, full_receipt, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            receipt_id,
            receipt_dict['version'],
            timestamp,
            intent_hash,
            action_type,
            target,
            executor_id,
            verification_status,
            confidence,
            signature_algorithm,
            signature_value,
            full_receipt_json,
            created_at
        ))
        
        conn.commit()
        conn.close()
        
        return receipt_id
    
    def get_receipt(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a receipt by ID.
        
        Args:
            receipt_id: UUID of receipt to retrieve
            
        Returns:
            Receipt dict or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            WHERE receipt_id = ?
        ''', (receipt_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def get_receipts_by_intent(self, intent_hash: str) -> List[Dict[str, Any]]:
        """
        Get all receipts for a specific intent hash.
        
        Args:
            intent_hash: SHA-256 hash of the intent
            
        Returns:
            List of receipt dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            WHERE intent_hash = ?
            ORDER BY timestamp DESC
        ''', (intent_hash,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]
    
    def get_receipts_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get receipts by verification status.
        
        Args:
            status: PASS, FAIL, PARTIAL, or UNVERIFIED
            limit: Maximum number of receipts to return
            
        Returns:
            List of receipt dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            WHERE verification_status = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (status, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]
    
    def get_receipts_by_executor(self, executor_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get receipts by executor ID.
        
        Args:
            executor_id: Agent/executor identifier
            limit: Maximum number of receipts to return
            
        Returns:
            List of receipt dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            WHERE executor_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (executor_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]
    
    def get_recent_receipts(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent receipts within time window.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of receipts to return
            
        Returns:
            List of receipt dicts
        """
        from datetime import timedelta
        
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (cutoff, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]
    
    def search_receipts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Full-text search across receipts.
        
        Searches in: action_type, target, executor_id, verification_status
        
        Args:
            query: Search term
            limit: Maximum results to return
            
        Returns:
            List of matching receipt dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            WHERE action_type LIKE ?
               OR target LIKE ?
               OR executor_id LIKE ?
               OR verification_status LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (search_pattern, search_pattern, search_pattern, search_pattern, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with counts and metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total count
        cursor.execute('SELECT COUNT(*) FROM receipts')
        total = cursor.fetchone()[0]
        
        # Count by status
        cursor.execute('''
            SELECT verification_status, COUNT(*) 
            FROM receipts 
            GROUP BY verification_status
        ''')
        by_status = dict(cursor.fetchall())
        
        # Count by executor
        cursor.execute('''
            SELECT executor_id, COUNT(*) 
            FROM receipts 
            GROUP BY executor_id
            ORDER BY COUNT(*) DESC
            LIMIT 10
        ''')
        by_executor = dict(cursor.fetchall())
        
        # Recent activity (last 24h)
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM receipts
            WHERE timestamp >= ?
        ''', (cutoff,))
        last_24h = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_receipts': total,
            'by_status': by_status,
            'top_executors': by_executor,
            'last_24_hours': last_24h,
            'database_path': self.db_path
        }
    
    def delete_receipt(self, receipt_id: str) -> bool:
        """
        Delete a receipt by ID.
        
        Args:
            receipt_id: UUID of receipt to delete
            
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM receipts WHERE receipt_id = ?
        ''', (receipt_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def export_all(self) -> List[Dict[str, Any]]:
        """
        Export all receipts for backup or audit.
        
        Returns:
            List of all receipt dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_receipt FROM receipts
            ORDER BY timestamp DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]


# Convenience functions
def init_db(db_path: Optional[str] = None) -> ReceiptDatabase:
    """Initialize and return a ReceiptDatabase instance."""
    return ReceiptDatabase(db_path)


def store_receipt(receipt, db_path: Optional[str] = None) -> str:
    """Store a receipt in the database."""
    db = ReceiptDatabase(db_path)
    return db.store_receipt(receipt)


def get_receipt(receipt_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a receipt by ID."""
    db = ReceiptDatabase(db_path)
    return db.get_receipt(receipt_id)


if __name__ == '__main__':
    print("=" * 60)
    print("RECEIPT DATABASE DEMO")
    print("=" * 60)
    
    # Initialize database
    db = ReceiptDatabase()
    print(f"\n✅ Database initialized at: {db.db_path}")
    
    # Show statistics
    stats = db.get_statistics()
    print(f"\n📊 Database Statistics:")
    print(f"   Total receipts: {stats['total_receipts']}")
    print(f"   Last 24 hours: {stats['last_24_hours']}")
    print(f"   By status: {stats['by_status']}")
    
    print("\n✅ Receipt database ready!")
