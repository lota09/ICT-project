"""
URL 이미지와 로컬 이미지에서 OCR 텍스트를 추출하는 함수들
LLM Agent에서 사용하기 위해 최적화됨
"""

import requests
import io
import logging
from PIL import Image
import numpy as np
import os
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Union

# PaddleOCR 임포트
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("PaddleOCR가 설치되지 않았습니다. 설치하려면: pip install paddleocr")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 OCR 객체 (한 번만 초기화)
_ocr_instance = None


def get_ocr_instance():
    """OCR 인스턴스를 가져오거나 생성합니다 (CPU 모드)."""
    global _ocr_instance
    
    if _ocr_instance is None:
        if not PADDLEOCR_AVAILABLE:
            raise ImportError("PaddleOCR가 설치되지 않았습니다.")
        
        try:
            # CPU 모드로 설정 (use_gpu 파라미터 제거)
            _ocr_instance = PaddleOCR(
                use_textline_orientation=True, 
                lang='korean'
            )
            logger.info("PaddleOCR 초기화 완료 (CPU 모드)")
        except Exception as e:
            logger.error(f"PaddleOCR 초기화 실패: {e}")
            raise
    
    return _ocr_instance


def ocr_url_images(img_url: str) -> str:
    """
    URL 이미지에서 OCR 텍스트를 추출합니다.
    
    Args:
        img_url (str): 이미지 URL
        
    Returns:
        str: 추출된 텍스트 (실패시 빈 문자열)
    """
    try:
        logger.info(f"OCR 처리 시작: {img_url}")
        
        # 1. 이미지 다운로드
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(img_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 2. PIL Image로 변환
        image = Image.open(io.BytesIO(response.content))
        
        # RGB로 변환 (필요한 경우)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 3. numpy 배열로 변환 (PaddleOCR는 PIL Image도 직접 처리 가능)
        img_array = np.array(image)
        
        logger.info(f"이미지 다운로드 완료: {img_array.shape}")
        
        # 4. OCR 수행 (numpy 배열 사용)
        ocr = get_ocr_instance()
        results = ocr.predict(img_array)
        
        # 5. 텍스트 추출 (PaddleOCR 3.x 결과 구조)
        if not results:
            logger.warning("OCR 결과가 없습니다.")
            return ""
        
        logger.info(f"OCR 결과 타입: {type(results)}, 길이: {len(results) if hasattr(results, '__len__') else 'N/A'}")
        
        text_lines = []
        
        # PaddleOCR 3.x 결과 구조 처리
        if isinstance(results, list) and len(results) > 0:
            first_result = results[0]
            
            # OCRResult 객체에서 rec_texts 추출
            if hasattr(first_result, 'rec_texts'):
                text_lines = first_result.rec_texts
                logger.info(f"rec_texts에서 {len(text_lines)}개 텍스트 라인 추출")
            elif isinstance(first_result, dict) and 'rec_texts' in first_result:
                text_lines = first_result['rec_texts']
                logger.info(f"딕셔너리 rec_texts에서 {len(text_lines)}개 텍스트 라인 추출")
            else:
                logger.warning(f"예상치 못한 결과 구조: {type(first_result)}")
                return ""
        
        ocr_text = '\n'.join(text_lines) if text_lines else ""
        
        logger.info(f"OCR 완료: {len(ocr_text)}자 추출")
        return ocr_text
        
    except Exception as e:
        logger.error(f"OCR 처리 실패: {e}")
        return ""


def ocr_file_images(img_path: str) -> str:
    """
    로컬 이미지 파일에서 OCR 텍스트를 추출합니다.
    
    Args:
        img_path (str): 이미지 파일 경로
        
    Returns:
        str: 추출된 텍스트 (실패시 빈 문자열)
    """
    try:
        logger.info(f"로컬 OCR 처리 시작: {img_path}")
        
        # 1. 파일 존재 확인
        if not os.path.exists(img_path):
            logger.error(f"파일을 찾을 수 없습니다: {img_path}")
            return ""
        
        # 2. 이미지 로딩
        image = Image.open(img_path)
        
        # RGB로 변환 (필요한 경우)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 3. numpy 배열로 변환
        img_array = np.array(image)
        
        logger.info(f"이미지 로딩 완료: {img_array.shape}")
        
        # 4. OCR 수행
        ocr = get_ocr_instance()
        results = ocr.predict(img_array)
        
        # 5. 텍스트 추출
        if not results:
            logger.warning("OCR 결과가 없습니다.")
            return ""
        
        text_lines = []
        
        # PaddleOCR 3.x 결과 구조 처리
        if isinstance(results, list) and len(results) > 0:
            first_result = results[0]
            
            # OCRResult 객체에서 rec_texts 추출
            if hasattr(first_result, 'rec_texts'):
                text_lines = first_result.rec_texts
                logger.info(f"rec_texts에서 {len(text_lines)}개 텍스트 라인 추출")
            elif isinstance(first_result, dict) and 'rec_texts' in first_result:
                text_lines = first_result['rec_texts']
                logger.info(f"딕셔너리 rec_texts에서 {len(text_lines)}개 텍스트 라인 추출")
            else:
                logger.warning(f"예상치 못한 결과 구조: {type(first_result)}")
                return ""
        
        ocr_text = '\n'.join(text_lines) if text_lines else ""
        
        logger.info(f"로컬 OCR 완료: {len(ocr_text)}자 추출")
        return ocr_text
        
    except Exception as e:
        logger.error(f"로컬 OCR 처리 실패: {e}")
        return ""

"""HTML 페이지의 이미지를 분석하는 클래스"""

def count_html_images(html_content: str) -> int:
    """
    HTML 페이지 내의 <img> 태그 개수를 반환
    
    Args:
        html_content (str): HTML 페이지의 문자열 내용
        
    Returns:
        int: <img> 태그 개수
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tags = soup.find_all('img', src=True)
        return len(img_tags)
    except Exception as e:
        print(f"HTML 분석 중 오류 발생: {str(e)}")
        return 0

def ocr_html_images(html_content: str, grouped: bool = False) -> Union[List[str], List[Dict[str, str]]]:
    """
    HTML 페이지 내의 <img> 태그 이미지만 OCR 처리
    tool_ocr.py의 perform_ocr_on_url 함수를 사용
    
    Args:
        html_content (str): HTML 페이지의 문자열 내용
        grouped (bool): True면 딕셔너리 리스트, False면 문자열 리스트 반환
        
    Returns:
        grouped=True: [{"class":"클래스명","text":"OCR텍스트","alt":"대체텍스트"}, ...]
        grouped=False: ["OCR텍스트1", "OCR텍스트2", ...]
    """
    
    # src 속성이 있는 <img> 태그만 찾기
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tags = soup.find_all('img', src=True)
    except Exception as e:
        return [] if not grouped else [{"error": f"HTML 분석 중 오류: {str(e)}"}]
    
    if not img_tags:
        return []
    
    results = []
    
    for index, img in enumerate(img_tags):
        try:
            url = img.get('src')
            if not url:
                continue
            
            # 완전한 URL이 아닌 경우 스킵 (상대경로 처리 제거)
            if not url.startswith('http'):
                continue
            
            # OCR 처리
            ocr_text = ocr_url_images(url)
            
            if ocr_text and ocr_text.strip():
                clean_text = ocr_text.strip()
                
                if grouped:
                    # 딕셔너리 형태로 반환
                    result_dict = {
                        "class": img.get('class', [''])[0] if img.get('class') else "",
                        "text": clean_text,
                        "alt": img.get('alt', "")
                    }
                    results.append(result_dict)
                else:
                    # 문자열만 반환
                    results.append(clean_text)
                
                logger.info(f"OCR 완료 ({index + 1}/{len(img_tags)}): {url[:50]}... -> {len(clean_text)}자")
            else:
                logger.info(f"OCR 실패 ({index + 1}/{len(img_tags)}): {url[:50]}... -> 빈 결과")
            
        except Exception as e:
            logger.error(f"OCR 오류 ({index + 1}/{len(img_tags)}): {str(e)}")
            continue
    
    return results

def test_ocr():
    """테스트 함수"""
    # URL OCR 테스트
    test_url = "https://scatch.ssu.ac.kr/wp-content/uploads/sites/5/2025/08/2025년-8월-학부-졸업자-학위수여-안내-20250814.pdf_page_1.jpg"
    
    print("=== URL OCR 테스트 ===")
    print(f"테스트 URL: {test_url}")
    print("\nOCR 처리 중...")
    
    result_url = ocr_url_images(test_url)
    
    print("\n=== URL OCR 결과 ===")
    if result_url:
        print(f"추출된 텍스트 길이: {len(result_url)}자")
        print("\n추출된 텍스트 (처음 500자):")
        print("=" * 50)
        print(result_url[:500])
        print("=" * 50)
    else:
        print("텍스트를 추출할 수 없습니다.")
    
    # 로컬 파일 OCR 테스트
    test_file = "src/img/홈페이지-공지-2025학년도-2학기-온라인-강좌-정원-증원-안내_1.png"
    
    print(f"\n=== 로컬 파일 OCR 테스트 ===")
    print(f"테스트 파일: {test_file}")
    
    if os.path.exists(test_file):
        print("\nOCR 처리 중...")
        result_file = ocr_file_images(test_file)
        
        print("\n=== 로컬 파일 OCR 결과 ===")
        if result_file:
            print(f"추출된 텍스트 길이: {len(result_file)}자")
            print("\n추출된 텍스트 (처음 500자):")
            print("=" * 50)
            print(result_file[:500])
            print("=" * 50)
        else:
            print("텍스트를 추출할 수 없습니다.")
    else:
        print(f"테스트 파일을 찾을 수 없습니다: {test_file}")


if __name__ == "__main__":
    test_ocr()
