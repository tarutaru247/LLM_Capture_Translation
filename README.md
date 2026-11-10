# たる翻訳

Windows向けの、画面のスクリーンショット・選択文字・クリップボードを翻訳するアプリです。
明るい緑をアクセントにした履歴付きの画面と、システム設定に合わせるダークモードを備えます。

**標準はローカル翻訳です。画像の文字認識も含め、翻訳内容を外部へ送りません。**
初回のモデル取得にはインターネット接続が必要です。クラウド翻訳は明示的に有効にした場合だけ使えます。

Built with PLaMo

## 初回の準備

事前に [Microsoft Visual C++ v14 x64 Runtime](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist) 14.44.35211以降が必要です。未導入の場合はMicrosoft公式から導入してください。

1. 配布フォルダーを丸ごと展開し、`tarutaru_translate.exe` を起動します。
2. ソフトウェアの利用条件とPLaMoのライセンス全文を読み、それぞれ同意します。
3. モデルを選び、公式Hugging Faceから取得します。既存ファイルも検証して使えます。
4. 起動時にモデルを読み込みます。通常はCPU / GPUを自動で選択します。

| モデル | 形式 | ダウンロードサイズ |
|---|---|---|
| 軽量 | PLaMo 3 Translate 0.8B GGUF Q4_K_M | 約573 MB |
| 品質優先 | PLaMo 3 Translate 2B GGUF Q4_K_M | 約1.81 GB |

サイズはモデルファイルのみです。実行時には別途メインメモリ・GPUメモリが必要です。
PLaMoの商業目的の利用にはPFNへの事前登録等が必要です。業務での利用も含まれます。
詳細は [第三者ライセンス](docs/THIRD_PARTY_NOTICES.md) と同梱の契約全文を確認してください。

## 使い方

- `Ctrl+Shift+X`：画面の範囲を選択して翻訳。
- `Ctrl+Shift+C`：他のアプリで選択中の文字を翻訳。
- 「貼り付けて翻訳」：クリップボードの文章を翻訳。
- 左側に翻訳履歴、中央に訳文、その下に原文を表示します。
- 画面上部に、現在の翻訳先が「ローカル」か「クラウド」かを常時表示します。
- 設定で履歴保存の無効化・削除、ショートカット、外観、モデルを変更できます。

スクリーンショットのローカルOCRにはWindows標準のOCRを使用します。
設定の「画像のOCR言語」で英語・中国語などを選択してください。言語機能が不足している場合は、
Windowsの「言語と地域」で該当言語のOCR機能を追加します。失敗しても自動でクラウドへ送信しません。
Windowsの優先言語は画像の言語を自動判定する機能ではありません。

## オプションのクラウド翻訳

設定の「クラウド・OCR」で外部送信への同意を行い、有効にしてから翻訳方式でクラウドを選びます。
APIキーとモデル名は利用者自身で設定してください。APIの利用料金やデータの取り扱いは接続先の条件に従います。

| 接続先 | 方式 | 画像の扱い |
|---|---|---|
| Google Gemini | Google GenAI SDK | 画像をそのままGoogleへ送信 |
| OpenAI | Responses API | PC内でOCRし、原文のみ送信 |
| Anthropic Claude | Messages API | PC内でOCRし、原文のみ送信 |
| DeepSeek / xAI / Groq / Mistral / OpenRouter | Chat Completions互換API | PC内でOCRし、原文のみ送信 |
| カスタムAPI | HTTPSのChat Completions互換API | PC内でOCRし、原文のみ送信 |

上記は実装した接続方式です。モデルごとの利用可否・認証・料金は提供元の最新情報を確認してください。
全サービスへの実通信を検証済みという意味ではありません。失敗時に別サービスへ自動転送しません。
Geminiの自動モードは同じGoogle API内でモデルを切り替えることがあります。
OpenRouter等はモデル提供者へ中継するサービスです。送信先全体の条件を確認してください。

## 高度なローカル設定

設定の「翻訳方式」→「高度な設定」で、PLaMoの代わりにOllama・LM Studio・llama.cppなどの
ローカルOpenAI互換APIを使用できます。例：`http://127.0.0.1:1234/v1`。
ループバックアドレス以外は指定できません。別サーバーのAPIキーはローカル接続へ渡しません。
接続先サーバー自体がクラウドへ中継しない構成かは、ご自身で確認してください。
PLaMo以外のモデルは自動で取得しません。各モデルのライセンスも別途確認してください。

## 保存データ

互換性のため、従来と同じ `%USERPROFILE%\.ocr_translator` に設定・同意記録・履歴を保存します。
APIキーはWindows DPAPIで暗号化し、暗号化に失敗した場合は保存を中止します。
翻訳履歴は暗号化されません。共有PCでは保存設定に注意してください。
処理中の画像・文章は一時ファイルになる場合があります。通常終了時に削除します。

## 開発・配布

Windows x64 / Python 3.12で検証します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docs/requirements-release-lock.txt
.\.venv\Scripts\python.exe setup_local_runtime.py
.\.venv\Scripts\python.exe main.py
```

再ビルド・ライセンス表示・対応ソースの提供方法は [配布手順](docs/DISTRIBUTION.md) を参照してください。
[配布前監査](docs/security/distribution-review-2026-11-10.md) に確認済みの範囲と残課題を記載します。

独自ソースと仮アイコンは [MIT License](LICENSE) です。
PySide6 / Qt / pynput等とモデルには別のライセンスが適用されます。
モデルの重み・APIキー・利用者の設定・履歴はソースリポジトリと配布物に含めません。

現在のリポジトリ： https://github.com/tarutaru247/LLM_Capture_Translation
リポジトリ名は `tarutaru_translate` へ変更予定です（改名完了までは上記URLを使用します）。
