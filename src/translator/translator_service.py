"""
翻訳サービスの抽象基底クラス
"""
import abc

class TranslatorService(abc.ABC):
    """翻訳サービスの抽象基底クラス"""
    
    @abc.abstractmethod
    def translate(self, text, source_lang=None, target_lang=None):
        """テキストを翻訳する
        
        Args:
            text (str): 翻訳するテキスト
            source_lang (str, optional): 元の言語コード。Noneの場合は自動検出
            target_lang (str, optional): 翻訳先の言語コード。Noneの場合はデフォルト言語
            
        Returns:
            str: 翻訳されたテキスト
        """
        pass
    
    @abc.abstractmethod
    def is_available(self):
        """翻訳サービスが利用可能かどうかを確認する
        
        Returns:
            bool: 利用可能な場合はTrue、そうでない場合はFalse
        """
        pass
