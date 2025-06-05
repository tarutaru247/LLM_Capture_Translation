# 範囲選択型OCR・AI翻訳ツール - README

## プロジェクト概要

このプロジェクトは、Windows デスクトップ上で選択した範囲の画像をキャプチャし、OCRで文字を抽出して、OpenAI APIまたはGemini APIを使用して翻訳するデスクトップアプリケーションです。

## ディレクトリ構成

```
ocr_translator_project/
├── main.py                     # アプリケーションのエントリーポイント
├── build_exe.py                # PyInstallerによるビルドスクリプト
├── src/                        # ソースコードディレクトリ
│   ├── __init__.py
│   ├── ui/                     # UIモジュール
│   │   ├── __init__.py
│   │   ├── main_window.py      # メインウィンドウ
│   │   ├── screen_capture.py   # 画面キャプチャ機能
│   │   └── settings_dialog.py  # 設定ダイアログ
│   ├── ocr/                    # OCRモジュール
│   │   ├── __init__.py
│   │   └── ocr_processor.py    # OCR処理
│   ├── translator/             # 翻訳モジュール
│   │   ├── __init__.py
│   │   ├── translator_service.py  # 翻訳サービス抽象基底クラス
│   │   ├── openai_translator.py   # OpenAI API翻訳
│   │   ├── gemini_translator.py   # Gemini API翻訳
│   │   └── translation_manager.py # 翻訳マネージャー
│   └── utils/                  # ユーティリティモジュール
│       ├── __init__.py
│       ├── utils.py            # 共通ユーティリティ関数
│       └── settings_manager.py # 設定管理
├── docs/                       # ドキュメント
│   ├── user_guide.md           # ユーザーガイド
│   └── technical_specification.md # 技術仕様書
└── dist/                       # ビルド済み実行ファイル（ビルド後に作成）
    └── OCR翻訳ツール.exe       # 実行ファイル
```

## 必要条件

- Python 3.8以上
- PyQt5
- pytesseract
- Pillow
- openai
- google-generativeai
- Tesseract OCR（外部依存）

## インストール方法

### 開発環境

1. リポジトリをクローンまたはダウンロードします
2. 必要なパッケージをインストールします：
   ```
   pip install -r requirements.txt
   ```
3. Tesseract OCRをインストールします：
   - Windows: https://github.com/UB-Mannheim/tesse ract/wiki
   - 日本語と英語の言語パックを選択してください

### エンドユーザー向け

1. 提供された実行ファイル（.exe）をダウンロードします
2. Tesseract OCRをインストールします
3. 実行ファイルをダブルクリックして起動します

## 使用方法

詳細な使用方法については、`user_guide.md`を参照してください。

## ビルド方法

実行ファイル（.exe）を作成するには：

```
python build_exe.py
```

ビルドされた実行ファイルは`dist`ディレクトリに作成されます。

## 技術仕様

詳細な技術仕様については、`technical_specification.md`を参照してください。

## 検証

アプリケーションの検証方法と検証項目については、`windows_validation_checklist.md`を参照してください。

## ライセンス

このプロジェクトは独自ライセンスの下で提供されています。詳細については、プロジェクト管理者にお問い合わせください。

## 注意事項

- APIキーは個人情報として扱い、他人と共有しないでください
- APIの使用には料金が発生する場合があります。各APIプロバイダの料金体系を確認してください
