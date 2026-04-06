# スクショAI翻訳

![スクショAI翻訳](https://user-images.githubusercontent.com/your-account/your-repo/your-image.png)  <!-- TODO: Add a screenshot of the application -->

「スクショAI翻訳」は、PC画面上の任意の範囲をキャプチャし、写っている文字をAIが認識して翻訳するWindows向けアプリケーションです。
Google AI を活用し、高精度なOCRと翻訳を実現します。

## 主な機能

- **範囲選択キャプチャ**: マウスでドラッグするだけで、必要な部分だけを簡単にキャプチャできます。
- **AIによるOCR・翻訳**: キャプチャした画像から直接翻訳結果を生成します。API呼び出しが1回で済むため、高速かつ効率的です。
- **Google AI 統一**: Google API に一本化し、通常は `gemini-3.1-flash-lite-preview`、混雑時などは `gemma-4-26b-a4b-it` へ自動で切り替えます。
- **多言語対応**: 日本語、英語、中国語、韓国語の UI と翻訳に対応しています。
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
    初回起動時に Google API キーの設定が必要です。

### 初期設定

1. メニューバーから `設定 / Setting` を開きます。
2. `API設定 / API Setting` で `Google APIキー` に [Google AI Studio](https://makersuite.google.com/app/apikey) の API キーを入力します。
3. 必要なら `APIキーを検証` で有効性を確認します。
4. 通常は `LLM設定` を `自動` のまま使います。
5. 特定モデルを使いたい場合だけ `カスタム` を選び、Google のモデル名を直接入力します。
6. 必要に応じて `APIタイムアウト (秒)` を調整して保存します。

### 基本的な使い方

1. メイン画面の `画面範囲をキャプチャ` を押します。
2. 翻訳したい範囲をドラッグで選択します。
3. マウスを離すと、自動で翻訳が始まります。
4. 処理中はローディング表示が出ます。
5. 完了すると翻訳結果が表示され、`コピー` ボタンでクリップボードへ送れます。

### トラブルシューティング

- **翻訳されない**
  - API キーが正しいか、設定画面の検証機能で確認してください。
  - インターネット接続と Google API の利用状況を確認してください。
  - `カスタム` を使っている場合は、モデル名が正しいか確認してください。
- **文字化けや誤訳がある**
  - 文字がぼやけている画像では精度が落ちます。なるべく文字が鮮明な範囲を選択してください。
  - `カスタム` で別の Google モデルを試すと改善する場合があります。

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
