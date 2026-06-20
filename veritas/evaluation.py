"""Record/replay evaluation harness for prompt, schema, and risk-rule changes."""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, Iterable, List

from .legacy import apply_risk_rules
from .report_schema import parse_report
from .versions import PROMPT_VERSION, RISK_RULE_VERSION, SCHEMA_VERSION

EVAL_PROMPT_VERSION = PROMPT_VERSION
EVAL_SCHEMA_VERSION = SCHEMA_VERSION
EVAL_RECORD_VERSION = "evaluation_record_v1"
DEFAULT_SYNTHETIC_CASES_DIR = Path("eval/cases/synthetic")
DEFAULT_SYNTHETIC_REPLAY_DIR = Path("eval/replay/synthetic")
DEFAULT_PUBLIC_CASES_DIR = Path("eval/cases/public")


@dataclass
class EvalCase:
    case_id: str
    input_text: str
    expected_risk_level: str
    expected_min_score: int = 0
    stat_result: Dict[str, Any] = field(default_factory=dict)
    image_audit: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    risk_level: str
    detection_score: int
    expected_risk_level: str
    errors: List[str] = field(default_factory=list)
    record_path: str = ""


def evaluation_input_hash(input_text: str) -> str:
    return sha256(str(input_text or "").encode("utf-8")).hexdigest()


def load_eval_case(path: Path) -> EvalCase:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvalCase(
        case_id=data["case_id"],
        input_text=data["input_text"],
        expected_risk_level=data["expected"]["risk_level"],
        expected_min_score=int(data.get("expected", {}).get("min_score", 0)),
        stat_result=dict(data.get("stat_result") or {}),
        image_audit=dict(data.get("image_audit") or {}),
        tags=list(data.get("tags") or []),
    )


def load_eval_cases(cases_dir: Path = DEFAULT_SYNTHETIC_CASES_DIR) -> List[EvalCase]:
    cases_path = Path(cases_dir)
    return [load_eval_case(path) for path in sorted(cases_path.glob("*.json"))]


def build_eval_record(
    case: EvalCase,
    response: Dict[str, Any],
    adapter: str,
    model: str,
    prompt_version: str = EVAL_PROMPT_VERSION,
    schema_version: str = EVAL_SCHEMA_VERSION,
    risk_rule_version: str = RISK_RULE_VERSION,
    recorded_at: str = "",
) -> Dict[str, Any]:
    return {
        "record_version": EVAL_RECORD_VERSION,
        "case_id": case.case_id,
        "adapter": adapter,
        "model": model,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "risk_rule_version": risk_rule_version,
        "input_hash": evaluation_input_hash(case.input_text),
        "recorded_at": recorded_at or time.strftime("%Y-%m-%d %H:%M:%S"),
        "response": dict(response),
    }


def write_eval_record(record: Dict[str, Any], records_dir: Path = DEFAULT_SYNTHETIC_REPLAY_DIR) -> Path:
    target_dir = Path(records_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{record['case_id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_eval_record(case: EvalCase, records_dir: Path = DEFAULT_SYNTHETIC_REPLAY_DIR) -> Dict[str, Any]:
    path = Path(records_dir) / f"{case.case_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    expected_hash = evaluation_input_hash(case.input_text)
    if record.get("input_hash") != expected_hash:
        raise ValueError(f"Replay input hash mismatch for {case.case_id}")
    return record


def run_eval_case_replay(case: EvalCase, record: Dict[str, Any], record_path: Path = None) -> EvalResult:
    response = record.get("response") or {}
    parsed = parse_report(json.dumps(response, ensure_ascii=False))
    errors = []
    if parsed.get("parse_error"):
        errors.append("schema_parse_error")
        ruled = {"risk_level": "parse_error", "detection_score": 0}
    else:
        ruled = apply_risk_rules(parsed, stat_result=case.stat_result, image_audit=case.image_audit)

    risk_level = ruled.get("risk_level", "未知")
    score = int(ruled.get("detection_score") or 0)
    if risk_level != case.expected_risk_level:
        errors.append(f"risk_level expected {case.expected_risk_level} got {risk_level}")
    if score < case.expected_min_score:
        errors.append(f"detection_score expected >= {case.expected_min_score} got {score}")
    return EvalResult(
        case_id=case.case_id,
        passed=not errors,
        risk_level=risk_level,
        detection_score=score,
        expected_risk_level=case.expected_risk_level,
        errors=errors,
        record_path=str(record_path or ""),
    )


def run_replay_suite(
    cases_dir: Path = DEFAULT_SYNTHETIC_CASES_DIR,
    records_dir: Path = DEFAULT_SYNTHETIC_REPLAY_DIR,
) -> List[EvalResult]:
    results = []
    for case in load_eval_cases(cases_dir):
        record_path = Path(records_dir) / f"{case.case_id}.json"
        results.append(run_eval_case_replay(case, load_eval_record(case, records_dir), record_path=record_path))
    return results


def run_record_suite(
    recorder: Callable[[EvalCase], Dict[str, Any]],
    cases: Iterable[EvalCase],
    records_dir: Path,
    adapter: str,
    model: str,
) -> List[Path]:
    """Explicit record mode; caller owns any real provider calls inside recorder."""
    written = []
    for case in cases:
        response = recorder(case)
        record = build_eval_record(case, response=response, adapter=adapter, model=model)
        written.append(write_eval_record(record, records_dir=records_dir))
    return written


def eval_results_payload(results: List[EvalResult]) -> Dict[str, Any]:
    return {
        "passed": all(result.passed for result in results),
        "total": len(results),
        "failures": [result.__dict__ for result in results if not result.passed],
        "results": [result.__dict__ for result in results],
        "prompt_version": EVAL_PROMPT_VERSION,
        "schema_version": EVAL_SCHEMA_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
    }


__all__ = [
    "EVAL_PROMPT_VERSION",
    "EVAL_SCHEMA_VERSION",
    "EVAL_RECORD_VERSION",
    "EvalCase",
    "EvalResult",
    "evaluation_input_hash",
    "load_eval_case",
    "load_eval_cases",
    "build_eval_record",
    "write_eval_record",
    "load_eval_record",
    "run_eval_case_replay",
    "run_replay_suite",
    "run_record_suite",
    "eval_results_payload",
]
