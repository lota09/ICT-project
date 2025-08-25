from tools.fetch import NotificationFetcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logging_config import setup_logger
import json
import time
from urllib.parse import urlparse
from collections import defaultdict

logger = setup_logger()

class ContentCrawler:
    """콘텐츠 크롤링을 담당하는 클래스"""
    
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.fast_domains = {'scatch.ssu.ac.kr'}
        
    def categorize_notifications(self, all_notifications):
        """알림을 빠른 처리/그룹 처리로 분류"""
        domain_groups = defaultdict(list)
        fast_notifications = []
        
        for notification in all_notifications:
            domain = urlparse(notification['link']).netloc
            if domain in self.fast_domains:
                fast_notifications.append(notification)
            else:
                domain_groups[domain].append(notification)
                
        return domain_groups, fast_notifications
    
    def fetch_with_retry(self, notification, fast_mode=False):
        """재시도 로직이 포함된 단일 알림 처리"""
        max_retries = 2
        retry_delay = 0.5 if fast_mode else 1.0
        mode_label = "빠른처리" if fast_mode else "그룹처리"
        
        for attempt in range(max_retries + 1):
            content_data = self.fetcher.fetch_content(notification, notification.get('content_selector'))
            content_data['notification_id'] = notification['notification_id']
            content_data['category'] = notification['category_title']
            
            if content_data['fetch_success']:
                return content_data
            else:
                if attempt < max_retries:
                    logger.warning(f"[{mode_label}] 재시도 {attempt + 1}/{max_retries}: {notification.get('title', 'Unknown')[:30]}...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"[{mode_label}] 최종 실패: {notification.get('title', 'Unknown')}: {content_data.get('error', 'Unknown error')}")
        
        return content_data
    
    def process_domain_group(self, domain, notifications):
        """특정 도메인의 알림들을 순차적으로 처리"""
        domain_results = []
        for notification in notifications:
            content_data = self.fetch_with_retry(notification, fast_mode=False)
            domain_results.append(content_data)
            if content_data['fetch_success']:
                logger.info(f"[{domain}] 완료: {content_data['title'][:30]}...")
        return domain_results
    
    def crawl_all_content(self, all_notifications):
        """모든 알림의 콘텐츠를 크롤링"""
        domain_groups, fast_notifications = self.categorize_notifications(all_notifications)
        
        logger.info(f"빠른 처리: {len(fast_notifications)}개, 그룹 처리: {len(domain_groups)}개 도메인")
        logger.info(f"그룹 도메인: {list(domain_groups.keys())}")
        
        # Worker 수 계산
        fast_workers = min(20, len(fast_notifications)) if fast_notifications else 0
        max_workers = max(1, len(domain_groups) + fast_workers)
        logger.info(f"Worker 수: 그룹({len(domain_groups)}) + 빠른처리({fast_workers}) = {max_workers}")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # 빠른 처리 도메인들 (병렬 처리)
            for notification in fast_notifications:
                future = executor.submit(self.fetch_with_retry, notification, fast_mode=True)
                futures.append(('fast', future, notification))
            
            # 그룹 처리 도메인들 (도메인별 순차)
            for domain, notifications in domain_groups.items():
                future = executor.submit(self.process_domain_group, domain, notifications)
                futures.append(('group', future, domain))
            
            # 완료된 작업들 처리
            for task_type, future, task_info in futures:
                try:
                    if task_type == 'fast':
                        result = future.result()
                        results.append(result)
                        logger.info(f"[빠른처리] 완료: {result['title'][:30]}...")
                    else:  # group
                        domain_results = future.result()
                        results.extend(domain_results)
                        logger.info(f"[{task_info}] 도메인 완료: {len(domain_results)}개")
                except Exception as e:
                    logger.error(f"크롤링 실패 ({task_type}): {e}")
        
        return results

class Email:
    def __init__(self):
        password = os.getenv('EMAIL_PASSWORD')
        sender_email = "abc@gmail.com"
        receiver_emails = state.get('receiver_emails')

def process_ai_summary(content_data):
    """AI 요약 처리 함수 (나중에 구현)"""
    # TODO: AI 요약 API 호출 구현
    # AI에게 전달할 데이터:  ['content'] (HTML), content_data['url'] (이미지 처리용)
    content_data['ai_summary'] = None  # 나중에 구현
    return content_data

def main():
    fetcher = NotificationFetcher()
    crawler = ContentCrawler(fetcher)
    
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
    
    # 2단계: Content 크롤링
    logger.info("Content 크롤링 시작...")
    results = crawler.crawl_all_content(all_notifications)
    
    # 3단계: AI 요약
    logger.info("AI 요약 준비 중...")
    final_results = []
    
    with ThreadPoolExecutor(max_workers=1) as executor:
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
    
    # for notification in final_results:
    #     fetcher.save_new_notification(notification)

    with open("notifications_with_content.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"완료! {len(final_results)}개 알림이 저장되었습니다.")

if __name__ == "__main__":
    import time
    start = time.time()
    main()
    end = time.time()
    logger.info(f"총 실행 시간: {end - start:.2f}초")