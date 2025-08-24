"""
공지사항 페이지에서 이미지를 추출하고 저장하는 도구
- URL에서 img src 주소 리스트 추출
- 이미지 파일을 로컬 파일시스템에 저장
"""

import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_image_urls(notice_url: str) -> list:
    """
    공지사항 페이지 URL을 입력받아 img src 주소들을 리스트로 반환
    
    Args:
        notice_url (str): 공지사항 페이지 URL
        
    Returns:
        list: img src 주소들의 리스트
    """
    try:
        # User-Agent 헤더 설정 (일부 사이트에서 차단 방지)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 웹페이지 가져오기
        response = requests.get(notice_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # img 태그에서 src 속성 추출
        img_tags = soup.find_all('img', src=True)
        image_urls = []
        
        for img in img_tags:
            src = img.get('src')
            if src:
                # 상대 경로를 절대 경로로 변환
                absolute_url = urljoin(notice_url, src)
                image_urls.append(absolute_url)
                logger.info(f"이미지 URL 발견: {absolute_url}")
        
        logger.info(f"총 {len(image_urls)}개의 이미지 URL을 추출했습니다.")
        return image_urls
        
    except requests.RequestException as e:
        logger.error(f"웹페이지 요청 중 오류 발생: {e}")
        return []
    except Exception as e:
        logger.error(f"이미지 URL 추출 중 오류 발생: {e}")
        return []


def download_images_from_notice(notice_url: str, save_directory: str = "downloaded_images") -> list:
    """
    공지사항 페이지 URL을 입력받아 img src 이미지들을 파일시스템에 저장
    
    Args:
        notice_url (str): 공지사항 페이지 URL
        save_directory (str): 이미지를 저장할 디렉터리 경로 (기본값: "downloaded_images")
        
    Returns:
        list: 저장된 파일 경로들의 리스트
    """
    try:
        # 저장 디렉터리 생성
        save_path = Path(save_directory)
        save_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"저장 디렉터리 생성: {save_path.absolute()}")
        
        # 이미지 URL 추출
        image_urls = extract_image_urls(notice_url)
        
        if not image_urls:
            logger.warning("다운로드할 이미지 URL이 없습니다.")
            return []
        
        downloaded_files = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        for i, img_url in enumerate(image_urls):
            try:
                # 이미지 다운로드
                response = requests.get(img_url, headers=headers, timeout=30)
                response.raise_for_status()
                
                # 파일명 생성 (URL에서 추출하거나 인덱스 사용)
                parsed_url = urlparse(img_url)
                filename = os.path.basename(parsed_url.path)
                
                # 파일명이 없거나 확장자가 없는 경우
                if not filename or '.' not in filename:
                    # URL에서 확장자 추정 또는 기본 확장자 사용
                    content_type = response.headers.get('content-type', '')
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        ext = '.jpg'
                    elif 'png' in content_type:
                        ext = '.png'
                    elif 'gif' in content_type:
                        ext = '.gif'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    else:
                        ext = '.jpg'  # 기본 확장자
                    
                    filename = f"image_{i+1:03d}{ext}"
                
                # 중복 파일명 처리
                file_path = save_path / filename
                counter = 1
                original_stem = file_path.stem
                original_suffix = file_path.suffix
                
                while file_path.exists():
                    file_path = save_path / f"{original_stem}_{counter}{original_suffix}"
                    counter += 1
                
                # 파일 저장
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                downloaded_files.append(str(file_path))
                logger.info(f"이미지 저장 완료: {file_path}")
                
            except requests.RequestException as e:
                logger.error(f"이미지 다운로드 실패 ({img_url}): {e}")
                continue
            except Exception as e:
                logger.error(f"이미지 저장 중 오류 ({img_url}): {e}")
                continue
        
        logger.info(f"총 {len(downloaded_files)}개의 이미지를 저장했습니다.")
        return downloaded_files
        
    except Exception as e:
        logger.error(f"이미지 다운로드 프로세스 중 오류 발생: {e}")
        return []


def test_functions():
    """테스트 함수"""
    # 테스트 URL (실제 공지사항 페이지로 변경 필요)
    test_url = "https://scatch.ssu.ac.kr/공지사항/?slug=2025학년도-2학기-신·편입생-학생증스마트카드-신청-안&category=학사"
    
    print("=== 이미지 URL 추출 테스트 ===")
    urls = extract_image_urls(test_url)
    print(f"추출된 이미지 URL 개수: {len(urls)}")
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")
    
    print("\n=== 이미지 다운로드 테스트 ===")
    downloaded = download_images_from_notice(test_url, "src/assets")
    print(f"다운로드된 파일 개수: {len(downloaded)}")
    for i, file_path in enumerate(downloaded, 1):
        print(f"{i}. {file_path}")

    from tool_ocr import ocr_url_images, ocr_file_images

    file_ocr_results = []
    url_ocr_results = []

    print("\n=== 이미지 OCR 테스트 ===")
    for i, file_path in enumerate(downloaded, 1):
        print(f"{i}. {file_path}")
        result = ocr_file_images(file_path)
        file_ocr_results.append(result)

    for url in urls:
        result = ocr_url_images(url)
        url_ocr_results.append(result)

    print("\n=== 파일 OCR 결과 ===")
    for i, result in enumerate(file_ocr_results, 1):
        print(f"{i}. {result}")

    print("\n=== URL OCR 결과 ===")
    for i, result in enumerate(url_ocr_results, 1):
        print(f"{i}. {result}")

if __name__ == "__main__":
    test_functions()
