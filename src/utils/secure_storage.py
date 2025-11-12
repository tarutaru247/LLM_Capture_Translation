"""
Windows DPAPI を利用して秘密情報を保護/復号するユーティリティ。
Windows 以外では平文をそのまま返すフォールバック動作を行う。
"""
from __future__ import annotations

import base64
import ctypes
import logging
import os
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger("ocr_translator")


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _to_blob(data: bytes) -> _DATA_BLOB:
    """バイト列から DATA_BLOB を作成する。"""
    buffer = (ctypes.c_byte * len(data))(*data)
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))


def _from_blob(blob: _DATA_BLOB) -> bytes:
    """DATA_BLOB から Python の bytes を抽出する。"""
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


def _protect_via_dpapi(secret: str) -> Optional[str]:
    """DPAPI で暗号化し base64 文字列を返す。失敗時は None。"""
    try:
        crypt32 = ctypes.windll.crypt32
        blob_in = _to_blob(secret.encode("utf-8"))
        blob_out = _DATA_BLOB()
        if crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            "ocr_translator_key",
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            return base64.b64encode(_from_blob(blob_out)).decode("ascii")
        error_code = ctypes.GetLastError()
        logger.error("CryptProtectData に失敗しました (code=%s)", error_code)
        return None
    except Exception as exc:
        logger.exception("DPAPI 暗号化中に例外が発生しました: %s", exc)
        return None


def _unprotect_via_dpapi(payload: str) -> Optional[str]:
    """dpapi: 接頭辞付き base64 データを復号する。失敗時は None。"""
    try:
        crypt32 = ctypes.windll.crypt32
        raw = base64.b64decode(payload)
        blob_in = _to_blob(raw)
        blob_out = _DATA_BLOB()
        if crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            return _from_blob(blob_out).decode("utf-8")
        error_code = ctypes.GetLastError()
        logger.error("CryptUnprotectData に失敗しました (code=%s)", error_code)
        return None
    except Exception as exc:
        logger.exception("DPAPI 復号中に例外が発生しました: %s", exc)
        return None


def protect_secret(secret: str) -> str:
    """
    秘密文字列を DPAPI で暗号化し、dpapi: 接頭辞付きで返す。
    Windows 以外では平文を返す。
    """
    if not secret:
        return ""
    if os.name != "nt":
        logger.warning("DPAPI 非対応環境のため平文を保存します (OS=%s)", os.name)
        return secret

    encrypted = _protect_via_dpapi(secret)
    if encrypted is None:
        logger.warning("DPAPI 暗号化に失敗したため平文を保存します")
        return secret
    return f"dpapi:{encrypted}"


def unprotect_secret(value: Optional[str]) -> str:
    """
    dpapi: 接頭辞付き文字列を復号して返す。平文や None の場合はそのまま返す。
    """
    if not value:
        return value or ""
    if not value.startswith("dpapi:"):
        return value
    payload = value.split("dpapi:", 1)[1]
    if os.name != "nt":
        logger.warning("DPAPI データですが非対応 OS のため復号できません")
        return ""
    decrypted = _unprotect_via_dpapi(payload)
    if decrypted is None:
        logger.error("DPAPI データの復号に失敗しました")
        return ""
    return decrypted
