from __future__ import annotations

import json
from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path
from typing import Any

CATALOG_RESOURCE = "data_signal_cases.json"
CATALOG_REQUIRED_FIELDS = {
    "id",
    "title",
    "domain",
    "priority",
    "modes",
    "automation",
    "preconditions",
    "inputs",
    "steps",
    "expected",
    "failure_criteria",
}
VALID_PRIORITIES = {"P0", "P1", "P2"}
VALID_MODES = {"gate", "live", "e2e"}


def _default_catalog_path() -> Path:
    return Path(str(files("app.qa").joinpath(CATALOG_RESOURCE)))


def validate_qa_catalog(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("catalog_version") != "1.0":
        errors.append("catalog_version must be 1.0")
    if not str(payload.get("strategy_version") or "").strip():
        errors.append("strategy_version is required")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return [*errors, "cases must be a non-empty list"]

    seen: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(CATALOG_REQUIRED_FIELDS - set(case))
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            errors.append(f"{prefix}.id is required")
        elif case_id in seen:
            errors.append(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if case.get("priority") not in VALID_PRIORITIES:
            errors.append(f"{case_id or prefix}.priority is invalid")
        modes = case.get("modes")
        if (
            not isinstance(modes, list)
            or not modes
            or not set(modes).issubset(VALID_MODES)
        ):
            errors.append(f"{case_id or prefix}.modes must use gate/live/e2e")
        for field in ("preconditions", "steps", "expected", "failure_criteria"):
            if not isinstance(case.get(field), list) or not case.get(field):
                errors.append(f"{case_id or prefix}.{field} must be a non-empty list")
        if not isinstance(case.get("inputs"), dict):
            errors.append(f"{case_id or prefix}.inputs must be an object")
        if not str(case.get("automation") or "").strip():
            errors.append(f"{case_id or prefix}.automation is required")
    return errors


def load_qa_catalog(path: Path | str | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else _default_catalog_path()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("QA catalog root must be an object")
    errors = validate_qa_catalog(payload)
    if errors:
        raise ValueError("Invalid QA catalog: " + "; ".join(errors))
    return payload


def _join(values: Iterable[object]) -> str:
    return "<br>".join(str(value).replace("|", "\\|") for value in values)


def render_qa_catalog_markdown(payload: dict[str, Any]) -> str:
    errors = validate_qa_catalog(payload)
    if errors:
        raise ValueError("Invalid QA catalog: " + "; ".join(errors))
    lines = [
        "# 데이터 연동·시그널 판단 QA 카탈로그",
        "",
        f"- 카탈로그 버전: `{payload['catalog_version']}`",
        f"- 기준 전략: `{payload['strategy_version']}`",
        f"- QA 항목: {len(payload['cases'])}개",
        "- 상태 규칙: `PASS` 정상, `WARN` 외부 원천 일시 장애 또는 허용된 caution, `FAIL` 계약 위반",
        "",
        "이 문서는 `app/qa/data_signal_cases.json`에서 생성합니다. 직접 수정하지 않습니다.",
        "",
    ]
    domains = list(dict.fromkeys(case["domain"] for case in payload["cases"]))
    for domain in domains:
        lines.extend(
            [
                f"## {domain}",
                "",
                "| QA ID | 우선순위 | 제목 | 실행 | 사전조건 | 입력 | 검증 절차 | 기대 결과 | 실패 기준 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for case in (item for item in payload["cases"] if item["domain"] == domain):
            inputs = (
                ", ".join(
                    f"{key}={value}" for key, value in case.get("inputs", {}).items()
                )
                or "-"
            )
            lines.append(
                "| {id} | {priority} | {title} | {modes}<br>{automation} | {preconditions} | {inputs} | {steps} | {expected} | {failure} |".format(
                    id=case["id"],
                    priority=case["priority"],
                    title=str(case["title"]).replace("|", "\\|"),
                    modes=", ".join(case["modes"]),
                    automation=str(case["automation"]).replace("|", "\\|"),
                    preconditions=_join(case["preconditions"]),
                    inputs=inputs.replace("|", "\\|"),
                    steps=_join(case["steps"]),
                    expected=_join(case["expected"]),
                    failure=_join(case["failure_criteria"]),
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_qa_catalog_markdown(
    output: Path | str,
    *,
    catalog_path: Path | str | None = None,
) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_qa_catalog_markdown(load_qa_catalog(catalog_path)),
        encoding="utf-8",
    )
    return destination
