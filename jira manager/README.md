# Jira Manager · Cursor Cloud 자동 실행

MEP Epic 기준 Slack 채널을 스캔해 한국어 Task를 자동 생성하고 Epic(parent)에 연결합니다.

## 구성 파일

- `jira manager/cursor_cloud_run.py`  
  Cursor SDK(Python)로 Cloud Agent를 1회 실행합니다.
- `jira manager/requirements.txt`  
  실행 의존성(`cursor-sdk`)
- `.github/workflows/jira-manager-daily.yml`  
  매일 09:00 KST 스케줄 실행 + 수동 실행 버튼
- `.cursor/skills/jira-manager/*`  
  실행 시 프롬프트에 주입되는 스킬 정의
- `jira manager/logs/*.md`  
  실행 결과 마크다운 로그 (Actions artifact로 업로드)

## GitHub Secrets

필수 시크릿은 **`CURSOR_API_KEY` 하나**입니다.

1. `CURSOR_API_KEY` (필수) — [Integrations → API Keys](https://cursor.com/dashboard/integrations)
2. `SLACK_MCP_CLIENT_ID` (선택) — 기본값 `3660753192626.8903469228982`

Cloud Agent는 **GitHub repo clone 없이** 실행합니다 (스킬 본문을 프롬프트에 주입).  
따서 `CURSOR_REPO_URL` / Cursor GitHub repo 연동은 **필요 없습니다**.

MCP(Atlassian Hyperconnect, Slack) 인증은 Cursor 계정에 연결된 상태여야 합니다.

## 주의사항

- Cloud 에이전트는 매 실행마다 새로운 VM에서 동작합니다.
- MCP 인증 상태가 필요합니다. 특히 Hyperconnect Atlassian/Slack MCP가 조직 정책상 차단되면 실행이 실패할 수 있습니다.
- Task 생성 본문/제목은 스킬 규칙에 따라 한국어로 작성됩니다.
- 실행 시 **스레드 우선 스캔 → 인벤토리 표 → Jira 생성** 순서를 따르며, 로그에 미생성 permalink·사유가 포함됩니다.

## 테스트

GitHub Actions에서 `Jira Manager Daily (KST 09:00)` 워크플로를 수동 실행(`workflow_dispatch`)해 먼저 검증하세요.

실행 후 확인:

1. Actions 실행 상세 페이지 열기
2. 하단 **Artifacts**에서 `jira-manager-log-<run_id>` 다운로드
3. 내부 `.md` 파일로 스캔/생성 결과 확인
