# 配布前レビュー — 2026-11-10

これは確認した範囲と残課題の記録です。未知の脆弱性がないこと、すべての利用形態での法的適合性を保証するものではありません。

## GitHubの公開状態

- `tarutaru247/LLM_Capture_Translation` はPublic。旧 `screenshot_translation` URLは転送される。
- 確認したリモート先端: main `5094cc0`、fix/translation-flow `9ee71c8`、codex/local-plamo-translation `4c7517d`。
- ローカルに全先端が存在することを照合し、到達可能な67コミット・255種類のblobをパターン検査。
- Google / OpenAI系 / GitHubトークン・秘密鍵形式・認証情報の文字列リテラルを確認。実際のAPIキーは検出されなかった。
- リテラル検出72件はすべて `localization.py` の画面ラベル。同じラベルの過去版も数えている。
- 過去の83,903,790バイトのexeをGitオブジェクトから取り出し、実行せずPyInstallerアーカイブを確認。
  設定・履歴・ログと分かるファイル名は見つからなかった。Google API仕様JSON内の秘密鍵ヘッダー表記は文書中の例示。
- この検査は一般的な形式の文字列検査で、形式不明の秘密・暗号化/圧縮された任意のデータの不存在は証明しない。
  GitHubの到達不能オブジェクト、LFS、個別利用者の設定やBOOTH上の配布物は対象外。
- 公開リリースには `v0.0.1-alpha/LLM_Capture_Translation.exe` がある。`v0.2.0-beta/AI.exe` はdraft。

参照: https://github.com/tarutaru247/LLM_Capture_Translation

## 過去のバイナリで残るライセンス課題

旧exeにはPyQt5が入っているが、アーカイブで確認した表示ファイルにPyQt5のGPL全文はなかった。
公開ページのMIT表記だけで、このバイナリ全体の配布条件が満たされるとは判断できない。
GPLv3に従う対応ソース・ビルド手順・依存ライセンスの提供、または適切な商用ライセンスを確認する必要がある。
旧リリースの再整備、BOOTH配布物の確認、必要なら旧版の提供停止を行うまでは「公開状態に問題なし」としない。
新版のPySide6移行は、過去のバイナリの条件を遡って解決しない。
Git履歴中にも旧exeがある。履歴改変・強制pushや旧リリース削除は、この作業では実施しない。

公式条件: https://www.riverbankcomputing.com/software/pyqt/intro

## 新版の対策

- 標準はPLaMoとWindows.Media.Ocr。ローカル画像経路からGoogle OCRを除去。
- ソフトウェアとPLaMoそれぞれの未選択の同意チェック、契約内容のハッシュと日時のローカル保存。
- 同意記録の保存失敗・同意拒否ではモデル取得を開始しない。既存モデルもサイズとSHA-256を検証。
- クラウドは初期状態で無効。旧Gemini設定も自動で有効化しない。設定画面の確認は初期選択「いいえ」。
- UIだけでなくワーカーとAPIクライアントでも送信許可を確認。選択先の変更時は送信を止める。
- クラウド接続はHTTPS、カスタムローカル接続は数値ループバックへ正規化・限定。URL内の認証情報等を拒否。
- カスタムAPIはリダイレクト・環境変数のプロキシを使わない。別サービスへキーを転用しない。
- Google APIの接続先を固定し、環境変数のVertex AI設定・プロキシ・リダイレクトによる宛先変更を抑止。
- APIキーはDPAPI。失敗時の平文保存を廃止。DPAPIにUIを出させず失敗時に終了する。
- API例外の本文・応答をログへ記録しない。履歴はローカル保存で暗号化なしと説明。
- モデル取得は固定版・サイズ制限・SHA-256検証。既存ファイルを上書きしない。
- llama.cppは127.0.0.1・ランダムポート・一時ランダムキー、Web UI無効、RPCサーバーは起動しない。
- 新版はPySide6 / QtのLGPLv3を選択し、ライセンス・対応ソース案内・アプリソース・差し替え手順を配布に含める。

## Python依存の監査

配布・ビルド対象の39依存をPyPIのリリース別JSON APIの `vulnerabilities` で照合。
CLIのDNSが使えないため、ブラウザーで公式APIの表示内容を読み取り、版・日時・出典を記録した。
初期環境のrequests、anyio、certifi、cryptography、idna、pyasn1、setuptools、urllib3に有効な勧告を検出し更新。
Pillowは11.2.1から13.0.0、GUIはPyQt5 / Qt5からPySide6 / Qt6へ移行。
更新用wheelのSHA-256をPyPIの掲載値と照合してからインストールした。
更新後の39依存の照合では、当該APIに有効な勧告の登録はなかった。
結果は `dependency-audit-2026-11-10.json`。これはアプリへの到達可能性・未登録の問題を網羅する検査ではない。

監査API仕様: https://docs.pypi.org/api/json/

## ネイティブ部品の確認と制約

llama.cpp b12140は公式版の固定ハッシュを使用。2026年のGGUF整数オーバーフロー勧告の修正対象ビルド
b8146 / b7824より新しい。RPCを起動せず、信頼できないモデルを標準ダウンロード経路に入れない。
任意のGGUF・実行ファイルを高度な設定で指定する場合は、その提供元と安全性を利用者が確認する必要がある。

- https://github.com/ggml-org/llama.cpp/security/advisories/GHSA-3p4r-fq3f-q74v
- https://github.com/ggml-org/llama.cpp/security/advisories/GHSA-96jg-mvhq-q7q7

Qt 6.12.0には、Pythonパッケージの監査では検出されないネイティブの勧告がある。
CVE-2026-105924はQCborValueのCBOR→JSON変換、本アプリのデータ経路はPythonのjsonとプレーンテキストで、
QCborValueを使用しない。CVE-2026-114366はQWebSocketの再接続、本アプリはQWebSocketを使用しない。
HTTPにはPythonのHTTPクライアントを使い、QtNetwork / QtWebSockets / QtHttpServer等はビルドから除外する。
現コードで該当機能への経路は確認されないが、ライブラリ自体を修正済みと表現してはならない。
Qtの対応修正版が利用可能になったら更新・再検証する。今後該当機能を追加する際にも再評価する。

- https://www.qt.io/blog/security-advisory-cve-2026-105924
- https://www.qt.io/blog/security-issue-cve-2026-114366
- https://wiki.qt.io/List_of_known_vulnerabilities_in_Qt_products

## 公開前に残る外部確認

- PLaMoの商用登録・追加契約が必要かは実際の配布・事業形態次第。エージェントは契約締結や登録を代行しない。
- 旧exe / BOOTH配布のライセンス再整備。
- GitHub改名: `tarutaru_translate` が指定名。CLIは接続失敗、操作可能なブラウザーは未ログインのため未完了。
- 各クラウドの実アカウントによる疎通・課金条件は未確認。モックによるプロトコル検証と混同しない。
- 新規PCの中国語OCR言語機能、異なるCPU / GPU / ドライバー環境の受け入れ確認。
- Python本体・Windows・ドライバー・Vulkan等の修正状況は、Python依存39件の結果には含まれない。
- コード署名は未実施。署名・SmartScreen実績のないexeはWindowsで警告される場合がある。

これらを残した状態では、生成物を「監査済みで問題のない正式配布版」として公開しない。

## 実行・パッケージ検証の追記

自動テスト47件で、外部送信の拒否・同意拒否・保存失敗・キー暗号化失敗・接続先制限・API形式・履歴・テーマを確認。
Windows標準OCRは用意した画像を外部通信なしで読み取った。exe版ワーカーでも同じ処理を確認。
このPCには日本語OCRがあり、英語・中国語を明示指定する場合の言語機能追加は利用者側で必要。

Qt移行後の初期ビルドで、PATHに含まれた別ツールのICU DLLをPyInstallerが誤って収集し、Qtが起動しなかった。
ビルド時のPATHを制限し、ネイティブ部品の収集元を検査する対策を追加。
WindowsのICU APIを別ツールのDLLで上書きしない。QtNetwork / QtSvgの不要なDLLと未使用プラグインも除去する。
実際の収集結果を確認し、宣言依存以外に取り込まれたPyYAML / rsaも固定版と監査に加えた。

この作業環境からPLaMoのHTTP接続を試すとWindowsエラー10013（ソケットアクセス拒否）が発生する。
既存のモデルは存在するが、本環境でのモデル→アプリの通信を含むCPU/GPU翻訳の完了は未確認。
アプリ側は権限拒否を検知して待ち続けず、接続権限の確認を案内する。実機での受け入れ確認を正式公開前の条件とする。

Microsoft C/C++ランタイムDLLは配布物から除外し、公式から利用者が導入する前提条件とした。
これにより、配布者のVisual Studio再配布権限が未確認のままDLLを同梱することを避ける。
https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist

Python本体も旧3.12.6から、セキュリティ修正を含む3.12.16へ更新した。
Astral python-build-standalone 20261026の公式配布を固定SHA-256で照合し、ワークスペース内の専用環境で使用。
PC全体のPythonや既存の開発用仮想環境は置き換えない。古い3.12のまま配布ビルドしないようビルド時にも版を確認する。
https://www.python.org/downloads/release/python-31213/
https://github.com/astral-sh/python-build-standalone/releases/tag/20261026
