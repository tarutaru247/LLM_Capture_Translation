# Third-party notices / 公開・配布時の条件

確認日: 2026-11-10

## PLaMo — Built with PLaMo

このアプリは Preferred Networks の PLaMo 3 Translate 0.8B / 2B をローカルで利用します。
モデル、モデルコード、トークナイザーには **PLaMo Community License** が適用されます。
アプリ自身のMITライセンスをモデルに適用することはできません。
モデルの重み・コード・トークナイザーはGitHubやexeに同梱せず、利用者が別途取得します。

- 個人の私的利用・学術利用等の非商用利用: 事前登録不要。
- 商業目的: 組織内利用、製品・サービスの開発・提供も含まれます。
  本人または関係会社の直近年度の収入・売上が10億円以下の場合も、PFNへの事前登録が必要です。
  超える場合は別途商業ライセンス契約が必要です。無料配布やGitHub公開だけを根拠に非商用とは判断できません。
- モデル等（出力も含む）を第三者へ提供する場合は、契約のコピー提供・受領者の遵守、
  「Built with PLaMo」表示等、契約第4条の条件に従ってください。
- 翻訳結果を公開する場合はPLaMoの出力であることを明示してください（第5条）。
  アプリ内に表示しているだけで、コピーした訳文に表示が自動付与されるわけではありません。
- PLaMoを利用して別のAIモデルを作成・出力で学習する場合には追加条件があります。

公式の条件とモデルに付属する契約の両方を確認してください。
モデルに付属する契約のコピーを `docs/licenses/PLaMo-ja.txt` / `PLaMo-en.txt` に収録しています。
公式サイトの条文はモデル添付版と差異がある場合があるため、配布時に再確認してください。

- 日本語公式契約: https://plamo.preferredai.jp/info/plamo-community-license-ja
- 英語公式契約: https://plamo.preferredai.jp/info/plamo-community-license-en
- 商用登録: https://forms.gle/mTL8tBLrMYXKNZD56
- モデル: https://huggingface.co/pfnet/plamo-3-translate-0.8b
- GGUF: https://huggingface.co/pfnet/plamo-3-translate-0.8b-GGUF

## llama.cpp

MIT License。公式ランタイムは別途 `setup_local_runtime.py` で取得します。
配布する場合は、著作権・ライセンス表示を保持してください。
`docs/licenses/llama.cpp.txt` に取得したバージョンのライセンスを収録しています。
ランタイムに付属する `LICENSE-LLVM-OpenMP` 等の表示も配布物に保持します。
組み込みのcpp-httplib、nlohmann/json、miniaudio、stb、ハッシュ関数等の表示は
`docs/licenses/llama-vendor/` に収録します。miniaudio / stb等ではパブリックドメインの選択肢があります。
公式ソース: https://github.com/ggml-org/llama.cpp/tree/b12140

## GUI: PySide6 / Shiboken6 / Qt 6.12.0

新版はPyQt5からPySide6へ移行しました。LGPLv3の選択肢を用います。
GNU LGPLv3 / GPLv3の全文・関連するQtのライセンスを `docs/licenses/Qt-*` に収録しています。
Qtの第三者部品の著作権・ライセンス表示は `Qt-third-party-attributions.json` と
`Qt-third-party/` を参照してください。FreeTypeはFreeType Licenseの条件を選択します。
Qtを使用していることを明示し、対応するソースの入手先・再ビルド・差し替え手順を
`DISTRIBUTION.md` に記載しています。DLLを別ファイルとするonedir形式で配布します。
ライブラリ改変・差し替え、およびそのデバッグのためのリバースエンジニアリングを禁止しません。
独自アプリの対応ソースとビルド手順は配布物の `application-source.zip` にも収録します。

- https://doc.qt.io/qtforpython-6/
- https://doc.qt.io/qt-6/licensing.html
- https://github.com/qtproject/pyside-pyside-setup/tree/v6.12.0
- https://github.com/qt/qtbase/tree/v6.12.0

過去のPyQt5版exeはGPLv3またはRiverbank商用ライセンスの条件確認が別途必要です。
新版の変更だけで、過去の配布物の条件が遡って解消するわけではありません。

## その他のライブラリ

Google GenAI (Apache-2.0)、Pillow (HPND等)、pynput (LGPL-3.0)、
過去のBF16比較用のPyTorch (BSD系)、Transformers / Accelerate (Apache-2.0)、Numba (BSD系) 等は
それぞれの配布物のライセンスが適用されます。再配布する依存物と推移的依存物の表示も保持してください。
現在のアプリはBF16を使わず、これらBF16用ライブラリを配布物に含めません。

## Windows OCR / 仮アイコン

画像の文字認識はWindows標準のWindows.Media.Ocrを利用します。
WindowsのOSファイル・OCR言語モデルをアプリに再配布しません。必要な機能はWindowsの言語設定から利用者が追加します。
Windows機能にはMicrosoftの利用条件が適用されます。
仮アイコンは本プロジェクト用に幾何学図形から作成したオリジナルで、独自コードと同じMITで提供します。
外部のロゴ・フォントファイル・画像生成サービスの素材は使っていません。

## 配布物の個別インベントリ

Python依存の正確な版と配布元は `dependencies.json`、各wheelが提供するライセンス・著作権表示は
`_internal/docs/dependency-licenses` に保存します。Python本体のライセンスも同梱します。
推論ランタイムの追加表示は `_internal/runtime/llama` / `llama-vulkan` の LICENSE ファイルを参照してください。
クラウドサービスのAPIキーやモデルの重みは配布物に含めません。
CPythonとそのネイティブ依存のライセンスは `Python-3.12.16.txt` / `Python-native/` に収録します。
Python本体の配布元と対応ソースは `DISTRIBUTION.md` を参照してください。

## Microsoft C/C++ Runtime（別途導入）

必要なMicrosoft C/C++ランタイムDLLは配布物に含めません。
Microsoft公式から利用者自身が導入します。Microsoftの利用条件が適用されます。
https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist
https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/
