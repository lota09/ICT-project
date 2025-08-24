import sqlite3
import csv
import os
from pathlib import Path

def import_csv_to_db(csv_path="../test/notificationList.csv", db_path="../db/notice.db"):
    """CSV 파일을 SQLite 데이터베이스로 가져오기"""
    
    # DB 경로 설정
    db_path = Path(db_path)
    
    # 기존 DB 파일 삭제 (새로 생성)
    if db_path.exists():
        print(f"기존 DB 파일 삭제: {db_path}")
        db_path.unlink()
    
    # DB 연결 및 테이블 생성
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # notificationList 테이블 생성 (새로운 스키마)
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
    
    # user 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            subscribe TEXT DEFAULT ''
        )
    ''')
    
    # user_subscriptions 테이블 생성
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
    
    # email_log 테이블 생성
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
    
    # CSV 파일에서 데이터 읽기
    if not os.path.exists(csv_path):
        print(f"오류: CSV 파일을 찾을 수 없습니다: {csv_path}")
        return
    
    print(f"CSV 파일 읽기: {csv_path}")
    
    # 여러 인코딩 시도
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'latin-1']
    csvfile = None
    
    for encoding in encodings:
        try:
            csvfile = open(csv_path, 'r', encoding=encoding)
            csv_reader = csv.DictReader(csvfile)
            # 첫 번째 행을 읽어서 인코딩이 올바른지 확인
            first_row = next(csv_reader)
            csvfile.seek(0)  # 파일 포인터를 처음으로 되돌림
            csv_reader = csv.DictReader(csvfile)
            print(f"성공한 인코딩: {encoding}")
            break
        except (UnicodeDecodeError, StopIteration) as e:
            if csvfile:
                csvfile.close()
            print(f"{encoding} 인코딩 실패: {e}")
            continue
    else:
        print("모든 인코딩 시도 실패")
        return
    
    try:
        
        # 데이터 삽입 카운터
        insert_count = 0
        
        for row in csv_reader:
            try:
                # CSV의 id는 무시하고 AUTOINCREMENT 사용
                cursor.execute('''
                    INSERT INTO notificationList 
                    (title, url, login, display_type, college, department, major, description, link_selector, content_selector)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['title'],
                    row['url'],
                    int(row['login']) if row['login'].isdigit() else 0,
                    row['display_type'],
                    row['college'] if row['college'] else None,
                    row['department'] if row['department'] else None,
                    row['major'] if row['major'] else None,
                    row['description'] if row['description'] else None,
                    row['link_selector'] if row['link_selector'] else None,
                    row['content_selector'] if row['content_selector'] else None
                ))
                insert_count += 1
            except Exception as e:
                print(f"행 삽입 오류: {e}")
                print(f"문제 행: {row}")
                continue
    
    finally:
        if csvfile:
            csvfile.close()
    
    # 변경사항 저장
    conn.commit()
    
    # 삽입된 데이터 확인
    cursor.execute('SELECT COUNT(*) FROM notificationList')
    total_count = cursor.fetchone()[0]
    
    print(f"성공적으로 {insert_count}개 행이 DB에 삽입되었습니다.")
    print(f"DB 총 레코드 수: {total_count}")
    
    # 일부 데이터 확인
    print("\n첫 5개 레코드:")
    cursor.execute('SELECT id, title, display_type, college, department FROM notificationList LIMIT 5')
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Title: {row[1]}, Type: {row[2]}, College: {row[3]}, Dept: {row[4]}")
    
    conn.close()
    print(f"\n데이터베이스 파일 생성 완료: {db_path}")

if __name__ == "__main__":
    import_csv_to_db()