#!/usr/bin/env python3
"""Run jira-manager skill on Cursor Cloud (scheduled/CI safe)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CursorAgentError


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def load_skill_text(repo_root: Path) -> str:
    skill_md = repo_root / ".cursor" / "skills" / "jira-manager" / "SKILL.md"
    ref_md = repo_root / ".cursor" / "skills" / "jira-manager" / "reference.md"

    if not skill_md.exists():
        raise RuntimeError(f"Skill file not found: {skill_md}")
    if not ref_md.exists():
        raise RuntimeError(f"Skill reference not found: {ref_md}")

    return (
        "\n\n[SKILL.md]\n"
        + skill_md.read_text(encoding="utf-8")
        + "\n\n[reference.md]\n"
        + ref_md.read_text(encoding="utf-8")
    )


def build_prompt(skill_text: str) -> str:
    return f"""
너는 Jira 자동화 실행 에이전트다.
아래 스킬 지시를 그대로 따라 지금 즉시 작업을 수행해라.

중요 (스킬 「추출 파이프라인」+ Notion + 체크박스 규칙):
1) 대상은 hyperconnect.atlassian.net 의 MEP 프로젝트.
2) Epic description에서 Slack 채널 ID와 **Notion Tag**를 읽는다. Notion Tag가 있으면 MG AI meeting notes DB를 notion-query-data-sources + notion-fetch로 스캔한다.
3) Slack: reply 있는 부모마다 slack_read_thread **무조건**. Task 후보는 스레드 단위.
4) **`- [ ]` 미체크 체크박스 한 줄은 Task로 만들지 않는다.** Notion Action item placeholder, 빈 todo 리스트 제외. 서술·합의·summary에서만 추출.
5) male/female, launch/infra, UUD/RBR 등 **평행 트랙은 별도 Task**로 분리. summary 접두 `[트랙 태그]`는 필수(체크박스와 무관).
6) Jira 생성 전 **인벤토리 표**(Slack/Notion permalink, 트랙 태그, Y/N, 스킵 사유). 표 없이 createJiraIssue 금지.
7) 후속 실행이 확실한 항목만 생성=Y. 단순 질문·prep·`- [ ]` only → 생성=N.
8) 중복은 같은 트랙·같은 행동일 때만. description에 Slack/Notion 근거 URL 포함.
9) 한국어 summary/description. Backlog면 To Do 전이.
10) 보고: Slack/Notion 스캔 통계, 인벤토리 표, 생성·미생성 목록. 사용자 확인 없이 실행.

{skill_text}
""".strip()


def now_kst() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def write_markdown_log(
    repo_root: Path,
    *,
    status: str,
    run_id: str | None,
    result_text: str | None,
    error_text: str | None,
    exit_code: int,
) -> Path:
    ts = now_kst()
    log_dir = repo_root / "jira manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{ts.strftime('%Y-%m-%d_%H%M%S')}_run.md"
    log_path = log_dir / file_name

    github_run_url = None
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id_env = os.getenv("GITHUB_RUN_ID")
    if repo and run_id_env:
        github_run_url = f"https://github.com/{repo}/actions/runs/{run_id_env}"

    body = [
        "# Jira Manager 실행 로그",
        "",
        f"- 실행 시각(KST): {ts.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"- 상태: `{status}`",
        f"- 종료 코드: `{exit_code}`",
        f"- Cursor Run ID: `{run_id or '-'}'",
    ]
    if github_run_url:
        body.append(f"- GitHub Actions Run: {github_run_url}")
    body.extend(["", "## 실행 결과 요약", ""])

    if result_text:
        body.extend(["```markdown", result_text.strip(), "```", ""])
    else:
        body.extend(["(결과 본문 없음)", ""])

    if error_text:
        body.extend(["## 에러", "", "```text", error_text.strip(), "```", ""])

    log_path.write_text("\n".join(body), encoding="utf-8")
    return log_path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    try:
        api_key = require_env("CURSOR_API_KEY")
        model_id = os.getenv("CURSOR_MODEL_ID", "composer-2.5")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        log_path = write_markdown_log(
            repo_root,
            status="startup_error",
            run_id=None,
            result_text=None,
            error_text=str(exc),
            exit_code=1,
        )
        print(f"log_file={log_path}")
        return 1

    try:
        skill_text = load_skill_text(repo_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        log_path = write_markdown_log(
            repo_root,
            status="skill_load_error",
            run_id=None,
            result_text=None,
            error_text=str(exc),
            exit_code=1,
        )
        print(f"log_file={log_path}")
        return 1

    prompt = build_prompt(skill_text)
    # Skill text is embedded in the prompt; no GitHub repo clone needed.
    # Omitting repos avoids Cursor GitHub App branch verification in CI.
    print("cloud_mode=no_repo")
    options = AgentOptions(
        api_key=api_key,
        model=model_id,
        cloud=CloudAgentOptions(
            skip_reviewer_request=True,
            auto_create_pr=False,
        ),
        mcp_servers={
            "atlassian_hyperconnect": {
                "type": "http",
                "url": "https://mcp.atlassian.com/v1/mcp/authv2",
            },
            "slack": {
                "type": "http",
                "url": "https://mcp.slack.com/mcp",
                "auth": {
                    "client_id": os.getenv("SLACK_MCP_CLIENT_ID", "3660753192626.8903469228982")
                },
            },
            "Notion": {
                "type": "http",
                "url": "https://mcp.notion.com/mcp",
            },
        },
    )

    try:
        result = Agent.prompt(prompt, options)
        print(f"run_status={result.status}")
        print(f"run_id={result.id}")
        if result.result:
            print(result.result)
        if result.status == "error":
            log_path = write_markdown_log(
                repo_root,
                status=result.status,
                run_id=result.id,
                result_text=result.result,
                error_text=None,
                exit_code=2,
            )
            print(f"log_file={log_path}")
            return 2
        log_path = write_markdown_log(
            repo_root,
            status=result.status,
            run_id=result.id,
            result_text=result.result,
            error_text=None,
            exit_code=0,
        )
        print(f"log_file={log_path}")
        return 0
    except CursorAgentError as exc:
        err = f"startup_failed: {exc.message} retryable={exc.is_retryable}"
        print(err, file=sys.stderr)
        log_path = write_markdown_log(
            repo_root,
            status="startup_failed",
            run_id=None,
            result_text=None,
            error_text=err,
            exit_code=1,
        )
        print(f"log_file={log_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
