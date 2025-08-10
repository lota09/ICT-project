# 프로젝트 워크플로우

## 개요

본 문서는 학사공지사항알리미 시스템의 전체적인 프로그램 흐름과 각 처리 단계를 상세히 설명합니다. 시스템은 크게 **동적 처리부**와 **정적 처리부**로 구분되어 동작합니다.

## 시스템 아키텍처

```
[사용자 인터페이스] → [동적 처리부] → [사용자 DB]
                                    ↓
[정적 처리부] ← [스케줄러] ← [시간 기반 트리거]
     ↓
[LLM 엔진] + [OCR 도구] + [Calendar 도구] + [Email 도구]
```

## 동적 처리부 (사용자 요청 기반)

### 1. 사용자 등록 프로세스

#### 1.1 신규 사용자 가입
- **입력**: 사용자 기본 정보
  - 이메일 주소 (필수)
  - 사용자명
  - 알림 설정 선호도
- **처리**: 사용자 DB에 신규 레코드 생성
- **출력**: 사용자 고유 ID 생성 및 반환

#### 1.2 구독 항목 관리
- **입력**: 사용자가 선택한 구독 항목
  - 학과별 공지사항
  - 학사 일정
  - 장학금 정보
  - 기타 관심 카테고리
- **처리**: 사용자 DB에 구독 정보 저장
- **출력**: 구독 설정 완료 확인

### 데이터베이스 스키마 (사용자 관련)
```sql
Users Table:
- user_id (PRIMARY KEY)
- email (UNIQUE)
- username
- created_at
- updated_at
- notification_preferences

Subscriptions Table:
- subscription_id (PRIMARY KEY)
- user_id (FOREIGN KEY)
- site_id
- category
- is_active
```

## 정적 처리부 (스케줄 기반 - 매시간 실행)

### 2. 웹 크롤링 및 데이터 수집

#### 2.1 사이트 목록 조회
- **처리**: 등록된 모든 사이트 객체 로드
- **데이터**: 사이트 URL, 크롤링 설정, 마지막 업데이트 시간

#### 2.2 웹 페이지 Fetch
- **대상**: 각 사이트의 공지사항 목록 페이지
- **방법**: HTTP 요청을 통한 HTML 컨텐츠 수집
- **오류 처리**: 타임아웃, 접근 거부 등 예외 상황 처리

### 3. 변경사항 감지 및 분석

#### 3.1 DB 비교 프로세스
```python
for site in all_sites:
    latest_notices = fetch_notices(site.url)
    stored_notices = get_stored_notices(site.id)
    
    new_notices = compare_notices(latest_notices, stored_notices)
    
    if not new_notices:
        continue  # 해당 사이트 처리 종료
    
    # 새로운 공지사항 처리 계속
```

#### 3.2 신규 공지사항 식별
- **비교 기준**: 제목, 게시일, 고유 ID
- **중복 제거**: 동일한 공지사항 필터링
- **우선순위**: 긴급도, 마감일 기준 정렬

### 4. 상세 콘텐츠 처리

#### 4.1 상세 페이지 Fetch
- **대상**: 새로 발견된 공지사항의 상세 페이지
- **수집 데이터**: 본문 텍스트, 첨부파일, 이미지

#### 4.2 이미지 콘텐츠 분석 (LLM 활용)
```python
def analyze_content_with_llm(html_content):
    """
    LLM을 사용하여 웹페이지에 이미지가 포함되어 있는지 판단
    """
    prompt = f"""
    다음 HTML 콘텐츠를 분석하여 중요한 정보가 포함된 이미지가 있는지 판단해주세요:
    {html_content}
    
    응답 형식: {{"has_important_images": true/false, "image_urls": [...]}}
    """
    return llm_query(prompt)
```

#### 4.3 OCR 처리 (조건부 실행)
- **실행 조건**: LLM이 중요한 이미지가 있다고 판단한 경우
- **처리 과정**:
  1. 이미지 다운로드 및 전처리
  2. OCR 엔진을 통한 텍스트 추출
  3. 추출된 텍스트와 기존 본문 병합
- **OCR 도구**: Tesseract, PaddleOCR 등 활용

```python
def process_images_with_ocr(image_urls):
    """
    OCR TOOL을 사용하여 이미지에서 텍스트 추출
    """
    extracted_text = ""
    for url in image_urls:
        image = download_image(url)
        text = ocr_tool.extract_text(image)
        extracted_text += f"\n[이미지에서 추출된 텍스트]\n{text}\n"
    return extracted_text
```

### 5. 일정 정보 추출 및 캘린더 연동

#### 5.1 일정 정보 식별 (LLM 활용)
```python
def extract_schedule_info(content):
    """
    LLM을 사용하여 본문에서 일정 관련 정보 추출
    """
    prompt = f"""
    다음 공지사항에서 중요한 일정 정보를 추출해주세요:
    {content}
    
    추출할 정보:
    - 이벤트명
    - 날짜 및 시간
    - 장소
    - 마감일
    
    응답 형식: JSON
    """
    return llm_query(prompt)
```

#### 5.2 Google Calendar 연동 (Calendar TOOL)
- **실행 조건**: 일정 정보가 발견된 경우
- **처리 과정**:
  1. 추출된 일정 정보 구조화
  2. Google Calendar API 호출
  3. 사용자별 캘린더에 이벤트 생성
- **권한 관리**: OAuth 2.0을 통한 사용자 캘린더 접근

```python
def create_calendar_event(schedule_info, user_email):
    """
    Calendar TOOL을 사용하여 Google Calendar에 일정 생성
    """
    event = {
        'summary': schedule_info['title'],
        'start': {'dateTime': schedule_info['start_time']},
        'end': {'dateTime': schedule_info['end_time']},
        'description': schedule_info['description'],
        'location': schedule_info.get('location', '')
    }
    
    calendar_api.create_event(user_email, event)
```

### 6. 콘텐츠 요약 및 전송

#### 6.1 본문 요약 (LLM 활용)
```python
def summarize_content(full_content):
    """
    LLM을 사용하여 공지사항 내용 요약
    """
    prompt = f"""
    다음 공지사항을 간결하고 핵심적으로 요약해주세요:
    {full_content}
    
    요약 기준:
    - 3-5문장 내외
    - 중요한 날짜 및 마감일 포함
    - 행동 요구사항 명시
    """
    return llm_query(prompt)
```

#### 6.2 이메일 전송 (Email TOOL)
- **수신자**: 해당 카테고리를 구독하는 모든 사용자
- **이메일 구성**:
  - 제목: 공지사항 제목 + 요약
  - 본문: LLM 요약 + 원문 링크
  - 첨부: 캘린더 초대장 (일정이 있는 경우)

```python
def send_notification_email(users, notice_summary, original_link):
    """
    Email TOOL을 사용하여 사용자들에게 알림 이메일 전송
    """
    for user in users:
        email_content = {
            'to': user.email,
            'subject': f"[학사공지] {notice_summary['title']}",
            'body': format_email_body(notice_summary, original_link),
            'attachments': []
        }
        
        email_tool.send_email(email_content)
```

## 핵심 구성 요소

### LLM 엔진
- **역할**: 이미지 분석, 일정 추출, 내용 요약
- **모델**: GPT-4, Claude, 또는 로컬 LLM
- **API 관리**: 토큰 사용량 최적화 및 오류 처리

### OCR 도구
- **엔진**: Tesseract, PaddleOCR, Cloud Vision API
- **전처리**: 이미지 품질 향상, 노이즈 제거
- **후처리**: 텍스트 정제 및 구조화

### Calendar 도구
- **API**: Google Calendar API
- **인증**: OAuth 2.0 사용자별 인증
- **기능**: 이벤트 생성, 수정, 삭제

### Email 도구
- **SMTP 서버**: Gmail, SendGrid 등
- **템플릿 엔진**: 사용자별 맞춤 이메일 생성
- **배치 처리**: 대량 이메일 효율적 전송

## 오류 처리 및 모니터링

### 오류 처리 전략
- **네트워크 오류**: 재시도 로직 및 백오프 전략
- **API 한도**: 요청 제한 관리 및 우선순위 큐
- **데이터 품질**: 유효성 검사 및 데이터 정제

### 모니터링 지표
- **처리 성공률**: 사이트별 크롤링 성공/실패율
- **응답 시간**: 각 처리 단계별 소요 시간
- **사용자 만족도**: 이메일 오픈율, 캘린더 이벤트 참여율

## 확장성 고려사항

### 수평적 확장
- **마이크로서비스**: 각 도구별 독립적 서비스 구성
- **메시지 큐**: 비동기 처리를 위한 Redis/RabbitMQ 활용
- **로드 밸런싱**: 다중 인스턴스 운영

### 성능 최적화
- **캐싱**: 중복 요청 방지를 위한 Redis 캐싱
- **배치 처리**: 유사한 작업의 일괄 처리
- **병렬 처리**: 멀티스레딩/멀티프로세싱 활용
