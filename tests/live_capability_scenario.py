#!/usr/bin/env python3
"""Live capability scenario for MultiFlexi MCP Server.

Exercises every MCP surface (resources, read-only tools, prompts) against a
real MultiFlexi API instance and reports whether each capability receives
usable data back.

Usage:
  MULTIFLEXI_HOST=https://demo.multiflexi.eu/api/VitexSoftware/MultiFlexi/1.0.0 \\
  MULTIFLEXI_USERNAME=demo MULTIFLEXI_PASSWORD=demo \\
    python tests/live_capability_scenario.py

  python tests/live_capability_scenario.py \\
    --host https://vyvojar.spoje.net/multiflexi/api/VitexSoftware/MultiFlexi/1.0.0 \\
    --username mcp-test --password '...'

Exit code is 0 only when every non-skipped check passes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Prefer this repo's src/ over an installed package.
SRC = str(Path(__file__).resolve().parent.parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@dataclass
class CheckResult:
    name: str
    kind: str  # resource | tool | prompt | meta
    ok: bool
    detail: str = ""
    sample: Any = None
    skipped: bool = False


@dataclass
class ScenarioReport:
    host: str
    results: List[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok and not r.skipped)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok and not r.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.skipped)


def _is_error_payload(data: Any) -> Optional[str]:
    """Return an error message if *data* looks like an MCP/API error blob."""
    if isinstance(data, str):
        if data.startswith("Unexpected error:") or data.startswith("Resource not found:"):
            return data
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(data, dict):
        return None
    if data.get("error") is True:
        parts = [
            str(data.get("message") or data.get("reason") or "error"),
            f"status={data.get('status')}" if data.get("status") is not None else "",
            f"operation={data.get('operation')}" if data.get("operation") else "",
        ]
        return " | ".join(p for p in parts if p)
    return None


def _has_usable_data(data: Any) -> Tuple[bool, str]:
    """Heuristic: response contains at least one record or a non-empty object."""
    if data is None:
        return False, "null response"
    if isinstance(data, str):
        err = _is_error_payload(data)
        if err:
            return False, err
        if not data.strip():
            return False, "empty string"
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return True, f"raw text ({len(data)} chars)"

    err = _is_error_payload(data)
    if err:
        return False, err

    if isinstance(data, list):
        return True, f"list len={len(data)}"
    if isinstance(data, dict):
        # Numeric-string keys (apps) or nested collections
        if not data:
            return True, "empty object (API OK, no rows)"
        for key in (
            "apps",
            "jobs",
            "companies",
            "users",
            "runtemplates",
            "credentials",
            "credential_types",
            "topics",
            "eventsources",
            "eventrules",
            "tasks",
            "response",
        ):
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    return True, f"{key} list len={len(val)}"
                if isinstance(val, dict):
                    return True, f"{key} dict keys={len(val)}"
        if all(str(k).isdigit() for k in data.keys()):
            return True, f"id-map keys={len(data)}"
        if "id" in data:
            return True, f"single record id={data.get('id')}"
        if "job_id" in data and "status" in data:
            return True, f"job_status={data.get('status')}"
        return True, f"dict keys={sorted(data.keys())[:8]}"
    return True, f"type={type(data).__name__}"


def _first_id(data: Any) -> Optional[int]:
    """Extract a usable numeric id from list/map/single-record payloads."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict):
        if "id" in data and isinstance(data["id"], int):
            return data["id"]
        for key in (
            "apps",
            "jobs",
            "companies",
            "users",
            "runtemplates",
            "credentials",
            "credential_types",
            "topics",
            "eventsources",
            "eventrules",
            "tasks",
            "response",
        ):
            if key in data:
                found = _first_id(data[key])
                if found is not None:
                    return found
        # id-keyed map: {"1": {...}, "2": {...}}
        for key, val in data.items():
            if str(key).isdigit():
                if isinstance(val, dict) and isinstance(val.get("id"), int):
                    return val["id"]
                try:
                    return int(key)
                except ValueError:
                    continue
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("id"), int):
            return first["id"]
        if isinstance(first, int):
            return first
    return None


def _parse_tool_text(content_list: Any) -> Any:
    if not content_list:
        return None
    text = getattr(content_list[0], "text", None)
    if text is None and isinstance(content_list[0], dict):
        text = content_list[0].get("text")
    if text is None:
        return content_list
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def run_scenario(
    host: str,
    username: str,
    password: str,
    *,
    verify_ssl: bool = True,
    include_mutating_readonly_check: bool = True,
) -> ScenarioReport:
    os.environ["MULTIFLEXI_HOST"] = host
    os.environ["MULTIFLEXI_USERNAME"] = username
    os.environ["MULTIFLEXI_PASSWORD"] = password
    os.environ["MULTIFLEXI_VERIFY_SSL"] = "true" if verify_ssl else "false"
    os.environ["MULTIFLEXI_READONLY"] = "true"
    os.environ["MULTIFLEXI_DEBUG"] = "false"

    # Fresh imports so module-level config/client pick up this host.
    for mod in list(sys.modules):
        if mod == "multiflexi_mcp_server" or mod.startswith("multiflexi_mcp_server."):
            del sys.modules[mod]

    from multiflexi_mcp_server.server import (  # noqa: WPS433
        call_tool,
        get_prompt,
        list_prompts,
        list_resources,
        list_tools,
        read_resource,
    )

    report = ScenarioReport(host=host)

    # --- Meta: inventories ---
    try:
        resources = await list_resources()
        report.add(
            CheckResult(
                "list_resources",
                "meta",
                len(resources) >= 11,
                detail=f"count={len(resources)}",
                sample=[str(r.uri) for r in resources],
            )
        )
    except Exception as exc:  # noqa: BLE001
        report.add(CheckResult("list_resources", "meta", False, detail=str(exc)))
        resources = []

    try:
        tools = await list_tools()
        report.add(
            CheckResult(
                "list_tools",
                "meta",
                len(tools) >= 37,
                detail=f"count={len(tools)}",
                sample=[t.name for t in tools],
            )
        )
        tool_names = {t.name for t in tools}
    except Exception as exc:  # noqa: BLE001
        report.add(CheckResult("list_tools", "meta", False, detail=str(exc)))
        tool_names = set()

    try:
        prompts = await list_prompts()
        report.add(
            CheckResult(
                "list_prompts",
                "meta",
                len(prompts) >= 3,
                detail=f"count={len(prompts)}",
                sample=[p.name for p in prompts],
            )
        )
    except Exception as exc:  # noqa: BLE001
        report.add(CheckResult("list_prompts", "meta", False, detail=str(exc)))

    # --- Resources ---
    resource_payloads: Dict[str, Any] = {}
    for res in resources:
        uri = str(res.uri)
        try:
            raw = await read_resource(uri)
            ok, detail = _has_usable_data(raw)
            parsed = raw
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = raw
            resource_payloads[uri] = parsed
            report.add(
                CheckResult(
                    uri,
                    "resource",
                    ok,
                    detail=detail,
                    sample=_short_sample(parsed),
                )
            )
        except Exception as exc:  # noqa: BLE001
            report.add(
                CheckResult(uri, "resource", False, detail=f"{exc}\n{traceback.format_exc()}")
            )

    ids = {
        "app": _first_id(resource_payloads.get("multiflexi://apps")),
        "job": _first_id(resource_payloads.get("multiflexi://jobs")),
        "company": _first_id(resource_payloads.get("multiflexi://companies")),
        "user": _first_id(resource_payloads.get("multiflexi://users")),
        "runtemplate": _first_id(resource_payloads.get("multiflexi://runtemplates")),
        "credential": _first_id(resource_payloads.get("multiflexi://credentials")),
        "credential_type": _first_id(resource_payloads.get("multiflexi://credential_types")),
        "topic": _first_id(resource_payloads.get("multiflexi://topics")),
        "event_source": _first_id(resource_payloads.get("multiflexi://eventsources")),
        "event_rule": _first_id(resource_payloads.get("multiflexi://eventrules")),
        "task": _first_id(resource_payloads.get("multiflexi://tasks")),
    }

    # --- Read-only tools (lists first so get_* can reuse discovered ids) ---
    def _need(id_key: str) -> Optional[str]:
        if ids.get(id_key) is None:
            return f"no {id_key} id available from list resource/tool"
        return None

    list_tool_cases: List[Tuple[str, Callable[[], Dict[str, Any]]]] = [
        ("list_companies", lambda: {"limit": 5}),
        ("list_users", lambda: {"limit": 5}),
        ("list_credentials", lambda: {"limit": 5}),
        ("list_credential_types", lambda: {"limit": 5}),
        ("list_topics", lambda: {"limit": 5}),
        ("list_event_sources", lambda: {"limit": 5}),
        ("list_event_rules", lambda: {"limit": 5}),
        ("list_tasks", lambda: {"limit": 5}),
    ]

    get_tool_cases: List[Tuple[str, Callable[[], Dict[str, Any]], Callable[[], Optional[str]]]] = [
        ("get_app", lambda: {"app_id": ids["app"]}, lambda: _need("app")),
        ("get_job", lambda: {"job_id": ids["job"]}, lambda: _need("job")),
        ("get_job_status", lambda: {"job_id": ids["job"]}, lambda: _need("job")),
        ("get_company", lambda: {"company_id": ids["company"]}, lambda: _need("company")),
        ("get_user", lambda: {"user_id": ids["user"]}, lambda: _need("user")),
        (
            "get_runtemplate",
            lambda: {"template_id": ids["runtemplate"]},
            lambda: _need("runtemplate"),
        ),
        (
            "get_credential",
            lambda: {"credential_id": ids["credential"]},
            lambda: _need("credential"),
        ),
        (
            "get_credential_type",
            lambda: {"credential_type_id": ids["credential_type"]},
            lambda: _need("credential_type"),
        ),
        ("get_topic", lambda: {"topic_id": ids["topic"]}, lambda: _need("topic")),
        (
            "get_event_source",
            lambda: {"event_source_id": ids["event_source"]},
            lambda: _need("event_source"),
        ),
        (
            "get_event_rule",
            lambda: {"event_rule_id": ids["event_rule"]},
            lambda: _need("event_rule"),
        ),
        ("get_task", lambda: {"task_id": ids["task"]}, lambda: _need("task")),
        (
            "list_company_users",
            lambda: {"company_id": ids["company"], "limit": 5},
            lambda: _need("company"),
        ),
        ("get_user_roles", lambda: {"user_id": ids["user"]}, lambda: _need("user")),
        (
            "test_event_source_connection",
            lambda: {"event_source_id": ids["event_source"]},
            lambda: _need("event_source"),
        ),
    ]

    list_id_map = {
        "list_companies": "company",
        "list_users": "user",
        "list_credentials": "credential",
        "list_credential_types": "credential_type",
        "list_topics": "topic",
        "list_event_sources": "event_source",
        "list_event_rules": "event_rule",
        "list_tasks": "task",
    }

    async def _run_tool(name: str, args: Dict[str, Any]) -> None:
        if name not in tool_names:
            report.add(
                CheckResult(name, "tool", False, detail="tool not advertised by list_tools")
            )
            return
        try:
            content = await call_tool(name, args)
            payload = _parse_tool_text(content)
            ok, detail = _has_usable_data(payload)
            report.add(
                CheckResult(
                    name,
                    "tool",
                    ok,
                    detail=detail,
                    sample=_short_sample(payload),
                )
            )
            id_key = list_id_map.get(name)
            if id_key and ok and ids.get(id_key) is None:
                maybe = _first_id(payload)
                if maybe is not None:
                    ids[id_key] = maybe
        except Exception as exc:  # noqa: BLE001
            report.add(
                CheckResult(name, "tool", False, detail=f"{exc}\n{traceback.format_exc()}")
            )

    for name, args_fn in list_tool_cases:
        await _run_tool(name, args_fn())

    for name, args_fn, skip_fn in get_tool_cases:
        skip_reason = skip_fn()
        if skip_reason:
            report.add(CheckResult(name, "tool", True, detail=skip_reason, skipped=True))
            continue
        await _run_tool(name, args_fn())

    report.add(
        CheckResult(
            "get_export_status",
            "tool",
            True,
            detail="needs a real export_id (skipped in read-only scenario)",
            skipped=True,
        )
    )

    # --- Mutating tools must be blocked in read-only mode ---
    if include_mutating_readonly_check:
        mutating = [
            ("create_job", {"runtemplate_id": ids.get("runtemplate") or 1}),
            ("update_runtemplate", {"template_id": 1, "template_data": {"name": "x"}}),
            ("request_data_export", {"export_type": "personal_data"}),
            ("assign_user_to_company", {"company_id": 1, "user_id": 1}),
            ("unassign_user_from_company", {"company_id": 1, "user_id": 1}),
            ("set_user_roles", {"user_id": 1, "roles": ["admin"]}),
            ("update_credential", {"credential_id": 1, "credential_data": {"name": "x"}}),
            (
                "update_credential_type",
                {"credential_type_id": 1, "credential_type_data": {"name": "x"}},
            ),
            ("update_topic", {"topic_id": 1, "topic_data": {"name": "x"}}),
            ("set_event_source", {"event_source_data": {"name": "x"}}),
            ("delete_event_source", {"event_source_id": 1}),
            ("set_event_rule", {"event_rule_data": {"name": "x"}}),
            ("delete_event_rule", {"event_rule_id": 1}),
        ]
        for name, args in mutating:
            if name not in tool_names:
                report.add(
                    CheckResult(
                        f"{name} (readonly block)",
                        "tool",
                        False,
                        detail="tool not advertised",
                    )
                )
                continue
            try:
                content = await call_tool(name, args)
                payload = _parse_tool_text(content)
                blocked = (
                    isinstance(payload, dict)
                    and payload.get("error") is True
                    and "read-only" in str(payload.get("message", "")).lower()
                )
                report.add(
                    CheckResult(
                        f"{name} (readonly block)",
                        "tool",
                        blocked,
                        detail="blocked as expected"
                        if blocked
                        else f"unexpected payload: {_short_sample(payload)}",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                report.add(
                    CheckResult(
                        f"{name} (readonly block)",
                        "tool",
                        False,
                        detail=str(exc),
                    )
                )

    # --- Prompts ---
    prompt_cases = [
        ("diagnose_job_failure", {"job_id": str(ids.get("job") or 1)}),
        (
            "task_fulfillment_report",
            {"runtemplate_id": str(ids["runtemplate"])} if ids.get("runtemplate") else {},
        ),
        ("gdpr_export_checklist", {"export_type": "personal_data"}),
    ]
    for name, args in prompt_cases:
        try:
            result = await get_prompt(name, args)
            messages = getattr(result, "messages", None) or []
            text = ""
            if messages:
                content = messages[0].content
                text = getattr(content, "text", "") or str(content)
            ok = bool(text) and "Unknown prompt" not in text
            report.add(
                CheckResult(
                    name,
                    "prompt",
                    ok,
                    detail=f"chars={len(text)}",
                    sample=text[:160],
                )
            )
        except Exception as exc:  # noqa: BLE001
            report.add(CheckResult(name, "prompt", False, detail=str(exc)))

    return report


def _short_sample(data: Any, limit: int = 240) -> Any:
    try:
        text = json.dumps(data, default=str)
    except TypeError:
        text = str(data)
    if len(text) > limit:
        return text[:limit] + "…"
    return data if not isinstance(data, (dict, list)) or len(text) < limit else text


def print_report(report: ScenarioReport) -> None:
    print(f"\n=== MultiFlexi MCP live capability scenario ===")
    print(f"host: {report.host}")
    print(f"passed={report.passed} failed={report.failed} skipped={report.skipped}")
    print()
    width = max((len(r.name) for r in report.results), default=10)
    for r in report.results:
        if r.skipped:
            flag = "SKIP"
        elif r.ok:
            flag = "PASS"
        else:
            flag = "FAIL"
        print(f"[{flag}] {r.kind:<8} {r.name:<{width}}  {r.detail}")
        if not r.ok and not r.skipped and r.sample is not None:
            print(f"       sample: {r.sample}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("MULTIFLEXI_HOST"))
    parser.add_argument("--username", default=os.getenv("MULTIFLEXI_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("MULTIFLEXI_PASSWORD", ""))
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification",
    )
    parser.add_argument(
        "--json-out",
        help="Write machine-readable report to this path",
    )
    args = parser.parse_args(argv)

    if not args.host:
        parser.error("MULTIFLEXI_HOST / --host is required")

    import asyncio

    report = asyncio.run(
        run_scenario(
            args.host.rstrip("/"),
            args.username,
            args.password,
            verify_ssl=not args.insecure,
        )
    )
    print_report(report)

    if args.json_out:
        payload = {
            "host": report.host,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
            "results": [
                {
                    "name": r.name,
                    "kind": r.kind,
                    "ok": r.ok,
                    "skipped": r.skipped,
                    "detail": r.detail,
                    "sample": r.sample,
                }
                for r in report.results
            ],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nWrote {args.json_out}")

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
