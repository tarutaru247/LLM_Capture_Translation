"""
OCR処理モジュール
"""
import os
import sys
import logging
import tempfile
from PIL import Image
import pytesseract
from PyQt5.QtGui import QPixmap, QImage

from ..utils.utils import get_temp_dir, handle_exception
from ..utils.settings_manager import SettingsManager

logger = logging.getLogger('ocr_translator')

class OCRProcessor:
    """OCR処理を行うクラス"""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self._check_tesseract_installation()
        logger.info("OCRProcessorを初期化しました")
    
    def _check_tesseract_installation(self):
        """Tesseractのインストール状況を確認する"""
        try:
            # Windowsの場合、Tesseractのパスを設定
            if sys.platform.startswith('win'):
                # デフォルトのインストールパス
                default_paths = [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                ]
                
                # 環境変数からパスを取得
                tesseract_path = os.environ.get('TESSERACT_PATH')
                if tesseract_path and os.path.exists(tesseract_path):
                    pytesseract.pytesseract.tesseract_cmd = tesseract_path
                else:
                    # デフォルトパスを試す
                    for path in default_paths:
                        if os.path.exists(path):
                            pytesseract.pytesseract.tesseract_cmd = path
                            break
            
            # Tesseractのバージョンを確認
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OCRバージョン: {version}")
            
            # 利用可能な言語を確認
            languages = pytesseract.get_languages()
            logger.info(f"利用可能なOCR言語: {languages}")
            
            # 日本語と英語のサポートを確認
            required_langs = ['jpn', 'eng']
            missing_langs = [lang for lang in required_langs if lang not in languages]
            
            if missing_langs:
                logger.warning(f"必要な言語データがインストールされていません: {missing_langs}")
                return False
            
            return True
        except Exception as e:
            error_msg = handle_exception(logger, e, "Tesseractのインストール確認")
            logger.error(error_msg)
            return False
    
    def process_image(self, pixmap, lang=None):
        """画像からテキストを抽出する
        
        Args:
            pixmap (QPixmap): 処理する画像
            lang (str, optional): OCR言語。指定がなければ設定から取得
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            if not pixmap or pixmap.isNull():
                logger.error("有効な画像がありません")
                return ""
            
            # 言語設定の取得
            if not lang:
                ocr_languages = self.settings_manager.get_ocr_languages()
                lang = '+'.join(ocr_languages)  # 例: 'jpn+eng'
            
            logger.info(f"OCR言語: {lang}")
            
            # QPixmapをPIL Imageに変換
            image = self._qpixmap_to_pil_image(pixmap)
            
            # 一時ファイルに保存（Tesseractの処理のため）
            temp_dir = get_temp_dir()
            temp_file = os.path.join(temp_dir, 'temp_ocr_image.png')
            image.save(temp_file)
            
            # OCR処理の実行
            logger.info("OCR処理を実行中...")
            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config='--psm 6'  # ページセグメンテーションモード: 単一のテキストブロックとして処理
            )
            
            # 一時ファイルの削除
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            logger.info(f"OCR処理が完了しました（{len(text)}文字）")
            return text
        except Exception as e:
            error_msg = handle_exception(logger, e, "OCR処理")
            return f"OCR処理エラー: {error_msg}"
    
    def _qpixmap_to_pil_image(self, pixmap):
        """QPixmapをPIL Imageに変換する"""
        # QPixmapをQImageに変換
        image = pixmap.toImage()
        
        # QImageをPIL Imageに変換
        size = image.size()
        buffer = image.bits().asstring(image.byteCount())
        img = Image.frombuffer(
            'RGBA', 
            (size.width(), size.height()), 
            buffer, 
            'raw', 
            'BGRA', 
            0, 
            1
        )
        
        # RGBAからRGBに変換（Tesseractの処理のため）
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        return img
    
    def detect_language(self, text):
        """テキストの言語を検出する（簡易版）
        
        Args:
            text (str): 検出対象のテキスト
            
        Returns:
            str: 検出された言語コード ('ja', 'en', 'unknown')
        """
        if not text:
            return 'unknown'
        
        # 日本語の文字コード範囲
        japanese_chars = len([c for c in text if ord(c) > 0x3000 and ord(c) < 0x30FF])
        
        # 英語（ASCII）の文字コード範囲
        english_chars = len([c for c in text if ord(c) < 0x007F])
        
        # 文字数の割合で判断
        total_chars = len(text)
        if total_chars == 0:
            return 'unknown'
        
        japanese_ratio = japanese_chars / total_chars
        english_ratio = english_chars / total_chars
        
        if japanese_ratio > 0.3:
            return 'ja'
        elif english_ratio > 0.5:
            return 'en'
        else:
            return 'unknown'
    
    def preprocess_image(self, pixmap):
        """OCR精度向上のための画像前処理
        
        Args:
            pixmap (QPixmap): 処理する画像
            
        Returns:
            QPixmap: 前処理された画像
        """
        # TODO: 画像の前処理（リサイズ、コントラスト調整など）を実装
        # 現在はそのまま返す
        return pixmap
