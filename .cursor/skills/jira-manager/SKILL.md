---
name: jira-manager
description: >-
  MGAI E&E Projects(MEP) 보드의 Epic별 Slack 채널을 조회하고, 채널 논의를 한국어 Task로
  만들어 해당 Epic 하위(parent)로 연결한다. 사용자가 Epic 기반 slack→Jira backlog 자동 생성,
  jira manager, MEP 에픽 슬랙 스캔을 요청할 때 이 스킬을 따른다.
disable-model-invocation: true
---

# Jira Manager · MGAI E&E Epic → Slack → Task

## 목적

- **프로젝트:** MGAI E&E Projects, Jira 키 **`MEP`**, 사이트 **`hyperconnect.atlassian.net`**.
- **입력:** 보드에 올라온 **Epic** 각각의 설명/필드에서 **Slack 채널 ID**(`C…`) 또는 채널 링크.
- **출력:** 해당 Slack 히스토리를 근거로 **Task** 생성 후 **동일 Epic에 parent로 연결**.
- **언어 규칙 (필수):** 새로 만드는 Jira 이슈의 **`summary`(제목)와 `description`(본문)은 한국어**로 작성한다. Slack permalink, 채널 ID, 제품/시스템 고유명(예: Tinder, E&E)은 원문 유지 가능.

## 생성 기준 (엄격)

1. **단순 질문은 생성 금지**  
   - 정보 확인, 의견 요청, 아이디어 브레인스토밍 수준은 Task로 만들지 않는다.
2. **미래 처리/팔로업이 확실할 때만 생성**  
   - 누가/무엇을/언제까지 또는 후속 실행이 명확한 항목만 Task 후보로 채택한다.
3. **Epic 내 중복 금지**  
   - 의미가 같은 기존 Task가 있으면 만들지 않는다(문구만 다른 경우도 중복으로 본다).
4. **새 Task는 칸반 보드 컬럼으로 이동**  
   - 생성 직후 상태가 Backlog이면 `To Do`(보드 첫 컬럼)로 전환한다.

## 사용 MCP

| 역할 | 서버 |
|------|------|
| Jira (Hyperconnect) | `user-atlassian_hyperconnect` |
| Slack | `user-slack` |

- `user-atlassian_hyperconnect`가 인증 필요로 보이면 **먼저** `mcp_auth`로 OAuth를 완료한다.
- Tool 스키마는 MCP 디스크립터 파일을 호출 전에 확인한다 (`createJiraIssue`, `searchJiraIssuesUsingJql`, `getJiraIssue`, `getAccessibleAtlassianResources`, `slack_read_channel`, 필요 시 `slack_read_thread`, `slack_search_channels`).

## 상수 · 식별자

1. **`cloudId`**: `getAccessibleAtlassianResources` 결과에서 URL이 `https://hyperconnect.atlassian.net`인 항목의 `id`(UUID).
2. **프로젝트**: `projectKey = "MEP"`.
3. **이슈 타입**: Epic 하위 작업은 `issueTypeName = "Task"` (프로젝트 설정상 Subtask가 아닌 경우).
4. **Epic 연결 (팀관리 간소형 MEP):** `createJiraIssue` 호출 시 **`parent` 문자열로 Epic 키** 지정 (예: `parent: "MEP-2"`). 메타데이터상 `parent` 필드가 있는 타입임을 확인했다.

## 워크플로 (순서 고정)

1. **`getAccessibleAtlassianResources`** 로 `hyperconnect` cloudId 확보.
2. **Epic 목록 조회:** `searchJiraIssuesUsingJql`  
   `jql`: `project = MEP AND type = Epic ORDER BY key ASC`  
   `maxResults`: 50~100 (필요 시 `nextPageToken`으로 페이지).
3. **Epic별 Slack 채널 추출**
   - `getJiraIssue`로 해당 Epic 전체 필드 확인 (설명/description 우선).
   - 다음에서 **첫 채널 후보만** 사용하지 말고, Epic 본문에 명시된 **모든 고유 채널 ID**를 수집:
     - 정규식: `\\bC[A-Z0-9]{8,}\\b` (Slack 채널 ID)
     - URL: `…/archives/(C[A-Z0-9]+)`
     - 본문에 `#채널명`만 있는 경우 **`slack_search_channels`** 로 채널 ID 해석 후 사용.
   - 채널을 찾지 못한 Epic은 **스킵**하고, 결과 요약에 "Slack 채널 미지정"으로 기록한다.
4. **Slack 스캔**
   - 각 채널: **`slack_read_channel`** (`limit` 최대 100, `pagination_info`의 cursor로 과거 페이지를 이어 간다.)
   - **시스템/잡메시지 무시**: 채널 가입·이름변경 등은 Task 후보에서 제외.
   - 스레드가 본문의 핵심이면 `slack_read_thread`으로 보강.
   - **민감/비공개:** `slack_search_public_and_private` 사용 시 사용자 규칙 및 도구 설명상 동의 요구 준수.
5. **Task 후보 선정**
   - 실질적인 **후속 실행 과제**만 Task로 분리한다.
   - **단순 질문/아이디어 탐색/잡담**은 생성하지 않는다.
   - 한 Epic·한 채널에서 의미가 같은 줄글이 여러 개면 **하나의 Task로 병합**.
   - 실행 가능성이 불분명하면 생성하지 않고 보고에 "후속 불명확"으로 남긴다.
6. **중복 방지**
   - 생성 전 해당 Epic 자식 검색:
     `jql`: `project = MEP AND parent = <EPIC_KEY> ORDER BY updated DESC`
   - 새 Task의 요약과 기존 `summary`가 사실상 동일하면 **생성하지 않음**.
   - 요약이 다르더라도 본문 의도/대상/행동이 같으면 **중복으로 간주하고 생성하지 않음**.
7. **Jira 생성**
   - `createJiraIssue`:
     - `cloudId`, `projectKey`: `MEP`, `issueTypeName`: `Task`, `parent`: `<Epic 키>`,
     - **`summary`:** 한글 (짧은 업무 명사형, 접두 `[Epic별 토픽]` 등 규칙 통일 가능),
     - **`description`:** 한글 배경·수용 기준 요약·Slack 링크(permalink)·원문 발화 영문 발췌(필요 시),
     - `contentFormat`: `markdown` 권장.
   - 생성 직후 상태 확인:
     - 상태가 `Backlog`면 `getTransitionsForJiraIssue`로 가능한 전이 조회 후
       `transitionJiraIssue`로 `To Do`(또는 보드 첫 컬럼 상태)로 이동한다.
     - 상태가 이미 `To Do`/`In Progress` 등 보드 컬럼 상태면 추가 전이하지 않는다.
8. **사용자 보고:** Epic별 생성된 키 목록과 링크(`https://hyperconnect.atlassian.net/browse/<키>`), 스킵/중복 사유 요약.

## 한국어 작성 가이드 (Task)

| 필드 | 규칙 |
|------|------|
| summary | 업무 행위 + 대상 중심, 80자 내외 가능하면 짧게. 예: 「봉은사 전용 종교 필터 차별 포인트 PRD 초안 작성」 |
| description | 맥락(누가/언제), 해야 할 일, Slack 근거 링크, 열린 질항목은 불릿. |

영어가 원문인 Slack 인용구는 필요 시 괄호로 짧게 붙인다.

## 보드 참고

보드 필터 확인이 필요하면: `https://hyperconnect.atlassian.net/jira/software/projects/MEP/boards/1747` (사용 환경에 따라 보드 ID는 다를 수 있음.)

## 에러 처리

- Jira 403 / 프로젝트 없음: Hyperconnect MCP 재인증·VPN·권한 안내.
- Slack `channel_not_found`: `slack_search_channels` 또는 채널 ID 재확인.
- 대량 생성: 한 번 실행에 에픽·채널당 Task 수가 과도하면 **요약 목록만 먼저 제안** 후 사용자 확인을 받고 생성 (사용자가 “전부 생성”이라고 하면 진행).

## 추가 참조

상세 JQL·필드 예시는 [reference.md](reference.md)를 본다.
