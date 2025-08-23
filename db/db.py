import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Optional, Any
import json

class DB:

    def __init__(self, path: str = "./notice.db"):
        """SQLite database initialization (Crawler & Email)"""
        self.main_logger = self._setup_logger(__name__)
        
        self.db_path = Path(path)
        self.conn = self._config_data_based(self.db_path)
    
    def __del__(self):
        self.conn.close()
    
    def _setup_logger(self, name):
        logger = logging.getLogger(name)
        
        if not logger.handlers:
            handler = logging.FileHandler('app.log', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.info("New logger created and configured")
        
        return logger
    
    def _config_data_based(self, path: str = "./db/notice.db"):
        """SQLite database connection"""
        self.db_path = Path(path)
        conn = sqlite3.connect(self.db_path, autocommit= True)
        cursor = conn.cursor()
        
        # main.notificationList table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notificationList (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                login INTEGER NOT NULL DEFAULT 0,
                display_type TEXT DEFAULT 'button',
                college TEXT DEFAULT NULL,
                department TEXT DEFAULT NULL,
                major TEXT DEFAULT NULL,
                description TEXT DEFAULT NULL,
                link_selector TEXT DEFAULT NULL,
                content_selector TEXT DEFAULT NULL
            )
        ''')
        
        # Email sending log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id INTEGER NOT NULL,
                sent_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                recipient_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                error_message TEXT DEFAULT NULL,
                FOREIGN KEY (notification_id) REFERENCES notificationList(id)
            )
        ''')
        
        return conn
    
    def save_program_to_db(self, notification_id, program: Dict[str, Any]):
        """Save program info to SQLite database"""
        cursor = self.conn.cursor()
        
        self._create_notification_data_table(notification_id)
        try:
            cursor.execute(f'''
                    INSERT INTO notification_data_{notification_id} 
                    (link, crawl_timestamp, title, raw_html, ai_json_data) 
                    VALUES (?, ?, ?, ?, ?)
            ''', (
                program.get('program_link'),
                program.get('crawl_timestamp', 'null'),
                program.get('title', 'null'),
                program.get('raw_html', 'null'),
                json.dumps(program.get('ai_json_data', 'null'), ensure_ascii=False, indent=2) if isinstance(program.get('ai_json_data', 'null'), dict) else str(program.get('ai_json_data', 'null'))
            ))
            return {"code" : 1}
        except:
            return {"code" : -1}

    def _create_notification_data_table(self, notification_id, cursor=None):
        cursor = self.conn.cursor()
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS notification_data_{notification_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL,
                crawl_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                title TEXT NOT NULL,
                raw_html TEXT,
                ai_json_data TEXT
            )
        ''')
    
    def get_notification_id_url(self) -> List[int]:
        """Get all notification ID, url list"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('SELECT id, url FROM notificationList')
            return cursor.fetchall()
        except Exception as e:
            self.main_logger.error(f"Get notification ID list failed: {e}")
            return []
    
    def get_unsent_notifications(self, notification_id: int, from_time: str = None, to_time: str = None) -> List[Dict[str, Any]]:
        """Get notification data added after specified time range (based on email_log)"""
        cursor = self.conn.cursor()
        
        try:
            # Check table existence
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (f'notification_data_{notification_id}',))
            if not cursor.fetchone():
                return []
            
            # Get last send time
            if not from_time:
                cursor.execute('''
                    SELECT MAX(sent_timestamp) 
                    FROM email_log 
                    WHERE notification_id = ? AND status = 'success'
                ''', (notification_id,))
                result = cursor.fetchone()
                last_sent_time = result[0] if result and result[0] else '1970-01-01 00:00:00'
            else:
                last_sent_time = from_time
            query = f'''
                SELECT id, link, title, crawl_timestamp, ai_json_data
                FROM notification_data_{notification_id}
                WHERE crawl_timestamp > ?
            '''
            params = [last_sent_time]
            
            if to_time:
                query += ' AND crawl_timestamp <= ?'
                params.append(to_time)
            
            query += ' ORDER BY crawl_timestamp DESC'
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            notifications = []
            for row in results:
                notifications.append({
                    'id': row[0],
                    'link': row[1],
                    'title': row[2],
                    'crawl_timestamp': row[3],
                    'ai_json_data': json.loads(row[4]) if row[4] else None
                })
            
            return notifications
            
        except Exception as e:
            self.main_logger.error(f"Get unsent notifications failed: {e}")
            return []
    
    def log_email_send(self, notification_id: int, recipient_count: int, status: str = 'success', error_message: str = None) -> Dict[str, Any]:
        """Save email sending log"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO email_log (notification_id, recipient_count, status, error_message)
                VALUES (?, ?, ?, ?)
            ''', (notification_id, recipient_count, status, error_message))
            
            return {"code": 1, "message": "Email send log saved successfully"}
        except Exception as e:
            self.main_logger.error(f"Save email send log failed: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_email_stats(self, days: int = 7) -> Dict[str, Any]:
        """Email sending statistics"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_sends,
                    SUM(recipient_count) as total_recipients,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_sends,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_sends
                FROM email_log
                WHERE sent_timestamp >= datetime('now', '-' || ? || ' days')
            ''', (days,))
            
            result = cursor.fetchone()
            
            return {
                'total_sends': result[0] or 0,
                'total_recipients': result[1] or 0,
                'successful_sends': result[2] or 0,
                'failed_sends': result[3] or 0,
                'success_rate': (result[2] / result[0] * 100) if result[0] > 0 else 0
            }
            
        except Exception as e:
            self.main_logger.error(f"Email stats query failed: {e}")
            return {
                'total_sends': 0,
                'total_recipients': 0,
                'successful_sends': 0,
                'failed_sends': 0,
                'success_rate': 0
            }
    
    def get_existing_links(self, notification_id: int) -> set:
        """Get existing crawled links from DB"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
                          (f'notification_data_{notification_id}',))
            if not cursor.fetchone():
                return set()
            
            cursor.execute(f'SELECT link FROM notification_data_{notification_id}')
            existing_links = cursor.fetchall()
            return {link[0] for link in existing_links}
            
        except Exception as e:
            self.main_logger.error(f"Get existing links failed (notification_id: {notification_id}): {e}")
            return set()
    
    def get_notification_info(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Get notification info from notificationList"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT title, url, link_selector, content_selector 
                FROM notificationList 
                WHERE id = ?
            ''', (notification_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'title': result[0],
                    'url': result[1], 
                    'link_selector': result[2],
                    'content_selector': result[3]
                }
            return None
            
        except Exception as e:
            self.main_logger.error(f"Get notification info failed (notification_id: {notification_id}): {e}")
            return None

    def get_all_ids(self) -> List[int]:
        """Return all notification IDs"""
        cursor = self.conn.cursor()
        
        try:
            # Get all notification IDs
            cursor.execute('SELECT id FROM notificationList ORDER BY id')
            notification_ids = [row[0] for row in cursor.fetchall()]
            
            return notification_ids
            
        except Exception as e:
            self.main_logger.error(f"Get all notification IDs failed: {e}")
            return []