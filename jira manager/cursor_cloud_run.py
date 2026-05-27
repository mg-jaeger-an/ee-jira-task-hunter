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

중요 (스킬 「추출 파이프라인」준수):
1) 대상은 hyperconnect.atlassian.net 의 MEP 프로젝트.
2) Epic별 Slack 채널 스캔 시 reply 있는 부모 메시지마다 slack_read_thread를 **무조건** 호출한다.
3) Task 후보는 스레드 단위(부모+reply)로 추출한다. male/female, launch/infra, 실험 ops/정책 등 **평행 트랙은 별도 Task 후보**로 분리하고 합치지 않는다.
4) Jira 생성 전 Epic·채널별 **인벤토리 표**를 먼저 작성한다(스레드 permalink, 트랙 태그, 생성 Y/N, 스킵 사유). 표 없이 createJiraIssue 호출 금지.
5) 커버리지 체크리스트(please/help, find a market, reserve, MDE, female/male 등)로 표 누락을 보완한다.
6) 후속 실행이 확실한 항목만 생성=Y로 두고, 단순 질문은 생성하지 않는다.
7) 중복은 **같은 트랙·같은 행동**일 때만; 다른 트랙은 중복 아님. summary에 [트랙 태그] 접두 필수.
8) 새 Task summary/description은 한국어. 생성 후 Backlog면 To Do로 전이.
9) 최종 보고에 반드시 포함: 스캔 통계(부모 수, thread-read 수), 인벤토리 표 전체, 생성 목록, **미생성 목록**(permalink+사유).
10) 사용자 확인 없이 실행한다.

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
