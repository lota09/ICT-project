#!/usr/bin/env python3
"""
Description 필드가 제대로 저장되었는지 확인
"""

import sqlite3
from pathlib import Path

def test_description_field():
    """Description 필드 테스트"""
    db_path = Path("./db/notice.db")
    
    if not db_path.exists():
        print("Database not found!")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("=== Testing Description Field ===")
            
            # 버튼 타입의 공지사항들 중 description이 있는 것들 확인
            cursor.execute('''
                SELECT id, title, display_type, description 
                FROM notificationList 
                WHERE display_type = "button" AND description IS NOT NULL
                ORDER BY id
            ''')
            
            button_results = cursor.fetchall()
            print(f"\nButton notifications with description: {len(button_results)}")
            
            for row in button_results:
                id, title, display_type, description = row
                print(f"ID {id}: {title}")
                print(f"  Description: {description[:100]}...")
                print()
            
            # 전체 통계
            cursor.execute('SELECT COUNT(*) FROM notificationList WHERE description IS NOT NULL')
            total_with_desc = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM notificationList')
            total = cursor.fetchone()[0]
            
            print(f"Total notifications: {total}")
            print(f"With description: {total_with_desc}")
            print(f"Without description: {total - total_with_desc}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_description_field()