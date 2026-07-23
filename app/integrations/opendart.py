from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any
from urllib.parse import urlencode

import requests


class OpenDartTransportError(RuntimeError):
    pass


def fetch_opendart_json(url: str, params: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    if curl_path:
        command = [curl_path, "--silent", "--show-error", "--fail-with-body", "--get", url]
        for key, value in params.items():
            if value is None:
                continue
            command.extend(["--data-urlencode", f"{key}={value}"])

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenDartTransportError("OpenDART curl request timed out.") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise OpenDartTransportError(f"OpenDART curl request failed: {detail}") from exc

        payload_text = completed.stdout
    else:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload_text = response.text

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        preview = payload_text[:300].strip()
        raise OpenDartTransportError(f"OpenDART returned invalid JSON: {preview}") from exc

    if not isinstance(payload, dict):
        raise OpenDartTransportError("OpenDART returned a non-object JSON payload.")

    return payload


def fetch_opendart_bytes(url: str, params: dict[str, Any], timeout: int = 30) -> bytes:
    filtered = {key: value for key, value in params.items() if value is not None}
    curl_path = shutil.which("curl")
    if curl_path:
        command = [curl_path, "--silent", "--show-error", "--fail-with-body", "--get", url]
        for key, value in filtered.items():
            command.extend(["--data-urlencode", f"{key}={value}"])
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenDartTransportError("OpenDART binary request timed out.") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="ignore").strip() or str(exc)
            raise OpenDartTransportError(f"OpenDART binary request failed: {detail}") from exc
        return completed.stdout

    response = requests.get(f"{url}?{urlencode(filtered)}", timeout=timeout)
    response.raise_for_status()
    return response.content
