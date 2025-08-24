from __future__ import annotations
import os
import re
import time
import base64
import hashlib
import pathlib
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import date, datetime, timedelta, timezone

# 기본 상수/경로
KST = timezone(timedelta(hours=9))
DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Google Calendar OAuth 설정
GSCOPES = ["https://www.googleapis.com/auth/calendar"]
CRED_PATH = os.getenv("GCAL_CREDENTIALS", "tools/credentials.json")
TOKEN_PATH = os.getenv("GCAL_TOKEN", str(DATA_DIR / "gcal_token.json"))

# 기본 리마인더 (1일/3시간/30분 전 팝업)
DEFAULT_REMINDERS: List[Tuple[str, int]] = [
    ("popup", 1440),
    ("popup", 180),
    ("popup", 30),
]

# 공통 유틸
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _clean_date(x: Any) -> Optional[str]:
    """datetime/date/문자열을 'YYYY-MM-DD' 또는 None으로 정규화."""
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        if not s or s.lower() in ("null", "none", "nan"):
            return None
        return s
    if isinstance(x, (datetime, date)):
        return (x.date() if isinstance(x, datetime) else x).isoformat()
    return None

def _parse_date_range(text: str) -> Optional[Tuple[str, str]]:
    """
    기간 텍스트에서 시작일과 종료일을 추출.
    예: "2024.12.01 ~ 2024.12.31", "2024-12-01 ~ 2024-12-31"
    """
    if not text:
        return None
    
    # 다양한 구분자 패턴
    patterns = [
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s*[~∼~]\s*(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})',
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s*[-~]\s*(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})',
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s*부터\s*(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s*까지',
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s*-\s*(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})',
        # 한국어 기간 패턴들
        r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)\s*[-~]\s*(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)',
        r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)부터\s*(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)까지',
        r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)\s*[-~]\s*(\d{1,2}월\s*\d{1,2}일)',
        r'(\d{1,2}월\s*\d{1,2}일)\s*[-~]\s*(\d{1,2}월\s*\d{1,2}일)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            start_date = _normalize_date_string(match.group(1))
            end_date = _normalize_date_string(match.group(2))
            if start_date and end_date:
                return (start_date, end_date)
    
    return None

def _parse_datetime(text: str) -> Optional[Tuple[str, str]]:
    """
    날짜와 시간이 포함된 텍스트에서 날짜와 시간을 추출.
    예: "2024.12.31 18:00", "2024-12-31 18:00", "2025.09.23.(수) 17:00"
    """
    if not text:
        return None
    
    # 날짜 + 시간 패턴 (한국어 요일 포함)
    patterns = [
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}\.\([월화수목금토일]\))\s+(\d{1,2}:\d{2})',  # 2025.09.23.(수) 17:00
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}\s*\([월화수목금토일]\))\s+(\d{1,2}:\d{2})',   # 2025-09-23 (수) 17:00
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s+(\d{1,2}:\d{2})',  # 2024.12.31 18:00
        r'(\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2})\s+(\d{1,2}:\d{2}:\d{2})',  # 2024.12.31 18:00:00
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = _normalize_date_string(match.group(1))
            time_str = match.group(2)
            if date_str:
                return (date_str, time_str)
    
    return None

def _normalize_date_string(date_str: str) -> Optional[str]:
    """다양한 날짜 형식을 'YYYY-MM-DD'로 정규화."""
    if not date_str:
        return None
    
    # 점, 슬래시, 하이픈으로 구분된 날짜를 정규화
    date_str = date_str.strip()
    
    # 한국어 요일이 포함된 패턴들 처리
    korean_weekday_patterns = [
        r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.\([월화수목금토일]\)',  # 2025.09.23.(수)
        r'(\d{4})-(\d{1,2})-(\d{1,2})\s*\([월화수목금토일]\)',   # 2025-09-23 (수)
        r'(\d{4})/(\d{1,2})/(\d{1,2})\s*\([월화수목금토일]\)',   # 2025/09/23 (수)
    ]
    
    for pattern in korean_weekday_patterns:
        match = re.match(pattern, date_str)
        if match:
            y, mo, d = match.groups()
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    
    # 시간이 포함된 패턴들 처리
    time_patterns = [
        r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.\([월화수목금토일]\)\s+\d{1,2}:\d{1,2}',  # 2025.09.23.(수) 17:00
        r'(\d{4})-(\d{1,2})-(\d{1,2})\s*\([월화수목금토일]\)\s+\d{1,2}:\d{1,2}',   # 2025-09-23 (수) 17:00
        r'(\d{4})/(\d{1,2})/(\d{1,2})\s*\([월화수목금토일]\)\s+\d{1,2}:\d{1,2}',   # 2025/09/23 (수) 17:00
        r'(\d{4})-(\d{1,2})-(\d{1,2})\s+\d{1,2}:\d{1,2}',  # 2024-12-31 14:30
        r'(\d{4})\.(\d{1,2})\.(\d{1,2})\s+\d{1,2}:\d{1,2}', # 2024.12.31 14:30
        r'(\d{4})/(\d{1,2})/(\d{1,2})\s+\d{1,2}:\d{1,2}',   # 2024/12/31 14:30
    ]
    
    for pattern in time_patterns:
        match = re.match(pattern, date_str)
        if match:
            y, mo, d = match.groups()
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    
    # 2024.12.31 -> 2024-12-31
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    
    # 2024/12/31 -> 2024-12-31
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    
    # 2024-12-31 -> 그대로 반환
    if '-' in date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    
    # 한국어 날짜 형식 처리
    korean_patterns = [
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',  # 2024년 12월 31일
        r'(\d{1,2})월\s*(\d{1,2})일',  # 12월 31일 (현재 년도 사용)
    ]
    
    for pattern in korean_patterns:
        match = re.match(pattern, date_str)
        if match:
            if len(match.groups()) == 3:  # 년도 포함
                y, mo, d = match.groups()
                return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
            elif len(match.groups()) == 2:  # 년도 없음
                mo, d = match.groups()
                current_year = datetime.now().year
                return f"{current_year}-{mo.zfill(2)}-{d.zfill(2)}"
    
    return None

def _to_dt(x: Any) -> Optional[datetime]:
    """문자열 날짜를 datetime(KST)로 변환."""
    if isinstance(x, datetime):
        return x
    if isinstance(x, str) and x:
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(x, fmt).replace(tzinfo=KST)
            except Exception:
                pass
    return None

def _ext_id(item: Dict[str, Any]) -> str:
    """
    이벤트 고유키(중복 방지): 링크 + (마감일 or 제목) 해시.
    Google Calendar의 privateExtendedProperty에 저장/검색할 ID.
    """
    base = (item.get("link") or "") + "|" + (item.get("deadline") or item.get("title") or "")
    h = hashlib.sha1(base.encode("utf-8")).digest()
    return "as_" + base64.b32encode(h).decode("ascii").rstrip("=").lower()[:24]

# ICS 생성
def _ics_escape(text: str) -> str:
    """iCalendar 이스케이프. CR/LF 정규화 후 RFC에 맞게 처리."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def _crlf_join(lines: List[str]) -> str:
    """iCalendar는 CRLF 권장."""
    return "\r\n".join(lines) + "\r\n"

def _ics_uid(item: Dict[str, Any]) -> str:
    return _ext_id(item) + "@autoscheduler"

def _ics_event(item: Dict[str, Any], tzid: str = "Asia/Seoul") -> str:
    """
    VEVENT 1개를 문자열로 생성.
    - deadline: 단일 날짜, 기간, 또는 날짜+시간 처리
    - 없으면 ""(스킵)
    """
    title = (item.get("title") or "").strip() or "제목 없음"
    link = (item.get("link") or "").strip()
    source = (item.get("source") or "").strip()
    cat = (item.get("category") or "").strip()
    posted = _clean_date(item.get("posted_at"))
    deadline_raw = item.get("deadline")

    # 일정 정보가 전혀 없으면 스킵
    if not deadline_raw and not posted:
        return ""

    # 설명 구성
    desc_lines: List[str] = []
    if cat:
        desc_lines.append(f"[카테고리] {cat}")
    if link:
        desc_lines.append(link)
    if item.get("summary"):
        if desc_lines:
            desc_lines.append("")
        desc_lines.append(item["summary"])
    description = _ics_escape("\n".join(desc_lines)) if desc_lines else ""

    uid = _ics_uid(item)
    dtstamp = _now_utc().strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{_ics_escape(title)}",
    ]

    # deadline 처리: 기간, 날짜+시간, 단일 날짜 순서로 확인
    if deadline_raw:
        deadline_str = str(deadline_raw).strip()
        
        # 1. 기간인지 확인 (예: "2024.12.01 ~ 2024.12.31")
        date_range = _parse_date_range(deadline_str)
        if date_range:
            start_date, end_date = date_range
            start_s = start_date.replace("-", "")
            end_s = end_date.replace("-", "")
            lines.append(f"DTSTART;VALUE=DATE:{start_s}")
            lines.append(f"DTEND;VALUE=DATE:{end_s}")
        
        # 2. 날짜+시간인지 확인 (예: "2024.12.31 18:00")
        elif _parse_datetime(deadline_str):
            date_part, time_part = _parse_datetime(deadline_str)
            datetime_str = f"{date_part}T{time_part}:00"
            start_dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
            end_dt = start_dt + timedelta(hours=1)
            
            start_s = start_dt.strftime("%Y%m%dT%H%M%S")
            end_s = end_dt.strftime("%Y%m%dT%H%M%S")
            lines.append(f"DTSTART:{start_s}")
            lines.append(f"DTEND:{end_s}")
        
        # 3. 단일 날짜인지 확인
        else:
            deadline = _clean_date(deadline_raw)
            if deadline:
                y, m, d = map(int, deadline.split("-"))
                start_s = f"{y:04d}{m:02d}{d:02d}"
                end_s = (date(y, m, d) + timedelta(days=1)).strftime("%Y%m%d")
                lines.append(f"DTSTART;VALUE=DATE:{start_s}")
                lines.append(f"DTEND;VALUE=DATE:{end_s}")
    
    # deadline이 없으면 posted_at 사용
    elif posted:
        y, m, d = map(int, posted.split("-"))
        start_s = f"{y:04d}{m:02d}{d:02d}"
        end_s = (date(y, m, d) + timedelta(days=1)).strftime("%Y%m%d")
        lines.append(f"DTSTART;VALUE=DATE:{start_s}")
        lines.append(f"DTEND;VALUE=DATE:{end_s}")

    if description:
        lines.append(f"DESCRIPTION:{description}")
    lines.append(f"CATEGORIES:{_ics_escape(source or 'AutoScheduler')}")
    lines.append("END:VEVENT")
    return _crlf_join(lines)

def items_to_ics(
    items: Iterable[Dict[str, Any]],
    calendar_name: str = "AutoScheduler",
    tzid: str = "Asia/Seoul",
    include_without_deadline: bool = True,
) -> str:
    """
    items → VCALENDAR 문자열 생성.
    - include_without_deadline=False면 deadline 없는 항목은 스킵
    - UID 중복 방지
    """
    body_parts: List[str] = []
    seen_uids: set[str] = set()

    for it in items:
        if not include_without_deadline and not _clean_date(it.get("deadline")):
            continue
        vevent = _ics_event(it, tzid=tzid)
        if not vevent:
            continue
        uid = _ics_uid(it)
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        body_parts.append(vevent)

    header = [
        "BEGIN:VCALENDAR",
        "PRODID:-//AutoScheduler//SSU//KR",
        "VERSION:2.0",
        f"X-WR-CALNAME:{_ics_escape(calendar_name)}",
        f"X-WR-TIMEZONE:{tzid}",
    ]
    footer = ["END:VCALENDAR"]

    return _crlf_join(header) + "".join(body_parts) + _crlf_join(footer)

def write_ics(
    path: str,
    items: Iterable[Dict[str, Any]],
    calendar_name: str = "AutoScheduler",
    tzid: str = "Asia/Seoul",
    include_without_deadline: bool = True,
) -> str:
    """ICS 파일로 저장."""
    ics = items_to_ics(items, calendar_name, tzid, include_without_deadline)
    pathlib.Path(path).write_text(ics, encoding="utf-8", newline="\r\n")
    return path

# Google Calendar API (OAuth 업서트)
def _ensure_service():
    """OAuth 토큰 확보 후 Calendar API 서비스 핸들 반환."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from google.auth.exceptions import RefreshError

    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, GSCOPES)
        except Exception as e:
            print(f"Error loading token file: {e}")
            # 토큰 파일이 손상된 경우 삭제
            os.remove(TOKEN_PATH)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                print(f"Token refresh failed: {e}")
                # 토큰 갱신 실패 시 파일 삭제하고 새로 인증
                if os.path.exists(TOKEN_PATH):
                    os.remove(TOKEN_PATH)
                creds = None
        
        if not creds:
            if not os.path.exists(CRED_PATH):
                raise FileNotFoundError(f"Google OAuth credentials not found: {CRED_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, GSCOPES)
            creds = flow.run_local_server(port=0)  # 최초 1회 브라우저 인증
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def _build_event_body(
    item: Dict[str, Any],
    tzid: str = "Asia/Seoul",
    reminders: Optional[List[Tuple[str, int]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Google Calendar 이벤트 바디 생성.
    - deadline: 단일 날짜, 기간, 또는 날짜+시간 처리
    - 날짜가 전혀 없으면 None 반환(스킵)
    """
    title = (item.get("title") or "").strip() or "제목 없음"
    link = (item.get("link") or "").strip()
    source = (item.get("source") or "").strip()
    cat = (item.get("category") or "").strip()
    posted = _clean_date(item.get("posted_at"))
    deadline_raw = item.get("deadline")
    ext_id = _ext_id(item)

    if not deadline_raw and not posted:
        return None

    desc_lines: List[str] = []
    if cat:
        desc_lines.append(f"[카테고리] {cat}")
    if link:
        desc_lines.append(link)
    if item.get("summary"):
        desc_lines.append("")
        desc_lines.append(item["summary"])
    description = "\n".join(desc_lines) if desc_lines else None

    # deadline 처리: 기간, 날짜+시간, 단일 날짜 순서로 확인
    start = None
    end = None
    
    if deadline_raw:
        deadline_str = str(deadline_raw).strip()
        
        # 1. 기간인지 확인 (예: "2024.12.01 ~ 2024.12.31")
        date_range = _parse_date_range(deadline_str)
        if date_range:
            start_date, end_date = date_range
            start = {"date": start_date, "timeZone": tzid}
            end = {"date": end_date, "timeZone": tzid}
        
        # 2. 날짜+시간인지 확인 (예: "2024.12.31 18:00")
        elif _parse_datetime(deadline_str):
            date_part, time_part = _parse_datetime(deadline_str)
            datetime_str = f"{date_part}T{time_part}:00"
            start = {"dateTime": datetime_str, "timeZone": tzid}
            # 기본 1시간 이벤트
            end_dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=1)
            end = {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tzid}
        
        # 3. 단일 날짜인지 확인
        else:
            deadline = _clean_date(deadline_raw)
            if deadline:
                y, m, d = map(int, deadline.split("-"))
                start = {"date": f"{y:04d}-{m:02d}-{d:02d}", "timeZone": tzid}
                end = {"date": (date(y, m, d) + timedelta(days=1)).isoformat(), "timeZone": tzid}
    
    # deadline이 없으면 posted_at 사용
    if not start and posted:
        y, m, d = map(int, posted.split("-"))
        start = {"date": f"{y:04d}-{m:02d}-{d:02d}", "timeZone": tzid}
        end = {"date": (date(y, m, d) + timedelta(days=1)).isoformat(), "timeZone": tzid}

    if not start:
        return None
    
    # deadline이 없으면 posted_at 사용
    if not start and posted:
        y, m, d = map(int, posted.split("-"))
        start = {"date": f"{y:04d}-{m:02d}-{d:02d}", "timeZone": tzid}
        end = {"date": (date(y, m, d) + timedelta(days=1)).isoformat(), "timeZone": tzid}

    if not start:
        return None

    if reminders is None:
        reminders = DEFAULT_REMINDERS

    return {
        "summary": title,
        "start": start,
        "end": end,
        "source": {"title": source or "AutoScheduler", "url": link or None},
        "description": description,
        "extendedProperties": {"private": {"autoscheduler_id": ext_id}},
        "reminders": {"useDefault": False, "overrides": [{"method": m, "minutes": mins} for m, mins in reminders]},
    }

def _find_existing_by_ext(service, calendar_id: str, ext_id: str) -> Optional[Dict[str, Any]]:
    """privateExtendedProperty(autoscheduler_id)로 기존 이벤트 조회."""
    resp = service.events().list(
        calendarId=calendar_id,
        privateExtendedProperty=f"autoscheduler_id={ext_id}",
        singleEvents=True,
        maxResults=1,
    ).execute()
    items = resp.get("items", [])
    return items[0] if items else None

def upsert_to_gcal(
    items: Iterable[Dict[str, Any]],
    calendar_id: str = "primary",
    tzid: str = "Asia/Seoul",
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    items를 구글 캘린더에 업서트.
    - 중복 기준: extendedProperties.private.autoscheduler_id
    - 날짜 전혀 없는 항목은 스킵
    """
    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError

    try:
        service = _ensure_service()
    except Exception as e:
        print(f"Failed to initialize Google Calendar service: {e}")
        raise Exception(f"Google Calendar 인증 실패: {str(e)}")

    stats = {"created": 0, "updated": 0, "skipped": 0}

    for it in items:
        try:
            body = _build_event_body(it, tzid=tzid)
            if body is None:
                stats["skipped"] += 1
                continue

            ext_id = body["extendedProperties"]["private"]["autoscheduler_id"]
            ex = _find_existing_by_ext(service, calendar_id, ext_id)

            if ex:
                if dry_run:
                    stats["updated"] += 1
                else:
                    service.events().update(calendarId=calendar_id, eventId=ex["id"], body=body).execute()
                    stats["updated"] += 1
            else:
                if dry_run:
                    stats["created"] += 1
                else:
                    service.events().insert(
                        calendarId=calendar_id,
                        body=body,
                        supportsAttachments=False,
                    ).execute()
                    stats["created"] += 1

            time.sleep(0.1)  # QPS 조절
        except HttpError as e:
            print(f"HTTP error for item {it.get('title', 'Unknown')}: {e}")
            stats["skipped"] += 1
        except RefreshError as e:
            print(f"Token refresh error: {e}")
            raise Exception("Google Calendar 토큰이 만료되었습니다. 다시 인증해주세요.")
        except Exception as e:
            print(f"Unexpected error for item {it.get('title', 'Unknown')}: {e}")
            stats["skipped"] += 1
    return stats
