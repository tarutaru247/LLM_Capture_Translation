import abc
from PyQt5.QtGui import QPixmap

class OCRService(abc.ABC):
    """OCRサービスのための抽象基底クラス"""

    @abc.abstractmethod
    def extract_text(self, pixmap: QPixmap, lang: str = None) -> str:
        """
        画像からテキストを抽出する抽象メソッド。

        Args:
            pixmap (QPixmap): 処理する画像。
            lang (str, optional): OCR言語。指定がなければ実装側でデフォルト言語を使用。

        Returns:
            str: 抽出されたテキスト。
        """
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """
        OCRサービスが利用可能かどうかを返す抽象メソッド。
        (例: APIキーが設定されているか、Tesseractがインストールされているかなど)

        Returns:
            bool: サービスが利用可能であればTrue、そうでなければFalse。
        """
        pass
