from __future__ import annotations
import hashlib, base64, pathlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone, date
from urllib.parse import quote

# ---------- 공통 util ----------
KST = timezone(timedelta(hours=9))
DATA_DIR = pathlib.Path("data"); DATA_DIR.mkdir(exist_ok=True)

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _clean_date(x: Any) -> Optional[str]:
    if x is None: return None
    if isinstance(x, str):
        s = x.strip()
        if not s or s.lower() in ("null","none","nan"): return None
        return s
    if isinstance(x, (datetime, date)):
        return (x.date() if isinstance(x, datetime) else x).isoformat()
    return None

def _parse_date_range(text: str) -> Optional[tuple[str, str]]:
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
    
    import re
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            start_date = _normalize_date_string(match.group(1))
            end_date = _normalize_date_string(match.group(2))
            if start_date and end_date:
                return (start_date, end_date)
    
    return None

def _parse_datetime(text: str) -> Optional[tuple[str, str]]:
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
    
    import re
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
    
    import re
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
    if isinstance(x, datetime):
        return x
    if isinstance(x, str) and x:
        for fmt in ("%Y-%m-%d","%Y.%m.%d","%Y/%m/%d"):
            try:
                return datetime.strptime(x, fmt).replace(tzinfo=KST)
            except Exception:
                pass
    return None

def _ext_id(item: Dict[str, Any]) -> str:
    base = (item.get("link") or "") + "|" + (item.get("deadline") or item.get("title") or "")
    h = hashlib.sha1(base.encode("utf-8")).digest()
    return "as_" + base64.b32encode(h).decode("ascii").rstrip("=").lower()[:24]

def _format_dates_for_gcal(item: Dict[str, Any], tzid: str="Asia/Seoul") -> Optional[str]:
    """
    구글 캘린더 'dates' 파라미터 문자열 반환.
    - 기간(시작일~종료일): YYYYMMDD/YYYYMMDD
    - 종일(단일 마감일): YYYYMMDD/다음날YYYYMMDD
    - 시간(날짜+시간): YYYYMMDDTHHMMSS/YYYYMMDDTHHMMSS
    - 날짜 전혀 없으면 None
    """
    deadline_raw = item.get("deadline", "")
    posted = _clean_date(item.get("posted_at"))

    # 1. 기간 처리 (시작일~종료일)
    if deadline_raw and ("~" in deadline_raw or "∼" in deadline_raw or "부터" in deadline_raw or "까지" in deadline_raw):
        date_range = _parse_date_range(deadline_raw)
        if date_range:
            start_date, end_date = date_range
            start_y, start_m, start_d = map(int, start_date.split("-"))
            end_y, end_m, end_d = map(int, end_date.split("-"))
            start_str = f"{start_y:04d}{start_m:02d}{start_d:02d}"
            end_str = f"{end_y:04d}{end_m:02d}{end_d:02d}"
            return f"{start_str}/{end_str}"

    # 2. 날짜+시간 처리 (예: 2025.09.23.(수) 17:00)
    if deadline_raw and (":" in deadline_raw or "시" in deadline_raw):
        datetime_result = _parse_datetime(deadline_raw)
        if datetime_result:
            date_str, time_str = datetime_result
            y, m, d = map(int, date_str.split("-"))
            
            # 시간 파싱
            if ":" in time_str:
                hour, minute = map(int, time_str.split(":"))
                start_dt = datetime(y, m, d, hour, minute, 0, tzinfo=KST)
                end_dt = start_dt + timedelta(hours=1)  # 기본 1시간
                
                start_str = start_dt.strftime("%Y%m%dT%H%M%S")
                end_str = end_dt.strftime("%Y%m%dT%H%M%S")
                return f"{start_str}/{end_str}"

    # 3. 단일 날짜 처리 (종일 이벤트)
    deadline = _clean_date(deadline_raw)
    if deadline:
        y, m, d = map(int, deadline.split("-"))
        start = f"{y:04d}{m:02d}{d:02d}"
        end = (date(y, m, d) + timedelta(days=1)).strftime("%Y%m%d")
        return f"{start}/{end}"

    # 4. 게시일로 대체 (기본값)
    if posted:
        dt = _to_dt(posted) or datetime.now(KST)
        start_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=1)
        s = start_dt.strftime("%Y%m%dT%H%M%S")
        e = end_dt.strftime("%Y%m%dT%H%M%S")
        return f"{s}/{e}"

    return None

def build_gcal_link(item: Dict[str, Any], tzid: str="Asia/Seoul") -> str:
    """
    구글 캘린더 '새 일정' 화면으로 여는 링크 생성.
    - action=TEMPLATE 사용 
    - ctz 파라미터로 타임존 전달
    - 제목/본문/링크/카테고리 포함
    - 날짜 없으면 빈 문자열 반환
    """
    dates = _format_dates_for_gcal(item, tzid=tzid)
    if not dates:
        return ""

    title = (item.get("title") or "제목 없음").strip()
    link  = (item.get("link") or "").strip()
    cat   = (item.get("category") or "").strip()
    posted= _clean_date(item.get("posted_at"))

    # details(본문)
    lines = []
    if cat:    lines.append(f"[카테고리] {cat}")
    if posted: lines.append(f"[게시일] {posted}")
    if link:   lines.append(link)
    if item.get("summary"):
        if lines: lines.append("")
        lines.append(item["summary"])
    details = "\n".join(lines)

    # 수동 인코딩: dates 값의 '/'와 'T'는 살려야 해서 별도 처리
    def enc(v: str, *, keep_slash=False) -> str:
        if v is None: return ""
        safe = "/T:-_." if keep_slash else "-_.~"
        return quote(v, safe=safe)

    query = [
        ("action", "TEMPLATE"),
        ("text",   enc(title)),
        ("dates",  enc(dates, keep_slash=True)),  # 슬래시는 보존
        ("details",enc(details)),
        ("ctz",    enc(tzid)),
    ]
    qs = "&".join(f"{k}={v}" for k, v in query if v)
    gcal_url= f"https://calendar.google.com/calendar/render?{qs}"
    return gcal_url
