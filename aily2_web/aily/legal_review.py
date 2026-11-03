"""Grounded evidence packet for institution-specific legal review.

Do not infer institutional scope or a legal hierarchy from a document title.
No function here determines legality, contractual authority, or final approver.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

from .generic_workspace import InstitutionDocument, Evidence, search_documents


@dataclass(frozen=True)
class LawEvidence:
    name: str
    identifier: str
    effective_date: str
    article: str
    text: str
    url: str = ''


@dataclass(frozen=True)
class ReviewPacket:
    institution: str
    question: str
    internal: tuple[Evidence, ...]
    laws: tuple[LawEvidence, ...]
    cautions: tuple[str, ...]


def build_packet(institution: str, question: str, docs: Sequence[InstitutionDocument],
                 laws: Sequence[LawEvidence]) -> ReviewPacket:
    if len(institution.strip()) > 100:
        raise ValueError('기관명은 100자 이하로 입력하세요.')
    if len(laws) > 12:
        raise ValueError('법령 근거는 최대 12개까지 선택할 수 있습니다.')
    internal = tuple(search_documents(docs, question))
    cautions = [
        '이 결과는 근거 탐색·비교 자료이며 위법 여부나 전결권자를 자동 확정하지 않습니다.',
        '적용 법령의 범위, 위임 근거, 특별법·조례 관계와 기준일은 담당자가 확인해야 합니다.',
        'HWP/PDF 표 추출 결과에서 결재권자 열·표 구조가 누락될 수 있으므로 원본 확인이 필요합니다.',
    ]
    if not docs:
        cautions.append('기관별 적용 내규가 등록되지 않아 특정 기관의 업무기준을 제시할 수 없습니다.')
    if not internal:
        cautions.append('질문과 일치하는 기관 규정 문구를 찾지 못했습니다. 근거 없는 판단은 하지 않습니다.')
    if not laws:
        cautions.append('선택된 국가법령정보 조문이 없습니다. 상위 법령 검증을 완료한 상태가 아닙니다.')
    if any(not law.effective_date for law in laws):
        cautions.append('일부 법령은 시행일을 확인할 수 없습니다. 국가법령정보센터 원문을 재확인하세요.')
    return ReviewPacket(institution.strip() or '기관 미지정', question, internal, tuple(laws), tuple(cautions))


def render_evidence_text(packet: ReviewPacket) -> str:
    lines = [f'질문: {packet.question}', f'기관: {packet.institution}',
             '※ 아래는 조회된 근거이며 법적 효력·충돌 여부의 확정 판정이 아닙니다.', '', '기관 내규 근거']
    if not packet.internal:
        lines.append('일치 근거 없음')
    for i, h in enumerate(packet.internal, 1):
        lines.append(f'[내규 {i}] {h.document} / {h.location}\n{h.excerpt}')
    lines += ['', '선택된 상위 법령 조문']
    if not packet.laws:
        lines.append('조회·선택된 법령 조문 없음')
    for i, x in enumerate(packet.laws, 1):
        lines.append(f'[법령 {i}] {x.name} / {x.article} / 시행일 {x.effective_date or "미확인"}\n{x.text[:2000]}\n{x.url}')
    lines += ['', '추가 확인 사항']
    lines.extend('- ' + c for c in packet.cautions)
    return '\n'.join(lines)
