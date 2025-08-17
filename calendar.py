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
    - 종일(마감일 있음): YYYYMMDD/다음날YYYYMMDD
    - 시간(마감 없고 posted_at만): YYYYMMDDTHHMMSS/YYYYMMDDTHHMMSS  (로컬시간, ctz로 해석)
    - 날짜 전혀 없으면 None
    """
    deadline = _clean_date(item.get("deadline"))
    posted   = _clean_date(item.get("posted_at"))

    if deadline:
        y, m, d = map(int, deadline.split("-"))
        start = f"{y:04d}{m:02d}{d:02d}"
        end   = (date(y, m, d) + timedelta(days=1)).strftime("%Y%m%d")
        return f"{start}/{end}"

    if posted:
        dt = _to_dt(posted) or datetime.now(KST)
        start_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        end_dt   = start_dt + timedelta(hours=1)
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
        # ("location", enc(item.get("location") or "")),  # 있으면 사용
        ("ctz",    enc(tzid)),
    ]
    qs = "&".join(f"{k}={v}" for k, v in query if v)
    return f"https://calendar.google.com/calendar/render?{qs}"
