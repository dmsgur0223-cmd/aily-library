"""One-click second-stage screening in bounded internal batches.

Outputs remain in caller session_state; no data is saved or sent except ISBN/title
for the existing YES24 path. Checkpoint after each chunk for partial failure.
"""
from __future__ import annotations
import pandas as pd
from .book_ai import apply_yes24_lookup

REVIEW_COLUMNS = ('2차판정','2차근거','서지설명','서지출처','YES24상품링크','신청취소사유')


def run_batches(results: pd.DataFrame, pending, key: str, *, qualifications=None,
                categories=(), progress=None, checkpoint=None, batch_size: int = 15,
                lookup=apply_yes24_lookup) -> pd.DataFrame:
    if not 1 <= batch_size <= 50: raise ValueError('내부 처리 묶음 크기는 1~50이어야 합니다.')
    result = results.copy()
    indexes = list(pending)
    total = len(indexes)
    if total > 5000: raise ValueError('한 번에 5,000권 이하만 처리할 수 있습니다.')
    if total and not str(key).strip(): raise ValueError('YES24 인증키가 없습니다.')
    for start in range(0, total, batch_size):
        indices = indexes[start:start+batch_size]
        def one_progress(fraction):
            if progress: progress(min(1.0,(start + float(fraction) * len(indices)) / max(total, 1)))
        try:
            checked = lookup(result.loc[indices], key, progress=one_progress,
                             qualifications=qualifications, enabled_categories=categories)
            if not isinstance(checked, pd.DataFrame): raise ValueError('YES24 검사 결과 형식이 올바르지 않습니다.')
            for col in REVIEW_COLUMNS:
                if col in checked.columns:
                    result.loc[indices,col] = checked[col]
        except (RuntimeError, ValueError, KeyError, TypeError, OSError):
            result.loc[indices,'2차판정'] = '조회 실패'
            result.loc[indices,'2차근거'] = 'YES24 2차 일괄 처리 중 오류 · 해당 건 재조회 필요'
        if checkpoint: checkpoint(result)
        if progress: progress(min(1.0,(start+len(indices))/max(total,1)))
    return result
