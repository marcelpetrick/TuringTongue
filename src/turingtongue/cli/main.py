# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""``turingtongue`` command line.

Exit codes (an AI verdict is data, not an error):

* 0 — a HUMAN or AI verdict was produced
* 2 — the run completed but produced NO_VERDICT
* 3 — invalid configuration, arguments or input
* 4 — unexpected internal failure
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from rich.console import Console

from turingtongue._version import __version__
from turingtongue.client import TRANSPORTS, Checker
from turingtongue.config import Settings
from turingtongue.errors import ConfigurationError
from turingtongue.models import CheckResult, Verdict

EXIT_VERDICT = 0
EXIT_NO_VERDICT = 2
EXIT_USAGE = 3
EXIT_INTERNAL = 4

PRIVACY_NOTE = (
    "Privacy: checking a text sends it to every selected third-party detection service; "
    "their own processing and retention policies apply. Results are indicators, not proof "
    "of authorship."
)


class _Parser(argparse.ArgumentParser):
    """argparse with our usage exit code (3) instead of 2, which means NO_VERDICT."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser (also used for --help tests)."""
    parser = _Parser(
        prog="turingtongue",
        description="Ask several AI-text detectors about a text and combine their answers.",
        epilog=PRIVACY_NOTE,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, help="TOML config file (no secrets)")
    parser.add_argument(
        "--debug", action="store_true", help="debug logging to stderr (never logs the text)"
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    check = sub.add_parser(
        "check",
        help="check one text",
        epilog=PRIVACY_NOTE,
        description="Print HUMAN, AI or NO_VERDICT for a text.",
    )
    source = check.add_mutually_exclusive_group()
    source.add_argument("file", nargs="?", help="UTF-8 text file, or '-' for stdin (default)")
    source.add_argument("--text", help="the text itself instead of a file")
    _add_run_options(check)
    output = check.add_mutually_exclusive_group()
    output.add_argument(
        "-v", "--verbose", action="store_true", help="explain every provider attempt"
    )
    output.add_argument("--json", action="store_true", help="versioned JSON result on stdout")

    batch = sub.add_parser("batch", help="check many files one after another", epilog=PRIVACY_NOTE)
    batch.add_argument("paths", nargs="+", help="files or directories (*.txt, *.md searched)")
    _add_run_options(batch)
    batch.add_argument("--jsonl", type=Path, help="write full per-file results as JSONL")
    batch.add_argument("--csv", type=Path, help="write the summary table as CSV (default: stdout)")

    bench = sub.add_parser(
        "benchmark", help="run the provenance-checked benchmark corpus", epilog=PRIVACY_NOTE
    )
    bench.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmark/corpus"),
        help="corpus directory with manifest.toml (default: benchmark/corpus)",
    )
    bench.add_argument("--split", choices=("calibration", "holdout"), help="only this split")
    bench.add_argument(
        "--out",
        type=Path,
        default=Path("benchmark/results"),
        help="directory for results-*.jsonl and reports",
    )
    bench.add_argument(
        "--from-results",
        type=Path,
        metavar="JSONL",
        help="only recompute the report from an earlier results file",
    )
    bench.add_argument(
        "--yes",
        action="store_true",
        help="confirm sending the corpus to real (possibly paid) providers",
    )
    _add_run_options(bench)

    providers = sub.add_parser("providers", help="list known providers and credential status")
    providers.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--provider",
        action="append",
        dest="providers",
        metavar="ID",
        help="provider id (repeatable, or comma-separated); 'all' for every provider",
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORTS,
        default="any",
        help="restrict to API/SDK, browser or mock providers (default: any)",
    )
    parser.add_argument(
        "--timeout", type=float, metavar="S", help="per-provider timeout in seconds"
    )
    parser.add_argument(
        "--deadline", type=float, metavar="S", help="overall run deadline in seconds"
    )


def read_text(file: str | None, inline: str | None, stdin: TextIO) -> str:
    """Read the text exactly: no newline translation, no stripping, strict UTF-8."""
    if inline is not None:
        return inline
    try:
        if file is None or file == "-":
            raw = stdin.buffer.read() if hasattr(stdin, "buffer") else stdin.read().encode()
        else:
            raw = Path(file).read_bytes()
        return raw.decode("utf-8")
    except FileNotFoundError as exc:
        raise ConfigurationError(f"file not found: {file}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigurationError(f"input is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"cannot read input: {exc}") from exc


def make_settings(args: argparse.Namespace) -> Settings:
    """Settings from env/config plus CLI overrides."""
    settings = Settings.load(args.config)
    changes: dict[str, float] = {}
    if getattr(args, "timeout", None) is not None:
        changes["timeout_s"] = args.timeout
    if getattr(args, "deadline", None) is not None:
        changes["deadline_s"] = args.deadline
    for name, value in changes.items():
        if value <= 0:
            raise ConfigurationError(f"--{name.removesuffix('_s')} must be positive")
    return settings.with_changes(**changes) if changes else settings


def _console(stream: TextIO) -> Console:
    interactive = hasattr(stream, "isatty") and stream.isatty()
    return Console(
        file=stream, soft_wrap=False, highlight=False, width=None if interactive else 140
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Entry point with injectable streams; returns the exit code."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG, stream=stderr, format="%(levelname)s %(name)s: %(message)s"
        )
    try:
        settings = make_settings(args)
        checker = Checker(settings)
        if args.command == "providers":
            return _providers(checker, args, stdout)
        if args.command == "batch":
            return _batch(checker, args, stdout, stderr)
        if args.command == "benchmark":
            return _benchmark(checker, args, stdout, stderr)
        text = read_text(args.file, args.text, stdin)
        providers = [p for item in args.providers or [] for p in item.split(",") if p.strip()]
        result = checker.check(
            text, providers=providers or None, transport=args.transport, verbose=args.verbose
        )
    except ConfigurationError as exc:
        print(f"turingtongue: error: {exc}", file=stderr)
        return EXIT_USAGE
    except Exception as exc:
        logging.getLogger("turingtongue").debug("internal failure", exc_info=True)
        print(f"turingtongue: internal error: {type(exc).__name__}: {exc}", file=stderr)
        return EXIT_INTERNAL
    if args.json:
        print(result.to_json(), file=stdout)
    elif args.verbose:
        from turingtongue.cli.output import render_verbose  # noqa: PLC0415 - rich only when needed

        render_verbose(result, _console(stdout))
    else:
        print(result.verdict.display, file=stdout)
    return EXIT_NO_VERDICT if result.verdict is Verdict.NO_VERDICT else EXIT_VERDICT


def _selected(args: argparse.Namespace) -> list[str] | None:
    names = [p for item in args.providers or [] for p in item.split(",") if p.strip()]
    return names or None


def _batch(checker: Checker, args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    import asyncio  # noqa: PLC0415

    from turingtongue import batch  # noqa: PLC0415

    files = batch.collect_files(args.paths)
    jsonl = args.jsonl.open("w", encoding="utf-8") if args.jsonl else None

    def on_result(path: Path, row: dict[str, object], result: CheckResult) -> None:
        print(f"{row['verdict']}\t{path}", file=stderr)
        if jsonl is not None:
            jsonl.write(batch.jsonl_line(path, row, result) + "\n")

    try:
        rows = asyncio.run(
            batch.run_batch(
                checker,
                files,
                providers=_selected(args),
                transport=args.transport,
                on_result=on_result,
            )
        )
    finally:
        if jsonl is not None:
            jsonl.close()
    if args.csv:
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
            batch.write_csv(rows, handle)
    else:
        batch.write_csv(rows, stdout)
    return EXIT_VERDICT


def _benchmark(checker: Checker, args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    import asyncio  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    from turingtongue.benchmark import corpus, metrics, report, runner  # noqa: PLC0415

    if args.from_results:
        records = runner.read_records(args.from_results)
        results_path = args.from_results
    else:
        samples = corpus.load_corpus(args.corpus, split=args.split)
        selection = checker.select(_selected(args), args.transport)
        real = [s.id for s in selection.run if s.transport.value != "mock"]
        if not selection.run:
            raise ConfigurationError("no provider would run; configure credentials or use -p")
        if real and not args.yes:
            raise ConfigurationError(
                f"this sends {len(samples)} texts to {len(real)} real provider(s) "
                f"({', '.join(real)}) and may consume paid credits; re-run with --yes"
            )

        def progress(index: int, total: int, sample: object) -> None:
            print(f"[{index}/{total}] {getattr(sample, 'id', '')}", file=stderr)

        records = asyncio.run(
            runner.run_samples(
                checker,
                samples,
                providers=_selected(args),
                transport=args.transport,
                progress=progress,
            )
        )
        results_path = runner.write_records(records, args.out)
    scores = metrics.compute(records)
    first = records[0]["result"] if records else {}
    meta = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "package_version": __version__,
        "samples": len(records),
        "results_file": str(results_path),
        "weights_version": first.get("aggregate", {}).get("weights_version"),
    }
    markdown = report.to_markdown(scores, meta=meta)
    stem = Path(results_path).with_suffix("")
    Path(f"{stem}.report.md").write_text(markdown + "\n", encoding="utf-8")
    Path(f"{stem}.report.json").write_text(report.to_json(scores, meta=meta), encoding="utf-8")
    print(markdown, file=stdout)
    print(f"results: {results_path}", file=stderr)
    return EXIT_VERDICT


def _providers(checker: Checker, args: argparse.Namespace, stdout: TextIO) -> int:
    if args.json:
        rows = [
            {
                "id": s.id,
                "name": s.name,
                "transport": s.transport.value,
                "enabled_by_default": s.enabled_by_default,
                "credential_env": list(s.credential_env),
                "credentials_present": not s.missing_credentials(checker.settings.env),
                "known_min_input": s.known_min_input,
                "recommended_min_input": s.recommended_min_input,
                "known_max_input": s.known_max_input,
                "limit_unit": s.limit_unit.value,
                "adapter_status": s.adapter_status,
                "last_verified": s.last_verified,
                "docs_url": s.docs_url,
            }
            for s in checker.registry
        ]
        print(json.dumps(rows, indent=2), file=stdout)
    else:
        from turingtongue.cli.output import render_providers  # noqa: PLC0415

        render_providers(checker.registry, checker.settings.env, _console(stdout))
    return EXIT_VERDICT


def main() -> None:
    """Console-script entry point."""
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
