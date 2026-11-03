# AILY 2.0 v4.96 — 공개 웹 배포용 코드

Streamlit Community Cloud 배포용으로 필요한 Python 소스만 담았습니다. 개인용 API 인증키, 기관 내부 규정 DB, 문서 원본은 포함하지 않습니다.

## Streamlit 배포

1. 본 폴더 **내의 파일 및 `aily/` 디렉터리**를 GitHub 저장소로 업로드합니다.
2. [Streamlit Community Cloud](https://share.streamlit.io/)의 Create app에서 해당 저장소·브랜치를 선택하고 엔트리포인트를 `web_app.py`로 설정합니다. GitHub에 이 폴더를 하위 디렉터리로 올린다면 파일 경로에 그 접두사를 붙입니다.
3. Advanced settings → Secrets에서 필요한 인증정보만 별도로 입력합니다. 예시 키 이름만 제시하며, 실제 값은 직접 입력해야 합니다.

```toml
AILY_LAW_OC = ""
AILY_YES24_API_KEY = ""
AILY_QNET_API_KEY = ""
AILY_OPENAI_API_KEY = ""
AILY_OPENAI_MODEL = "gpt-4.1-mini"
```

4. 처음에는 민감정보가 없는 공개 질의로 통계·법령·도서 조회를 확인하고, 실제 외부 API 성공 여부와 화면 표시를 구분해 검증하세요.

## 보안·기능 범위

- 로그인 없는 공개 시연본입니다. 개인정보·기관 내부 문서·민감한 원본 업로드를 금지합니다.
- 업로드 문서는 명시적으로 **AI 적용**을 누른 경우에만 현재 브라우저 세션에 사용됩니다. 영구 저장 및 다른 기관 공유 기능은 없습니다.
- API 인증키는 배포 플랫폼의 Secrets에만 등록합니다. 저장소, ZIP, 화면에 인증키를 넣지 마세요.
- '관리자 · 공개' 페이지는 서버 설정 수정 권한이 없는 상태/세션관리 UI입니다.
- KOSIS 등 MCP의 자동 호출은 네트워크 및 제공 도구 사양에 따라 실패할 수 있습니다. 실제 연결 성공은 별도 확인이 필요합니다.
- 법령 신구 비교의 개정일·조문은 국가법령정보 API 반환 자료에 한하며 자동 법률판단이 아닙니다.
- 화면상 문서 파일명과 정책 기준은 기관별 운영규정 검증이 필요하며, 실제 기관 규칙을 추측해서 적용하지 않습니다.
- 기존 Windows 로컬판과 기능 및 자료 저장 방식이 다릅니다.

## 로컬 시험

```bash
python -m pip install -r requirements.txt
python -m streamlit run web_app.py
```
