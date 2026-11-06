# スクショAI翻訳 — Built with PLaMo

Windows上のスクショや、他のアプリで選択した文字を翻訳します。
**翻訳はPLaMo 3 Translate 0.8Bをローカル実行**します。起動時にモデルを読み込み、終了まで使い続けます。

- スクショ: **Ctrl+Shift+X** → 範囲選択 → Google AIで文字読み取り → ローカル翻訳
- 選択文字: 他のアプリで文字を選択 → **Ctrl+Shift+C** → キーを離す → ローカル翻訳
- 選択文字の翻訳はAPIキー不要・外部送信なし。スクショは画像をGoogle AIに送信します。
- GGUF（Q4_K_M）とBF16を設定で切り替えて、同じ文章の結果を比較できます。
- 原文と訳文を表示し、コピーできます。日本語・英語・中国語・韓国語に対応します。

## 起動（ソース版）

Windows 10/11、Python 3.12を推奨します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_local_runtime.py
.\.venv\Scripts\python.exe main.py
```

`setup_local_runtime.py` は公式llama.cppのWindows x64 CPU版 b12140を取得し、SHA256を検証します。
モデルはダウンロードしません。モデルは公式配布元の利用条件を確認して別途取得してください。

- [GGUFモデル](https://huggingface.co/pfnet/plamo-3-translate-0.8b-GGUF)
- [BF16モデル](https://huggingface.co/pfnet/plamo-3-translate-0.8b)

初期値は以下です。別のPCでは設定画面で実際の保存先を指定してください。

| 設定 | 初期値 |
|---|---|
| 形式 | GGUF |
| GGUF | `D:\LocalLLM\models\plamo-3-translate-0.8b-Q4_K_M.gguf` |
| BF16 | `D:\LocalLLM\models\plamo-3-translate-0.8b-bf16` |

起動後に「PLaMoを読み込み中」と表示されます。準備完了後に翻訳できます。
読み込みに失敗したら設定画面でパスを修正できます。モデル設定を変更・保存すると自動で読み直します。
GGUFの「llama-server.exe」を空欄にすると、取得した付属ランタイムを使います。
GPU対応のllama.cppを別途用意した場合は、その実行ファイルを指定できます。

## BF16で比較する

BF16には追加のPythonライブラリが必要です。モデルフォルダーには重みだけでなく、
設定、トークナイザー、公式の `modeling_plamo.py` と `tokenization_plamo.py` を揃えてください。
これらのローカルPythonコードを実行するため、信頼できる公式配布元のフォルダーだけを指定してください。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-bf16.txt
```

NVIDIA GPUで使う場合は、GPUとドライバーに対応したCUDA版PyTorchを先に
[PyTorch公式手順](https://pytorch.org/get-started/locally/)でインストールしてください。
CUDAが利用できるときはGPU、利用できないときはCPUで実行します。
モデル読み込み後はオフラインで動作し、実行中に別モデルを自動ダウンロードしません。

設定の「モデル形式」でBF16を選んで保存すると切り替わります。
exe版では「BF16用Python」に追加ライブラリを導入した `python.exe` の絶対パスも指定してください。
BF16のPython環境やモデルはexeに同梱しません。
両形式で同じ原文・翻訳先を指定して品質を比較してください。
CPU版GGUFとGPU版BF16の速度差は、量子化形式だけの差ではありません。

## スクショの文字読み取り

設定の「スクショの文字読み取り」でGoogle APIキーを登録します。
OCRモデルの自動／カスタム設定は文字読み取りにだけ使われ、翻訳は常にPLaMoです。
文字選択で使う場合はGoogle APIキーを設定する必要はありません。

選択文字はコピー操作で取得し、その後元のクリップボード内容を復元します。
コピー禁止のアプリや管理者権限の異なるアプリでは取得できないことがあります。
選択なし・コピー失敗時には古いクリップボードを翻訳せず終了します。
ホットキーが登録できない場合は、他のアプリとの重複を確認してください。
現在の入力上限は原文・訳文を合わせて8192トークン、訳文は最大2048トークンです。
上限に達した場合は短く分けて再実行してください。

## ライセンス・GitHub公開

このリポジトリの独自コードは[MIT License](LICENSE)です。
**PLaMo本体はMITではありません**。[PLaMo Community License](docs/licenses/PLaMo-ja.txt)の条件が適用されます。
「Built with PLaMo」をUI・ドキュメントに表示し、契約のコピーを同梱しています。
訳文を公開する場合はPLaMoの出力であることを明示してください。
商用利用は、収入・売上が10億円以下でもPFNへの事前登録が必要で、超える場合は別契約が必要です。

**既存依存のPyQt5にもGPLv3または商用ライセンスの条件があります。**
独自コードのMIT表記は、PyQtを含むexe全体の配布条件を代替しません。
モデル、BF16実行環境、既存の公開バイナリも含めた詳細は
[第三者ライセンスと公開時の条件](docs/THIRD_PARTY_NOTICES.md)を確認してください。
モデルの重み・公式モデルコード・トークナイザーはGitに登録せず、ビルドでも含めません。

## ビルドと確認

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build_exe.py
```

ビルドには取得済みllama.cppランタイムが必要です。出力は `dist/ocr_translator.exe`。
BF16用の外部Pythonとモデルは別途用意してください。
配布時は第三者ライセンス、対応するソース、依存するQt/PyQt等の条件も満たしてください。

読み込みエラーの詳細は、設定フォルダーの `plamo-runtime.log` に記録されます。
