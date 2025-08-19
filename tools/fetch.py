import csv
import json
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import logging
import re
import html
import urllib3
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
import sys
import os

# Add parent directory to path to import db module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.db import DB

# SSL warning disable
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationFetcher:
    def __init__(self, db_path="db/notice.db", delay=1.0):
        """Crawling and duplicate check class"""
        self.db = DB(db_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        self.delay = delay
    
    def __del__(self):
        if hasattr(self, 'db'):
            del self.db
    
    def scrape_url(self, url, title, link_selector):
        """Extract links and text from single URL (based on csv_link_scraper.py)"""
        try:
            logger.info(f"Scraping: {url}")
            response = self.session.get(url, timeout=30, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
                      
            if url == "https://materials.ssu.ac.kr/bbs/board.php?tbl=bbs51":
                # materials.ssu.ac.kr specific handling
                try:
                    news_items = soup.select('.news-list ul li')
                    for item in news_items[:10]:
                        link_element = item.select_one('a')
                        if link_element and link_element.get('href'):
                            href = link_element.get('href')
                            full_url = urljoin(url, href)
                            
                            title_element = item.select_one('.tit_box strong')
                            if title_element:
                                title_text = title_element.get_text(strip=True)
                                for span in title_element.select('span'):
                                    span.decompose()
                                title_text = title_element.get_text(strip=True)
                                
                                if title_text and len(title_text) > 3:
                                    links.append({
                                        'text': title_text,
                                        'url': full_url
                                    })
                except Exception as e:
                    logger.error(f"Error parsing materials.ssu.ac.kr: {str(e)}")
                      
            elif url == "http://media.ssu.ac.kr/sub.php?code=XxH00AXY&category=1":
                found_links = soup.select(link_selector)
                for link in found_links[:10]:
                    href = link.get('onclick')
                    if href:
                        match = re.search(r"viewData\('(\d+)'\)", href)
                        text = link.get_text(strip=True)

                        if match and text and len(text) > 3:
                            full_url = f"http://media.ssu.ac.kr/sub.php?code=XxH00AXY&mode=view&board_num={match.group(1)}&category=1"
                            links.append({
                                'text': text,
                                'url': full_url
                            })
                        
            elif url.startswith("http://ssfilm.ssu.ac.kr/notice/notice_list"):
                try:
                    json_data = response.json()
                    if 'data_list' in json_data:
                        for item in json_data['data_list'][:10]:
                            title_text = item.get('Title', '').strip()
                            notice_index = item.get('NoticeIndex', '')
                            if title_text and notice_index:
                                detail_url = f"http://ssfilm.ssu.ac.kr/notice/notice_view/{notice_index}"
                                links.append({
                                    'text': title_text,
                                    'url': detail_url
                                })
                except:
                    pass
                        
            elif url == "https://api.mediamba.ssu.ac.kr/v1/board/?page=0&size=15&menuId=89&content=":
                try:
                    json_data = response.json()
                    if json_data.get('success') and 'data' in json_data and 'boards' in json_data['data']:
                        for item in json_data['data']['boards'][:10]:
                            title_text = item.get('title', '').strip()
                            board_id = item.get('id', '')
                            if title_text and board_id:
                                detail_url = f"https://mediamba.ssu.ac.kr/board/notice/{board_id}"
                                links.append({
                                    'text': title_text,
                                    'url': detail_url
                                })
                except:
                    pass
                
            else:
                # Use link_selector specified in CSV
                if link_selector and link_selector.strip():
                    found_links = soup.select(link_selector)
                    if found_links:
                        for link in found_links[:10]:
                            href = link.get('href')
                            text = link.get_text(strip=True)
                            
                            if href and text and len(text) > 3:
                                full_url = urljoin(url, href)
                                links.append({
                                    'text': text,
                                    'url': full_url
                                })
            
            return links[:10]
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return []
    
    def get_new_notifications(self, notification_id: int) -> List[Dict[str, Any]]:
        """Return only new uncrawled links for specific notification"""
        try:
            # Get notification info from notificationList
            notification_info = self.db.get_notification_info(notification_id)
            if not notification_info:
                logger.error(f"Notification ID {notification_id} not found.")
                return []
            
            title = notification_info['title']
            url = notification_info['url']
            link_selector = notification_info['link_selector']
            
            # Get existing crawled links
            existing_links = self.db.get_existing_links(notification_id)
            
            # URL scraping
            scraped_links = self.scrape_url(url, title, link_selector)
            
            # Filter only new links
            new_links = []
            for link_data in scraped_links:
                link_url = link_data['url']
                if link_url not in existing_links:
                    new_links.append({
                        'title': link_data['text'],
                        'link': link_url,
                        'notification_id': notification_id,
                        'category_title': title
                    })
            
            logger.info(f"{title}: Found {len(new_links)} new links out of {len(scraped_links)} total links")
            return new_links
            
        except Exception as e:
            logger.error(f"Get new notifications failed (notification_id: {notification_id}): {e}")
            return []
    
    def get_all_new_notifications(self) -> Dict[int, List[Dict[str, Any]]]:
        """Return new uncrawled links from all notifications"""
        cursor = self.db.conn.cursor()
        
        try:
            # Get all notification IDs
            cursor.execute('SELECT id FROM notificationList ORDER BY id')
            notification_ids = [row[0] for row in cursor.fetchall()]
            
            all_new_notifications = {}
            
            for notification_id in notification_ids:
                new_links = self.get_new_notifications(notification_id)
                if new_links:
                    all_new_notifications[notification_id] = new_links
                
                # Delay between requests
                time.sleep(self.delay)
            
            total_new = sum(len(links) for links in all_new_notifications.values())
            logger.info(f"Total: Found {total_new} new links from {len(notification_ids)} notifications")
            
            return all_new_notifications
            
        except Exception as e:
            logger.error(f"Get all new notifications failed: {e}")
            return {}
    
    def save_new_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save new notification to DB"""
        try:
            program_data = {
                'program_link': notification_data['link'],
                'title': notification_data['title'],
                'crawl_timestamp': None,  # Auto generated by DB
                'raw_html': None,
                'ai_json_data': None
            }
            
            return self.db.save_program_to_db(notification_data['notification_id'], program_data)
            
        except Exception as e:
            logger.error(f"Save notification failed: {e}")
            return {"code": -1, "message": str(e)}

def main():
    """Test main function"""
    fetcher = NotificationFetcher(delay=1.0)
    
    try:
        # Get new links for specific notification (e.g., ID 1)
        print("=== Get new links for specific notification (ID: 1) ===")
        new_links = fetcher.get_new_notifications(1)
        print(f"Found {len(new_links)} new links:")
        for link in new_links[:3]:  # Show first 3 only
            print(f"  - {link['title']}: {link['link']}")
        
        print("\n=== Get new links for all notifications (first 3 notifications only) ===")
        all_new = fetcher.get_all_new_notifications()
        count = 0
        for notification_id, links in all_new.items():
            if count >= 3:  # First 3 notifications only
                break
            print(f"\nNotification ID {notification_id}: {len(links)} new links")
            for link in links[:2]:  # Show 2 each
                print(f"  - {link['title']}: {link['link']}")
            count += 1
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()