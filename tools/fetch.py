import csv
import json
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
import html
import urllib3
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
import sys
import os
import hashlib
from urllib.parse import unquote

# Add parent directory to path to import db module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.db import CrawlerDB
from utils.logging_config import setup_logger

# SSL warning disable
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NotificationFetcher:
    def __init__(self, db_path="db/notice.db", delay=1.0):
        """Crawling and duplicate check class"""
        self.main_logger = setup_logger()
        
        self.db = CrawlerDB(db_path)
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
    
    def _scrape_url(self, url, title, link_selector):
        """Extract links and text from single URL (based on csv_link_scraper.py)"""
        try:
            # self.main_logger.info(f"Scraping: {url}")
            response = self.session.get(url, timeout=30, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []

            if url.startswith("https://lawyer.ssu.ac.kr/web/05/notice_list.do"):
                try:
                    news_items = soup.select('#main > section.contents > div.board-list-style.board-course > div.board-list-body > div')
                    for item in news_items:
                        if item and item.get('id'):
                            id = item.get('id')
                            full_url = f"https://lawyer.ssu.ac.kr/web/05/notice_view.do?post={id}"
                            
                            title_element = item.select_one('p.b-title > a')
                            if title_element:
                                title_text = title_element.get_text(strip=True)
                                
                                if title_text and len(title_text) > 3:
                                    links.append({
                                        'text': title_text,
                                        'url': full_url
                                    })
                except Exception as e:
                    self.main_logger.error(f"Error parsing lawyer.ssu.ac.kr: {str(e)}")
                      
            elif url == "https://materials.ssu.ac.kr/bbs/board.php?tbl=bbs51":
                # materials.ssu.ac.kr specific handling
                try:
                    news_items = soup.select('.news-list ul li')
                    for item in news_items:
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
                    self.main_logger.error(f"Error parsing materials.ssu.ac.kr: {str(e)}")
                      
            elif url == "http://media.ssu.ac.kr/sub.php?code=XxH00AXY&category=1":
                found_links = soup.select(link_selector)
                for link in found_links:
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
                        for item in json_data['data_list']:
                            title_text = item.get('Title', '').strip()
                            notice_index = item.get('NoticeIndex', '')
                            if title_text and notice_index:
                                detail_url = f"http://ssfilm.ssu.ac.kr/notice/notice_view?NoticeIndex={notice_index}"
                                links.append({
                                    'text': title_text,
                                    'url': detail_url
                                })
                except:
                    pass
                        
            elif url.startswith("https://api.mediamba.ssu.ac.kr/v1/board"):
                try:
                    json_data = response.json()
                    if json_data.get('success') and 'data' in json_data and 'boards' in json_data['data']:
                        for item in json_data['data']['boards'][:10]:
                            title_text = item.get('title', '').strip()
                            board_id = item.get('id', '')
                            if title_text and board_id:
                                detail_url = f"https://api.mediamba.ssu.ac.kr/v1/board/{board_id}"
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
                        for link in found_links:
                            href = link.get('href')
                            text = link.get_text(strip=True)
                            
                            if href and text and len(text) > 3:
                                full_url = urljoin(url, href)
                                #세션 id 제거
                                full_url = full_url.split("PHPSESSID=")[0]
                                links.append({
                                    'text': text,
                                    'url': full_url
                                })
            
            return links
            
        except Exception as e:
            self.main_logger.error(f"Error scraping {url}: {str(e)}")
            return []
    
    def get_all_ids(self) -> List[int]:
        """Return all notification IDs from notificationList"""
        try:
            return self.db.get_all_ids()
        except Exception as e:
            self.main_logger.error(f"Get all IDs failed: {e}")
            return []
    
    def get_new_notifications(self, notification_id: int) -> List[Dict[str, Any]]:
        """Return only new uncrawled links for specific notification"""
        try:
            # Get notification info from notificationList
            notification_info = self.db.get_notification_info(notification_id)
            if not notification_info:
                self.main_logger.error(f"Notification ID {notification_id} not found.")
                return []
            
            title = notification_info['title']
            url = notification_info['url']
            link_selector = notification_info['link_selector']
            content_selector = notification_info['content_selector']

            # Get existing crawled links
            existing_links = self.db.get_existing_links(notification_id)
            
            # URL scraping
            scraped_links = self._scrape_url(url, title, link_selector)
            
            # Filter only new links
            new_links = []
            for link_data in scraped_links:
                link_url = link_data['url']
                if link_url not in existing_links:
                    new_links.append({
                        'notification_id': notification_id,
                        'category_title': title,
                        'title': link_data['text'],
                        'link': link_url,
                        'content_selector': content_selector,
                    })
            
            # self.main_logger.info(f"{title}: Found {len(new_links)} new links out of {len(scraped_links)} total links")
            return new_links[::-1]
            
        except Exception as e:
            self.main_logger.error(f"Get new notifications failed (notification_id: {notification_id}): {e}")
            return []

    def fetch_content(self, notification_data: Dict[str, Any], content_selector: str = None) -> Dict[str, Any]:
        """Fetch content from notification link"""
        try:
            url = notification_data['link']
            title = notification_data['title']
            
            # self.main_logger.info(f"Fetching content from: {url}")
            
            if url.startswith("https://lawyer.ssu.ac.kr"):
                # 법률 상담소 공지사항 페이지 처리
                base_url = url.split("?post=")[0]
                post_id = url.split("?post=")[-1]
                response = self.session.post(base_url, data={'pdsid': post_id}, timeout=30, verify=False)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                if content_selector:
                    content_element = soup.select_one(content_selector)
                    if content_element:
                        content = str(content_element)
                    else:
                        content = ""
                else:
                    content = ""
                    
            elif url.startswith("http://ssfilm.ssu.ac.kr/notice/notice_view"):
                # 영화예술과 공지사항 JSON API 처리
                response = self.session.get(url, timeout=30, verify=False)
                response.raise_for_status()
                try:
                    json_data = response.json().get('data_modify', {}).get('Content', '')
                    content = json_data.strip() if json_data else ""
                except:
                    content = ""
                    
            elif url.startswith("https://api.mediamba.ssu.ac.kr/v1/board"):
                # 미디어경영학과 API 처리
                if url.startswith("https://mediamba.ssu.ac.kr/board/notice"):
                    # Convert frontend URL to API URL
                    board_id = url.split("/")[-1]
                    api_url = f"https://api.mediamba.ssu.ac.kr/v1/board/{board_id}"
                else:
                    api_url = url
                    
                response = self.session.get(api_url, timeout=30, verify=False)
                response.raise_for_status()
                try:
                    json_data = response.json()
                    if json_data:
                        content = json_data.get('data', {}).get('content', '').strip()
                        # 첨부파일 처리
                        attachments = json_data.get('data', {}).get('attachments', [])
                        if attachments:
                            for att in attachments:
                                file_id = att.get('fileId', '')
                                if file_id:
                                    file_response = self.session.patch(f"https://api.mediamba.ssu.ac.kr/v1/file/{file_id}", timeout=30, verify=False)
                                    if file_response.status_code == 200:
                                        file_data = file_response.json()
                                        if file_data.get('success'):
                                            file_url = file_data.get('data', {}).get('url', '').strip()
                                            file_name = file_data.get('data', {}).get('name', '').strip()
                                            content += f"\n\n[첨부파일]\n{file_name}: {file_url}"
                except:
                    content = ""
                    
            else:
                # 일반적인 웹페이지 처리
                response = self.session.get(url, timeout=30, verify=False)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                if content_selector and content_selector.strip():
                    content_element = soup.select_one(content_selector)
                    if content_element:
                        content = str(content_element)
                    else:
                        content = ""
                else:
                    content = ""
            
            # 이미지 정보 추출
            media_info = []
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                url1 = url if not url.startswith('https://api.mediamba.ssu.ac.kr/v1/board') else None
                media_info = self._extract_media(soup, url1)

            return {
                'title': title,
                'url': url,
                'content': self.clean_html_content(content),
                'image': media_info,
                'fetch_success': True
            }
            
        except Exception as e:
            self.main_logger.error(f"Error fetching content from {notification_data.get('link', '')}: {str(e)}")
            return {
                'title': notification_data.get('title', ''),
                'url': notification_data.get('link', ''),
                'content': "",
                'fetch_success': False,
                'error': str(e)
            }

    def clean_html_content(self, html_content: str) -> str:
        """
        HTML 내용을 정리하는 함수
        - 주석 제거
        - 스크립트와 스타일 태그 제거
        - 모든 HTML 속성 제거 (태그만 보존)
        """
        if not html_content or html_content.strip() == "":
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 주석 제거
            from bs4 import Comment
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # 스크립트와 스타일 태그 제거
            for tag in soup(['script', 'style']):
                tag.decompose()
            
            # 모든 태그에서 모든 속성 제거
            for tag in soup.find_all():
                tag.attrs = {}
            
            # 연속된 공백 줄바꿈 정리
            cleaned_html = str(soup)
            cleaned_html = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_html)
            
            return cleaned_html.strip()
            
        except Exception as e:
            self.main_logger.warning(f"HTML cleaning failed: {e}")
            return html_content

    def _get_image_base_url(self, img_url: str) -> str:
        """이미지 URL에서 베이스 부분 추출 (크기 정보 제거)"""
        url = re.sub(r'-\d+x\d+(?=\.[^.]*$)', '', img_url)
        url = re.sub(r'_\d+(?=\.[^.]*$)', '', url)
        return url

    def _extract_image_dimensions(self, img_url: str) -> tuple:
        """이미지 URL에서 크기 정보 추출"""
        match = re.search(r'-(\d+)x(\d+)(?=\.[^.]*$)', img_url)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    def _extract_media(self, soup: BeautifulSoup, base_url: str = None) -> list:
        """HTML에서 이미지 추출 (URL과 filename만 반환)"""
        media_info = []
        
        all_image_urls = set()
        
        for img in soup.find_all('img', src=True):
            img_url = img['src']
            if base_url and not img_url.startswith('http'):
                img_url = urljoin(base_url, img_url)
            all_image_urls.add(img_url)
        
        for img in soup.find_all('img', srcset=True):
            srcset = img['srcset']
            for src_info in srcset.split(','):
                img_url = src_info.strip().split(' ')[0]
                if base_url and not img_url.startswith('http'):
                    img_url = urljoin(base_url, img_url)
                all_image_urls.add(img_url)
        
        image_groups = {}
        for img_url in all_image_urls:
            base_url_key = self._get_image_base_url(img_url)
            
            if base_url_key not in image_groups:
                image_groups[base_url_key] = []
            image_groups[base_url_key].append(img_url)
        
        for base_url_key, urls in image_groups.items():
            largest_url = max(urls, key=lambda url: self._extract_image_dimensions(url)[0] * self._extract_image_dimensions(url)[1])
            
            parsed_url = urlparse(largest_url)
            filename = unquote(os.path.basename(parsed_url.path))
            
            if not filename or '.' not in filename:
                url_hash = hashlib.md5(largest_url.encode()).hexdigest()[:8]
                filename = f"image_{url_hash}.jpg"
            
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            
            media_info.append({
                'url': largest_url,
                'filename': filename
            })
        
        return media_info

    def save_new_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save new notification to DB"""
        try:
            program_data = {
                'program_link': notification_data['url'],
                'title': notification_data['title'],
                'crawl_timestamp': None,
                'raw_html': notification_data['content'],
                'ai_json_data': notification_data['content']
            }
            
            return self.db.save_program_to_db(notification_data['notification_id'], program_data)
            
        except Exception as e:
            self.main_logger.error(f"Save notification failed: {e}")
            return {"code": -1, "message": str(e)}
