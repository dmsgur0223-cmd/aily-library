"""Optional privacy-minimized LLM category advisory.

Only allowlisted bibliographic fields are sent. This is not evidence of a book's contents.
The user's institution must authorize external API usage before enabling.
"""
from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import pandas as pd

EXCLUDED = ["판타지", "무협지", "로맨스", "인터넷 소설", "만화", "팝업북", "각종 원서류", "전문·전공서", "문제집", "참고서", "수험서", "자격증", "대학교재", "다이어리북", "워크북", "시리즈물"]

SCHEMA = {
    "type": "object",
    "properties": {
        "result": {"type": "string", "enum": ["제외유형 의심", "명백한 제외유형 단서 없음", "판단 불가"]},
        "category": {"type": "string"},
        "evidence": {"type": "string"},
        "confidence": {"type": "string", "enum": ["높음", "보통", "낮음"]},
    },
    "required": ["result", "category", "evidence", "confidence"],
    "additionalProperties": False,
}


def category_advisory(book: dict, key: str, model: str = "gpt-4o-mini",
                      enabled_categories=None) -> dict:
    """Submit ONLY limited book data; never entire rows or applicant information."""
    allowed = {k: str(book.get(k, "")) for k in ("서명", "저자", "발행자", "발행년", "ISBN", "주제구분", "서지설명")}
    payload = {
        "model": model,
        "store": False,
        "instructions": (
            "도서관 희망도서 검토의 참고 의견만 작성한다. 외부 도서 DB에 접속할 수 없으므로 "
            "제목과 서지정보에 명백히 드러나는 단서만 평가한다. "
            "분야 '문학'만으로 판타지/로맨스로 판단하지 않는다. "
            "일반 교양서와 전공·수험서를 구별하되 모르면 판단 불가. "
            "검사 대상 제외 유형은 다음과 같다: " + ", ".join(EXCLUDED if enabled_categories is None else enabled_categories) + ". "
            "내용, 절판 여부, 소장 여부를 임의로 지어내지 않는다. "
            "evidence에는 실제 입력에 드러난 단서만 짧게 적는다. "
            "어떤 경우에도 최종 취소/선정 결정을 내려서는 안 된다."
        ),
        "input": [{"role": "user", "content": "다음 도서가 제외 유형일 가능성을 참고용으로 분류: " + json.dumps(allowed, ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": "book_advisory", "strict": True, "schema": SCHEMA}},
        "max_output_tokens": 220,
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=35) as resp:
            data = json.load(resp)
    except HTTPError as exc:
        # Avoid displaying request payload, credentials or server body.
        raise RuntimeError(f"AI API 요청 실패 (HTTP {exc.code}). 모델·권한·요금 설정을 확인하세요.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("AI API에 연결하지 못했습니다. 네트워크를 확인하세요.") from None
    # Responses API may return several output items. Only consume text content.
    for item in data.get("output", []):
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                return json.loads(part["text"])
    raise RuntimeError("AI가 분석 결과를 반환하지 않았습니다.")


def apply_advisories(results: pd.DataFrame, key: str, model: str = "gpt-4o-mini", progress=None,
                     enabled_categories=None) -> pd.DataFrame:
    results = results.copy()
    for i, (idx, row) in enumerate(results.iterrows()):
        book = {k: row.get(k, "") for k in ("서명", "저자", "발행자", "발행년", "ISBN", "주제구분", "서지설명")}
        try:
            opinion = category_advisory(book, key, model, enabled_categories)
            result = opinion["result"]
            results.at[idx, "AI분석"] = f"{result} · {opinion['category']} · 신뢰도 {opinion['confidence']}"
            results.at[idx, "AI근거"] = opinion["evidence"]
            if result == "제외유형 의심" and row["1차판정"] == "1차 필터링 통과":
                results.at[idx, "2차근거"] = str(results.at[idx, "2차근거"]) + " / 선택 AI가 추가 검토 의견 제시: 사서 확인 (2차 규칙 판정은 유지)"
            if result == "판단 불가" and row["1차판정"] == "1차 필터링 통과":
                results.at[idx, "2차근거"] = str(results.at[idx, "2차근거"]) + " / AI의 장르 판단 불가"
        except (RuntimeError, ValueError, KeyError, json.JSONDecodeError):
            results.at[idx, "AI분석"] = "AI 분석 실패"
            results.at[idx, "AI근거"] = "설정/호출 오류로 분석을 완료하지 못함"
        if progress:
            progress((i + 1) / max(len(results), 1))
    return results

# Official YES24 Goods API: https://developers.yes24.com/api-doc/goods-item-detail
# Only ISBN, NEVER applicant/user fields, is sent to the provider.
YES24_API_ENDPOINT = "https://apis.yes24.com/v1/goods/itemDetail"
YES24_SEARCH_ENDPOINT = "https://apis.yes24.com/v1/goods/itemList"


def _yes24_request(endpoint: str, params: dict, api_key: str, opener=None) -> dict:
    from urllib.parse import urlencode
    opener = opener or urlopen
    req = Request(endpoint + "?" + urlencode(params),
                  headers={"X-Api-Key": api_key.strip(), "Accept": "application/json",
                           "User-Agent": "AILY/4.8.3 BookReview"})
    try:
        with opener(req, timeout=18) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError("YES24 API 인증 실패 (HTTP %s). 키를 재확인하세요." % exc.code) from None
        if exc.code == 404:
            return {"success": True, "data": {"items": [], "totalCount": 0}}
        if exc.code == 429:
            raise RuntimeError("YES24 API 요청 한도 초과 (429). 잠시 후 재시도하세요.") from None
        raise RuntimeError(f"YES24 API HTTP {exc.code} 오류.") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("YES24 API 연결 실패. 네트워크를 확인하세요.") from None
    except (ValueError, TypeError):
        raise RuntimeError("YES24 API JSON 해석 실패.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("YES24 API 응답 형식을 확인할 수 없습니다.")
    if payload.get("success") is not True:
        # Never display echoed API-key, response bodies or attacker-controlled message.
        code = str(payload.get("errorCode") or "UNKNOWN")[:30]
        raise RuntimeError(f"YES24 API 오류 코드: {code}")
    if not isinstance(payload.get("data"), dict):
        raise RuntimeError("YES24 API 응답 형식을 확인할 수 없습니다.")
    if not isinstance(payload["data"].get("items"), list):
        raise RuntimeError("YES24 API 상품 목록이 올바르지 않습니다.")
    return payload


def _normalize_yes24_item(item: dict) -> dict:
    detail = item.get("contentDetail") or {}
    if not isinstance(detail, dict):
        detail = {}
    return {
        "TITLE": str(item.get("title") or ""),
        "SUBTITLE": str(item.get("subTitle") or ""),
        "AUTHOR": str(item.get("author") or ""),
        "PUBLISHER": str(item.get("publisher") or ""),
        "PUB_YEAR": str(item.get("publishDate") or "")[:4],
        "PUBLISH_DATE": str(item.get("publishDate") or ""),
        "EA_ISBN": str(item.get("isbn13") or item.get("isbn10") or ""),
        "SUBJECT": str(item.get("goodsSortNm") or ""),
        "FORM_DETAIL": str(item.get("itemFormat") or item.get("goodsType") or ""),
        "BOOK_INTRODUCTION": str(detail.get("bookIntroduction") or "")[:1200],
        "TABLE_OF_CONTENTS": str(detail.get("tableOfContents") or "")[:1200],
        "PAGES": item.get("pages"),
        "SHOP_PRICE": item.get("shopPrice"),
        "SALE_PRICE": item.get("salePrice"),
        "ITEM_STATUS": str(item.get("itemStatus") or ""),
        "SERIES_TITLE": ", ".join(str(v.get("seriesName") or "") for v in (item.get("series") or []) if isinstance(v, dict)),
        "SOURCE": "YES24 Open API",
        "LINK": str(item.get("link") or ""),
    }


def _to_isbn13(isbn: str) -> str:
    from .books import normalize_isbn
    value = normalize_isbn(isbn)
    if len(value) == 13:
        return value
    if len(value) == 10 and value[:9].isdigit() and (value[-1].isdigit() or value[-1] == "X"):
        digits = "978" + value[:9]
        check = (10 - sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(digits)) % 10) % 10
        return digits + str(check)
    return ""


def fetch_yes24_book(isbn: str, api_key: str, title: str = "", trace: list | None = None,
                     opener=None) -> dict | None:
    """Exact ISBN-13 detail, optional strict-ISBN title fallback; never fuzzy-match."""
    from .books import normalize_isbn
    original = normalize_isbn(isbn)
    normalized = _to_isbn13(original)
    if not normalized:
        return None
    if not api_key.strip():
        raise ValueError("YES24 Open API 인증키가 없습니다.")

    def scan(endpoint, params, method):
        payload = _yes24_request(endpoint, params, api_key, opener=opener)
        items = payload["data"]["items"]
        matching = next((item for item in items if isinstance(item, dict) and
                        (normalize_isbn(item.get("isbn13")) == normalized or
                         normalize_isbn(item.get("isbn10")) == original)), None)
        if trace is not None:
            trace.append({"검색 방식": method, "서버 검색건수": payload["data"].get("totalCount", len(items)),
                          "ISBN 일치": bool(matching)})
        return _normalize_yes24_item(matching) if matching is not None else None

    book = scan(YES24_API_ENDPOINT, {"searchType": "ISBN13", "query": normalized, "detail": "Y"}, "ISBN13 상세검색")
    if book is not None:
        return book
    # Search engines may silently correct title searches: exact ISBN check is mandatory.
    if str(title).strip():
        return scan(YES24_SEARCH_ENDPOINT, {"query": str(title).strip()[:100], "category": "ALL",
                                             "page": 1, "pageSize": 30, "detail": "Y"}, "서명 보조검색")
    return None


def second_pass(record: dict, qualifications: set[str] | None = None,
                enabled_categories=None) -> dict:
    """YES24 evidence + optional Q-Net; no automatic final purchasing decision."""
    from .qualifications import classify_study_material
    return classify_study_material(record, qualifications, enabled_categories)


def apply_yes24_lookup(results: pd.DataFrame, api_key: str, progress=None, fetcher=None,
                       qualifications: set[str] | None = None, enabled_categories=None) -> pd.DataFrame:
    """Use only ISBN/title for YES24; no reader or library employee details leave app."""
    from .books import _amount
    results = results.copy()
    fetch = fetcher or fetch_yes24_book
    cache = {}
    for i, (idx, row) in enumerate(results.iterrows()):
        if row.get("1차판정") == "통과 안 됨":
            results.at[idx, "2차판정"] = "1차 통과 안 됨 · 조회 생략"
            if progress: progress((i + 1) / max(len(results), 1))
            continue
        isbn = str(row.get("ISBN") or "")
        try:
            if isbn not in cache:
                cache[isbn] = (fetch(isbn, api_key, title=str(row.get("서명") or "")) if fetcher is None
                               else fetch(isbn, api_key))
            record = cache[isbn]
            verdict = second_pass(record, qualifications, enabled_categories)
            results.at[idx, "2차판정"] = verdict["status"]
            results.at[idx, "2차근거"] = verdict["evidence"]
            if record:
                results.at[idx, "서지출처"] = "YES24"
                results.at[idx, "YES24상품링크"] = str(record.get("LINK") or "")
                results.at[idx, "서지설명"] = " / ".join(str(record.get(k) or "")[:400] for k in
                    ("SUBJECT", "FORM_DETAIL", "BOOK_INTRODUCTION", "SERIES_TITLE") if record.get(k))[:1000]
                shop_price = _amount(record.get("SHOP_PRICE"))
                local_price = _amount(row.get("가격"))
                if shop_price is not None and local_price is not None and shop_price != local_price:
                    results.at[idx, "2차근거"] += f" / YES24 정가 {shop_price:,}원 · 신청 {local_price:,}원 (정가 불일치)"
                if record.get("ITEM_STATUS"):
                    results.at[idx, "2차근거"] += f" / YES24 판매상태: {record['ITEM_STATUS']} (타 판매처 상태와 다를 수 있음)"
            if verdict["status"] == "2차 탈락":
                results.at[idx, "신청취소사유"] = (
                    f"신청하신 도서는 {verdict['category']} 자료유형에 해당하는 근거가 확인되었습니다. "
                    "담당자가 선정기준과 서지정보를 확인한 뒤 최종 처리 결과를 안내드리겠습니다.")
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            results.at[idx, "2차판정"] = "조회 실패"
            results.at[idx, "2차근거"] = f"YES24 API 조회 오류: {str(exc)[:130]}"
        if progress: progress((i + 1) / max(len(results), 1))
    return results
