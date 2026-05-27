---
name: jira-manager
description: >-
  MGAI E&E Projects(MEP) 보드의 Epic별 Slack 채널·Notion 미팅 노트(Notion Tag)를 조회하고,
  한국어 Task를 만들어 해당 Epic 하위(parent)로 연결한다. Epic slack/Notion→Jira,
  jira manager, MEP 에픽 스캔을 요청할 때 이 스킬을 따른다.
disable-model-invocation: true
---

# Jira Manager · MGAI E&E Epic → Slack · Notion → Task

## 목적

- **프로젝트:** MGAI E&E Projects, Jira 키 **`MEP`**, 사이트 **`hyperconnect.atlassian.net`**.
- **입력 (Epic description에서 추출):**
  - **Slack 채널 ID**(`C…`) 또는 채널 링크
  - **Notion Tag** (예: `uud`, `RBR`) — MG AI meeting notes DB에서 해당 태그 미팅 노트
- **출력:** Slack·Notion 근거로 **Task** 생성 후 **동일 Epic에 parent로 연결**.
- **언어 규칙 (필수):** 새로 만드는 Jira 이슈의 **`summary`(제목)와 `description`(본문)은 한국어**로 작성한다. Slack permalink, 채널 ID, 제품/시스템 고유명(예: Tinder, E&E)은 원문 유지 가능.

## 생성 기준 (엄격)

1. **단순 질문은 생성 금지**  
   - 정보 확인, 의견 요청, 아이디어 브레인스토밍 수준은 Task로 만들지 않는다.
2. **미래 처리/팔로업이 확실할 때만 생성**  
   - 누가/무엇을/언제까지 또는 후속 실행이 명확한 항목만 Task 후보로 채택한다.
3. **Epic 내 중복 금지**  
   - 의미가 같은 기존 Task가 있으면 만들지 않는다(문구만 다른 경우도 중복으로 본다).
   - **다른 실행 트랙**(성별·코호트·실험 arm·인프라 vs 실험 ops 등)은 중복이 **아니다** — 아래 「평행 트랙 분리」 참고.
4. **새 Task는 칸반 보드 컬럼으로 이동**  
   - 생성 직후 상태가 Backlog이면 `To Do`(보드 첫 컬럼)로 전환한다.
5. **미체크 체크박스(`- [ ]`)는 Task로 만들지 않음 (필수)**  
   - Notion·Slack 본문의 **`- [ ]` …** (미완료 todo 한 줄)은 Task 후보에서 **제외**한다.  
   - 빈 Action item 섹션, 템플릿 placeholder, 회의 중 메모용 체크리스트를 Jira로 옮기지 않는다.  
   - Task는 **서술형 논의·합의·미팅 summary·명시적 실행 요청**에서만 추출한다.  
   - 참고: summary의 **`[트랙 태그]`**(예: `[UUD infra]`)는 체크박스가 아니며 **필수 접두**이다.

## 추출 파이프라인 (필수 — 누락 방지)

아래 규칙은 **채널 스캔 → 후보 선정 → Jira 생성** 전 과정에 적용한다. 한 번에 “읽고 곧바로 생성”만 하지 않는다.

### 1) 스레드 우선 스캔 (thread-first)

- 각 채널: **`slack_read_channel`** 로 기간 내 부모 메시지를 수집한다.
- **기간 내 `reply_count ≥ 1`(또는 스레드 reply가 존재)인 부모 메시지는 무조건 `slack_read_thread`로 전체 스레드를 읽는다.**  
  “스레드가 본문의 핵심이면” 같은 판단은 하지 않는다 — reply가 있으면 항상 thread-read.
- **Task 후보는 스레드 단위**(부모 + 모든 reply)로 추출한다. 부모 메시지 한 줄만 보고 판단하지 않는다.
- 스레드 permalink를 후보·Task description에 반드시 남긴다.

### 2) 평행 트랙 분리 (병합 금지)

한 메시지·한 스레드에 여러 실행 축이 섞여 있으면 **트랙마다 최소 1개 Task 후보**로 분리한다. 서로 다른 트랙을 하나의 Task로 합치지 않는다.

| 구분 예시 | 별도 Task |
|-----------|-----------|
| male test vs female test | 각각 |
| launch 일정 vs 인프라 실험 충돌 | 각각 |
| 모델 재학습 vs 마켓 예약/MDE | 각각 |
| 정책 조사 vs throttling 검증 | 각각 |

- **실험 ops**(마켓 find/reserve, MDE, test duration, tracker)는 **런치/인프라 일정** Task에 흡수하지 않는다.
- 부모가 “male 준비 + female market 찾기”처럼 **두 요청을 한 문장에** 말해도, female 전용 후보를 반드시 표에 적는다.

### 3) 2단계 실행: 인벤토리 → 생성

**1단계 — 인벤토리 표 (Jira 생성 전 필수 산출물)**  
Epic·채널마다 아래 표를 먼저 작성한다. 표 없이 `createJiraIssue`를 호출하지 않는다.

| 근거 permalink (Slack 스레드 / Notion 페이지) | 트랙 태그 (예: `[RBR female]`) | 후속 작업 요약 (한국어) | 생성? (Y/N) | 스킵/보류 사유 |
|-----------------------------------------------|-------------------------------|------------------------|-------------|----------------|

- `생성=Y`인 행만 **2단계**에서 Jira에 생성한다.
- 스킵 사유에 `체크박스 [ ]`를 자주 사용한다(해당 줄만으로는 생성하지 않음).
- actionable한데 표에 없으면 **「누락 후보」** 행을 추가하고, 중복이 아니면 `생성=Y`로 올린다.

**활발한 채널 휴리스틱:** 기간 내 reply 있는 스레드가 10개 이상이면, 후보 표에 **최소 3개 이상** actionable 행이 있는지 검토한다(상한은 「대량 생성」 규칙).

### 4) 커버리지 체크리스트 (생성 전 검증)

인벤토리 표 작성 후, Slack 본문·스레드에 아래 패턴이 있으면 **대응 행이 표에 있는지** 확인한다. 없으면 누락 후보로 추가한다.

- 명시적 요청: `please`, `help`, `need to`, `could you`, `@mention` + 실행 요청
- 실험 ops: `find a market`, `reserve`, `MDE`, `experiment`, `test duration`, `tracker`
- 결정·합의: `we reserved`, `is enough`, `confirmed`, `agreed`, 일정·마켓·기간 확정 문맥
- 성별·arm: `female`, `male`, `swiper`, `cohort`, `2b`, `5a` 등 **트랙 식별자**

Epic description에 **트래킹 필수 키워드**가 있으면(예: `female test`, `market reserve`) 해당 키워드에 대한 표 행 존재 여부를 우선 확인한다.

### 5) 중복 판단 (좁게)

- 생성 전 JQL: `project = MEP AND parent = <EPIC_KEY> ORDER BY updated DESC`
- 새 Task `summary`에는 **트랙 태그**를 포함한다 — 예: `[RBR female] Female swiper 테스트 마켓 예약 및 MDE 확정`
- 중복 비교 시 **summary·description·트랙 태그·핵심 키워드**(female, male, MDE, throttling, infra 등)를 교차 확인한다.
- **같은 Epic의 다른 주제·다른 트랙**은 중복이 아니다. “런치 일정” Task가 있어도 “female market reserve”는 별도 생성 가능.
- 요약 문구만 다르고 **같은 트랙·같은 행동·같은 대상**일 때만 중복으로 스킵한다.

### 6) 실행 보고·로그 (미생성 의무 기록)

사용자 보고 및 Cloud 실행 로그(`jira manager/logs/`)에 **반드시** 포함한다.

- 읽은 부모 메시지 수 / **`slack_read_thread` 호출 수**
- Notion: 조회 태그·**fetch한 페이지 수**·`- [ ]`로 스킵한 줄 수(대략)
- 인벤토리 표 후보 수 / **실제 생성 수**
- **미생성 목록**: permalink · 한 줄 사유 (`중복→MEP-n`, `후속 불명확`, `병합 금지→별도 트랙으로 분리함`, `단순 질문` 등)
- 생성된 이슈 키·링크 목록

## Notion 연동 (Epic Notion Tag)

### Epic에서 태그 추출

- `getJiraIssue` description에서 **`# Notion Tag:`** (또는 `Notion Tag:`) 아래 값을 읽는다.
- 여러 태그면 쉼표·줄바꿈 단위로 분리, **소문자 정규화** 후 DB `Tags` 옵션명과 매칭 (예: `uud`, `RBR`, `risk-based-retreival`).
- Notion Tag가 없으면 Notion 스캔은 **스킵**하고 Slack만 처리한다.

### MG AI meeting notes DB

- 기본 DB: **⌨️ MG AI meeting notes**  
  `https://www.notion.so/4a85deaf44db4d6e8f6448dc85a35a16`
- data source ID: `collection://f68f73ca-0ddb-4030-a9e9-35a10c408374` (`notion-fetch`로 확인)

### Notion 스캔 순서

1. 인증 필요 시 **`user-Notion`** 에서 `mcp_auth` 먼저 수행.
2. **`notion-query-data-sources`** (SQL): Epic 태그별 페이지 목록 조회 (최근 `Date` 내림차순, 상한 30~50).
3. 후보 페이지마다 **`notion-fetch`** 로 전문·`AI summary`·meeting-notes summary 읽기.
4. **`- [ ]` 줄은 Task 추출에 사용하지 않음** — 본문 서술·합의·summary의 실행 과제만 후보화.
5. Epic에 **여러 Notion Tag**가 있으면 태그마다 쿼리; **다른 트랙**이면 별도 Task(평행 트랙 분리).
6. 한 미팅 노트에 여러 실행 축이 있으면 **페이지 permalink는 같고 트랙 태그만 다른** 행으로 인벤토리 표에 여러 줄 가능.
7. description에 **Notion 페이지 URL** 필수 (Slack과 동시 근거면 둘 다 링크).

### Notion만 해당하는 스킵

- prep/브레인스토밍·OKR **현황 공유만** 있는 노트 → `생성=N`, `단순 질문` 또는 `현황 공유`
- 태그는 있으나 본문이 Epic 주제와 무관한 섹션(다른 프로젝트 OKR 등) → 해당 섹션만 제외

## 사용 MCP

| 역할 | 서버 |
|------|------|
| Jira (Hyperconnect) | `user-atlassian_hyperconnect` |
| Slack | `user-slack` |
| Notion | `user-Notion` |

- `user-atlassian_hyperconnect` / `user-Notion` 인증 필요 시 **먼저** `mcp_auth`.
- Tool 스키마는 호출 전 디스크립터 확인: Jira(`createJiraIssue`, `searchJiraIssuesUsingJql`, `getJiraIssue`, …), Slack(`slack_read_channel`, `slack_read_thread`, …), Notion(`notion-fetch`, `notion-query-data-sources`, `notion-search`).

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
   - 채널을 찾지 못한 Epic은 Slack 스캔 **스킵**, "Slack 채널 미지정" 기록.
3b. **Epic별 Notion Tag 추출** (「Notion 연동」 참고)
   - Notion Tag 없으면 4b 스킵.
4. **Slack 스캔 (스레드 우선)** — 채널이 있을 때만
   - 각 채널: **`slack_read_channel`** (`limit` 최대 100, cursor로 페이지 이어 읽기).
   - **시스템/잡메시지 무시**: 채널 가입·이름변경 등은 Task 후보에서 제외.
   - **reply 있는 부모 → 무조건 `slack_read_thread`** (「추출 파이프라인」1항).
   - **민감/비공개:** `slack_search_public_and_private` 사용 시 사용자 규칙 및 도구 설명상 동의 요구 준수.
4b. **Notion 스캔** — Notion Tag가 있을 때만 (「Notion 연동」 순서)
5. **1단계 — 인벤토리 표 작성** (Slack + Notion 통합)
   - Slack: 스레드 단위 / Notion: 페이지(및 트랙) 단위로 후속 실행 과제 추출.
   - **`- [ ]` 체크박스 줄만으로는 행을 추가하지 않음.**
   - 단순 질문/잡담은 `생성=N` + 사유 `단순 질문` 또는 `체크박스 [ ]`.
   - **커버리지 체크리스트**로 누락 후보 보완(Slack·Notion 각각).
6. **중복 방지 (표 단계)**
   - Epic 자식 JQL 조회 후, 표의 각 `생성=Y` 행이 기존 Task와 **같은 트랙·행동**인지 확인.
   - 중복이면 `생성=N`, 사유 `중복→<기존 키>`.
7. **2단계 — Jira 생성** (`생성=Y`만)
   - `createJiraIssue`:
     - `cloudId`, `projectKey`: `MEP`, `issueTypeName`: `Task`, `parent`: `<Epic 키>`,
     - **`summary`:** 한글 + **`[트랙 태그]`** 접두 (예: `[RBR female] …`),
     - **`description`:** 한글 배경·수용 기준·**근거 링크**(Slack 스레드 / Notion 페이지)·필요 시 영문 발췌,
     - `contentFormat`: `markdown` 권장.
   - 생성 직후 Backlog이면 `getTransitionsForJiraIssue` → `transitionJiraIssue`로 `To Do` 이동.
8. **사용자 보고** (「실행 보고·로그」항목 전체 포함).

## 한국어 작성 가이드 (Task)

| 필드 | 규칙 |
|------|------|
| summary | `[트랙 태그]` + 업무 행위 + 대상, 80자 내외. 예: `[RBR female] Female swiper 테스트 마켓 예약 및 MDE(2b·5a) 확정` |
| description | 맥락(누가/언제), 해야 할 일, **근거 Slack/Notion permalink**, 열린 항목은 불릿. `- [ ]` 원문을 그대로 복사하지 않는다. |

영어가 원문인 Slack 인용구는 필요 시 괄호로 짧게 붙인다.

## 운영 점검 (선택·권장)

- **주 1회:** 해당 Epic Slack 채널에서 “permalink는 있는데 Jira 자식 Task에 없는 actionable 스레드”를 5분 내 수동 점검한다.
- Epic description에 이번 분기 **트래킹 필수 키워드**를 적어 두면 커버리지 체크리스트 매칭이 쉬워진다.

## 보드 참고

`https://hyperconnect.atlassian.net/jira/software/projects/MEP/boards/1747`

## 에러 처리

- Jira 403 / 프로젝트 없음: Hyperconnect MCP 재인증·VPN·권한 안내.
- Slack `channel_not_found`: `slack_search_channels` 또는 채널 ID 재확인.
- 대량 생성: Epic·채널당 `생성=Y` 행이 과도하면 **인벤토리 표만 먼저 보고** 후 사용자 확인(사용자가 “전부 생성”이면 2단계 진행). Cloud 일일 실행은 표+생성을 한 번에 하되, 보고에 표 전체를 포함한다.

## 추가 참조

인벤토리 표 템플릿·체크리스트 키워드·JQL 예시는 [reference.md](reference.md)를 본다.
