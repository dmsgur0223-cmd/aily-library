"""Local-only operator settings and credentials; never part of update packages."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile

APP_DEFAULTS = {"institution_name": "인천서구시설관리공단", "department_name": "도서관사업단"}
SETTINGS_FILE = "app_settings.json"
AUTH_FILE = "admin_auth.json"
SECRETS = {
    "law": ("law_oc.txt", "AILY_LAW_OC"),
    "yes24": ("yes24_api_key.txt", "AILY_YES24_API_KEY"),
    "qnet": ("qnet_api_key.txt", "AILY_QNET_API_KEY"),
}


def config_dir(root: Path) -> Path:
    return root / "config"


def _json_read(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("설정 파일이 올바른 JSON 객체가 아닙니다.")
    return value


def _atomic_private_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".aily_", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_settings(root: Path) -> dict[str, str]:
    saved = _json_read(config_dir(root) / SETTINGS_FILE)
    result = APP_DEFAULTS.copy()
    for key in APP_DEFAULTS:
        value = saved.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()[:100]
    return result


def save_settings(root: Path, institution_name: str, department_name: str) -> None:
    data = {}
    for key, value in (("institution_name", institution_name), ("department_name", department_name)):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100 or any(ord(c) < 32 for c in value):
            raise ValueError("기관명/부서명은 1~100자 일반 문자로 입력하세요.")
        data[key] = value.strip()
    _atomic_private_write(config_dir(root) / SETTINGS_FILE, json.dumps(data, ensure_ascii=False, indent=2))


def read_secret(root: Path, service: str) -> str:
    filename, env = SECRETS[service]
    path = config_dir(root) / filename
    if path.is_file():
        saved = path.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    return os.environ.get(env, "").strip()


def save_secret(root: Path, service: str, value: str) -> None:
    filename, _ = SECRETS[service]
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 2048 or any(ord(c) < 33 or ord(c) > 126 for c in value.strip()):
        raise ValueError("인증값은 공백이나 줄바꿈 없는 1~2048자 문자열이어야 합니다.")
    _atomic_private_write(config_dir(root) / filename, value.strip() + "\n")


def delete_secret(root: Path, service: str) -> None:
    filename, _ = SECRETS[service]
    (config_dir(root) / filename).unlink(missing_ok=True)


def has_admin_password(root: Path) -> bool:
    return (config_dir(root) / AUTH_FILE).exists()


def set_admin_password(root: Path, password: str, *, replace: bool = False) -> None:
    path = config_dir(root) / AUTH_FILE
    if path.exists() and not replace:
        raise PermissionError("관리자 비밀번호가 이미 설정되어 있습니다.")
    if not isinstance(password, str) or len(password) < 12 or len(password) > 256:
        raise ValueError("관리자 비밀번호는 12~256자로 설정하세요.")
    salt = secrets.token_bytes(16)
    count = 350_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, count)
    _atomic_private_write(path, json.dumps({"algorithm": "pbkdf2_sha256", "iterations": count,
                                           "salt": salt.hex(), "hash": digest.hex()}))


def verify_admin_password(root: Path, password: str) -> bool:
    try:
        value = _json_read(config_dir(root) / AUTH_FILE)
        if value.get("algorithm") != "pbkdf2_sha256":
            return False
        count = int(value["iterations"])
        if not 100_000 <= count <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(value["salt"]), count)
        return hmac.compare_digest(actual, bytes.fromhex(value["hash"]))
    except (OSError, KeyError, TypeError, ValueError, OverflowError):
        return False
