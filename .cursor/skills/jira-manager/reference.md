# Jira Manager — reference

## JQL 스니펫

```text
# MEP 에픽 전체
project = MEP AND issuetype = Epic ORDER BY key ASC

# 특정 에픽의 자식(팀관리 간소형, parent 필드 기준)
project = MEP AND parent = MEP-2 ORDER BY updated DESC

# 채널 ID가 에픽 설명에 없을 때: 최근 수정 에픽만
project = MEP AND issuetype = Epic AND updated >= -30d ORDER BY updated DESC
```

## Slack 채널 ID 추출

- 패턴 `C[A-Z0-9]{8,}`
- 예시 URL: `https://matchgroup.enterprise.slack.com/archives/C0B4Z81LVQS/p1779257598902289` → 채널 `C0B4Z81LVQS`

## createJiraIssue (Hyperconnect MCP) 필수 인자 예시

개념적으로 다음을 채운다 (실제 키는 MCP 스키마와 일치시킴):

- `cloudId`: hyperconnect 리소스 UUID
- `projectKey`: `"MEP"`
- `issueTypeName`: `"Task"`
- `parent`: `"MEP-2"` (대상 에픽)
- `summary`: 한글
- `description`: 한글 + markdown Slack 링크
- `contentFormat`: `"markdown"`

## MCP 도구 이름 (Atlassian 원격 MCP)

브리지 제공 도구 이름이 다를 수 있음. 디스크립터 기준 예:

- `getAccessibleAtlassianResources`
- `searchJiraIssuesUsingJql`
- `getJiraIssue`
- `createJiraIssue`
- `getTransitionsForJiraIssue`
- `transitionJiraIssue`

## 칸반 컬럼 배치

- 새 Task 생성 후 상태가 `Backlog`라면 전이 도구로 `To Do`(보드 첫 컬럼)로 옮긴다.
- 프로젝트 워크플로 이름이 다르면 보드 첫 컬럼 상태명을 우선 사용한다.
