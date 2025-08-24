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

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVLinkScraper:
    def __init__(self, delay=1.0):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        self.delay = delay
    
    def read_csv_file(self, csv_path):
        """CSV 파일을 읽고 데이터를 반환"""
        data = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
        except UnicodeDecodeError:
            # Try with different encoding
            with open(csv_path, 'r', encoding='cp949') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
        return data
    
    def scrape_url(self, url, title, link_selector):
        """단일 URL에서 링크와 텍스트를 추출"""
        try:
            # logger.info(f"Scraping: {url}")
            response = self.session.get(url, timeout=30, verify=False)  # SSL 검증 비활성화
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            links = []
            if url.startswith("https://lawyer.ssu.ac.kr/web/05/notice_list.do"):
                try:
                    # 국제법무학과 공지사항 페이지 처리
                    news_items = soup.select('#main > section.contents > div.board-list-style.board-course > div.board-list-body > div')
                    for item in news_items[:10]:
                        # post(id) 추출
                        if item and item.get('id'):
                            id = item.get('id')
                            full_url =  f"https://lawyer.ssu.ac.kr/web/05/notice_view.do?post={id}"
                            
                            # 제목 추출 - strong 태그 안의 텍스트
                            title_element = item.select_one('p.b-title > a')
                            if title_element:
                                title = title_element.get_text(strip=True)
                                
                                if title and len(title) > 3:
                                    links.append({
                                        'title': title,
                                        'url': full_url
                                    })
                                    
                except Exception as e:
                    logger.error(f"Error parsing lawyer.ssu.ac.kr: {str(e)}")
                    pass
                      
            elif url == "https://materials.ssu.ac.kr/bbs/board.php?tbl=bbs51":
                # materials.ssu.ac.kr 전용 처리 - 제목과 링크가 분리된 구조
                try:
                    # 뉴스 리스트에서 각 li 요소를 찾음
                    news_items = soup.select('.news-list ul li')
                    for item in news_items[:10]:
                        # 링크(href) 추출
                        link_element = item.select_one('a')
                        if link_element and link_element.get('href'):
                            href = link_element.get('href')
                            full_url = urljoin(url, href)
                            
                            # 제목 추출 - strong 태그 안의 텍스트
                            title_element = item.select_one('.tit_box strong')
                            if title_element:
                                title = title_element.get_text(strip=True)
                                # 태그(공지) 제거 - span 태그 제거
                                for span in title_element.select('span'):
                                    span.decompose()
                                title = title_element.get_text(strip=True)
                                
                                if title and len(title) > 3:
                                    links.append({
                                        'title': title,
                                        'url': full_url
                                    })
                except Exception as e:
                    logger.error(f"Error parsing materials.ssu.ac.kr: {str(e)}")
                    pass
                      
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
                                'title': text,
                                'url': full_url
                            })
                        
            elif url.startswith("http://ssfilm.ssu.ac.kr/notice/notice_list"):
                try:
                    json_data = response.json()
                    if 'data_list' in json_data:
                        for item in json_data['data_list'][:10]:
                            title = item.get('Title', '').strip()
                            notice_index = item.get('NoticeIndex', '')
                            if title and notice_index:
                                # 개별 공지사항 상세 페이지 URL 생성
                                detail_url = f"http://ssfilm.ssu.ac.kr/notice/notice_view?NoticeIndex={notice_index}"
                                links.append({
                                    'title': title,
                                    'url': detail_url
                                })
                except:
                    pass
                        
            elif url.startswith("https://api.mediamba.ssu.ac.kr/v1/board"):
                # JSON API 응답 처리
                try:
                    json_data = response.json()
                    if json_data.get('success') and 'data' in json_data and 'boards' in json_data['data']:
                        for item in json_data['data']['boards'][:10]:
                            title = item.get('title', '').strip()
                            board_id = item.get('id', '')
                            if title and board_id:
                                # 개별 게시글 상세 페이지 URL 생성
                                detail_url = f"https://api.mediamba.ssu.ac.kr/v1/board/{board_id}"
                                links.append({
                                    'title': title,
                                    'url': detail_url
                                })
                except:
                    pass
                
            else:
                # CSV에서 지정된 link_selector 사용
                if link_selector and link_selector.strip():
                    found_links = soup.select(link_selector)
                    if found_links:
                        for link in found_links[:10]:  # 최대 10개까지만
                            href = link.get('href')
                            text = link.get_text(strip=True)
                            
                            if href and text and len(text) > 3:  # 의미있는 텍스트가 있는 링크만
                                full_url = urljoin(url, href)
                                links.append({
                                    'title': text,
                                    'url': full_url
                                })
            
            return links[:10]  # 최대 10개까지만 반환
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return []
    
    def process_csv_and_scrape(self, csv_path, output_path):
        """CSV 파일을 처리하고 모든 URL을 스크래핑"""
        csv_data = self.read_csv_file(csv_path)
        result = {}
        
        for row in csv_data:
            title = row.get('title', '').strip()
            url = row.get('url', '').strip()
            link_selector = row.get('link_selector', '').strip()
            content_selector = row.get('content_selector', '').strip()

            if title and url:
                logger.info(f"Processing: {title}")
                
                # URL에서 데이터 추출 (link_selector 포함)
                scraped_links = self.scrape_url(url, title, link_selector)
                scrape_contents = self.scrape_content(scraped_links, content_selector)

                # 결과 형식: {title: [{link_text: link_url}, ...]}
                result[title] = scrape_contents
                
                # 요청 간 지연
                time.sleep(self.delay)
        
        # JSON 파일로 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to {output_path}")
        return result

    def scrape_content(self, data, content_selector):
        """단일 URL에서 링크와 텍스트를 추출"""
        try:
            datas = []
            for i in data:
                if i['url'].startswith("https://lawyer.ssu.ac.kr"):
                    # 법률 상담소 공지사항 페이지 처리
                    url = i['url'].split("?post=")[0]
                    post = i['url'].split("?post=")[-1]
                    response = self.session.post(url, data={'pdsid': post}, timeout=30, verify=False)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    content = soup.select_one(content_selector)
                    if content:
                        datas.append({
                            'title': i['title'],
                            'url': i['url'],
                            'content': str(content)
                        })
                else:
                    # logger.info(f"Scraping: {i['url']}")
                    response = self.session.get(i['url'], timeout=30, verify=False)  # SSL 검증 비활성화
                    response.raise_for_status()

                    soup = BeautifulSoup(response.content, 'html.parser')
                                    
                    if i['url'].startswith("http://ssfilm.ssu.ac.kr/notice/notice_view"):
                        try:
                            json_data = response.json().get('data_modify', {}).get('Content', '')
                            if json_data:
                                content = json_data.strip()
                                if content:
                                    datas.append({
                                        'title' : i['title'],
                                        'url' : i['url'],
                                        'content' : content
                                    })
                        except:
                            pass

                    elif i['url'].startswith("https://api.mediamba.ssu.ac.kr/v1/board"):
                        # JSON API 응답 처리
                        try:
                            json_data = response.json()
                            if json_data:
                                content = json_data.get('data', {}).get('content', '').strip()
                                if content:
                                    attachments = json_data.get('data', {}).get('attachments', [])
                                    if attachments:
                                        attachments_url = [f"https://api.mediamba.ssu.ac.kr/v1/file/{att.get('fileId', '')}" for att in attachments]
                                        for att in attachments_url:
                                            response1 = self.session.patch(att, timeout=30, verify=False)  # SSL 검증 비활성화
                                            response1.raise_for_status()
                                            json_data1 = response1.json()
                                            if json_data1.get('success'):
                                                file_url = json_data1.get('data', {}).get('url', '').strip()
                                                file_name = json_data1.get('data', {}).get('name', '').strip()
                                                content += f"\n\n[첨부파일]\n{file_name}: {file_url}"
                                    datas.append({
                                        'title' : i['title'],
                                        'url' : i['url'],
                                        'content' : content
                                    })
                        except:
                            pass
                        
                    else:
                        # CSV에서 지정된 content_selector 사용
                        if content_selector and content_selector.strip():
                            content_found = soup.select_one(content_selector)
                            if content_found:
                                datas.append({
                                    'title' : i['title'],
                                    'url' : i['url'],
                                    'content' : str(content_found)
                                })
                    
            return datas
            
        except Exception as e:
            logger.error(f"Error scraping_content : {str(e)}")
            return []

def main():
    scraper = CSVLinkScraper(delay=1.0)
    
    csv_path = "notificationList.csv"
    csv_path = "notify.csv"
    output_path = "scraped_links.json"
    
    try:
        result = scraper.process_csv_and_scrape(csv_path, output_path)
        print(f"Successfully scraped {len(result)} entries")
        print(f"Results saved to {output_path}")
        
        # 결과 샘플 출력 (앞 2개, 뒤 2개)
        # titles = list(result.keys())
        # if len(titles) > 4:
        #     display_titles = titles[:2] + titles[-2:]
        # else:
        #     display_titles = titles
        
        # for title in display_titles:
        #     links = result[title]
        #     print(f"\n{title}:")
        #     for link in links[:3]:  # 각 항목당 최대 3개 링크만 표시
        #         for text, url in link.items():
        #             print(f"  - {text}: {url}")
        
        # if len(titles) > 4:
        #     print(f"\n... (총 {len(titles)}개 항목 중 앞 2개, 뒤 2개만 표시)")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()