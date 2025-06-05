# 範囲選択型OCR・AI翻訳ツール - 技術仕様書

## システム概要

本アプリケーションは、Windows デスクトップ上で選択した範囲の画像をキャプチャし、OCRで文字を抽出して、OpenAI APIまたはGemini APIを使用して翻訳するデスクトップアプリケーションです。

## 技術スタック

- **開発言語**: Python 3.8+
- **UIフレームワーク**: PyQt5
- **OCRエンジン**: Tesseract OCR (pytesseract)
- **翻訳API**: 
  - OpenAI API (GPT-3.5/GPT-4)
  - Google Gemini API
- **画像処理**: Pillow (PIL)
- **パッケージング**: PyInstaller

## システムアーキテクチャ

アプリケーションは以下の主要モジュールで構成されています：

1. **メインアプリケーション (main.py)**
   - アプリケーションのエントリーポイント
   - 各モジュールの初期化と連携

2. **UI管理モジュール (ui/main_window.py)**
   - メインウィンドウとUI要素の管理
   - ユーザー操作のイベントハンドリング
   - 設定画面の管理

3. **スクリーンキャプチャモジュール (ui/screen_capture.py)**
   - 画面範囲選択機能
   - スクリーンショット取得機能

4. **OCR処理モジュール (ocr/ocr_processor.py)**
   - Tesseract OCRとの連携
   - 画像からのテキスト抽出処理
   - 言語検出と前処理

5. **翻訳モジュール (translator/)**
   - 翻訳サービスの抽象化 (translator_service.py)
   - OpenAI APIとの連携 (openai_translator.py)
   - Gemini APIとの連携 (gemini_translator.py)
   - 翻訳マネージャー (translation_manager.py)

6. **設定管理モジュール (utils/settings_manager.py)**
   - APIキーの保存と読み込み
   - ユーザー設定の管理
   - 設定の永続化

7. **ユーティリティモジュール (utils/utils.py)**
   - 共通機能や補助関数
   - エラーハンドリング
   - ロギング

## データフロー

1. **キャプチャフロー**
   - ユーザーがキャプチャトリガーを起動
   - 範囲選択UI表示
   - ユーザーが範囲を選択
   - 選択範囲の画像をキャプチャ
   - キャプチャ画像をOCRモジュールに渡す

2. **OCRフロー**
   - キャプチャ画像を受け取る
   - 必要に応じて前処理（リサイズ、コントラスト調整など）
   - Tesseract OCRでテキスト抽出
   - 抽出テキストを翻訳モジュールに渡す

3. **翻訳フロー**
   - 抽出テキストを受け取る
   - 設定から選択されたAPI（OpenAIまたはGemini）を確認
   - 対応するAPIを使用してテキスト翻訳
   - 翻訳結果をUI管理モジュールに渡す

4. **結果表示フロー**
   - 原文と翻訳結果を受け取る
   - 結果表示UIを更新
   - コピー機能の提供

## 設定管理

ユーザー設定は以下の場所に保存されます：
- Windows: `%USERPROFILE%\.ocr_translator\config\settings.json`

設定ファイルには以下の情報が含まれます：
- APIキー（OpenAI、Gemini）
- 選択されたAPI
- 翻訳先言語
- OCR言語設定
- UI設定

## 依存関係

- **PyQt5**: UIフレームワーク
- **pytesseract**: OCR処理
- **Pillow**: 画像処理
- **openai**: OpenAI API連携
- **google-generativeai**: Gemini API連携

## ビルドと配布

アプリケーションは PyInstaller を使用して単一の実行ファイル (.exe) にパッケージングされます。
ビルドプロセスは `build_exe.py` スクリプトで自動化されています。

## 制限事項と既知の問題

1. Tesseract OCRは別途インストールが必要です
2. 高DPI環境では一部のUI要素が適切にスケーリングされない場合があります
3. 複雑な背景を持つ画像ではOCR精度が低下する可能性があります
4. APIキーは暗号化されずに保存されます（セキュリティ上の考慮が必要）

## 将来の拡張可能性

1. 他の翻訳APIのサポート追加
2. OCR精度向上のための画像前処理機能の強化
3. ホットキーによるキャプチャ起動
4. APIキーの暗号化保存
5. 翻訳履歴の保存と管理
6. クラウド同期機能

## テスト

アプリケーションは以下の環境でテストされています：
- Windows 10 (21H2)
- Windows 11 (22H2)

テスト項目の詳細は `windows_validation_checklist.md` を参照してください。
