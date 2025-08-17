import json
from typing import List, Optional
from pydantic import BaseModel, ValidationError

# schedule 배열 안에 들어갈 객체의 설계도
class ScheduleItem(BaseModel):
    description: str
    period: str
    location: Optional[str] = None # location은 없을 수도 있으므로 Optional로 지정

# 최종 JSON 전체의 설계도
class NoticeOutput(BaseModel):
    title: str
    summary: str
    schedule: List[ScheduleItem] # schedule은 ScheduleItem 객체들의 리스트여야 함
    target: str
    application_method: str
    important_notes: str

# JSON 문자열을 Pydantic 객체로 변환하는 함수
def parse_notice_output(json_string: str) -> Optional[NoticeOutput]:
    try:
        # JSON 문자열을 파이썬 딕셔너리로 변환
        data = json.loads(json_string)
        
        # 딕셔너리를 Pydantic 모델에 넣어 객체를 생성
        parsed_output = NoticeOutput(**data)
        
        # 검증에 성공한 객체를 반환
        return parsed_output
    
    except ValidationError as e:
        # Pydantic 모델 검증에 실패한 경우
        print(f"Pydantic 유효성 검사 실패: {e}")
        return None
    except json.JSONDecodeError:
        # 유효한 JSON 형식이 아닌 경우
        print("JSON 형식 오류: 문자열을 파싱할 수 없습니다.")
        return None