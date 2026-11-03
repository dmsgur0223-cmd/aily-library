"""Local, read-only MCP client for the AILY Law MCP Hub (SDK 2.x).

MCP and direct REST are independent paths. This module never sends keys as
MCP tool arguments and never treats a successful tool handshake as proof of a
successful upstream legal API request.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

from aily.law_api import LawEntry


class MCPConnectionError(RuntimeError):
    """Safe, non-secret error intended for the operator UI."""


READ_ONLY_TOOLS = frozenset({"law_connection_info", "search_laws", "get_law_articles"})


def _sdk():
    try:
        from mcp import Client, StdioServerParameters
    except ImportError:
        raise MCPConnectionError("MCP 라이브러리가 설치되지 않았습니다. AILY를 재시작해 의존성을 설치하세요.") from None
    return Client, StdioServerParameters


def _parse_payload(response) -> dict:
    """Read SDK structured results or older text-only JSON tool responses.

    Some MCP SDK transports return a tool's dict as a JSON TextContent block
    without structured_content. Never parse non-JSON text as Python code or
    surface raw tool text: it could include upstream URLs or credentials.
    """
    if getattr(response, "is_error", False):
        raise MCPConnectionError("MCP 도구가 오류를 반환했습니다. 서버 설정과 호출 기록을 확인하세요.")
    payload = getattr(response, "structured_content", None)
    if payload is None:
        blocks = getattr(response, "content", None)
        if not isinstance(blocks, (list, tuple)) or len(blocks) != 1:
            raise MCPConnectionError("MCP 응답 구조가 올바르지 않습니다.")
        block = blocks[0]
        if getattr(block, "type", None) != "text":
            raise MCPConnectionError("MCP 응답 구조가 올바르지 않습니다.")
        raw = getattr(block, "text", None)
        if not isinstance(raw, str) or len(raw) > 2_000_000:
            raise MCPConnectionError("MCP 텍스트 응답이 비어 있거나 너무 큽니다.")
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            raise MCPConnectionError("MCP 응답의 JSON 형식이 올바르지 않습니다.") from None
    if not isinstance(payload, dict):
        raise MCPConnectionError("MCP 응답 구조가 올바르지 않습니다.")
    if "result" in payload and isinstance(payload["result"], dict):
        payload = payload["result"]
    if payload.get("ok") is not True:
        # Server exceptions and REST errors use fixed, credential-free messages.
        reason = payload.get("error", "알 수 없는 도구 오류")
        if reason not in {
            "국가법령정보 OC 미설정", "법령 ID 또는 MST가 필요합니다.",
            "조문 검색어는 80자 이하 일반 문자여야 합니다.",
            "조문 표시 개수는 1~50이어야 합니다.",
        }:
            reason = "국가법령정보 API 조회 실패. 인증값·네트워크·검색 조건을 확인하세요."
        raise MCPConnectionError(reason)
    return payload


async def _run_tool(root: Path, tool: str | None = None, arguments: dict | None = None):
    if tool is not None and tool not in READ_ONLY_TOOLS:
        raise MCPConnectionError("허용되지 않은 MCP 도구입니다.")
    Client, StdioServerParameters = _sdk()
    root = root.resolve()
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "aily.mcp_server"],
        env={"PYTHONPATH": str(root)},
    )
    try:
        async with Client(server) as client:
            found = await asyncio.wait_for(client.list_tools(), timeout=20)
            names = {item.name for item in found.tools}
            if not READ_ONLY_TOOLS.issubset(names):
                raise MCPConnectionError("AILY MCP 서버의 필수 도구를 찾을 수 없습니다.")
            if tool is None:
                return {"connected": True, "tools": sorted(names), "live_api_checked": False}
            response = await asyncio.wait_for(client.call_tool(tool, arguments or {}), timeout=35)
            return _parse_payload(response)
    except MCPConnectionError:
        raise
    except Exception:
        # Do not put raw SDK errors (which might contain environment or URLs) in UI.
        raise MCPConnectionError("MCP 연결 또는 호출에 실패했습니다. 실행환경과 서버 설치 상태를 확인하세요.") from None


def _run(root: Path, tool: str | None = None, arguments: dict | None = None) -> dict:
    try:
        return asyncio.run(_run_tool(root, tool, arguments))
    except MCPConnectionError:
        raise
    except Exception:
        raise MCPConnectionError("MCP 실행환경 오류가 발생했습니다.") from None


def check_mcp_connection(root: Path) -> dict:
    """Only performs protocol tool discovery, NOT a law API call."""
    return _run(root)


def search_laws_mcp(root: Path, query: str, *, limit: int = 10) -> list[LawEntry]:
    """Actually query law.go.kr through MCP and convert validated response."""
    if not 2 <= len(query.strip()) <= 80 or not 1 <= limit <= 100:
        raise ValueError("법령 검색어는 2~80자, 검색 건수는 1~100으로 입력하세요.")
    payload = _run(root, "search_laws", {"query": query.strip(), "limit": limit})
    rows = payload.get("items")
    if not isinstance(rows, list):
        raise MCPConnectionError("MCP 검색 결과 형식이 올바르지 않습니다.")
    results = []
    for row in rows:
        if not isinstance(row, dict):
            raise MCPConnectionError("MCP 검색 결과 형식이 올바르지 않습니다.")
        try:
            results.append(LawEntry(**{field: str(row.get(field, "")) for field in
                                       ("name", "law_id", "mst", "effective_date", "ministry", "detail_link", "promulgation_date", "revision_type")}))
        except (TypeError, ValueError):
            raise MCPConnectionError("MCP 법령 목록 검증 실패") from None
    return results


def law_articles_mcp(root: Path, law_id: str, *, mst: str = "", keyword: str = "", limit: int = 30,
                     related_terms: list[str] | None = None) -> dict:
    arguments = {"law_id": law_id, "mst": mst, "keyword": keyword, "limit": limit}
    if related_terms:
        arguments["related_terms"] = related_terms
    payload = _run(root, "get_law_articles", arguments)
    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise MCPConnectionError("MCP 조문 응답 형식이 올바르지 않습니다.")
    return payload
