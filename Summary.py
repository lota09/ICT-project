import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re

# 기본 프롬프트 템플릿
DEFAULT_PROMPT_TEMPLATE = """
You are a highly competent assistant responsible for accurately extracting key information from academic notices and delivering it to students.

Analyze the following academic notice. Extract the essential information and return it **strictly in JSON format**.
- The JSON keys must be in English and snake_case.
- All JSON values must be written in Korean.
- If a specific field or piece of information is not mentioned in the text, omit its corresponding key from the JSON object entirely.
- In the `schedule` field, find and extract only crucial single dates like deadlines (마감일).
- If the text provides a period (e.g., 'Application Period: YYYY.MM.DD HH:MM ~ YYYY.MM.DD HH:MM'), extract ONLY the end date and its corresponding time, and set the description to '신청 마감' (Application Deadline).

Prioritize the most critical information by placing the `title` and `summary` first in the JSON structure.

---
### JSON Format Example ###
{{
    "title": "{input_title}",
    "summary": "(A detailed summary of the notice. It MUST include the main purpose, key activities, and expected benefits for participants.)",
    "schedule": [
        {{
            "description": "(The type of deadline, e.g., '신청 마감', '서류 제출 마감'. MUST be a single event.)",
            "date": "(The corresponding single date ONLY. e.g., 'YYYY.MM.DD HH:MM' or 'YYYY.MM.DD'. If the time is specified in the notice, it must be included.)",
            "location": "(A place where the event on the specified date takes place)"
        }}
    ],
    "target": "(Who the notice is for)",
    "application_method": "(A full phrase describing the method, e.g., 'OOO 홈페이지에서 온라인 신청', 'XX관 YY실로 방문 제출')",
    "important_notes": "(Key details like capacity, selection method, benefits, or contact info. Key details are separated by a slash.e.g., '정원: OO명 / 선발 방식: 서류 심사 / 혜택: 활동비 지원 / 문의: OOO팀 (02-123-4567)'))"
}}
---
### Text to Summarize ###
{input_content}
---
"""

class GeminiSummarizer:
    def __init__(self, model_name: str = 'gemini-1.5-flash'):

        try:
            # API 키 로드
            api_key = os.getenv("GOOGLE_API_KEY") or self._load_api_key_from_env()
            if not api_key:
                raise ValueError("API 키를 찾을 수 없습니다.")
            genai.configure(api_key=api_key)

            # 생성 옵션 설정
            self.generation_config = {
                "temperature": 0.2,         
                "top_p": 1,                 
                "top_k": 1,                 
                "max_output_tokens": 2048,  
            }
            
            # 모델 초기화
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=self.generation_config
            )
            # print(f"GeminiSummarizer 초기화 완료 (모델: {model_name})")

        except Exception as e:
            print(f"초기화 중 오류 발생: {e}")
            self.model = None

    # API 키 반환
    def _load_api_key_from_env(self):
        load_dotenv()
        return os.getenv("GOOGLE_API_KEY")

    # 요약 함수
    def summarize(self, title: str, ocr_text: str, content: str, prompt_template: str = DEFAULT_PROMPT_TEMPLATE) -> str:
        if not self.model:
            return "요약에 실패했습니다. 모델이 초기화되지 않았습니다."

        try:
            input_content=f"{ocr_text}\n\n{content}"

            prompt = prompt_template.format(input_title=title, input_content=input_content)
            response = self.model.generate_content(prompt)
            
            # LLM의 전체 응답 텍스트를 변수에 저장
            raw_response_text = response.text
            
            # 정규 표현식(re)을 사용해 텍스트에서 '{...}' 패턴을 탐색
            # re.DOTALL: 줄바꿈 문자를 포함하여 모든 문자를 '.'에 매칭
            json_match = re.search(r'\{.*\}', raw_response_text, re.DOTALL)
            
            # JSON 패턴을 찾았는지 확인
            if json_match:
                # 찾은 JSON 문자열을 추출
                json_string = json_match.group(0)
                
                # 추출한 문자열이 실제 JSON 형식이 맞는지 검증
                json.loads(json_string)
                
                return json_string.strip() # 검증된 순수 JSON 문자열을 반환
            else:
                # LLM 응답에서 '{...}' 패턴을 찾지 못한 경우
                raise ValueError("LLM 응답에서 유효한 JSON을 찾을 수 없습니다.")

        except Exception as e:
            print(f"요약 중 오류 발생: {e}")
            print(f"Gemini가 보낸 원본 응답:\n---\n{response.text}\n---")
            return "요약에 실패했습니다."