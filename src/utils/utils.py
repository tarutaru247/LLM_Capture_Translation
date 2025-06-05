"""
ユーティリティ関数モジュール
"""
import os
import logging
from datetime import datetime

# ロギング設定
def setup_logger():
    """アプリケーションのロガーを設定する"""
    log_dir = os.path.join(os.path.expanduser('~'), '.ocr_translator', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'ocr_translator_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('ocr_translator')

# エラーハンドリング
def handle_exception(logger, e, context=""):
    """例外をログに記録し、ユーザーフレンドリーなメッセージを返す"""
    error_msg = f"エラーが発生しました: {str(e)}"
    if context:
        error_msg = f"{context}中にエラーが発生しました: {str(e)}"
    
    logger.error(error_msg, exc_info=True)
    return error_msg

# 画像処理ユーティリティ
def ensure_dir(directory):
    """ディレクトリが存在することを確認し、存在しない場合は作成する"""
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def get_temp_dir():
    """一時ファイル用のディレクトリパスを取得する"""
    temp_dir = os.path.join(os.path.expanduser('~'), '.ocr_translator', 'temp')
    return ensure_dir(temp_dir)

def get_config_dir():
    """設定ファイル用のディレクトリパスを取得する"""
    config_dir = os.path.join(os.path.expanduser('~'), '.ocr_translator', 'config')
    return ensure_dir(config_dir)
