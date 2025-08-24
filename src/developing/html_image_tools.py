"""
HTML 페이지 분석을 위한 LLM 도구들
- 이미지 개수 카운        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # src 속성이 있는 img 태그만 찾기 (data-src는 제외)
            img_tags = soup.find_all('img', src=True)
            return len(img_tags) 이미지 OCR 처리 (tool_ocr.py 함수 활용)
"""

from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Union
import logging
from tool_ocr import perform_ocr_on_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HTMLImageAnalyzer:
    """HTML 페이지의 이미지를 분석하는 클래스"""
    
    def count_html_images(self, html_content: str) -> int:
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

    def ocr_html_images(self, html_content: str, grouped: bool = False) -> Union[List[str], List[Dict[str, str]]]:
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
                ocr_text = perform_ocr_on_url(url)
                
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

# 테스트용 함수들
if __name__ == "__main__":
    # 테스트용 분석기 인스턴스
    analyzer = HTMLImageAnalyzer()
    
    # fetched.html 파일 테스트
    html_file_path = "src/assets/fetched.html"

    try:
        # HTML 파일 읽기
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print(f"=== {html_file_path} 파일 분석 ===")
        
        # 이미지 개수 카운팅
        img_count = analyzer.count_html_images(html_content)
        print(f"발견된 <img> 태그 (src 속성 포함) 개수: {img_count}")
        
        # 이미지가 있으면 OCR 수행
        if img_count > 0:
            print(f"\n=== OCR 처리 시작 ===")
            ocr_results = analyzer.ocr_html_images(html_content, grouped=True)
            print(f"OCR 결과 :")
            print(ocr_results)
        else:
            print("이미지가 없어서 OCR을 수행하지 않습니다.")
            
    except FileNotFoundError:
        print(f"오류: {html_file_path} 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"오류: {str(e)}")
    