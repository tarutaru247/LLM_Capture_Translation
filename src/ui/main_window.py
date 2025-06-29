"""
メインウィンドウモジュール
"""
import sys
import logging
import ctypes
from ctypes import wintypes

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QTextEdit, QComboBox,
                            QAction, QMenu, QToolBar, QStatusBar, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap

from ..ui.screen_capture import ScreenCaptureWindow
from ..utils.settings_manager import SettingsManager
from ..ui.settings_dialog import SettingsDialog
from ..ui.translation_overlay import TranslationOverlay
from ..ocr.vision_ocr_service import VisionOCRService
from ..translator.translation_manager import TranslationManager

logger = logging.getLogger('ocr_translator')

# --- Windows APIのための定数 ---
# https://learn.microsoft.com/ja-jp/windows/win32/api/winuser/nf-winuser-registerhotkey
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_X = 0x58
WM_HOTKEY = 0x0312

class MainWindow(QMainWindow):
    """アプリケーションのメインウィンドウ"""
    
    def __init__(self):
        super().__init__()
        
        # --- ホットキーID ---
        self.hotkey_id = 1 
        
        # 設定マネージャーの初期化
        self.settings_manager = SettingsManager()
        
        # スクリーンキャプチャウィンドウ
        self.capture_window = None
        
        # OCRサービス（Vision API）の初期化
        self.ocr_service = VisionOCRService()
        
        # 翻訳マネージャーの初期化
        self.translation_manager = TranslationManager()
        
        # キャプチャした画像
        self.captured_pixmap = None
        
        # OCRで抽出したテキスト
        self.extracted_text = ""
        
        # 翻訳されたテキスト
        self.translated_text = ""

        # オーバーレイウィンドウ
        self.overlay = None
        
        # UIの初期化
        self._init_ui()
        
        # グローバルホットキーの登録
        self._register_global_hotkey()
        
        logger.info("メインウィンドウを初期化しました")
    
    def _init_ui(self):
        """UIの初期化"""
        # ウィンドウの基本設定
        self.setWindowTitle("キャプチャAI翻訳くん")
        self.setMinimumSize(800, 600)

        # スタイルシートの適用
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                color: #333333;
            }
            QPushButton {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                font-family: "Yu Gothic UI", "Meiryo UI", monospace;
                font-size: 14px;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QComboBox {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QToolBar {
                background-color: #e0e0e0;
                spacing: 10px;
            }
            QStatusBar {
                background-color: #e0e0e0;
                color: #333333;
            }
        """)
        
        # メニューバーの設定
        self._create_menu_bar()
        
        # ステータスバーの設定
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了 (ホットキー: Ctrl+Shift+X)")
        
        # 中央ウィジェットの設定
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout(central_widget)
        
        # キャプチャボタン
        capture_button = QPushButton(QIcon("icons/capture.png"), "画面範囲をキャプチャ")
        capture_button.setIconSize(QSize(24, 24))
        capture_button.setMinimumHeight(40)
        capture_button.clicked.connect(self._on_capture_button_clicked)
        main_layout.addWidget(capture_button)
        
        # 言語選択
        language_layout = QHBoxLayout()
        language_layout.addWidget(QLabel("翻訳先言語:"))
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["日本語", "英語", "中国語", "韓国語", "フランス語", "ドイツ語"])
        language_layout.addWidget(self.language_combo)
        
        # 現在選択されている言語を設定
        target_lang = self.settings_manager.get_target_language()
        lang_index = 0  # デフォルトは日本語
        if target_lang == "en":
            lang_index = 1
        elif target_lang == "zh":
            lang_index = 2
        elif target_lang == "ko":
            lang_index = 3
        elif target_lang == "fr":
            lang_index = 4
        elif target_lang == "de":
            lang_index = 5
        self.language_combo.setCurrentIndex(lang_index)
        
        language_layout.addStretch()
        main_layout.addLayout(language_layout)
        
        # 結果表示エリア
        result_layout = QHBoxLayout()
        
        # 原文表示用のウィジェットを作成
        self.original_widget = QWidget()
        original_layout = QVBoxLayout(self.original_widget)
        original_layout.setContentsMargins(0, 0, 0, 0) # ウィジェット間のマージンを調整
        original_layout.addWidget(QLabel("原文:"))
        
        self.original_text_edit = QTextEdit()
        self.original_text_edit.setReadOnly(True)
        original_layout.addWidget(self.original_text_edit)
        
        copy_original_button = QPushButton("コピー")
        copy_original_button.clicked.connect(self._copy_original_text)
        original_layout.addWidget(copy_original_button)
        
        result_layout.addWidget(self.original_widget)
        
        # 翻訳表示
        translation_layout = QVBoxLayout()
        translation_layout.addWidget(QLabel("翻訳:"))
        
        self.translation_text_edit = QTextEdit()
        self.translation_text_edit.setReadOnly(True)
        translation_layout.addWidget(self.translation_text_edit)
        
        copy_translation_button = QPushButton("コピー")
        copy_translation_button.clicked.connect(self._copy_translation_text)
        translation_layout.addWidget(copy_translation_button)
        
        result_layout.addLayout(translation_layout)
        
        main_layout.addLayout(result_layout)

        # 進捗表示用のラベル
        self.progress_label = QLabel("処理中...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("font-size: 18px; color: #007bff; font-weight: bold;")
        self.progress_label.hide() # 初期状態では非表示
        main_layout.addWidget(self.progress_label)

        # UIの表示状態を更新
        self._update_ui_visibility()

    def _update_ui_visibility(self):
        """設定に基づいてUIの表示/非表示を切り替える"""
        transcribe_original = self.settings_manager.get_transcribe_original_text()
        self.original_widget.setVisible(transcribe_original)
    
    def _create_menu_bar(self):
        """メニューバーの作成"""
        menu_bar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menu_bar.addMenu("ファイル")
        
        exit_action = QAction(QIcon("icons/exit.png"), "終了", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 設定メニュー
        settings_menu = menu_bar.addMenu("設定")
        
        api_settings_action = QAction(QIcon("icons/settings.png"), "設定", self)
        api_settings_action.triggered.connect(self._show_settings_dialog)
        settings_menu.addAction(api_settings_action)
        
        # ヘルプメニュー
        help_menu = menu_bar.addMenu("ヘルプ")
        
        about_action = QAction(QIcon("icons/info.png"), "バージョン情報", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
        
        usage_action = QAction(QIcon("icons/help.png"), "使い方", self)
        usage_action.triggered.connect(self._show_usage_dialog)
        help_menu.addAction(usage_action)
    
    def start_capture(self):
        """領域選択キャプチャを開始する。ホットキーから呼び出されることを想定。"""
        # 既にキャプチャウィンドウが開いている場合は何もしない
        if self.capture_window and self.capture_window.isVisible():
            return
            
        logger.info("領域選択キャプチャを開始します。")
        self.status_bar.showMessage("画面の翻訳したい領域をドラッグで選択してください...")
        
        # キャプチャ中はメインウィンドウを非表示にする
        self.hide()
        # 少し待ってからキャプチャを開始しないと、非表示処理が間に合わず、
        # メインウィンドウ自身がスクリーンショットに写り込んでしまう
        QApplication.processEvents()
        
        self.capture_window = ScreenCaptureWindow()
        self.capture_window.region_selected.connect(self._on_capture_complete)
        # ウィンドウが閉じたときにメインウィンドウを再表示するための接続
        self.capture_window.destroyed.connect(self.show)
        self.capture_window.show()

    def _on_capture_button_clicked(self):
        """キャプチャボタンがクリックされたときの処理"""
        self.start_capture()
    
    def _on_capture_complete(self, pixmap: QPixmap):
        """キャプチャ完了時の処理"""
        # キャプチャがキャンセルされた（空のPixmapが来た）場合は何もしない
        if not pixmap or pixmap.isNull():
            logger.info("キャプチャがキャンセルまたは失敗しました。")
            self.status_bar.showMessage("キャプチャがキャンセルされました", 3000)
            # メインウィンドウを再表示
            self.show()
            return

        self.captured_pixmap = pixmap
        self.status_bar.showMessage("キャプチャ完了、翻訳処理中...")
        self.progress_label.setText("翻訳処理中...")
        self.progress_label.show()
        QApplication.processEvents() # UIの更新を即時反映

        # --- 翻訳処理 ---
        target_lang = self._get_selected_target_language()
        transcribe_original = self.settings_manager.get_transcribe_original_text()
        self._update_ui_visibility()

        translated_text = None
        error_message = None

        if transcribe_original:
            # フロー1: OCR -> 翻訳
            extracted_text = self.ocr_service.extract_text(self.captured_pixmap)
            if extracted_text and not extracted_text.startswith("エラー:"):
                self.extracted_text = extracted_text
                self.original_text_edit.setText(extracted_text)
                translated_text = self.translation_manager.translate(extracted_text, target_lang)
            else:
                error_message = extracted_text or "テキストの抽出に失敗しました。"
        else:
            # フロー2: 画像から直接翻訳
            translated_text = self.translation_manager.translate_image(self.captured_pixmap, target_lang)

        # --- 処理結果の表示 ---
        self.progress_label.hide()
        self.show() # メインウィンドウを再表示

        if translated_text and not translated_text.startswith("エラー:"):
            self.translated_text = translated_text
            self.translation_text_edit.setText(translated_text)
            api_info = f"(API: {self.settings_manager.get_selected_api().upper()})"
            self.status_bar.showMessage(f"翻訳が完了しました。{api_info}", 5000)
            logger.info("翻訳成功")

            # --- オーバーレイ表示 ---
            # 以前のオーバーレイが残っていれば閉じる
            try:
                if self.overlay and self.overlay.isVisible():
                    self.overlay.close()
            except RuntimeError:
                # このブロックは、前のオーバーレイが自動的に閉じた後に新しい翻訳が実行された場合に正常に到達します
                logger.info("古いオーバーレイは自動的に破棄済みのため、新しいオーバーレイを表示します。")
                self.overlay = None # 参照をクリア
            
            # 表示位置を計算（キャプチャ領域の下中央）
            capture_rect = self.capture_window.rubber_band.geometry()
            pos_x = capture_rect.x() + (capture_rect.width() / 2) - 200 # overlay幅の半分を引く
            pos_y = capture_rect.y() + capture_rect.height() + 10 # 10px下に表示

            self.overlay = TranslationOverlay(translated_text, position=(int(pos_x), int(pos_y)))
            self.overlay.show_and_fade_out()

        else:
            # エラー処理
            final_error = error_message or translated_text or "不明なエラーが発生しました。"
            self.status_bar.showMessage(f"エラー: {final_error}", 5000)
            self.translation_text_edit.setText(f"翻訳に失敗しました。\n詳細: {final_error}")
            logger.error(f"翻訳失敗: {final_error}")
    
    def _get_selected_target_language(self) -> str:
        """選択されている翻訳先言語コードを取得するヘルパーメソッド"""
        lang_index = self.language_combo.currentIndex()
        if lang_index == 0: return 'ja'
        elif lang_index == 1: return 'en'
        elif lang_index == 2: return 'zh'
        elif lang_index == 3: return 'ko'
        elif lang_index == 4: return 'fr'
        elif lang_index == 5: return 'de'
        return 'ja' # デフォルト

    # _process_ocr と _translate_text は _on_capture_complete に統合されたため削除
    # def _process_ocr(self):
    #     pass

    # def _translate_text(self):
    #     pass
    
    def _copy_original_text(self):
        """原文テキストをクリップボードにコピー"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.original_text_edit.toPlainText())
        self.status_bar.showMessage("原文をクリップボードにコピーしました", 3000)
    
    def _copy_translation_text(self):
        """翻訳テキストをクリップボードにコピー"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.translation_text_edit.toPlainText())
        self.status_bar.showMessage("翻訳をクリップボードにコピーしました", 3000)
    
    def _show_settings_dialog(self):
        """設定ダイアログを表示"""
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec_():
            # 設定が保存された場合、SettingsManagerの内部設定を再読み込みし、UIを更新
            self.settings_manager.settings = self.settings_manager._load_settings() # 設定を再読み込み

            # UIの表示状態を更新
            self._update_ui_visibility()

            target_lang = self.settings_manager.get_target_language()
            lang_index = 0  # デフォルトは日本語
            
            if target_lang == "en":
                lang_index = 1
            elif target_lang == "zh":
                lang_index = 2
            elif target_lang == "ko":
                lang_index = 3
            elif target_lang == "fr":
                lang_index = 4
            elif target_lang == "de":
                lang_index = 5
                
            self.language_combo.setCurrentIndex(lang_index)
            self.status_bar.showMessage("設定を保存しました", 3000)
    
    def _show_about_dialog(self):
        """バージョン情報ダイアログを表示"""
        QMessageBox.about(self, "バージョン情報", 
                         "OCR翻訳ツール v0.0.1\n"
                         "© 2025 tarutaru247")
    
    def _show_usage_dialog(self):
        """使い方ダイアログを表示"""
        QMessageBox.information(self, "使い方",
                               "ホットキー(Ctrl+Shift+X)を押して、\n"
                               "翻訳したいテキストの範囲を選択します。\n\n"
                               "メインウィンドウのボタンからも実行できます。\n"
                               "必要に応じて結果をコピーして利用できます")

    def _register_global_hotkey(self):
        """Windows APIを使用してグローバルホットキーを登録する"""
        try:
            # user32.dllをロード
            user32 = ctypes.windll.user32
            
            # ウィンドウハンドルを取得
            hwnd = self.winId()
            
            # ホットキーを登録
            if not user32.RegisterHotKey(wintypes.HWND(int(hwnd)), self.hotkey_id, MOD_CONTROL | MOD_SHIFT, VK_X):
                error_code = ctypes.GetLastError()
                logger.error(f"グローバルホットキーの登録に失敗しました。エラーコード: {error_code}")
                self.status_bar.showMessage("エラー: ホットキーの登録に失敗しました")
            else:
                logger.info(f"グローバルホットキー(Ctrl+Shift+X)をID {self.hotkey_id} で登録しました。")
        except Exception as e:
            logger.error(f"ホットキー登録中に予期せぬエラーが発生しました: {e}")
            self.status_bar.showMessage("エラー: ホットキー登録中に例外が発生しました")

    def _unregister_global_hotkey(self):
        """登録したグローバルホットキーを解除する"""
        try:
            user32 = ctypes.windll.user32
            hwnd = self.winId()
            user32.UnregisterHotKey(wintypes.HWND(int(hwnd)), self.hotkey_id)
            logger.info("グローバルホットキーを解除しました。")
        except Exception as e:
            logger.error(f"ホットキー解除中にエラーが発生しました: {e}")

    def nativeEvent(self, eventType, message):
        """Windowsのネイティブイベントを処理する"""
        # QPAプラグインからのイベントメッセージを処理
        if eventType == b'windows_generic_MSG':
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_HOTKEY:
                if msg.wParam == self.hotkey_id:
                    logger.info("グローバルホットキーが検出されました！")
                    self.start_capture()
                    return True, 0 # イベントを処理したことを示す
        
        # 親クラスのnativeEventを呼び出す
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event):
        """ウィンドウが閉じられるときの処理"""
        # ホットキーの解除
        self._unregister_global_hotkey()
        # 設定を保存
        self.settings_manager.save_settings()
        logger.info("アプリケーションを終了します。")
        event.accept()
