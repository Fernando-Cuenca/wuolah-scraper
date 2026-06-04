from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests


@dataclass
class AuthMaterial:
    access_token: str = ""
    refresh_token: str = ""
    cookie_header: str = ""
    cookies: dict[str, str] = field(default_factory=dict)


def _b64url_decode(payload: str) -> bytes:
    padding = '=' * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def jwt_exp(token: str) -> int | None:
    if not token or token.count('.') < 2:
        return None
    try:
        payload = token.split('.')[1]
        data = json.loads(_b64url_decode(payload).decode('utf-8'))
        exp = data.get('exp')
        return int(exp) if exp is not None else None
    except Exception:
        return None


def token_is_fresh(token: str, margin_seconds: int = 60) -> bool:
    exp = jwt_exp(token)
    if exp is None:
        return bool(token)
    return exp > int(time.time()) + margin_seconds


def _parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in (header or '').split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        key, value = part.split('=', 1)
        cookies[key.strip()] = value.strip()
    return cookies


def _load_cookie_file(path: str) -> dict[str, str]:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Cookie file not found: {p}')

    text = p.read_text(encoding='utf-8', errors='replace').strip()
    if not text:
        return {}

    if text.startswith('{') or text.startswith('['):
        data = json.loads(text)
        cookies: dict[str, str] = {}
        if isinstance(data, dict) and isinstance(data.get('cookies'), list):
            items = data['cookies']
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            value = item.get('value')
            if name and value is not None:
                cookies[str(name)] = str(value)
        return cookies

    if '\t' in text or text.startswith('# Netscape HTTP Cookie File'):
        cookies: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]
        return cookies

    return _parse_cookie_header(text)


def load_auth_material(auth_cfg: dict[str, Any] | None) -> AuthMaterial:
    auth_cfg = auth_cfg or {}
    cookie_header = str(auth_cfg.get('cookie_header') or '').strip()
    cookie_file = str(auth_cfg.get('cookie_file') or '').strip()
    access_token = str(auth_cfg.get('access_token') or '').strip()
    refresh_token = str(auth_cfg.get('refresh_token') or '').strip()

    cookies: dict[str, str] = {}
    if cookie_header:
        cookies.update(_parse_cookie_header(cookie_header))
    if cookie_file:
        cookies.update(_load_cookie_file(cookie_file))

    access_token = access_token or cookies.get('token', '')
    refresh_token = refresh_token or cookies.get('refreshToken', '')

    return AuthMaterial(
        access_token=access_token,
        refresh_token=refresh_token,
        cookie_header=cookie_header,
        cookies=cookies,
    )


def apply_auth_to_session(session: requests.Session, material: AuthMaterial) -> None:
    for name, value in material.cookies.items():
        session.cookies.set(name, value)
    if material.access_token:
        session.headers['Authorization'] = f'Bearer {material.access_token}'


def refresh_access_token(api_base_url: str, refresh_token: str, user_agent: str | None = None) -> dict[str, Any]:
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if user_agent:
        headers['User-Agent'] = user_agent
    response = requests.post(
        f"{api_base_url.rstrip('/')}/login/refresh",
        headers=headers,
        json={'refreshToken': refresh_token},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or 'accessToken' not in data:
        raise RuntimeError('Unexpected refresh response shape')
    return data
