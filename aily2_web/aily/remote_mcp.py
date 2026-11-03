"""Opt-in, local-admin managed remote MCP connections. No arbitrary code execution.

Server text and tool descriptions are untrusted. Remote tools are NEVER invoked
merely because they were discovered: each tool needs an explicit approval.
Uploads, keys and institution documents must not be passed as tool arguments.
"""
from __future__ import annotations
import asyncio
import ipaddress
import json
from pathlib import Path
import re
import secrets
import socket
from urllib.parse import urlsplit
from .settings import _atomic_private_write
from .mcp_presets import BUILTIN_MCP, builtin_by_id, is_trusted_builtin

REGISTRY_FILE = 'mcp_connections.json'
ALLOWED_CATEGORIES = {'statistics', 'procurement', 'law', 'business', 'library', 'policy', 'qualification', 'other'}
ALLOWED_SCOPES = {'both', 'corp', 'external'}
BLOCKED_TOOL_NAME = re.compile(r'(delete|remove|write|create|update|modify|upload|post|send|execute|shell|command|transfer|mail|publish|submit|drop|insert|erase|삭제|수정|등록|발송|생성|업로드|실행|제출)', re.I)
QUERY_KEYS = ('query', 'keyword', 'search', 'searchTerm', 'search_term', 'q', 'text', 'term')
SENSITIVE_KEYS = {'access_token', 'authorization', 'apikey', 'api_key', 'servicekey', 'service_key', 'secret', 'token', 'password', 'client_secret', 'key'}


def _public_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 500 or any(ord(c) <= 32 for c in url):
        raise ValueError('MCP URL은 공백 없이 500자 이내여야 합니다.')
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('인증정보·쿼리 없는 공개 HTTPS MCP URL만 허용합니다.')
    if parts.port not in (None, 443):
        raise ValueError('MCP 서버는 HTTPS 기본 포트(443)만 허용합니다.')
    host = parts.hostname.lower().rstrip('.')
    if not re.fullmatch(r'[a-z0-9.-]{4,253}', host) or '.' not in host or '..' in host:
        raise ValueError('MCP 호스트 이름이 올바르지 않습니다.')
    if host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid')):
        raise ValueError('내부망/로컬 주소를 외부 MCP로 등록할 수 없습니다.')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('IP 주소 대신 신뢰할 수 있는 공개 도메인을 사용하세요.')
    return url


def _assert_public_dns(url: str, resolver=socket.getaddrinfo):
    """Basic SSRF safety gate; only connect to public-address DNS resolutions.

    The HTTP client may re-resolve: deployment firewalls / egress allowlists are
    still necessary against DNS rebinding for hostile internet domains.
    """
    host = urlsplit(_public_url(url)).hostname
    try:
        answers = resolver(host, 443, type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        raise RuntimeError('MCP 도메인의 공개 IP 확인에 실패했습니다.') from None
    if not answers:
        raise RuntimeError('MCP 도메인의 IP 주소를 확인할 수 없습니다.')
    for answer in answers:
        try:
            ip = ipaddress.ip_address(answer[4][0].split('%', 1)[0])
        except (ValueError, IndexError, TypeError):
            raise RuntimeError('MCP 도메인의 IP 정보가 유효하지 않습니다.') from None
        if not ip.is_global:
            raise RuntimeError('사설망·내부망으로 연결되는 MCP 주소는 차단됩니다.')


def _path(root: Path) -> Path:
    return root / 'config' / REGISTRY_FILE


def load_connections(root: Path) -> list[dict]:
    path = _path(root)
    if not path.exists(): return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, list): raise ValueError()
        return [dict(x) for x in data if isinstance(x, dict) and
                isinstance(x.get('id'), str) and re.fullmatch(r'[a-f0-9]{16}', x['id']) and
                isinstance(x.get('tools'), list)]
    except (ValueError, OSError, TypeError):
        raise ValueError('외부 MCP 설정을 읽지 못했습니다. 설정 파일을 확인하세요.') from None


def effective_connections(root: Path) -> list[dict]:
    """Merge auto-ready vetted presets with user's saved preferences.

    User-managed records take priority (including explicit disable). An older
    manually registered matching URL is kept without introducing duplicates.
    """
    stored = load_connections(root)
    result = [dict(c) for c in stored]
    urls = {c.get('url') for c in result}
    ids = {c['id'] for c in result}
    for preset in BUILTIN_MCP:
        if preset['id'] not in ids and preset['url'] not in urls:
            result.append(dict(preset))
    return result


def set_builtin_enabled(root: Path, identifier: str, enabled: bool) -> None:
    """Persist an explicit opt-out or opt-in without affecting other servers."""
    preset = builtin_by_id(identifier)
    if not preset: raise ValueError('기본 MCP가 아닙니다.')
    rows = load_connections(root)
    saved = next((r for r in rows if r['id'] == identifier), None)
    if saved:
        if saved.get('url') != preset['url']: raise ValueError('기본 MCP 주소가 변경됐습니다.')
        saved['enabled'] = bool(enabled)
    else:
        rows.append({**preset, 'enabled': bool(enabled)})
    _write(root, rows)


def _write(root: Path, rows: list[dict]):
    if len(rows) > 15: raise ValueError('외부 MCP 서버는 최대 15개까지 등록할 수 있습니다.')
    _atomic_private_write(_path(root), json.dumps(rows, ensure_ascii=False, indent=2))


def add_connection(root: Path, name: str, url: str, category: str, scope: str, *, trusted: bool = False) -> dict:
    if not trusted: raise ValueError('외부 전송·서버 운영자에 대한 확인 동의가 필요합니다.')
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
        raise ValueError('연결명은 2~80자 일반 문자여야 합니다.')
    url = _public_url(url.strip())
    if category not in ALLOWED_CATEGORIES or scope not in ALLOWED_SCOPES:
        raise ValueError('연결 분류/적용 범위가 올바르지 않습니다.')
    rows = load_connections(root)
    if any(c['url'] == url for c in rows): raise ValueError('이미 등록된 MCP 주소입니다.')
    entry = {'id': secrets.token_hex(8), 'name': name.strip(), 'url': url,
             'category': category, 'scope': scope, 'enabled': False, 'tools': []}
    rows.append(entry)
    _write(root, rows)
    return entry


def update_connection(root: Path, connection_id: str, *, enabled: bool | None = None,
                      approved_tools: list[str] | None = None, delete: bool = False) -> None:
    rows = load_connections(root)
    found = next((r for r in rows if r['id'] == connection_id), None)
    if not found and builtin_by_id(connection_id):
        found = builtin_by_id(connection_id)
        rows.append(found)
    if not found: raise ValueError('MCP 연결을 찾지 못했습니다.')
    if delete:
        rows.remove(found)
    else:
        if approved_tools is not None:
            if not isinstance(approved_tools, list) or len(approved_tools) > 100:
                raise ValueError('허용 도구 목록이 올바르지 않습니다.')
            found['tools'] = sorted(set(t for t in approved_tools if isinstance(t, str)
                                        and 1 <= len(t) <= 100 and not BLOCKED_TOOL_NAME.search(t)))
            # Administrator's explicit tool approval is enough to make this
            # connection available for automatic public-information searches.
            found['enabled'] = bool(found['tools'])
        if enabled is not None:
            found['enabled'] = bool(enabled) and (is_trusted_builtin(found) or bool(found['tools']))
    _write(root, rows)


def _safe_result(result) -> dict:
    # Don't log or persist arbitrary content from an untrusted remote server.
    data = getattr(result, 'structured_content', None)
    if data is None:
        blocks = getattr(result, 'content', ())
        text = '\n'.join(str(getattr(b, 'text', '')) for b in list(blocks)[:3] if getattr(b, 'type', None) == 'text')[:15000]
        try: data = json.loads(text)
        except (ValueError, TypeError):
            # Text-only MCP servers (including KOSIS) may prepend long guidance
            # before their table IDs. Keeping only 1500 characters made verified
            # orgId/tblId disappear before the chain could read them. This is
            # untrusted provider text, *not* instructions to the application.
            data = {'text': text[:12000]}
    if getattr(result, 'is_error', False):
        return {'ok': False, 'error': '원격 MCP 도구가 오류를 반환했습니다.'}
    def clip(value, depth=0):
        if depth > 4: return '[깊이 제한]'
        if isinstance(value, dict):
            return {str(k)[:80]: ('[비공개]' if str(k).casefold().replace('-', '_') in SENSITIVE_KEYS else clip(v, depth+1))
                    for k,v in list(value.items())[:30]}
        if isinstance(value, list): return [clip(v, depth+1) for v in value[:12]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value[:10000] if isinstance(value,str) else value
        return str(type(value).__name__)
    return {'ok': True, 'data': clip(data)}


def safe_auto_tool_name(name: str) -> bool:
    if not isinstance(name, str) or not 2 <= len(name) <= 100 or BLOCKED_TOOL_NAME.search(name):
        return False
    if re.search(r'(secret|credential|password|token|api.?key|personal|private|internal|user.?data|account|개인정보|비밀)', name, re.I):
        return False
    return bool(re.search(r'(^|_)(search|find|get|list|query|lookup|read|fetch|stat|statistics)(_|$)', name, re.I)
                or re.match(r'^(kosis_search|kosis_local_search|(search|get|find|list|query|lookup|read|fetch)(?:_|[A-Z]))', name))

# Do not relay any question containing likely secrets, personal contacts, or
# internal/confidential document language to third-party MCP endpoints.
BLOCK_EXTERNAL_QUESTION = re.compile(
    r'\b\d{6}[- ]?[1-8]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b|'
    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|'
    r'(?:api[_ -]?key|access[_ -]?token|secret|password|인증키|비밀번호|주민등록번호|'
    r'개인정보|비공개|대외비|기밀|내부전용|비밀문서|내부결재)', re.I)


def public_search_question(question: str) -> str:
    if not isinstance(question, str) or not 2 <= len(question.strip()) <= 500:
        return ''
    if BLOCK_EXTERNAL_QUESTION.search(question):
        return ''
    return question.strip()[:300]


def _query_arguments(schema: dict, question: str) -> dict:
    """Populate a single natural-language search argument, never invented IDs.

    For other required fields (table IDs, year/region codes, auth tokens),
    the tool is skipped and a diagnostic is shown instead.
    """
    if not isinstance(schema, dict) or schema.get('type', 'object') != 'object': return {}
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    if not isinstance(properties, dict) or not isinstance(required, list): return {}
    query = public_search_question(question)
    if not query: return {}
    candidates = (*QUERY_KEYS, 'keywords', 'searchKeyword', 'search_word', 'searchText',
                  'natural_language_query', 'question', 'stat_name', 'statNm')
    for key in candidates:
        prop = properties.get(key)
        if not isinstance(prop, dict) or prop.get('type') != 'string': continue
        limit = prop.get('maxLength', 300)
        if not isinstance(limit, int) or limit < 2: continue
        # Allow optional defaults, not additional required parameters.
        if all(k == key for k in required):
            return {key: query[:min(limit, 300)]}
    return {}


async def _connect(url: str, *, tool: str | None = None, arguments: dict | None = None, bearer: str = ''):
    try:
        from mcp import Client
    except ImportError:
        raise RuntimeError('MCP Python SDK 설치가 필요합니다.') from None
    _assert_public_dns(url)
    if bearer:
        try:
            import httpx2
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            raise RuntimeError('MCP 인증 모듈이 설치되지 않았습니다.') from None
        async with httpx2.AsyncClient(headers={'Authorization': 'Bearer '+bearer}, timeout=30.0) as http:
            async with Client(streamable_http_client(url, http_client=http)) as client:
                return await _inspect_or_call(client, tool, arguments)
    async with Client(url) as client:
        return await _inspect_or_call(client, tool, arguments)


async def _inspect_or_call(client, tool, arguments):
    available = await client.list_tools()
    tools = list(available.tools)[:100]
    if tool is None:
        return [{'name': t.name, 'description': str(getattr(t, 'description', '') or '')[:250],
                 'input_schema': getattr(t, 'input_schema', None) or getattr(t, 'inputSchema', None) or {}}
                for t in tools]
    if tool not in [t.name for t in tools]: raise RuntimeError('등록된 MCP 도구를 서버에서 찾지 못했습니다.')
    if BLOCKED_TOOL_NAME.search(tool): raise RuntimeError('쓰기·수정 가능성이 있는 도구는 실행하지 않습니다.')
    result = await client.call_tool(tool, arguments or {})
    return _safe_result(result)


def _safe_connection_reason(exc: BaseException) -> str:
    """Classify remote transport errors without leaking URLs, auth or response bodies."""
    def types(e, depth=0):
        if depth > 5: return []
        name = type(e).__name__
        result = [name]
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if isinstance(status, int): result.append('HTTP:'+str(status))
        for inner in list(getattr(e, 'exceptions', ()) or ())[:5]:
            result.extend(types(inner, depth+1))
        if getattr(e, '__cause__', None) is not None:
            result.extend(types(e.__cause__, depth+1))
        return result
    names = set(types(exc))
    for tag in names:
        if tag.startswith('HTTP:'):
            code = int(tag.split(':',1)[1])
            if code in (401,403): return f'HTTP {code}: MCP 인증/권한 거부'
            if code in (404,405,406,415): return f'HTTP {code}: MCP 주소 또는 전송 프로토콜 불일치'
            if code == 429: return 'HTTP 429: 호출 제한'
            if 500 <= code <= 599: return f'HTTP {code}: 원격 MCP 서버 오류'
            return f'HTTP {code}: 원격 서버 응답 오류'
    if any('Timeout' in n or 'TimedOut' in n for n in names):
        return '시간 초과: 서버 지연 또는 네트워크 장애'
    if any(n in names for n in ('ConnectError','ConnectTimeout','DNSError','gaierror','NameResolutionError')):
        return '연결 실패: DNS/네트워크/방화벽 확인 필요'
    if any('Protocol' in n or 'SSE' in n for n in names):
        return 'MCP 전송 프로토콜 불일치'
    if 'ImportError' in names or 'ModuleNotFoundError' in names:
        return 'MCP Python SDK 또는 인증용 라이브러리 누락'
    return 'MCP 연결/도구 오류 (' + ', '.join(sorted(n for n in names if n not in {'Exception','ExceptionGroup','BaseExceptionGroup'})[:3])[:100] + ')'


def _run(url: str, *, tool: str | None = None, arguments: dict | None = None, bearer: str = ''):
    try:
        return asyncio.run(asyncio.wait_for(_connect(url, tool=tool, arguments=arguments, bearer=bearer), timeout=50))
    except ValueError:
        raise
    except Exception as exc:
        # Never surface exception text, URLs, headers, or credentials.
        raise RuntimeError(_safe_connection_reason(exc)) from None


def discover(root: Path, connection_id: str, *, bearer: str = '') -> list[dict]:
    record = next((r for r in effective_connections(root) if r['id'] == connection_id), None)
    if not record: raise ValueError('MCP 연결을 찾지 못했습니다.')
    return _run(record['url'], bearer=bearer)


def invoke(root: Path, record: dict, tool: str, question: str, schema: dict, *, bearer: str = '') -> dict:
    current = next((r for r in effective_connections(root) if r['id'] == record['id']), None)
    if not current or not current.get('enabled') or not safe_auto_tool_name(tool) or (tool not in current.get('tools', []) and not (is_trusted_builtin(current) and safe_auto_tool_name(tool))):
        raise RuntimeError('승인·활성화되지 않은 도구는 사용할 수 없습니다.')
    if not 2 <= len(question.strip()) <= 300: raise ValueError('검색 질문은 2~300자여야 합니다.')
    args = _query_arguments(schema, question)
    if not args: raise ValueError('자동 호출에 필요한 검색어 입력 스키마가 아니므로 실행하지 않습니다.')
    return _run(_public_url(current['url']), tool=tool, arguments=args, bearer=bearer)


def invoke_arguments(root: Path, record: dict, tool: str, arguments: dict, *, bearer: str = '') -> dict:
    """Call a reviewed read-only tool with explicitly verified input values.

    Used by bounded MCP workflows; never accepts arbitrary user supplied Python.
    """
    allowed = {'kosis_local_search','kosis_search','kosis_item_search',
               'kosis_validate','kosis_region_code','kosis_table_info','kosis_get_data'}
    current = next((r for r in effective_connections(root) if r['id'] == record.get('id')), None)
    if not current or not current.get('enabled'):
        raise RuntimeError('MCP 연결이 비활성화되어 있습니다.')
    if not (is_trusted_builtin(current) and current.get('category') == 'statistics'
            and tool in allowed and isinstance(arguments, dict)
            and len(arguments) <= 8
            and all(isinstance(k,str) and isinstance(v,(str,int)) and len(str(v)) <= 300
                    for k,v in arguments.items())):
        raise RuntimeError('다단계 조회는 검증된 KOSIS 읽기 전용 도구만 허용합니다.')
    return _run(_public_url(current['url']), tool=tool, arguments=arguments, bearer=bearer)


def _token_path(root: Path, identifier: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{16}', identifier): raise ValueError('MCP 식별자가 올바르지 않습니다.')
    return root / 'config' / 'mcp_tokens' / (identifier + '.txt')


def save_bearer(root: Path, identifier: str, token: str) -> None:
    if not any(r['id'] == identifier for r in load_connections(root)): raise ValueError('등록된 연결이 아닙니다.')
    if not isinstance(token, str) or not 1 <= len(token) <= 2048 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('Bearer 인증값 형식이 올바르지 않습니다.')
    _atomic_private_write(_token_path(root, identifier), token + '\n')


def read_bearer(root: Path, identifier: str) -> str:
    path = _token_path(root, identifier)
    return path.read_text(encoding='utf-8').strip() if path.is_file() else ''


def delete_bearer(root: Path, identifier: str) -> None:
    _token_path(root, identifier).unlink(missing_ok=True)
