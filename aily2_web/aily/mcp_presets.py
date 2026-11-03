"""Explicitly vetted public-data MCP endpoints for AILY local default discovery.

A preset is not a successful API connection. Its advertised read-only tools must
still be discovered and checked against their schemas at call time.
"""
from __future__ import annotations

# Never attach API credentials or institution documents to these connections.
BUILTIN_MCP = (
    {'id': 'a11e000000000001', 'name': 'KOSIS 국가통계 MCP',
     'url': 'https://kosismcp2026.vercel.app/api/mcp',
     'category': 'statistics', 'scope': 'both', 'enabled': True,
     'tools': [], 'builtin': True, 'auto_readonly': True},
    {'id': 'a11e000000000002', 'name': 'HRDKorea 국가자격 MCP',
     'url': 'https://openapi.hrdkorea.or.kr/mcp',
     'category': 'qualification', 'scope': 'both', 'enabled': True,
     'tools': [], 'builtin': True, 'auto_readonly': True},
)

# Information Naru requires an API key and its official remote connection URL
# has not been verified here. Do not invent or auto-connect an endpoint.
PENDING_MCP = (
    {'name': '도서관 정보나루 MCP', 'reason': '공식 서버 주소·인증 연동 방식 확인 후 연결 가능',
     'docs': 'https://data4library.kr/mcpUtilization'},
)


def builtin_by_id(identifier: str):
    return next((dict(r) for r in BUILTIN_MCP if r['id'] == identifier), None)


def is_trusted_builtin(record: dict) -> bool:
    """Saved config cannot escalate an arbitrary URL to a trusted preset."""
    original = builtin_by_id(record.get('id', ''))
    return bool(original and record.get('url') == original['url'] and
                record.get('category') == original['category'])
