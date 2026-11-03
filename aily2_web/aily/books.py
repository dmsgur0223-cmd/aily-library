"""Rules-based first pass for library acquisition requests.

No remote services, file system persistence, or PII logging in this module.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, date
from dataclasses import dataclass
from io import BytesIO
import re
from typing import Optional

import pandas as pd

# Source: user-provided 희망도서 신청/선정 기준, 2026-10-21.
POLICY = {
    "price_limit": 30_000,
    "years": 5,
    "monthly_count": 2,
    "four_libraries": 4,
}

BOOK_COLUMNS = ["서명", "저자", "발행자", "발행년", "가격", "ISBN", "도서관명", "신청일자", "주제구분", "작업비고"]
RESULT_COLUMNS = ["원본행", "도서관명", "신청일자", "서명", "저자", "발행자", "발행년", "가격", "ISBN", "주제구분", "월신청순서", "1차판정", "판정사유", "적용기준", "추가확인", "2차판정", "2차근거", "서지설명", "서지출처", "YES24상품링크", "신청취소사유", "최종처리", "AI분석", "AI근거"]
# Never export applicant names, user IDs, mobile numbers, addresses or DOBs.
@dataclass(frozen=True)
class BookFilterSettings:
    """User-chosen criteria, not a statutory or institution-wide default.

    Month-based age checks require a real publication month; a year-only value
    at the boundary must be held for verification, not silently assumed.
    """
    price_enabled: bool = True
    price_limit: int = 30_000
    year_enabled: bool = True
    max_age_years: int = 5
    month_precision: bool = False
    extra_months: int = 0
    cross_library_duplicate_enabled: bool = False
    monthly_limit_enabled: bool = False
    monthly_limit_count: int = 2
    holdings_enabled: bool = False
    holdings_limit: int = 4
    second_enabled: bool = True
    second_categories: tuple[str, ...] = (
        '수험서·자격증 교재', '문제집·기출문제집', '교과서·학습참고서·전공교재',
        '사전·연감·백서·보고서', '악보집·대본집·전시도록',
        '퍼즐북·스티커북·컬러링북', '워크북·쓰기익힘책·필사책',
    )

    def __post_init__(self):
        if not isinstance(self.price_limit, int) or self.price_limit < 0 or self.price_limit % 1000:
            raise ValueError("가격 상한은 1,000원 단위의 0 이상 정수여야 합니다.")
        if not isinstance(self.max_age_years, int) or not 0 <= self.max_age_years <= 100:
            raise ValueError("발행 연수는 0~100년 범위여야 합니다.")
        if not isinstance(self.extra_months, int) or not 0 <= self.extra_months <= 11:
            raise ValueError("추가 개월 수는 0~11개월이어야 합니다.")
        if not isinstance(self.monthly_limit_count, int) or not 1 <= self.monthly_limit_count <= 100:
            raise ValueError("월 신청권수는 1~100권으로 설정해야 합니다.")
        if not isinstance(self.holdings_limit, int) or not 1 <= self.holdings_limit <= 100:
            raise ValueError("통합 소장 도서관 수 기준은 1~100개관이어야 합니다.")
        from .qualifications import STUDY_CATEGORIES
        if not set(self.second_categories).issubset(STUDY_CATEGORIES):
            raise ValueError("지원하지 않는 2차 검사 유형입니다.")


PRIVATE_COLUMNS = {"신청자", "대출자번호", "주소", "생년월일", "휴대폰번호", "대출자명", "연락처"}


def normalize_isbn(value) -> str:
    if value is None or pd.isna(value):
        return ""
    v = str(value).strip()
    if re.fullmatch(r"\d+\.0", v):
        v = v[:-2]
    return re.sub(r"[^0-9Xx]", "", v).upper()


def _text(value) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def _amount(value) -> Optional[int]:
    if value is None or pd.isna(value):
        return None
    raw = re.sub(r"[\s,원₩]", "", str(value))
    try:
        number = float(raw)
        if not number.is_integer() or number < 0:
            return None
        return int(number)
    except ValueError:
        return None


def _year(value) -> Optional[int]:
    if value is None or pd.isna(value):
        return None
    m = re.match(r"^\s*(\d{4})", str(value))
    return int(m.group(1)) if m else None


def _month(value) -> Optional[str]:
    try:
        ts = pd.to_datetime(value, errors="coerce")
        return ts.strftime("%Y-%m") if not pd.isna(ts) else None
    except Exception:
        return None


def _publication_month(row: pd.Series) -> Optional[tuple[int, int]]:
    """Use only an explicitly supplied publication month, never infer January."""
    for column in ("발행년월", "발행일", "출판년월", "출판일", "발행년"):
        value = row.get(column)
        if value is None or pd.isna(value):
            continue
        if isinstance(value, (datetime, date, pd.Timestamp)):
            return (value.year, value.month)
        raw = str(value).strip()
        match = re.match(r"^(\d{4})\s*(?:[-./]|년\s*)(\d{1,2})(?:\D|$)", raw)
        if not match and re.fullmatch(r"\d{6}", raw):
            match = re.match(r"^(\d{4})(\d{2})$", raw)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12:
                return year, month
    year, month = _year(row.get("발행년")), row.get("발행월")
    if year is not None:
        try:
            m = int(str(month).strip())
            if 1 <= m <= 12:
                return year, m
        except (TypeError, ValueError):
            pass
    return None


def _oldest_month(as_of: date, settings: BookFilterSettings) -> tuple[int, int]:
    total = as_of.year * 12 + as_of.month - 1 - 12 * settings.max_age_years - settings.extra_months
    return divmod(total, 12)[0], divmod(total, 12)[1] + 1


def prepare_general_candidates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """No agency names, cross-library deduplication, or borrower monthly limits."""
    if "비치상태" not in df:
        return df.copy().reset_index(drop=True), {"검토 대상": len(df)}
    cancelled = df["비치상태"].map(lambda v: any(x in _text(v) for x in CANCEL_KEYWORDS))
    result = df.loc[~cancelled].copy().reset_index(drop=True)
    return result, {"취소·반려 제외": int(cancelled.sum()), "검토 대상": len(result)}


def detect_header(raw: pd.DataFrame) -> int:
    for i in range(min(30, len(raw))):
        row = {_text(x) for x in raw.iloc[i].tolist()}
        if {"서명", "저자", "발행자"}.issubset(row):
            return i
    raise ValueError("엑셀에서 '서명 / 저자 / 발행자' 머리글 행을 찾지 못했습니다.")


def load_candidates(file_bytes: bytes) -> pd.DataFrame:
    """Read LMS exports with preamble (sample uses header on Excel row 6).

    Raw private columns remain in memory only for count checks; exported results are allowlisted.
    """
    raw = pd.read_excel(BytesIO(file_bytes), header=None, dtype=object)
    header = detect_header(raw)
    df = pd.read_excel(BytesIO(file_bytes), header=header, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    if "서명" not in df:
        raise ValueError("'서명' 열이 없습니다.")
    df = df.loc[df["서명"].notna()].copy()
    df = df.loc[df["서명"].astype(str).str.strip() != ""].copy()
    df["_원본행"] = df.index.to_series().astype(int) + header + 2
    return df.reset_index(drop=True)


def load_holdings(file_bytes: bytes) -> dict[str, set[str]]:
    """Optional integrated holdings file: ISBN and 도서관명/소장도서관 columns.

    A delimited list of libraries in a single cell is supported as a convenience.
    """
    df = pd.read_excel(BytesIO(file_bytes), dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    library_col = next((c for c in ["도서관명", "소장도서관", "소장관", "도서관"] if c in df), None)
    if "ISBN" not in df or not library_col:
        raise ValueError("통합소장 파일은 'ISBN'과 '도서관명' 또는 '소장도서관' 열이 필요합니다.")
    out: dict[str, set[str]] = defaultdict(set)
    for _, row in df.iterrows():
        isbn = normalize_isbn(row.get("ISBN"))
        if not isbn:
            continue
        names = re.split(r"[,;/|\n]", _text(row.get(library_col)))
        for name in names:
            name = name.strip()
            if name:
                out[isbn].add(name)
    return out


GENERAL_LIBRARIES = ("검암", "아라누리", "단봉늘봄", "검단", "석남", "심곡", "신석")
CANCEL_KEYWORDS = ("취소", "반려")


def _received(value):
    """Return a timestamp or NaT; never infer missing time or reorder by input row."""
    try:
        return pd.to_datetime(value, errors="coerce")
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def _library_type(value: str) -> str:
    name = _text(value).replace(" ", "")
    if "스마트" in name or "예약대출기" in name:
        return "스마트/거점"
    if name and any(label in name for label in GENERAL_LIBRARIES) and "도서관" in name:
        return "일반 구립도서관"
    return "도서관명 확인 필요"


def prepare_month(df: pd.DataFrame, today: Optional[date] = None):
    """Limit scope to current calendar month, excluding smart/other service points.

    Return data AND the exclusion stats; no user identifiers appear in stats.
    """
    today = today or date.today()
    rows = []
    stats = Counter()
    for _, row in df.iterrows():
        when = _received(row.get("신청일자"))
        lib_type = _library_type(row.get("도서관명")) if "도서관명" in df else "도서관명 확인 필요"
        if pd.isna(when):
            stats["신청일시 누락/오류"] += 1
            continue
        if (when.year, when.month) != (today.year, today.month):
            stats["다른 월 신청"] += 1
            continue
        if when.date() > today:
            stats["기준일 이후 신청"] += 1
            continue
        if lib_type == "스마트/거점":
            stats["스마트도서관/거점 제외"] += 1
            continue
        if lib_type != "일반 구립도서관":
            stats["도서관명 미확인"] += 1
            continue
        status = _text(row.get("비치상태"))
        if any(word in status for word in CANCEL_KEYWORDS):
            stats["취소·반려 제외"] += 1
            continue
        rows.append(row.name)
    subset = df.loc[rows].copy().reset_index(drop=True)
    stats["당월 일반 구립도서관 유효 신청"] = len(subset)
    return subset, dict(stats)


def _count_order(df: pd.DataFrame):
    """Return per-row (rank, warning) using member+month; ties at cutoff are ambiguous."""
    result = {}
    groups = defaultdict(list)
    for i, row in df.iterrows():
        member = _text(row.get("대출자번호"))
        ts = _received(row.get("신청일자"))
        if member and not pd.isna(ts):
            groups[(member, ts.year, ts.month)].append((ts, i))
        else:
            result[i] = (None, "회원번호 또는 접수시각 누락")
    for _, pairs in groups.items():
        pairs.sort(key=lambda x: x[0])
        for n, (ts, index) in enumerate(pairs, 1):
            same = [j for t, j in pairs if t == ts]
            lower = sum(t < ts for t, _ in pairs)
            tied_cutoff = len(same) > 1 and lower < POLICY["monthly_count"] < lower + len(same)
            result[index] = (n, "신청시각 동률로 2권 경계 순서 확인 필요" if tied_cutoff else "")
    return result


def _source_checks(df: pd.DataFrame, settings: BookFilterSettings) -> dict[int, dict]:
    """Per-upload cross-branch application checks; member numbers never leave memory.

    Only valid non-cancelled application records count. No inference about missing
    branches or months; a missing applicant/date/ISBN is not treated as a pass.
    """
    facts = {int(i): {} for i in df.index}
    if not (settings.cross_library_duplicate_enabled or settings.monthly_limit_enabled):
        return facts
    groups = defaultdict(list)
    books = defaultdict(list)
    for i, row in df.iterrows():
        member = _text(row.get('대출자번호'))
        when = _received(row.get('신청일자'))
        library = _text(row.get('도서관명'))
        if not member or pd.isna(when) or not library or _library_type(library) == '스마트/거점':
            facts[i]['missing'] = '대출자번호·신청일시·도서관명 중 누락 또는 스마트/거점 자료'
            continue
        key = (member, when.year, when.month)
        groups[key].append((when, i))
        isbn = normalize_isbn(row.get('ISBN'))
        if len(isbn) in (10, 13):
            books[(*key, isbn)].append((when, i, library))
        elif settings.cross_library_duplicate_enabled:
            facts[i]['missing_isbn'] = True
    for pairs in groups.values():
        pairs.sort(key=lambda x: (x[0], x[1]))
        for index, (when, row_id) in enumerate(pairs):
            earlier = sum(timestamp < when for timestamp, _ in pairs)
            rank = index + 1
            # At the cutoff, simultaneous requests cannot be time-ranked reliably.
            boundary = (earlier < settings.monthly_limit_count < earlier + sum(ts == when for ts, _ in pairs))
            facts[row_id]['rank'] = rank
            if boundary:
                facts[row_id]['tie'] = True
            elif earlier >= settings.monthly_limit_count:
                facts[row_id]['over_limit'] = True
    for pairs in books.values():
        if len(pairs) < 2:
            continue
        pairs.sort(key=lambda x: (x[0], x[1]))
        for _, row_id, library in pairs[1:]:
            facts[row_id]['duplicate'] = True
            facts[row_id]['duplicate_scope'] = '타 구립도서관 포함' if any(x[2] != library for x in pairs) else '동일 도서관'
    return facts


def _cancel_text(reasons: list[str]) -> str:
    if not reasons:
        return ""
    clean = "; ".join(reasons)
    return ("신청하신 도서는 희망도서 구입기준 검토 결과, " + clean +
            " 사유로 선정 제외 기준에 해당합니다. 담당자 확인 후 최종 처리 결과를 안내드리겠습니다.")


def review_requests(
    df: pd.DataFrame,
    holdings: Optional[dict[str, set[str]]] = None,
    complete_monthly_data: bool = False,
    today: Optional[date] = None,
    settings: Optional[BookFilterSettings] = None,
    complete_holdings_data: bool = False,
) -> pd.DataFrame:
    """Rule-based 1st pass. Passing settings opts in to institution-neutral checks.

    Calls without settings preserve legacy institution-specific behavior for
    existing offline integrations; the 4.8.1 UI always supplies settings.
    """
    today = today or date.today()
    legacy = settings is None
    settings = settings or BookFilterSettings()
    if legacy:
        df, _ = prepare_month(df, today)
        order = _count_order(df)
    else:
        df, _ = prepare_general_candidates(df)
        order = {}
    source_facts = _source_checks(df, settings) if not legacy else {}
    out = []
    for idx, row in df.iterrows():
        amount = _amount(row.get("가격"))
        published_month = _publication_month(row)
        year = _year(row.get("발행년"))
        if year is None and published_month is not None:
            year = published_month[0]
        title = _text(row.get("서명"))
        isbn = normalize_isbn(row.get("ISBN"))
        reasons, checks, criteria = [], [], []
        exclude = False
        missing_essentials = []
        if settings.price_enabled:
            criteria.append(f"정가 {settings.price_limit:,}원 이하")
            if amount is None:
                missing_essentials.append("정가 누락/오류")
                checks.append("정가 확인 필요")
            elif amount > settings.price_limit:
                exclude = True
                reasons.append(f"정가 {amount:,}원으로 설정 상한 {settings.price_limit:,}원 초과")
        if settings.year_enabled:
            limit_year = today.year - settings.max_age_years
            criteria.append(
                f"발행 {settings.max_age_years}년 {settings.extra_months}개월 이내 (연·월 기준)"
                if settings.month_precision else f"발행연도 {limit_year}년 이후"
            )
            if year is None:
                missing_essentials.append("발행연도 누락/오류")
                checks.append("발행연도 확인 필요")
            elif year > today.year:
                missing_essentials.append("미래 발행연도")
                checks.append("미래 발행연도: 입력 오류 확인")
            elif settings.month_precision:
                published = published_month
                oldest = _oldest_month(today, settings)
                if year < oldest[0]:
                    exclude = True
                    reasons.append(f"{year}년 발행: 최소 허용 발행월 {oldest[0]}-{oldest[1]:02d} 이전")
                elif year == oldest[0] and published is None:
                    missing_essentials.append(f"발행월 누락: {oldest[0]}년은 월 확인 필요")
                    checks.append("발행월 정보가 있어야 연·월 기준을 판정할 수 있음")
                elif published:
                    if published > (today.year, today.month):
                        missing_essentials.append("미래 발행월")
                        checks.append("미래 발행월: 입력 오류 확인")
                    elif published < oldest:
                        exclude = True
                        reasons.append(f"{published[0]}-{published[1]:02d} 발행: 최소 허용 {oldest[0]}-{oldest[1]:02d} 이전")
            elif year < limit_year:
                exclude = True
                reasons.append(f"{year}년 발행: 최소 허용 연도 {limit_year}년 이전")
        rank = None
        if legacy:
            rank, warning = order.get(idx, (None, "신청자/접수일 정보 부족"))
            if warning:
                missing_essentials.append(warning)
                checks.append(warning)
            elif rank is not None and rank > POLICY["monthly_count"]:
                exclude = True
                reasons.append(f"해당 월 접수순서 {rank}번째: 월 2권 초과")
                criteria.append("통합 월 2권 한도 · 시각 순")
            elif not complete_monthly_data:
                checks.append("타 구립도서관 포함 월간 전체 신청내역 여부 확인 필요(현재 파일 기준 판정)")
        if not legacy:
            checks_data = source_facts.get(idx, {})
            if settings.cross_library_duplicate_enabled:
                criteria.append('업로드된 구립도서관 신청목록의 동일 신청자·ISBN 중복 검사')
                if checks_data.get('duplicate'):
                    exclude = True
                    reasons.append('동일 신청자·ISBN 중복 신청 확인 (' + checks_data['duplicate_scope'] + ')')
                elif checks_data.get('missing') or checks_data.get('missing_isbn'):
                    checks.append('중복 신청 판정 불가: 신청자번호·신청일시·도서관명·ISBN 확인 필요')
                if not complete_monthly_data:
                    checks.append('타 구립도서관 전체 신청내역 미확인: 업로드 범위 외 중복은 검사 불가')
            if settings.monthly_limit_enabled:
                criteria.append(f'업로드 신청목록 기준 신청자별 월 {settings.monthly_limit_count}권 한도')
                rank = checks_data.get('rank')
                if checks_data.get('missing') or rank is None:
                    checks.append('월 신청권수 판정 불가: 신청자번호·신청일시·도서관명 확인 필요')
                elif checks_data.get('tie'):
                    checks.append('한도 경계 접수시각 동률: 신청 순서 확인 필요')
                elif checks_data.get('over_limit'):
                    exclude = True
                    reasons.append(f'월 {settings.monthly_limit_count}권 초과 (업로드 기준 {rank}번째 신청)')
                if not complete_monthly_data:
                    checks.append('타 구립도서관 포함 당월 전체 신청목록인지 확인 필요')
            if settings.holdings_enabled:
                criteria.append(f'통합 소장 {settings.holdings_limit}개관 이상 제외 조건')
                if holdings is None:
                    checks.append('통합 소장자료 미제공: 소장 여부 판정 불가')
                elif len(isbn) not in (10, 13):
                    checks.append('통합 소장 확인 불가: ISBN 누락/오류')
                else:
                    count = len(holdings.get(isbn, set()))
                    if count >= settings.holdings_limit:
                        exclude = True
                        reasons.append(f'제공된 통합 소장자료에서 {count}개관 확인 (설정 기준 {settings.holdings_limit}개관 이상)')
                    elif not complete_holdings_data:
                        checks.append(f'통합 소장자료 기준 {count}개관 확인 · 전체 소장자료 완전성 별도 검증 필요')
        if not isbn or len(isbn) not in (10, 13):
            checks.append("ISBN 확인 후 2차 서지조회 가능")
        if legacy:
            checks.extend(["전체 시리즈 권수: 담당사서 판단", "4개관 이상 소장·대출수요: 담당사서 판단",
                           "구매 가능 여부 및 도서 유형: 2차 조회 또는 사서 확인"])
        else:
            checks.append("이용기관의 기타 선정기준은 담당자 확인")
        if missing_essentials:
            reasons.extend(f"1차 판정자료 미비: {v}" for v in missing_essentials)
        status = "통과 안 됨" if exclude or missing_essentials else "1차 필터링 통과"
        out.append({
            "원본행": int(row.get("_원본행", idx+2)),
            "도서관명": _text(row.get("도서관명")),
            "신청일자": _text(row.get("신청일자")),
            "서명": title, "저자": _text(row.get("저자")), "발행자": _text(row.get("발행자")),
            "발행년": year, "가격": amount, "ISBN": isbn,
            "주제구분": _text(row.get("주제구분")), "월신청순서": rank,
            "1차판정": status, "판정사유": " / ".join(reasons) if reasons else "1차 검사 기준 충족",
            "적용기준": " / ".join(dict.fromkeys(criteria)) or "1차 검사 기준 미사용",
            "추가확인": " / ".join(dict.fromkeys(checks)),
            "2차판정": "미실행" if settings.second_enabled else "검사 안 함", "2차근거": "", "서지설명": "", "서지출처": "", "YES24상품링크": "", "신청취소사유": _cancel_text(reasons) if (legacy or exclude) else "",
            "최종처리": "미결정", "AI분석": "미실행", "AI근거": "",
        })
    return pd.DataFrame(out, columns=RESULT_COLUMNS)


def export_results(results: pd.DataFrame, info: dict, settings: Optional[BookFilterSettings] = None) -> bytes:
    """Return an allowlisted XLSX with no applicant identifiers or contacts."""
    safe = results.reindex(columns=RESULT_COLUMNS).copy()
    # Prevent Excel formula injection from untrusted title / author / publisher text.
    for col in safe.select_dtypes(include=['object', 'string']).columns:
        safe[col] = safe[col].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
    if settings is None:
        policy_rows = [
        ["신청권수", "구립도서관 통합 1인 월 2권"],
        ["신청조건", "권당 30,000원 이하; 출간 5년 이내"],
        ["정보/유통", "도서정보 부족, 품절/절판 구입 불가"],
        ["제외 유형", "판타지, 무협지, 로맨스, 인터넷소설, 만화, 팝업북, 원서, 전문/전공·수험·자격증·대학교재, 다이어리북, 워크북, 시리즈"],
        ["복본 제한", "4개 도서관 이상 소장; 대출현황에 따라 탄력적 추가 구입 가능"],
        ["예산 조정", "유사 주제/대중적 이용 가능성 등을 고려해 일부 제한 가능"],
        ["1차 검사", "정가 30,000원 초과 / 신청연도-5보다 이전 연도 / 같은 달 유효 접수 3건째부터"],
        ["대상", "실행 기준월의 일반 구립도서관 신청만; 스마트도서관·취소·반려 제외"],
        ["담당자 확인", "통합 소장 4개관, 시리즈 전체 권수, 품절/절판, 2차 분류의 불명확 사례"],
        ["확인 유의", "1차 통과는 구매확정 아님. 통과 안 됨 중 필수항목 누락은 자료 정정 뒤 재검사. ISBN/AI 결과 최종 선정 아님"],
        ["개인정보", "결과 파일에는 신청자명·대출자번호·주소·생년월일·휴대폰번호를 포함하지 않음"],
        ]
    else:
        policy_rows = [
            ["검토 범위", "업로드 자료 중 취소·반려 상태 제외; 선택한 검사만 적용"],
            ["구립도서관 중복 신청", "사용 · 업로드 내 동일 회원·ISBN" if settings.cross_library_duplicate_enabled else "검사 안 함"],
            ["월 신청권수", f"사용 · 월 {settings.monthly_limit_count}권" if settings.monthly_limit_enabled else "검사 안 함"],
            ["전체 소장 여부", f"사용 · {settings.holdings_limit}개관 이상" if settings.holdings_enabled else "검사 안 함"],
            ["가격", f"사용 · {settings.price_limit:,}원 이하" if settings.price_enabled else "검사 안 함"],
            ["발행일", (f"사용 · 최근 {settings.max_age_years}년 {settings.extra_months}개월 (월 단위)" if settings.month_precision
                      else f"사용 · 최근 {settings.max_age_years}년 (연도 기준)") if settings.year_enabled else "검사 안 함"],
            ["2차 검사", "사용 · " + ", ".join(settings.second_categories) if settings.second_enabled and settings.second_categories else "검사 안 함"],
            ["주의", "자료 누락은 통과로 처리하지 않음. 결과는 선정 확정이 아니라 담당자 검토 참고"],
            ["개인정보", "신청자명·대출자번호·연락처 등은 결과에 포함하지 않음"],
        ]
    policy = pd.DataFrame(policy_rows, columns=["항목", "설명"])
    notes = pd.DataFrame([[str(k), str(v)] for k, v in info.items()], columns=["항목", "값"])
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        first_pass = safe['1차판정'].eq('1차 필터링 통과')
        sheets = {
            '전체 결과': safe,
            '1차 통과': safe[first_pass],
            '1차 실패': safe[~first_pass],
            '2차 통과': safe[first_pass & safe['2차판정'].eq('2차 통과')],
            '2차 실패': safe[first_pass & safe['2차판정'].eq('2차 탈락')],
        }
        for name, subset in sheets.items():
            subset.to_excel(writer, index=False, sheet_name=name)
        policy.to_excel(writer, index=False, sheet_name="선정기준_요약")
        notes.to_excel(writer, index=False, sheet_name="검토환경")
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        for sheet in writer.book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.fill = PatternFill(fill_type="solid", fgColor="29325B")
                cell.font = Font(bold=True, color="FFFFFF")
                cell.alignment = Alignment(vertical="center")
            sheet.row_dimensions[1].height = 25
            for col_cells in sheet.columns:
                letter = get_column_letter(col_cells[0].column)
                widths = {"A": 12, "B": 36, "C": 26, "D": 23, "E": 14, "F": 14, "G": 19, "H": 16, "I": 23, "J": 54, "K": 48, "L": 70, "M": 25, "N": 45}
                sheet.column_dimensions[letter].width = widths.get(letter, 22)
            if sheet.title in sheets:
                for numeric_name in ("가격", "발행년", "월신청순서"):
                    number_col = RESULT_COLUMNS.index(numeric_name) + 1
                    for row_idx in range(2, sheet.max_row + 1):
                        cell = sheet.cell(row_idx, number_col)
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = '#,##0' if numeric_name == "가격" else '0'
                for cells in list(sheet.rows)[1:]:
                    status = cells[RESULT_COLUMNS.index("1차판정")]
                    if status.value == "통과 안 됨":
                        for cell in cells:
                            cell.fill = PatternFill(fill_type="solid", fgColor="FDE2E2")
                            cell.font = Font(color="991B1B", bold=cell.column == RESULT_COLUMNS.index("1차판정") + 1)
                    else:
                        status.font = Font(bold=True, color="166534")
    return buf.getvalue()
