import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Optional, Any
import json

class DB:
    def __init__(self, path: str = "./notice.db"):
        """SQLite 데이터베이스 초기화 (Website 전용)"""
        self.main_logger = self._setup_logger(__name__)
        
        self.db_path = Path(path)
        self.conn = self._config_data_based(self.db_path)
    
    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'conn') and self.conn:
            if exc_type is not None:
                self.conn.rollback()
            else:
                self.conn.commit()
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
    
    def _config_data_based(self, path: str = "./notice.db"):
        """SQLite 데이터베이스 연결"""
        self.db_path = Path(path)
        conn = sqlite3.connect(self.db_path)
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
                description TEXT DEFAULT NULL,
                link_selector TEXT DEFAULT NULL,
                content_selector TEXT DEFAULT NULL
            )
        ''')
        
        # main.user 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS  user  (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                subscribe TEXT DEFAULT ''
            )
        ''')
        
        # user_subscriptions 테이블 (새로운 구독 방식)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                user_id TEXT NOT NULL,
                notification_id INTEGER NOT NULL,
                subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                PRIMARY KEY (user_id, notification_id),
                FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
                FOREIGN KEY (notification_id) REFERENCES notificationList(id) ON DELETE CASCADE
            )
        ''')
        
        return conn
    
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
    
    # === 웹사이트 전용 메서드들 ===
    
    def subscribe_user(self, user_id: str, notification_id: int) -> Dict[str, Any]:
        """사용자를 특정 공지사항에 구독"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user_subscriptions (user_id, notification_id, is_active)
                VALUES (?, ?, 1)
            ''', (user_id, notification_id))
            return {"code": 1, "message": "구독 완료"}
        except Exception as e:
            self.main_logger.error(f"구독 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def unsubscribe_user(self, user_id: str, notification_id: int) -> Dict[str, Any]:
        """사용자의 특정 공지사항 구독 해제"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE user_subscriptions 
                SET is_active = 0 
                WHERE user_id = ? AND notification_id = ?
            ''', (user_id, notification_id))
            return {"code": 1, "message": "구독 해제 완료"}
        except Exception as e:
            self.main_logger.error(f"구독 해제 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """사용자의 구독 목록 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT us.notification_id, us.subscribed_at, us.is_active,
                       nl.title, nl.url, nl.display_type, nl.college, nl.department, nl.major
                FROM user_subscriptions us
                JOIN notificationList nl ON us.notification_id = nl.id
                WHERE us.user_id = ? AND us.is_active = 1
                ORDER BY us.subscribed_at DESC
            ''', (user_id,))
            
            results = cursor.fetchall()
            subscriptions = []
            
            for row in results:
                subscriptions.append({
                    'notification_id': row[0],
                    'subscribed_at': row[1],
                    'is_active': bool(row[2]),
                    'title': row[3],
                    'url': row[4],
                    'display_type': row[5],
                    'college': row[6],
                    'department': row[7],
                    'major': row[8]
                })
            
            return subscriptions
        except Exception as e:
            self.main_logger.error(f"구독 목록 조회 실패: {e}")
            return []
    
    def update_user_subscriptions(self, user_id: str, notification_ids: List[int]) -> Dict[str, Any]:
        """사용자의 구독 목록을 일괄 업데이트"""
        cursor = self.conn.cursor()
        
        try:
            # 기존 구독을 모두 비활성화
            cursor.execute('''
                UPDATE user_subscriptions 
                SET is_active = 0 
                WHERE user_id = ?
            ''', (user_id,))
            
            # 새로운 구독 목록 추가/활성화
            for notification_id in notification_ids:
                cursor.execute('''
                    INSERT OR REPLACE INTO user_subscriptions 
                    (user_id, notification_id, is_active, subscribed_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ''', (user_id, notification_id))
            
            return {"code": 1, "message": f"{len(notification_ids)}개 구독 업데이트 완료"}
        except Exception as e:
            self.main_logger.error(f"구독 업데이트 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_notification_subscribers(self, notification_id: int) -> List[Dict[str, Any]]:
        """특정 공지사항의 구독자 목록 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT us.user_id, us.subscribed_at, u.email
                FROM user_subscriptions us
                JOIN user u ON us.user_id = u.id
                WHERE us.notification_id = ? AND us.is_active = 1
                ORDER BY us.subscribed_at DESC
            ''', (notification_id,))
            
            results = cursor.fetchall()
            subscribers = []
            
            for row in results:
                subscribers.append({
                    'user_id': row[0],
                    'subscribed_at': row[1],
                    'email': row[2]
                })
            
            return subscribers
        except Exception as e:
            self.main_logger.error(f"구독자 목록 조회 실패: {e}")
            return []
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """구독 통계 조회"""
        cursor = self.conn.cursor()
        
        try:
            # 전체 구독 수
            cursor.execute('SELECT COUNT(*) FROM user_subscriptions WHERE is_active = 1')
            total_subscriptions = cursor.fetchone()[0]
            
            # 공지사항별 구독자 수
            cursor.execute('''
                SELECT nl.title, COUNT(us.user_id) as subscriber_count
                FROM notificationList nl
                LEFT JOIN user_subscriptions us ON nl.id = us.notification_id AND us.is_active = 1
                GROUP BY nl.id, nl.title
                ORDER BY subscriber_count DESC
            ''')
            
            notification_stats = []
            for row in cursor.fetchall():
                notification_stats.append({
                    'title': row[0],
                    'subscriber_count': row[1]
                })
            
            return {
                'total_subscriptions': total_subscriptions,
                'notification_stats': notification_stats
            }
        except Exception as e:
            self.main_logger.error(f"통계 조회 실패: {e}")
            return {'total_subscriptions': 0, 'notification_stats': []}
    
    def get_user_subscription_ids(self, user_id: str) -> List[int]:
        """사용자의 구독 ID 목록만 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT notification_id 
                FROM user_subscriptions 
                WHERE user_id = ? AND is_active = 1
            ''', (user_id,))
            
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.main_logger.error(f"구독 ID 목록 조회 실패: {e}")
            return []
    
    def get_notification_categories(self):
        """공지사항 카테고리 데이터 조회 (버튼 및 드롭다운)"""
        cursor = self.conn.cursor()
        
        try:
            # 버튼 방식 공지사항
            cursor.execute('''
                SELECT id, title, url, display_type , description
                FROM notificationList 
                WHERE display_type = "button" 
                ORDER BY id
            ''')
            button_notifications = cursor.fetchall()
            
            # 드롭다운 방식 공지사항
            cursor.execute('''
                SELECT id, title, url, college, department, major, display_type
                FROM notificationList 
                WHERE display_type = "dropdown" 
                ORDER BY college, department, major
            ''')
            dropdown_notifications = cursor.fetchall()
            
            # 드롭다운 데이터 구조화
            dropdown_data = {}
            for row in dropdown_notifications:
                id, title, url, college, department, major, display_type = row
                
                if college not in dropdown_data:
                    dropdown_data[college] = {}
                
                if department not in dropdown_data[college]:
                    dropdown_data[college][department] = []
                
                dropdown_data[college][department].append({
                    'id': id,
                    'title': title,
                    'url': url,
                    'major': major
                })
            
            return button_notifications, dropdown_data
        except Exception as e:
            self.main_logger.error(f"카테고리 데이터 조회 실패: {e}")
            return [], {}
    
    def get_user_notifications(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """사용자의 구독 공지사항 데이터 조회"""
        cursor = self.conn.cursor()
        subscribed_ids = self.get_user_subscription_ids(user_id)
        
        if not subscribed_ids:
            return []
        
        notifications = []
        
        try:
            for sub_id in subscribed_ids:
                # 테이블이 존재하는지 확인
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (f'notification_data_{sub_id}',))
                if not cursor.fetchone():
                    self._create_notification_data_table(sub_id)
                    continue
                
                try:
                    cursor.execute(f'''
                        SELECT nd.title, nd.link, nd.crawl_timestamp, nl.title as category
                        FROM notification_data_{sub_id} nd
                        JOIN notificationList nl ON nl.id = {sub_id}
                        ORDER BY nd.crawl_timestamp DESC
                        LIMIT 10
                    ''')
                    
                    for row in cursor.fetchall():
                        notifications.append({
                            'title': row[0],
                            'link': row[1],
                            'timestamp': row[2],
                            'category': row[3]
                        })
                except Exception as table_error:
                    self.main_logger.error(f"테이블 {sub_id} 조회 오류: {table_error}")
                    continue
            
            # 시간순 정렬 후 페이지네이션
            notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return notifications[offset:offset + limit]
            
        except Exception as e:
            self.main_logger.error(f"사용자 공지사항 조회 실패: {e}")
            return []
    
    def register_user(self, user_id: str, email: str) -> Dict[str, Any]:
        """사용자 등록/업데이트"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user (id, email, subscribe) 
                VALUES (?, ?, COALESCE((SELECT subscribe FROM user WHERE id = ?), ''))
            ''', (user_id, email, user_id))
            return {"code": 1, "message": "사용자 등록 성공"}
        except Exception as e:
            self.main_logger.error(f"사용자 등록 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """사용자 삭제"""
        cursor = self.conn.cursor()
        
        try:
            # 사용자 데이터 삭제
            cursor.execute('DELETE FROM user WHERE id = ?', (user_id,))
            
            if cursor.rowcount == 0:
                return {"code": -1, "message": "사용자를 찾을 수 없습니다"}
            
            return {"code": 1, "message": "사용자 삭제 성공"}
        except Exception as e:
            self.main_logger.error(f"사용자 삭제 실패: {e}")
            return {"code": -1, "message": str(e)}