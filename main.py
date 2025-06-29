import sys
import logging
import threading
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QMetaObject, Qt
from pynput import keyboard

from src.ui.main_window import MainWindow
from src.utils.utils import setup_logger

# --- グローバル変数 ---
main_window = None
logger = setup_logger() # ロガーをグローバルに設定

# --- ホットキー処理 ---
def on_activate_hotkey():
    """ホットキーが有効化されたときに呼び出される関数"""
    logger.info("ホットキーが検出されました。キャプチャを開始します。")
    if main_window:
        # GUI操作はメインスレッドで行う必要があるため、invokeMethodを使用
        QMetaObject.invokeMethod(main_window, "start_capture", Qt.QueuedConnection)

def start_hotkey_listener():
    """ホットキーリスナーを別スレッドで開始する"""
    # <ctrl>+<shift>+x のホットキーを定義
    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse('<ctrl>+<shift>+x'),
        on_activate_hotkey
    )

    # リスナーを作成
    # on_pressとon_releaseにhotkeyのメソッドを渡す
    with keyboard.Listener(on_press=hotkey.press, on_release=hotkey.release) as listener:
        logger.info("ホットキーリスナーを開始しました。(Ctrl+Shift+X)")
        listener.join()

def main():
    """アプリケーションのメインエントリーポイント"""
    global main_window
    
    logger.info("アプリケーションを起動しています...")
    
    # PyQt5アプリケーションの作成
    app = QApplication(sys.argv)
    app.setApplicationName("OCR翻訳ツール")
    app.setOrganizationName("OCR Translator")
    
    # メインウィンドウの作成と表示
    main_window = MainWindow()
    main_window.show()
    
    logger.info("メインウィンドウを表示しました")
    
    # ホットキーリスナーをデーモンスレッドで開始
    hotkey_thread = threading.Thread(target=start_hotkey_listener, daemon=True)
    hotkey_thread.start()
    
    # アプリケーションの実行
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
