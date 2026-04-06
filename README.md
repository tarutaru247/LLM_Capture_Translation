# スクショAI翻訳

![スクショAI翻訳](https://user-images.githubusercontent.com/your-account/your-repo/your-image.png)  <!-- TODO: Add a screenshot of the application -->

「スクショAI翻訳」は、PC画面上の任意の範囲をキャプチャし、写っている文字をAIが認識して翻訳するWindows向けアプリケーションです。
Google AI を活用し、高精度なOCRと翻訳を実現します。

## 主な機能

- **範囲選択キャプチャ**: マウスでドラッグするだけで、必要な部分だけを簡単にキャプチャできます。
- **AIによるOCR・翻訳**:
    - **一括翻訳モード (デフォルト)**: キャプチャした画像から直接翻訳結果を生成します。API呼び出しが1回で済むため、高速かつ効率的です。
    - **文字起こしモード**: 画像から抽出した原文を確認してから、翻訳結果を見ることができます。原文のコピーも可能です。
- **Google AI 統一**: Google API に一本化し、通常は `gemini-3.1-flash-lite-preview`、混雑時などは `gemma-4-26b-a4b-it` へ自動で切り替えます。
- **多言語対応**: 日本語、英語、中国語、韓国語、フランス語、ドイツ語への翻訳に対応しています。
- **カスタマイズ可能な設定**: 通常は自動選択のまま使えます。必要な場合だけ、任意の Google モデル名を直接指定できます。

## 動作環境

- Windows 10 / 11
- インターネット接続

## インストールと使い方

### ユーザー向け

1.  **実行ファイルのダウンロード**:
    [リリースページ](https://github.com/tarutaru247/LLM_Capture_Translation/releases)もしくは[Booth](https://tarutaru247.booth.pm/items/7640843)から最新の `.exe` ファイルをダウンロードします。
2.  **起動**:
    ダウンロードした `.exe` ファイルをダブルクリックしてアプリケーションを起動します。
3.  **初期設定**:
    初回起動時にAPIキーの設定が必要です。詳しい手順は以下の使用方法ガイドをご覧ください。

**詳細な使用方法については、こちらのガイドを参照してください。**
▶ [**使用方法ガイド**](./docs/範囲選択型OCR・AI翻訳ツール%20-%20使用方法ガイド.md)

### 開発者向け

#### 必要条件

- Python 3.8以上
- 必要なパッケージ:
  ```
  pip install -r requirements.txt
  ```

#### 実行方法

```bash
python main.py
```

#### ビルド方法

実行ファイル（`.exe`）を作成するには、`build_exe.py` を実行します。

```bash
python build_exe.py
```

ビルドされた実行ファイルは `dist` ディレクトリに作成されます。

## ディレクトリ構成

```
.
├── main.py                     # アプリケーションのエントリーポイント
├── build_exe.py                # PyInstallerによるビルドスクリプト
├── requirements.txt            # 依存パッケージリスト
├── README.md                   # このファイル
├── docs/                       # ドキュメント
│   └── 範囲選択型OCR・AI翻訳ツール - 使用方法ガイド.md
└── src/                        # ソースコード
    ├── ocr/
    │   ├── ocr_service.py
    │   └── vision_ocr_service.py
    ├── translator/
    │   ├── combined_vision_translator.py
    │   ├── gemini_translator.py
    │   ├── translation_manager.py
    │   └── translator_service.py
    ├── ui/
    │   ├── main_window.py
    │   ├── screen_capture.py
    │   └── settings_dialog.py
    └── utils/
        ├── settings_manager.py
        └── utils.py
```

## 注意事項

- APIキーは他人に知られないよう、厳重に管理してください。
- APIの利用には、各サービスプロバイダが定める料金が発生する場合があります。ご利用の際は料金体系を必ずご確認ください。
- 本アプリケーションの使用によって生じたいかなる損害についても、開発者は責任を負いません。

- 設定画面では Google API キーと LLM モードのみを扱います。`カスタム` を選ぶと、Google AI に渡すモデル名を直接入力できます。

## ライセンス

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
