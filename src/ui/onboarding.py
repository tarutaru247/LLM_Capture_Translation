"""Terms are separate from download; neither checkbox is preselected."""
from pathlib import Path
import threading
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QMessageBox, QProgressBar, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout)
from ..translator.plamo_runtime import resource_root
from ..utils.consent import has_terms_consent, record_terms_consent
from ..utils.model_catalog import MODELS, download_model, verify_model
from .theme import apply_palette, is_dark, native_title_bar, stylesheet


class SetupBridge(QObject):
    progress = Signal(int)
    finished = Signal(str)


class TermsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle('たる翻訳 — 利用条件の確認')
        self.resize(780, 680)
        dark = is_dark(settings.get_setting('ui', 'theme', 'system'))
        self.setStyleSheet(stylesheet(dark))
        layout = QVBoxLayout(self)
        title = QLabel('たる翻訳へようこそ'); title.setObjectName('heading'); layout.addWidget(title)
        note = QLabel('まず利用条件をご確認ください。同意するまでモデルの取得・読み込みを行いません。\nクラウド翻訳は初期状態で無効です。')
        note.setWordWrap(True); layout.addWidget(note)
        tabs = QTabWidget()
        for title, files in [('ソフトウェア・プライバシー', ['docs/TERMS-ja.md', 'LICENSE']),
                             ('PLaMo 契約全文（日本語）', ['docs/licenses/PLaMo-ja.txt']),
                             ('PLaMo License (English)', ['docs/licenses/PLaMo-en.txt'])]:
            browser = QTextBrowser()
            browser.setPlainText('\n\n'.join((resource_root() / f).read_text(encoding='utf-8') for f in files))
            tabs.addTab(browser, title)
        layout.addWidget(tabs, 1)
        self.software_agree = QCheckBox('ソフトウェアの利用条件とデータの取り扱いを確認し、同意します')
        self.plamo_agree = QCheckBox('PLaMoコミュニティライセンス全文を確認し、同意します')
        layout.addWidget(self.software_agree); layout.addWidget(self.plamo_agree)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton('同意しない'); cancel.clicked.connect(self.reject)
        self.continue_button = QPushButton('同意して次へ'); self.continue_button.setObjectName('primary')
        self.continue_button.setEnabled(False)
        self.software_agree.toggled.connect(self._changed); self.plamo_agree.toggled.connect(self._changed)
        self.continue_button.clicked.connect(self._accept_terms)
        buttons.addWidget(cancel); buttons.addWidget(self.continue_button); layout.addLayout(buttons)
        apply_palette(self, dark); native_title_bar(self, dark)

    def _changed(self):
        self.continue_button.setEnabled(self.software_agree.isChecked() and self.plamo_agree.isChecked())

    def _accept_terms(self):
        if not (self.software_agree.isChecked() and self.plamo_agree.isChecked()):
            return
        try:
            record_terms_consent(self.settings)
        except RuntimeError as exc:
            QMessageBox.warning(self, '保存できません', str(exc)); return
        self.accept()


def ensure_terms(settings, parent=None):
    return has_terms_consent(settings) or TermsDialog(settings, parent).exec() == QDialog.Accepted


class ModelSetupDialog(QDialog):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.running = False; self.cancelled = threading.Event(); self._close_after = False
        self.bridge = SetupBridge(self)
        self.bridge.progress.connect(lambda value: self.progress.setValue(value))
        self.bridge.finished.connect(self._finished)
        self.setWindowTitle('たる翻訳 — ローカルモデルの準備'); self.resize(650, 410)
        dark = is_dark(settings.get_setting('ui', 'theme', 'system')); self.setStyleSheet(stylesheet(dark))
        layout = QVBoxLayout(self)
        title = QLabel('PC内で翻訳する準備'); title.setObjectName('heading'); layout.addWidget(title)
        note = QLabel('公式Hugging FaceからPLaMoを取得します。画像や原文は送信しません。\n取得後のOCRと翻訳はPC内で行います。Built with PLaMo')
        note.setWordWrap(True); layout.addWidget(note)
        self.profile = QComboBox()
        self.profile.addItem('軽量：0.8B GGUF（約573 MB・推奨）', 'lightweight')
        self.profile.addItem('品質優先：2B GGUF（約1.81 GB）', 'quality')
        self.profile.setCurrentIndex(max(0, self.profile.findData(settings.get_local_profile())))
        layout.addWidget(self.profile)
        self.progress = QProgressBar(); layout.addWidget(self.progress)
        self.status = QLabel('すでにモデルがある場合も、サイズとSHA-256を確認します。')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True); layout.addWidget(self.status)
        ocr = QLabel('画像の文字認識にはWindowsのOCR言語機能が必要です。\n英語・中国語など、読み取る言語はアプリの設定で選べます。')
        ocr.setWordWrap(True); layout.addWidget(ocr)
        layout.addStretch(); row = QHBoxLayout()
        self.cancel = QPushButton('終了'); self.cancel.clicked.connect(self.reject); row.addWidget(self.cancel)
        self.existing = QPushButton('既存モデルを選択'); self.existing.clicked.connect(self._browse); row.addWidget(self.existing)
        self.start = QPushButton('モデルを取得して開始'); self.start.setObjectName('primary'); self.start.clicked.connect(lambda: self._run()); row.addWidget(self.start)
        layout.addLayout(row); apply_palette(self, dark); native_title_bar(self, dark)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, '公式GGUFモデルを選択', '', 'GGUF (*.gguf)')
        if path: self._run(path)

    def _run(self, selected=None):
        if self.running or not has_terms_consent(self.settings): return
        self.running = True; self.cancelled.clear(); self.progress.setValue(0)
        for widget in (self.profile, self.start, self.existing): widget.setEnabled(False)
        profile = self.profile.currentData()
        path = selected or self.settings.get_setting('local_model', profile + '_path')
        self.status.setText('検証・取得しています…')
        self._profile, self._path = profile, path
        def run():
            error = ''
            try:
                if Path(path).exists(): verify_model(profile, path, self.cancelled.is_set)
                else: download_model(profile, path, lambda n, total: self.bridge.progress.emit(int(n * 100 / total)), self.cancelled.is_set)
                if self.cancelled.is_set(): raise RuntimeError('中止しました。')
            except Exception as exc:
                from ..utils.utils import sanitize_sensitive_data
                error = sanitize_sensitive_data(str(exc))
            self.bridge.finished.emit(error)
        threading.Thread(target=run, name='first-run-model', daemon=True).start()

    def _finished(self, error):
        self.running = False
        for widget in (self.profile, self.start, self.existing): widget.setEnabled(True)
        if self._close_after: super().reject(); return
        if error: self.status.setText(error); return
        before = {key: dict(self.settings.settings[key]) for key in ('local_model', 'onboarding', 'translation')}
        self.settings.set_setting('local_model', 'profile', self._profile)
        self.settings.set_setting('local_model', self._profile + '_path', self._path)
        self.settings.set_setting('onboarding', 'completed', True)
        self.settings.set_setting('translation', 'provider', 'plamo')
        if not self.settings.save_settings():
            self.settings.settings.update(before); self.status.setText('設定を保存できません。'); return
        self.accept()

    def reject(self):
        if self.running:
            self.cancelled.set(); self._close_after = True; self.cancel.setEnabled(False); return
        super().reject()

    def closeEvent(self, event):
        if self.running: self.reject(); event.ignore()
        else: super().closeEvent(event)
