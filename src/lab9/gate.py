"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
from statistics import mean

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _report_grid(report: dict, side: str, graded: set[str], problems: list[str]) -> tuple[set, dict]:
    """Validate a complete item/seed grid and return its per-item slice tags."""
    manifest = report["manifest"]
    seeds = manifest["seeds"]
    rows = report["rows"]
    keys = {(row["item_id"], row["seed"]) for row in rows}
    item_ids = {item for item, _ in keys}
    expected = {(item, seed) for item in item_ids for seed in seeds}

    if len(rows) != manifest["items"] * len(seeds) or len(item_ids) != manifest["items"]:
        problems.append(f"{side}: row or item count differs from manifest")
    if len(keys) != len(rows):
        problems.append(f"{side}: duplicate (item_id, seed) row")
    if len(seeds) != len(set(seeds)) or keys != expected:
        problems.append(f"{side}: incomplete or invalid item/seed grid")
    if report.get("evaluator_failures"):
        problems.append(f"{side}: evaluator_failures is non-empty")
    for metric, value in report["metrics"].items():
        if isinstance(value, float) and not isfinite(value):
            problems.append(f"{side}: non-finite metric {metric}")

    tags_by_item = {}
    for row in rows:
        item = row["item_id"]
        tags = frozenset(row.get("slices") or [])
        if tags_by_item.setdefault(item, tags) != tags:
            problems.append(f"{side}: inconsistent slice tags for {item}")
    invalid = sorted({mid for row in rows for mid in graded if type(row.get(mid)) is not bool})
    for mid in invalid:
        problems.append(f"{side}: missing or invalid graded value for {mid}")
    return keys, tags_by_item


def _ratchet_entries(old: dict, new: dict, label: str, problems: list[str], *, nested: bool) -> None:
    for key, previous in old.items():
        current = new.get(key)
        if current is None:
            problems.append(f"ratchet: removed {label} {key}")
            continue
        if previous.get("blocking") and not current.get("blocking"):
            problems.append(f"ratchet: {label} {key} is no longer blocking")
        old_threshold = previous.get("threshold", {}) if nested else previous
        new_threshold = current.get("threshold", {}) if nested else current
        for bound in ("min", "max", "max_increase"):
            if bound not in old_threshold:
                continue
            before, after = old_threshold[bound], new_threshold.get(bound)
            if after is None or (after < before if bound == "min" else after > before):
                problems.append(f"ratchet: loosened {label} {key} {bound}")
        if old_threshold.get("no_significant_drop") and not new_threshold.get("no_significant_drop"):
            problems.append(f"ratchet: removed CI check from {label} {key}")


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """Reject invalid reports, changed evaluation coverage and weakened rules."""
    problems: list[str] = []
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        old_metrics = {m["id"]: m for m in base_spec["metrics"]}
        new_metrics = {m["id"]: m for m in spec["metrics"]}
        _ratchet_entries(old_metrics, new_metrics, "metric", problems, nested=True)
        old_slices = {(s["name"], s["metric"]): s for s in base_spec.get("slices", [])}
        new_slices = {(s["name"], s["metric"]): s for s in spec.get("slices", [])}
        _ratchet_entries(old_slices, new_slices, "slice", problems, nested=False)

    graded = {m["id"] for m in spec["metrics"] if m["id"] in GRADERS}
    pr_keys, pr_tags = _report_grid(pr, "PR", graded, problems)
    base_keys, base_tags = _report_grid(base, "baseline", graded, problems)
    if pr_keys != base_keys:
        problems.append("PR and baseline have different (item_id, seed) pairs")
    if any(pr_tags[item] != base_tags[item] for item in pr_tags.keys() & base_tags.keys()):
        problems.append("PR and baseline have different slice tags for the same item")
    return problems


def _paired_interval(candidate: dict, baseline: dict, bootstrap: dict) -> tuple[float, float, float] | None:
    if not candidate or candidate.keys() != baseline.keys():
        return None
    keys = sorted(candidate)
    if len(keys) == 1:
        (key,) = keys
        delta = candidate[key] - baseline[key]
        return delta, delta, delta
    return stats.paired_bootstrap(
        [candidate[key] for key in keys],
        [baseline[key] for key in keys],
        n_resamples=bootstrap.get("n_resamples", 1000),
        rng=bootstrap.get("rng", 2027),
        confidence=bootstrap.get("confidence", 0.95),
    )


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """Evaluate each configured slice using the item as the unit of comparison."""
    blocked, lines = [], []
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        key = f"slice:{name}/{metric}"
        candidate = per_item(pr, metric, slice_name=name)
        baseline = per_item(base, metric, slice_name=name)
        note = ""
        if not candidate or candidate.keys() != baseline.keys():
            verdict = "missing"
            value = None
        else:
            value = mean(candidate.values())
            fails = "min" in rule and value < rule["min"]
            if rule.get("no_significant_drop"):
                d, lo, hi = _paired_interval(candidate, baseline, spec.get("bootstrap", {}))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                fails = fails or hi < 0
            verdict = "fail" if fails else "ok"
        if verdict != "ok" and rule.get("blocking"):
            blocked.append(key)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if rule.get("blocking") else "warn")
        score = f"{value:.4f}" if value is not None else "None"
        lines.append(f"  {key:<36} {score:<8} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            interval = _paired_interval(a, b, bs)
            if interval is None:
                verdict = "missing"
            else:
                d, lo, hi = interval
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
