"""Anonymous per-session institution documents: parse, preview and search ONLY.

No upload is persisted, indexed in a shared DB, embedded or transmitted to AI.
The caller must obtain an explicit 'apply to session' click before retaining it
in st.session_state. Evidence is deliberately lexical, not a legal judgment.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
import hashlib
import re
from typing import Sequence

MAX_FILE_BYTES = 8_000_000
MAX_DOCS = 10
MAX_PARAGRAPHS = 2000
MAX_TOTAL_CHARS = 400_000
MAX_PDF_PAGES = 50
SUPPORTED = {'.txt', '.md', '.pdf', '.docx', '.hwp', '.hwpx'}


@dataclass(frozen=True)
class Passage:
    location: str
    text: str


@dataclass(frozen=True)
class InstitutionDocument:
    name: str
    digest: str
    passages: tuple[Passage, ...]
    declared_date: str = ''  # User-supplied; not verified from document metadata.


@dataclass(frozen=True)
class Evidence:
    document: str
    location: str
    excerpt: str
    score: int


def _paragraphs(text: str, location: str) -> list[Passage]:
    chunks = re.split(r'\n\s*\n|(?<=\.)\n(?=제\d+조)', text)
    out = []
    for chunk in chunks:
        chunk = re.sub(r'[\t\r ]+', ' ', chunk).strip()
        if len(chunk) < 3:
            continue
        # Keep long sections searchable without losing their provenance.
        for index in range(0, len(chunk), 1200):
            part = chunk[index:index + 1200]
            if len(part) >= 3:
                out.append(Passage(location + (f' · 부분 {1 + index // 1200}' if len(chunk) > 1200 else ''), part))
    return out


def _validate_zip(data: bytes) -> None:
    from zipfile import ZipFile, BadZipFile
    try:
        with ZipFile(BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > 1200 or sum(x.file_size for x in infos) > 25_000_000:
                raise ValueError('압축 내부 데이터가 너무 큽니다.')
            if any(x.file_size > 12_000_000 or (x.compress_size and x.file_size > x.compress_size * 250)
                   for x in infos):
                raise ValueError('압축 내부 파일의 크기 또는 압축 비율을 확인해 주세요.')
    except BadZipFile as exc:
        raise ValueError('문서 압축 구조를 읽을 수 없습니다.') from exc


def parse_document(filename: str, data: bytes, declared_date: str = '') -> InstitutionDocument:
    """Extract text for user preview. Errors are explicit; no fake text fallback."""
    safe_name = PurePath(filename.replace('\\', '/')).name[:150]
    ext = '.' + safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if ext not in SUPPORTED:
        raise ValueError('지원하지 않는 형식입니다. TXT, MD, PDF, DOCX, HWP, HWPX만 허용합니다.')
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError('문서는 1바이트 이상, 8MB 이하이어야 합니다.')
    if declared_date and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', declared_date):
        raise ValueError('자료 기준일은 YYYY-MM-DD 형식으로 입력해 주세요.')
    passages: list[Passage] = []
    try:
        if ext in ('.txt', '.md'):
            decoded = data.decode('utf-8-sig')
            passages.extend(_paragraphs(decoded, '본문'))
        elif ext == '.pdf':
            from pypdf import PdfReader
            pdf = PdfReader(BytesIO(data), strict=False)
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ValueError('PDF는 최대 50쪽까지만 지원합니다.')
            for i, page in enumerate(pdf.pages, 1):
                passages.extend(_paragraphs(page.extract_text() or '', f'{i}쪽'))
        elif ext == '.docx':
            _validate_zip(data)
            from docx import Document
            doc = Document(BytesIO(data))
            for i, para in enumerate(doc.paragraphs, 1):
                passages.extend(_paragraphs(para.text, f'문단 {i}'))
            for n, table in enumerate(doc.tables, 1):
                for r, row in enumerate(table.rows, 1):
                    content = ' | '.join(cell.text.replace('\n', ' / ') for cell in row.cells)
                    passages.extend(_paragraphs(content, f'표 {n}행 {r}'))
        elif ext == '.hwp':
            from .hwp_extract import sections
            if not data.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
                raise ValueError('이 파일은 HWP5 형식이 아닙니다. HWPX 또는 PDF로 변환해 주세요.')
            for i, chunk in enumerate(sections(data)[:MAX_PARAGRAPHS], 1):
                passages.extend(_paragraphs(chunk, f'추출 문단 {i}'))
        elif ext == '.hwpx':
            from zipfile import ZipFile
            import xml.etree.ElementTree as ET
            _validate_zip(data)
            with ZipFile(BytesIO(data)) as z:
                names = sorted(n for n in z.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n, re.I))
                for i, path in enumerate(names[:MAX_PDF_PAGES], 1):
                    contents = z.read(path)
                    if b'<!DOCTYPE' in contents.upper() or b'<!ENTITY' in contents.upper():
                        raise ValueError('허용되지 않은 XML 선언이 포함됐습니다.')
                    root = ET.fromstring(contents)
                    for n, elem in enumerate(root.iter(), 1):
                        if elem.tag.split('}')[-1] in ('p', 'paragraph'):
                            text = ''.join(t.text or '' for t in elem.iter() if t.tag.split('}')[-1] in ('t', 'text'))
                            passages.extend(_paragraphs(text, f'섹션 {i} · 문단 {n}'))
    except (UnicodeDecodeError, ImportError) as exc:
        raise ValueError('문서를 읽을 수 없습니다. UTF-8로 저장하거나 PDF/DOCX로 변환해 주세요.') from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('문서 텍스트를 추출하지 못했습니다. 파일 형식이나 암호 설정을 확인해 주세요.') from exc
    if not passages:
        raise ValueError('추출할 텍스트가 없습니다. 이미지형 스캔 PDF라면 OCR 처리가 필요합니다.')
    final = []
    total = 0
    for part in passages[:MAX_PARAGRAPHS]:
        total += len(part.text)
        if total > MAX_TOTAL_CHARS:
            break
        final.append(part)
    if not final:
        raise ValueError('텍스트 추출 한도를 초과했습니다.')
    return InstitutionDocument(safe_name, hashlib.sha256(data).hexdigest(), tuple(final), declared_date)


STOPWORDS = {'관련', '안내', '어떻게', '알려줘', '해주세요', '위해', '기준', '대해', '대한', '있는',
             '아니면', '가능한가요', '가능', '내용', '내규', '법령', '기관', '업무', '필요', '적용'}


def question_terms(question: str) -> list[str]:
    if not 2 <= len(question.strip()) <= 500:
        raise ValueError('질문을 2~500자로 입력해 주세요.')
    words = re.findall(r'[가-힣A-Za-z0-9]{2,}', question)
    return list(dict.fromkeys(w.lower() for w in words if w not in STOPWORDS))[:30]


def search_documents(documents: Sequence[InstitutionDocument], question: str, limit: int = 8) -> list[Evidence]:
    terms = question_terms(question)
    if not terms or not documents:
        return []
    hits = []
    for doc in documents:
        for passage in doc.passages:
            lower = passage.text.lower()
            matched = [t for t in terms if t in lower]
            if not matched:
                continue
            # Show an excerpt around the first matching term, not arbitrary leading paragraphs.
            pos = min(lower.find(t) for t in matched)
            start = max(0, pos - 150)
            end = min(len(passage.text), pos + 430)
            snippet = ('…' if start else '') + passage.text[start:end] + ('…' if end < len(passage.text) else '')
            hits.append(Evidence(doc.name, passage.location, snippet, len(set(matched)) * 10 + min(len(matched), 5)))
    hits.sort(key=lambda x: (-x.score, x.document, x.location))
    return hits[:max(1, min(limit, 20))]
