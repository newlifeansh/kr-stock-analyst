"""Export only the safe lifecycle fields emitted by disposable batch jobs."""

import argparse
import json
import re
import subprocess

EVENT = re.compile(
    r"Maintenance job (?P<phase>started|exited|failed) job=(?P<job>[a-z_]+)"
    r"(?: exit=(?P<exit_code>[0-9]+) elapsed_seconds=(?P<seconds>[0-9.]+)"
    r"| error_type=(?P<error_type>[A-Za-z]+))?"
)


def evidence(project: str, service: str) -> list[dict]:
    result = subprocess.run([
        "railway", "logs", "--latest", "--json", "--lines", "200",
        "--filter", "Maintenance job", "--project", project,
        "--environment", "production", "--service", service,
    ], text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Batch lifecycle log query failed")
    events = []
    for line in result.stdout.splitlines():
        row = json.loads(line)
        match = EVENT.search(str(row.get("message", "")))
        if match:
            events.append({key: value for key, value in match.groupdict().items() if value is not None})
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--service", required=True)
    args = parser.parse_args()
    print(json.dumps(evidence(args.project, args.service), indent=2))
