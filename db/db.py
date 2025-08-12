import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Optional, Any
import json

class DB:

    def __init__(self, path: str = "./notice.db"):
        """SQLite 데이터베이스 초기화 (Crawler & Email 전용)"""
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
            logger.info("새 로거 생성 및 설정 완료")
        
        return logger
    
    def _config_data_based(self, path: str = "./db/notice.db"):
        """SQLite 데이터베이스 연결"""
        self.db_path = Path(path)
        conn = sqlite3.connect(self.db_path, autocommit= True)
        cursor = conn.cursor()
        
        # main.notificationList 테이블
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
                description TEXT DEFAULT NULL
            )
        ''')
        
        # 이메일 전송 기록 테이블
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
        """프로그램 정보를 SQLite 데이터베이스에 저장"""
        cursor = self.conn.cursor()
        
        self._create_notification_data_table(notification_id)
        try:
            # 프로그램 정보 삽입
            cursor.execute(f'''
                    INSERT INTO notification_data_{notification_id} 
                    (id, link, crawl_timestamp, title, crawl_seq, raw_html, ai_json_data) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                program.get('id'),
                program.get('program_link'),
                program.get('crawl_timestamp', 'null'),
                program.get('title', 'null'),
                program.get('crawl_seq', 1),
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
                id INTEGER PRIMARY KEY,
                link TEXT NOT NULL,
                crawl_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                title TEXT NOT NULL,
                crawl_seq INTEGER,
                raw_html TEXT,
                ai_json_data TEXT,
                sent INTEGER DEFAULT 0
            )
        ''')
    
    def get_notification_ids(self) -> List[int]:
        """모든 공지사항 ID 목록 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('SELECT id FROM notificationList')
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.main_logger.error(f"공지사항 ID 목록 조회 실패: {e}")
            return []
    
    def get_unsent_notifications(self, notification_id: int, from_time: str = None, to_time: str = None) -> List[Dict[str, Any]]:
        """아직 전송되지 않은 공지사항 데이터 조회"""
        cursor = self.conn.cursor()
        
        try:
            # 테이블 존재 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (f'notification_data_{notification_id}',))
            if not cursor.fetchone():
                return []
            
            query = f'''
                SELECT id, link, title, crawl_timestamp, ai_json_data
                FROM notification_data_{notification_id}
                WHERE sent = 0
            '''
            params = []
            
            if from_time and to_time:
                query += ' AND crawl_timestamp BETWEEN ? AND ?'
                params.extend([from_time, to_time])
            
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
            self.main_logger.error(f"미전송 공지사항 조회 실패: {e}")
            return []
    
    def mark_as_sent(self, notification_id: int, data_ids: List[int]) -> Dict[str, Any]:
        """공지사항 데이터를 전송 완료로 표시"""
        cursor = self.conn.cursor()
        
        try:
            if not data_ids:
                return {"code": 1, "message": "표시할 데이터가 없습니다"}
            
            placeholders = ','.join('?' * len(data_ids))
            cursor.execute(f'''
                UPDATE notification_data_{notification_id}
                SET sent = 1
                WHERE id IN ({placeholders})
            ''', data_ids)
            
            return {"code": 1, "message": f"{len(data_ids)}개 데이터 전송 완료 표시"}
        except Exception as e:
            self.main_logger.error(f"전송 완료 표시 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def log_email_send(self, notification_id: int, recipient_count: int, status: str = 'success', error_message: str = None) -> Dict[str, Any]:
        """이메일 전송 기록 저장"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO email_log (notification_id, recipient_count, status, error_message)
                VALUES (?, ?, ?, ?)
            ''', (notification_id, recipient_count, status, error_message))
            
            return {"code": 1, "message": "이메일 전송 기록 저장 성공"}
        except Exception as e:
            self.main_logger.error(f"이메일 전송 기록 저장 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_email_stats(self, days: int = 7) -> Dict[str, Any]:
        """이메일 전송 통계 조회"""
        cursor = self.conn.cursor()
        
        try:
            # 최근 N일 내 전송 통계
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
            self.main_logger.error(f"이메일 통계 조회 실패: {e}")
            return {
                'total_sends': 0,
                'total_recipients': 0,
                'successful_sends': 0,
                'failed_sends': 0,
                'success_rate': 0
            }