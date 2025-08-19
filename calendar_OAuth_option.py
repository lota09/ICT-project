from __future__ import annotations
import os
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
    - deadline 있으면 종일 이벤트
    - deadline 없고 posted_at 있으면 09:00~10:00 이벤트
    - 둘 다 없으면 ""(스킵)
    """
    title = (item.get("title") or "").strip() or "제목 없음"
    link = (item.get("link") or "").strip()
    source = (item.get("source") or "").strip()
    cat = (item.get("category") or "").strip()
    posted = _clean_date(item.get("posted_at"))
    deadline = _clean_date(item.get("deadline"))

    # 일정 정보가 전혀 없으면 스킵
    if not deadline and not posted:
        return ""

    # 설명 구성
    desc_lines: List[str] = []
    if cat:
        desc_lines.append(f"[카테고리] {cat}")
    if posted:
        desc_lines.append(f"[게시일] {posted}")
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

    if deadline:
        # 종일 이벤트: DTEND는 다음날
        y, m, d = map(int, deadline.split("-"))
        start_s = f"{y:04d}{m:02d}{d:02d}"
        end_s = (date(y, m, d) + timedelta(days=1)).strftime("%Y%m%d")
        lines.append(f"DTSTART;VALUE=DATE:{start_s}")
        lines.append(f"DTEND;VALUE=DATE:{end_s}")
    else:
        # posted_at 기반 09:00~10:00
        dt = _to_dt(posted) or datetime.now(KST)
        start_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=1)
        lines.append(f"DTSTART;TZID={tzid}:{start_dt.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"DTEND;TZID={tzid}:{end_dt.strftime('%Y%m%dT%H%M%S')}")

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

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, GSCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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
    - deadline 종일 이벤트, 아니면 posted_at 기반 09:00~10:00
    - 날짜가 전혀 없으면 None 반환(스킵)
    """
    title = (item.get("title") or "").strip() or "제목 없음"
    link = (item.get("link") or "").strip()
    source = (item.get("source") or "").strip()
    cat = (item.get("category") or "").strip()
    posted = _clean_date(item.get("posted_at"))
    deadline = _clean_date(item.get("deadline"))
    ext_id = _ext_id(item)

    if not deadline and not posted:
        return None

    desc_lines: List[str] = []
    if cat:
        desc_lines.append(f"[카테고리] {cat}")
    if posted:
        desc_lines.append(f"[게시일] {posted}")
    if link:
        desc_lines.append(link)
    if item.get("summary"):
        desc_lines.append("")
        desc_lines.append(item["summary"])
    description = "\n".join(desc_lines) if desc_lines else None

    if deadline:
        y, m, d = map(int, deadline.split("-"))
        start = {"date": f"{y:04d}-{m:02d}-{d:02d}", "timeZone": tzid}
        end = {"date": (date(y, m, d) + timedelta(days=1)).isoformat(), "timeZone": tzid}
    else:
        dt = _to_dt(posted) or datetime.now(KST)
        start_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=1)
        start = {"dateTime": start_dt.isoformat(), "timeZone": tzid}
        end = {"dateTime": end_dt.isoformat(), "timeZone": tzid}

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

    service = _ensure_service()
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
        except HttpError:
            stats["skipped"] += 1
        except Exception:
            stats["skipped"] += 1
    return stats
