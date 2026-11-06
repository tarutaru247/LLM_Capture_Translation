import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.ui.settings_dialog import SettingsDialog
from src.ui.theme import is_dark, palette
from src.utils.settings_manager import SettingsManager

ROOT = Path(__file__).resolve().parents[1] / "runtime/test-theme"
ROOT.mkdir(parents=True, exist_ok=True)


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.folder.cleanup)
        self.config = patch("src.utils.settings_manager.get_config_dir", return_value=self.folder.name)
        self.config.start()
        self.addCleanup(self.config.stop)

    def window(self):
        with patch.object(MainWindow,"_register_global_hotkey"), patch("src.ui.main_window.QTimer.singleShot"), patch("src.ui.main_window.native_title_bar"):
            window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.theme_timer.stop)
        return window

    def test_initial_preference_is_system(self):
        self.assertEqual(SettingsManager().get_setting("ui","theme"),"system")

    def test_system_and_manual_modes(self):
        with patch("src.ui.theme.system_is_dark", return_value=True):
            self.assertTrue(is_dark("system"))
            self.assertFalse(is_dark("light"))
        with patch("src.ui.theme.system_is_dark", return_value=False):
            self.assertFalse(is_dark("system"))
            self.assertTrue(is_dark("dark"))

    def test_windows_apps_setting_overrides_qt_light_palette(self):
        with patch("src.ui.theme.sys.platform","win32"), patch("winreg.OpenKey"), patch("winreg.QueryValueEx",return_value=(0,4)):
            self.assertTrue(is_dark("system"))
        with patch("src.ui.theme.sys.platform","win32"), patch("winreg.OpenKey"), patch("winreg.QueryValueEx",return_value=(1,4)):
            self.assertFalse(is_dark("system"))

    def test_running_window_and_open_settings_follow_system_changes(self):
        with patch("src.ui.main_window.is_dark",return_value=False):
            window = self.window()
        with patch("src.ui.settings_dialog.native_title_bar"):
            dialog = SettingsDialog(window)
        self.addCleanup(dialog.deleteLater)
        with patch("src.ui.main_window.is_dark",return_value=True), patch("src.ui.main_window.native_title_bar"):
            window._sync_system_theme()
        self.assertTrue(window._dark_theme)
        self.assertEqual(window.palette().color(QPalette.Window).name(),"#181c1a")
        self.assertEqual(dialog.palette().color(QPalette.Window).name(),"#181c1a")
        self.assertEqual(window.history_search.palette().color(QPalette.PlaceholderText).name(),"#a0b0a5")
        self.assertEqual(dialog.custom_model_edit.palette().color(QPalette.PlaceholderText).name(),"#a0b0a5")
        self.assertEqual(dialog.styleSheet(),window.styleSheet())
        with patch("src.ui.main_window.is_dark",return_value=False), patch("src.ui.main_window.native_title_bar"):
            window._sync_system_theme()
        self.assertFalse(window._dark_theme)
        self.assertEqual(window.palette().color(QPalette.Window).name(),"#ffffff")

    def test_manual_choice_is_not_overridden_by_system_event(self):
        with patch("src.ui.main_window.is_dark",return_value=True):
            window = self.window()
        window.settings_manager.set_setting("ui","theme","dark")
        with patch("src.ui.main_window.is_dark",return_value=False) as resolve:
            window._sync_system_theme()
        resolve.assert_not_called()
        self.assertTrue(window._dark_theme)

    def test_dark_palette_covers_inputs_and_placeholder(self):
        dark = palette(True)
        self.assertLess(dark.color(QPalette.Base).lightness(),70)
        self.assertGreater(dark.color(QPalette.Text).lightness(),200)
        self.assertGreater(dark.color(QPalette.PlaceholderText).lightness(),100)


if __name__ == "__main__": unittest.main()
