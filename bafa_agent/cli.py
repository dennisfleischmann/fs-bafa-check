from __future__ import annotations

import argparse
from pathlib import Path

from .communications import render_customer_email, render_secretary_memo
from .diffing import diff_bundles, requires_human_review
from .pipeline import compile_rules, evaluate_offer, init_workspace
from .source import BAFA_OVERVIEW_URL
from .utils import read_json, write_json


def cmd_init(args: argparse.Namespace) -> int:
    init_workspace(args.base_dir)
    print(f"initialized workspace at {args.base_dir}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    report = compile_rules(
        args.base_dir,
        fetch=args.fetch,
        source=args.source,
        source_url=args.source_url,
    )
    print("compile complete")
    print(report)
    return 0 if report.get("validation_passed") else 2


def cmd_evaluate(args: argparse.Namespace) -> int:
    payload = evaluate_offer(args.base_dir, args.offer)
    out_file = Path(args.base_dir) / "data" / "cases" / payload["case_id"] / "evaluation.json"
    print(f"evaluation written: {out_file}")
    print(payload)
    return 0


def cmd_memo(args: argparse.Namespace) -> int:
    evaluation = read_json(args.evaluation, default={})
    memo = render_secretary_memo(evaluation)
    print(memo)
    if args.output:
        Path(args.output).write_text(memo, encoding="utf-8")
    return 0


def cmd_email(args: argparse.Namespace) -> int:
    evaluation = read_json(args.evaluation, default={})
    results = evaluation.get("results", [])
    index = max(0, min(args.index, len(results) - 1))
    if not results:
        print("no results in evaluation")
        return 1
    email = render_customer_email(results[index])
    print(email)
    if args.output:
        Path(args.output).write_text(email, encoding="utf-8")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    previous = read_json(args.previous, default={})
    current = read_json(args.current, default={})
    report = diff_bundles(previous, current)
    report["needs_human_review"] = requires_human_review(report)
    print(report)
    if args.output:
        write_json(args.output, report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BAFA/BEG deterministic pipeline")
    parser.add_argument("--base-dir", default=".", help="workspace base directory")

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.set_defaults(func=cmd_init)

    p_compile = sub.add_parser("compile")
    p_compile.add_argument("--fetch", action="store_true", help="download source urls")
    p_compile.add_argument(
        "--source",
        default="local",
        choices=["local", "local-default", "bafa"],
        help="source registry mode",
    )
    p_compile.add_argument(
        "--source-url",
        default=BAFA_OVERVIEW_URL,
        help="source page url for dynamic source modes",
    )
    p_compile.set_defaults(func=cmd_compile)

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--offer", required=True, help="offer text path")
    p_eval.set_defaults(func=cmd_evaluate)

    p_memo = sub.add_parser("memo")
    p_memo.add_argument("--evaluation", required=True)
    p_memo.add_argument("--output")
    p_memo.set_defaults(func=cmd_memo)

    p_email = sub.add_parser("email")
    p_email.add_argument("--evaluation", required=True)
    p_email.add_argument("--index", type=int, default=0)
    p_email.add_argument("--output")
    p_email.set_defaults(func=cmd_email)

    p_diff = sub.add_parser("diff")
    p_diff.add_argument("--previous", required=True)
    p_diff.add_argument("--current", required=True)
    p_diff.add_argument("--output")
    p_diff.set_defaults(func=cmd_diff)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
