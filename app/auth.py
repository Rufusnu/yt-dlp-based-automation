import hashlib, hmac, json, os, secrets
from pathlib import Path

DATA = Path(os.environ.get("YT_BASE", "/data/yt-dlp")) / "webui"
AUTH = DATA / "auth.json"
KEY = DATA / "secret.key"


def _hash(pw, salt):
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def _write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(path, 0o600)


def set_password(pw):
    DATA.mkdir(exist_ok=True)
    salt = secrets.token_bytes(16)
    _write_private(AUTH, json.dumps({"salt": salt.hex(), "hash": _hash(pw, salt)}))
    _write_private(KEY, secrets.token_hex(32))  # new session key: old sessions stop working after a restart


def check_password(pw):
    try:
        d = json.loads(AUTH.read_text())
        return hmac.compare_digest(_hash(pw, bytes.fromhex(d["salt"])), d["hash"])
    except Exception:
        return False


def secret_key():
    DATA.mkdir(exist_ok=True)
    if not KEY.exists():
        _write_private(KEY, secrets.token_hex(32))
    return KEY.read_text().strip()
