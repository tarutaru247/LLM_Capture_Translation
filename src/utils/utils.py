"""
ユーティリティ関数モジュール
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime

_SENSITIVE_PATTERNS = [
    # OpenAI API keys (sk-*, sk-live-*, sk-proj-*, gsk_...)
    re.compile(r"(sk-[A-Za-z0-9\-]{16,})"),
    re.compile(r"(gsk_[A-Za-z0-9\-]{16,})"),
    re.compile(r"(pk-[A-Za-z0-9\-]{16,})"),
    # Google API keys
    re.compile(r"(AIza[0-9A-Za-z\-_]{12,})"),
]


# ロギング設定
def setup_logger() -> logging.Logger:
    """アプリケーションのロガーを設定する"""
    log_dir = os.path.join(os.path.expanduser('~'), '.ocr_translator', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"ocr_translator_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger('ocr_translator')


def _mask_token(token: str) -> str:
    """機密トークンをマスク表示に変換する。"""
    if len(token) <= 8:
        return '*' * len(token)
    return f"{token[:4]}{'*' * (len(token) - 6)}{token[-2:]}"


def sanitize_sensitive_data(text: str | None) -> str:
    """
    APIキーなどの機密となり得る文字列をマスクする。
    """
    if not text:
        return text or ""
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(lambda m: _mask_token(m.group(1)), sanitized)
    return sanitized


# エラーハンドリング
def handle_exception(logger: logging.Logger, e: Exception, context: str = "") -> str:
    """例外をログに記録し、ユーザーフレンドリーなメッセージを返す"""
    detail = sanitize_sensitive_data(str(e))
    error_msg = f"エラーが発生しました: {detail}"
    if context:
        error_msg = f"{context}中にエラーが発生しました: {detail}"

    logger.error(error_msg, exc_info=True)
    return error_msg


# 画像ディレクトリユーティリティ
def ensure_dir(directory: str) -> str:
    """ディレクトリが存在することを確認し、存在しない場合は作成する"""
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def get_temp_dir() -> str:
    """一時ファイル用のディレクトリパスを取得する"""
    temp_dir = os.path.join(os.path.expanduser('~'), '.ocr_translator', 'temp')
    return ensure_dir(temp_dir)


def get_config_dir() -> str:
    """設定ファイル用のディレクトリパスを取得する"""
    config_dir = os.path.join(os.path.expanduser('~'), '.ocr_translator', 'config')
    return ensure_dir(config_dir)
