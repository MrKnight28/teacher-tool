"""The one place that opens HTTP connections to providers (stdlib only)."""
from __future__ import annotations
import json
import secrets
import urllib.request


def get_json(url: str, headers: dict | None = None, timeout: int = 20) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r:
        return json.load(r)


def post_json(url: str, body: bytes, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, body, headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def multipart(fields: dict, file_field: str, filename: str, file_bytes: bytes, mime: str) -> tuple[bytes, str]:
    boundary = "----tutor" + secrets.token_hex(12)
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    head = f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
    parts.append(head.encode() + file_bytes + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"
