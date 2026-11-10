# たる翻訳 — 配布候補

このフォルダーは、正式公開前の確認用です。

実装・自動テスト・exeのローカルOCR・クラウド無効時の送信拒否を確認しています。
Python 3.12.16と、確認した固定版の依存ライブラリを使用しています。
モデルの重み・APIキー・利用者の設定・履歴は含みません。

## 起動前に必要なもの

Microsoft Visual C++ v14 x64 Runtime 14.44.35211以降。
未導入の場合はMicrosoft公式から導入してください。Microsoft DLLはこの配布物に含めません。
https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist

## この作業環境で確認できなかったこと

- PLaMoとアプリ間の通信を含むCPU / GPU翻訳の完了。作業環境がソケット接続を拒否するため、通常のデスクトップ環境で確認が必要です。
- 各クラウドサービスへの実アカウント・APIキーでの通信。
- 中国語等のWindows OCR言語機能を追加した新規PCや、別のGPU / ドライバー環境での動作。

## 公開前に確認すること

- 配布者の利用形態に応じたPLaMoの事前登録・商用契約の要否。
- 過去のPyQt5版exeのライセンス文書・対応ソースの提供方法。新版への移行だけでは遡って解消しません。
- 第三者ライセンス・対応ソース案内をダウンロードの近くで提供すること。
- Windowsでの受け入れ確認。コード署名は未実施です。

詳細は `DISTRIBUTION.md` と、`application-source.zip` 内の
`docs/security/distribution-review-2026-11-10.md` を参照してください。

リポジトリ名の `tarutaru_translate` への変更は、ユーザーの指示により別の機会に行います。
