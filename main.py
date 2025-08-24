from tools.fetch import NotificationFetcher
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
import logging

logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.FileHandler('app.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.info("New logger created and configured-main")

def fetch_single_content(fetcher, notification):
    """단일 notification의 content를 가져오는 함수"""
    try:
        content_data = fetcher.fetch_content(notification, notification.get('content_selector'))
        content_data['notification_id'] = notification['notification_id']
        content_data['category'] = notification['category_title']
        return content_data
    except Exception as e:
        logger.error(f"Error fetching content for {notification.get('title', 'Unknown')}: {e}")
        return {
            'title': notification.get('title', ''),
            'url': notification.get('link', ''),
            'content': '',
            'fetch_success': False,
            'error': str(e),
            'notification_id': notification['notification_id'],
            'category': notification['category_title']
        }

def process_ai_summary(content_data):
    """AI 요약 처리 함수 (나중에 구현)"""
    # TODO: AI 요약 API 호출 구현
    # AI에게 전달할 데이터:  ['content'] (HTML), content_data['url'] (이미지 처리용)
    content_data['ai_summary'] = None  # 나중에 구현
    return content_data

def main():
    fetcher = NotificationFetcher()
    
    # 1단계: 모든 notification 링크 수집
    logger.info("수집 중인 notification 링크들...")
    all_notifications = []
    ids = fetcher.get_all_ids()
    
    for notification_id in ids:
        new_notifications = fetcher.get_new_notifications(notification_id)
        all_notifications.extend(new_notifications)
    
    logger.info(f"총 {len(all_notifications)}개의 새로운 알림을 찾았습니다.")
    
    if not all_notifications:
        logger.info("새로운 알림이 없습니다.")
        return
    
    # 2단계: Content 병렬 크롤링
    logger.info("Content 병렬 크롤링 시작...")
    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        # 모든 content 크롤링 작업 제출
        future_to_notification = {
            executor.submit(fetch_single_content, fetcher, notification): notification
            for notification in all_notifications
        }
        
        # 완료된 작업들 처리
        for future in as_completed(future_to_notification):
            try:
                result = future.result()
                results.append(result)
                logger.info(f"완료: {result['title'][:50]}...")
            except Exception as e:
                logger.error(f"Content 크롤링 실패: {e}")
    
    # 3단계: AI 요약
    logger.info("AI 요약 준비 중...")
    final_results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # AI 요약 작업들 제출
        future_to_content = {
            executor.submit(process_ai_summary, content): content
            for content in results if content['fetch_success']
        }
        
        # 완료된 작업들 처리
        for future in as_completed(future_to_content):
            try:
                result = future.result()
                final_results.append(result)
            except Exception as e:
                logger.error(f"AI 요약 실패: {e}")
    
    # 결과 저장
    output = {
        "success": True,
        "count": len(final_results),
        "notifications": final_results
    }
    
    # database.save_notifications(final_results)
    
    with open("notifications_with_content.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"완료! {len(final_results)}개 알림이 저장되었습니다.")

if __name__ == "__main__":
    main()