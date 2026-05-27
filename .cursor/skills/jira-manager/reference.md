# Jira Manager — reference

## JQL 스니펫

```text
# MEP 에픽 전체
project = MEP AND issuetype = Epic ORDER BY key ASC

# 특정 에픽의 자식(팀관리 간소형, parent 필드 기준)
project = MEP AND parent = MEP-7 ORDER BY updated DESC

# 트랙 키워드로 기존 Task 교차 확인 (중복 판단 보조)
project = MEP AND parent = MEP-7 AND (summary ~ "female" OR description ~ "female test")
project = MEP AND parent = MEP-7 AND (summary ~ "MDE" OR description ~ "MDE")
project = MEP AND parent = MEP-7 AND (summary ~ "throttl" OR description ~ "throttl")

# 채널 ID가 에픽 설명에 없을 때: 최근 수정 에픽만
project = MEP AND issuetype = Epic AND updated >= -30d ORDER BY updated DESC
```

## 체크박스 `- [ ]` 제외 (필수)

Task **생성 금지** 대상:

- Notion·Slack의 **미체크 todo 한 줄**: `- [ ] …`
- Action item 섹션에만 있고 본문 논의·합의가 없는 placeholder

Task **생성 가능** 출처:

- 서술형 논의, 결정, deadline이 있는 실행 문장
- meeting-notes `<summary>` / `AI summary`의 확정된 후속 과제
- Slack 스레드 본문의 명시적 요청

**구분:** summary 접두 `[UUD infra]` 등 **트랙 태그**는 체크박스가 아님.

## Epic Notion Tag 추출

Epic description 예:

```markdown
# Notion Tag:

uud
```

- 여러 태그: 줄 단위 또는 쉼표 구분
- DB `Tags` multi_select 값과 일치해야 함 (`risk-based-retreival` 등 철자 주의)

## Notion SQL (MG AI meeting notes)

```sql
SELECT url, Name, "date:Date:start" AS meeting_date, Tags, "AI summary"
FROM "collection://f68f73ca-0ddb-4030-a9e9-35a10c408374"
WHERE Tags LIKE '%uud%'
ORDER BY "date:Date:start" DESC
LIMIT 30
```

- `notion-query-data-sources` → 후보마다 `notion-fetch`
- DB URL: https://www.notion.so/4a85deaf44db4d6e8f6448dc85a35a16

## 인벤토리 표 템플릿 (1단계 필수)

Epic `MEP-7` · Slack + Notion 예시:

| 근거 permalink | 트랙 태그 | 후속 작업 요약 (한국어) | 생성? | 스킵/보류 사유 |
|----------------|-----------|------------------------|-------|----------------|
| https://…/p1771479003601889 | `[RBR female]` | Female swiper 테스트 US 마켓… | Y | — |
| https://www.notion.so/36cce00… | `[UUD infra]` | HyperPod 파이프라인 마무리 | Y | — |
| https://www.notion.so/31bce00… | — | Hinge prep | N | 체크박스 [ ] / prep only |

- `생성=Y` 행만 2단계에서 `createJiraIssue` 호출.
- actionable인데 표에 없으면 **누락 후보** 행 추가.

## 커버리지 체크리스트 키워드

생성 전 Slack·스레드 본문에 아래가 있으면 인벤토리 표에 대응 행이 있는지 확인:

| 유형 | 키워드/패턴 예 |
|------|----------------|
| 명시적 요청 | please, help, need to, could you, @mention + 실행 요청 |
| 실험 ops | find a market, reserve, MDE, experiment, test duration, tracker |
| 결정·합의 | we reserved, is enough, confirmed, agreed, 일정/마켓/기간 확정 |
| 트랙 식별 | female, male, swiper, cohort, 2b, 5a, 4a, 5b |

Epic description의 **트래킹 필수 키워드**도 동일하게 매칭한다.

## summary 트랙 태그 규칙

- 형식: `[<Epic/프로젝트 토픽> <세부>] …` — 예: `[RBR female]`, `[RBR infra]`, `[봉은사 PRD]`
- 중복 비교 시 태그 + 핵심 키워드(female, MDE, throttling 등)를 함께 본다.
- **다른 태그 = 다른 Task** (런치 일정 Task ≠ female market Task).

## Slack 채널 ID 추출

- 패턴 `C[A-Z0-9]{8,}`
- 예시 URL: `https://matchgroup.enterprise.slack.com/archives/C0B4Z81LVQS/p1779257598902289` → 채널 `C0B4Z81LVQS`

## thread-first 스캔

1. `slack_read_channel` — 기간 내 부모 메시지
2. reply 있는 부모마다 `slack_read_thread` — **무조건**
3. 후보·Task는 **스레드 permalink** 기준

## createJiraIssue (Hyperconnect MCP) 필수 인자 예시

- `cloudId`: hyperconnect 리소스 UUID
- `projectKey`: `"MEP"`
- `issueTypeName`: `"Task"`
- `parent`: `"MEP-7"` (대상 에픽)
- `summary`: `[RBR female] Female swiper 테스트 마켓 예약 및 MDE 확정` (한글 + 태그)
- `description`: 한글 + markdown + **스레드 permalink**
- `contentFormat`: `"markdown"`

## MCP 도구 이름 (Atlassian 원격 MCP)

- `getAccessibleAtlassianResources`
- `searchJiraIssuesUsingJql`
- `getJiraIssue`
- `createJiraIssue`
- `getTransitionsForJiraIssue`
- `transitionJiraIssue`

## Notion MCP 도구

- `mcp_auth` (인증)
- `notion-fetch`
- `notion-query-data-sources`
- `notion-search` (보조)

## 실행 보고 필수 섹션 (로그·사용자 응답)

```markdown
## 스캔 통계
- 부모 메시지: N
- slack_read_thread 호출: M
- Notion 태그: uud
- notion-fetch 페이지: K
- `- [ ]` 스킵(대략): L줄

## 인벤토리 표
(표 전체 붙여넣기)

## 생성됨
- MEP-XX: https://hyperconnect.atlassian.net/browse/MEP-XX

## 미생성
- <permalink>: <사유>
```

## 칸반 컬럼 배치

- 새 Task 생성 후 상태가 `Backlog`라면 전이 도구로 `To Do`(보드 첫 컬럼)로 옮긴다.
