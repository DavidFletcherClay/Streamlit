"""Where the tracker's CSV files live: Dropbox if configured, otherwise ./data.

Dropbox is used when .streamlit/secrets.toml (or the Streamlit Cloud "Secrets"
box) contains:

    [dropbox]
    app_key = "..."
    app_secret = "..."
    refresh_token = "..."
    folder = "/Exercise Tracker"   # optional

Run `python get_dropbox_token.py` once to get the refresh token.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

LOCAL_DIR = Path(__file__).parent / "data"


class ConflictError(Exception):
    """The file changed in Dropbox after the app loaded it."""


def _dropbox_config() -> dict | None:
    try:
        cfg = st.secrets.get("dropbox")
    except Exception:  # no secrets file at all
        return None
    if not cfg or not all(cfg.get(k) for k in ("app_key", "app_secret", "refresh_token")):
        return None
    return dict(cfg)


@st.cache_resource
def _client(app_key: str, app_secret: str, refresh_token: str):
    import dropbox

    return dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=app_key, app_secret=app_secret)


def backend() -> str:
    return "dropbox" if _dropbox_config() else "local"


def folder() -> str:
    cfg = _dropbox_config() or {}
    f = str(cfg.get("folder", "/Exercise Tracker")).strip().rstrip("/")
    return f if not f or f.startswith("/") else "/" + f


def location_label() -> str:
    if backend() == "dropbox":
        return f"Dropbox: {folder() or '/'}"
    return f"Local folder: {LOCAL_DIR}"


def _dbx():
    cfg = _dropbox_config()
    return _client(cfg["app_key"], cfg["app_secret"], cfg["refresh_token"])


def read(name: str, seed: bytes) -> tuple[bytes, str | None]:
    """Return (file contents, revision). Creates the file from `seed` if it is missing.

    The revision is None for local files.
    """
    if backend() == "local":
        path = LOCAL_DIR / name
        if not path.exists():
            LOCAL_DIR.mkdir(exist_ok=True)
            path.write_bytes(seed)
        return path.read_bytes(), None

    import dropbox

    dbx = _dbx()
    path = f"{folder()}/{name}"
    try:
        md, resp = dbx.files_download(path)
        return resp.content, md.rev
    except dropbox.exceptions.ApiError as e:
        err = e.error
        if not (err.is_path() and err.get_path().is_not_found()):
            raise
    # First run: copy the starting data into Dropbox.
    md = dbx.files_upload(seed, path, mode=dropbox.files.WriteMode.add)
    return seed, md.rev


def write(name: str, data: bytes, rev: str | None) -> str | None:
    """Save `data`. With Dropbox, refuses to overwrite a newer version than `rev`."""
    if backend() == "local":
        LOCAL_DIR.mkdir(exist_ok=True)
        (LOCAL_DIR / name).write_bytes(data)
        return None

    import dropbox

    mode = dropbox.files.WriteMode.update(rev) if rev else dropbox.files.WriteMode.overwrite
    try:
        md = _dbx().files_upload(data, f"{folder()}/{name}", mode=mode)
    except dropbox.exceptions.ApiError as e:
        err = e.error
        if err.is_path() and err.get_path().reason.is_conflict():
            raise ConflictError(name) from e
        raise
    return md.rev
