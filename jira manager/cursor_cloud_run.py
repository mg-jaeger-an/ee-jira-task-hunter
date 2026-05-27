#!/usr/bin/env python3
"""Run jira-manager skill on Cursor Cloud (scheduled/CI safe)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CloudRepository, CursorAgentError


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

중요:
1) 대상은 hyperconnect.atlassian.net 의 MEP 프로젝트.
2) Epic별 Slack 채널을 스캔하고, 후속 실행이 확실한 항목만 Task를 생성해 parent로 Epic에 연결.
3) 새로 만드는 Jira Task의 summary/description은 한국어.
4) 단순 질문(정보 확인/의견 질문/브레인스토밍)은 Task로 만들지 않는다.
5) Epic 내 중복 내용의 Task가 이미 있으면 만들지 않는다.
6) 새 Task는 Backlog가 아닌 칸반 보드 컬럼(To Do) 상태가 되도록 처리한다.
7) 결과로 생성한 이슈 키와 링크를 간단히 보고.
8) 사용자 확인 없이 실행한다.

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
        repo_url = require_env("CURSOR_REPO_URL")
        starting_ref = os.getenv("CURSOR_REPO_REF", "main")
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
    options = AgentOptions(
        api_key=api_key,
        model=model_id,
        cloud=CloudAgentOptions(
            repos=[CloudRepository(url=repo_url, starting_ref=starting_ref)],
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
