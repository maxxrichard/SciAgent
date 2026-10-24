"""Command-line interface: ``sciagent <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sciagent.core.config import get_settings


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("sciagent.api.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    from sciagent.api.container import build_container
    from sciagent.core.ids import new_id

    container = build_container(get_settings())
    principal = container.auth.authenticate(args.api_key)
    result = container.agent.run(args.question, principal, new_id("cli"))
    if args.json:
        print(json.dumps(result.__dict__, indent=2, default=str))
    else:
        print(result.answer)
        for step in result.steps:
            print(f"  · {step['tool']} [{step['decision']}] {json.dumps(step['arguments'])}")
    return 0 if result.status == "completed" else 1


def _cmd_tools(_: argparse.Namespace) -> int:
    from sciagent.tools import default_registry

    for spec in default_registry().specs():
        print(f"{spec['server']:<9} {spec['name']:<24} {spec['description']}")
    return 0


def _cmd_pipelines(args: argparse.Namespace) -> int:
    from sciagent.catalog.db import Database
    from sciagent.catalog.repository import DatasetRepository
    from sciagent.data.lake import Lake
    from sciagent.data.pipelines import get_spec, load_specs, run_pipeline

    specs = load_specs()
    if args.action == "list":
        for s in specs:
            print(f"{s.id:<40} {s.kind:<22} {s.schedule}")
        return 0
    settings = get_settings()
    db = Database(settings.database_url)
    db.create_all()
    repo, lake = DatasetRepository(db), Lake(settings.data_lake_uri)
    targets = specs if args.pipeline == "all" else [get_spec(args.pipeline, specs)]
    for spec in targets:
        r = run_pipeline(spec, lake, repo)
        print(f"{r.pipeline:<40} v{r.version:<3} rows={r.rows:<6} {r.uri}")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from sciagent.eval.gate import evaluate_gate, load_gate
    from sciagent.eval.harness import build_runner
    from sciagent.eval.tasks import load_tasks
    from sciagent.llm import build_llm

    settings = get_settings()
    llm = build_llm(settings)
    judge_llm = llm if args.judge == "llm" else None
    report = build_runner(llm, judge_llm).run(load_tasks(Path(args.tasks)))
    report.write(Path(args.out))
    print(report.markdown())
    if args.gate:
        problems = evaluate_gate(report.summary, load_gate(Path(args.gate)))
        if problems:
            print("RELEASE GATE FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        print("Release gate passed.")
    return 0


def _cmd_audit(_: argparse.Namespace) -> int:
    from sciagent.catalog.db import Database
    from sciagent.governance.audit import AuditLog

    ok, bad = AuditLog(Database(get_settings().database_url)).verify()
    print("audit chain intact" if ok else f"audit chain broken at seq {bad}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sciagent", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the API server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(fn=_cmd_serve)

    p = sub.add_parser("query", help="ask the agent a question locally")
    p.add_argument("question")
    p.add_argument("--api-key", default="dev-researcher-key")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_cmd_query)

    sub.add_parser("tools", help="list registered tools").set_defaults(fn=_cmd_tools)

    p = sub.add_parser("pipelines", help="list or run data pipelines")
    p.add_argument("action", choices=["list", "run"])
    p.add_argument("pipeline", nargs="?", default="all")
    p.set_defaults(fn=_cmd_pipelines)

    p = sub.add_parser("eval", help="run the evaluation harness")
    p.add_argument("--tasks", default="evals/tasks")
    p.add_argument("--gate", default=None)
    p.add_argument("--out", default="evals/reports/latest")
    p.add_argument("--judge", choices=["heuristic", "llm"], default="heuristic")
    p.set_defaults(fn=_cmd_eval)

    sub.add_parser("audit-verify", help="verify the audit hash chain").set_defaults(fn=_cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
