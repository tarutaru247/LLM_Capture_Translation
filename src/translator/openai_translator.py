"""
OpenAI APIを使用した翻訳サービス
"""
import logging
from openai import OpenAI, APIStatusError, APIConnectionError, AuthenticationError # 変更
from ..utils.utils import handle_exception
from ..utils.settings_manager import SettingsManager
from .translator_service import TranslatorService

logger = logging.getLogger('ocr_translator')

class OpenAITranslator(TranslatorService):
    """OpenAI APIを使用した翻訳サービス"""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.api_key = self.settings_manager.get_api_key('openai')
        self.client = None # OpenAIクライアントを初期化
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        logger.info("OpenAITranslatorを初期化しました")
    
    def translate(self, text, source_lang=None, target_lang=None):
        """OpenAI APIを使用してテキストを翻訳する
        
        Args:
            text (str): 翻訳するテキスト
            source_lang (str, optional): 元の言語コード。Noneの場合は自動検出
            target_lang (str, optional): 翻訳先の言語コード。Noneの場合はデフォルト言語
            
        Returns:
            str: 翻訳されたテキスト
        """
        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""
        
        if not self.api_key:
            logger.error("OpenAI APIキーが設定されていません")
            return "エラー: OpenAI APIキーが設定されていません。設定画面でAPIキーを設定してください。"
        
        if not self.client:
            self.client = OpenAI(api_key=self.api_key) # APIキーが設定されたらクライアントを初期化
        
        try:
            # 翻訳先言語の取得
            if not target_lang:
                target_lang = self.settings_manager.get_target_language()
            
            # 言語名のマッピング
            language_names = {
                'ja': '日本語',
                'en': '英語',
                'zh': '中国語',
                'ko': '韓国語',
                'fr': 'フランス語',
                'de': 'ドイツ語'
            }
            
            target_language_name = language_names.get(target_lang, target_lang)
            
            # 翻訳プロンプトの作成
            prompt = f"以下のテキストを{target_language_name}に翻訳してください。翻訳のみを出力し、余計な説明は不要です。\n\n{text}"
            
            logger.info(f"OpenAI APIを使用して翻訳を実行中... (対象言語: {target_language_name})")
            
            # OpenAI APIを使用して翻訳 (新しいインターフェース)
            response = self.client.chat.completions.create(
                model=self.settings_manager.get_model() or "gpt-4o-mini", # 設定からモデル名を取得、またはデフォルト
                messages=[
                    {"role": "system", "content": "あなたは翻訳アシスタントです。入力されたテキストを指定された言語に翻訳してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 低い温度で一貫性のある翻訳を生成
                max_tokens=1024,
                timeout=self.settings_manager.get_timeout() # タイムアウト設定を追加
            )
            
            # 翻訳結果の取得
            translated_text = response.choices[0].message.content.strip()
            
            logger.info("翻訳が完了しました")
            return translated_text
            
        except AuthenticationError:
            logger.error("OpenAI APIキーの認証に失敗しました。")
            return "エラー: OpenAI APIキーが無効です。認証情報を確認してください。"
        except APIConnectionError as e:
            logger.error(f"OpenAI APIへの接続に失敗しました: {e}")
            return f"翻訳エラー: APIへの接続エラーが発生しました: {e}"
        except APIStatusError as e:
            logger.error(f"OpenAI APIからエラー応答: {e.status_code} - {e.response}")
            return f"翻訳エラー: APIエラーが発生しました: {e.status_code} - {e.response}"
        except Exception as e:
            error_msg = handle_exception(logger, e, "OpenAI APIによる翻訳")
            return f"翻訳エラー: {error_msg}"
    
    def is_available(self):
        """OpenAI APIが利用可能かどうかを確認する
        
        Returns:
            bool: 利用可能な場合はTrue、そうでない場合はFalse
        """
        return bool(self.api_key)

    def verify_api_key(self, api_key):
        """提供されたAPIキーがOpenAI APIで有効かどうかを検証する

        Args:
            api_key (str): 検証するAPIキー

        Returns:
            bool: 有効な場合はTrue、そうでない場合はFalse
            str: エラーメッセージ（有効な場合は空文字列）
        """
        if not api_key:
            return False, "APIキーが入力されていません。"
        
        try:
            # 検証用のクライアントを一時的に作成し、タイムアウトを設定
            client = OpenAI(api_key=api_key, timeout=5.0) # 5秒のタイムアウト
            # 認証をテストするために簡単なAPI呼び出しを試みる
            # 例: 利用可能なモデルのリストを取得
            list(client.models.list()) # 新しいインターフェース
            logger.info("OpenAI APIキーの検証に成功しました。")
            return True, ""
        except AuthenticationError:
            logger.error("OpenAI APIキーの認証に失敗しました。")
            return False, "APIキーが無効です。認証情報を確認してください。"
        except APIConnectionError as e:
            logger.error(f"OpenAI APIへの接続に失敗しました: {e}")
            return False, f"APIへの接続エラー: {e} (タイムアウトの可能性あり)"
        except APIStatusError as e:
            logger.error(f"OpenAI APIからエラー応答: {e.status_code} - {e.response}")
            return False, f"APIエラーが発生しました: {e.status_code} - {e.response}"
        except Exception as e:
            error_msg = f"OpenAI APIキーの検証中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            return False, error_msg
