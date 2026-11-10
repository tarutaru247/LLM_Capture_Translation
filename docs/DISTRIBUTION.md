# たる翻訳 — 配布・再ビルドの手順

このファイルと同じフォルダーにある全ファイルが配布単位です。exeだけを取り出さないでください。
モデルの重み・APIキー・利用者の設定・履歴は同梱しません。PLaMoは初回の明示的な同意後に取得します。

## ライセンスとソース

独自ソースコードとオリジナルの仮アイコン: MIT（LICENSE）。
PySide6 / Shiboken6 / Qt: LGPLv3の選択肢を利用します。ライセンス全文は `_internal/docs/licenses`、
Python依存の表示は `_internal/docs/dependency-licenses` に収録します。
LGPL対象ライブラリの改変・差し替え、改変のデバッグのためのリバースエンジニアリングを禁止しません。
認証・署名によってライブラリ差し替えを妨げる仕組みは設けていません。
PLaMoは別プロセスのllama.cppで動作し、Qtにモデルをリンクしません。

独自アプリの対応ソース・ビルドスクリプトは `application-source.zip`、依存の固定版は
`requirements-lock.txt` / `dependencies.json` にあります。第三者ライブラリは改変していません。
以下の公式配布元から、同じバージョンの対応ソースを無償で入手できます。
ダウンロード配布時には、この案内とリンクをバイナリのダウンロードのすぐ近くにも掲載してください。
リンク切れ・対応ソースの不一致があれば、配布者が対応ソースを同じ配布先に用意してから公開してください。

- Qt 6.12.0（公式ソース配布）: https://download.qt.io/archive/qt/6.12/6.12.0/
- Qtのビルド手順: https://doc.qt.io/qt-6/windows-building.html
- PySide6 / Shiboken6 6.12.0: https://github.com/qtproject/pyside-pyside-setup/tree/v6.12.0
- PySide6のビルド手順: https://doc.qt.io/qtforpython-6/building_from_source/index.html
- pynput 1.8.1（LGPLv3）: https://pypi.org/project/pynput/1.8.1/#files
- その他の依存の版・提供元: `dependencies.json` を参照。対応版のPyPIページにソース配布があります。
- llama.cpp b12140: https://github.com/ggml-org/llama.cpp/tree/b12140

Qt DLLは `_internal/PySide6` 内にあります。同じABI・ビルド条件のDLLに差し替えるか、
上記ソースと本アプリのソースから環境全体を再ビルドできます。pynput等のPythonモジュールは
対応ソースの改変版を使って再ビルドできます。アプリに改変版を認識させない制約はありません。

## 再ビルド（Windows x64 / Python 3.12.16以降（3.12系））

1. `application-source.zip` を展開します。
2. 新しい仮想環境を作り、`pip install -r docs/requirements-release-lock.txt` を実行します。
3. `python setup_local_runtime.py` で公式CPU / Vulkan推論ランタイムを取得します。
4. `python -m unittest discover -s tests` で検証します。
5. `python docs/release_inventory.py` で依存の版・ライセンス表示を確認します。
6. `python docs/audit_dependencies.py` で公開前の最新の既知脆弱性情報を照合します。
7. `python build_exe.py --distpath runtime/dist-distribution --workpath runtime/build-distribution` を実行します。

ビルドでは、確認済みの依存版と監査記録が一致しないと停止します。
依存を更新したら、監査記録も実際の照合結果に更新してください。
`SHA256SUMS.txt` は改変検出用です。コード署名や公開者の身元保証の代わりではありません。

## 公開前の確認

- PLaMoの商業目的の利用に該当する場合は、配布者自身がPFNへの登録・必要な契約を済ませること。
- 受領者にも同梱のPLaMo契約を提供し、「Built with PLaMo」を表示すること。
- 同梱物のライセンス・対応ソース・差し替え手順をダウンロードの近くで提供すること。
- Windowsの新規ユーザー環境で初回同意・モデル取得・OCR言語機能・CPU / GPU実行を確認すること。
- API実通信は各提供元の有効なキーで確認すること（プロトコルのテストだけではアカウントでの動作を保証しません）。
- ソースだけを公開する場合も、APIキー・設定・履歴・翻訳対象の私的な文章を含めないこと。

セキュリティ監査の範囲・残課題は `docs/security/distribution-review-2026-11-10.md` を参照してください。
過去のPyQt5版exeのライセンス対応は、新版の移行だけで遡って解消されるものではありません。

## Microsoftランタイムの前提条件

Microsoft Visual C++ v14 x64 Runtime 14.44.35211以降が必要です。Microsoft DLLは配布物に同梱しません。
未導入のPCでは、Microsoft公式の最新版インストーラーから利用者自身がインストールします。
第三者のDLL配布サイトから取得しないでください。
https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist

## この候補のPython本体

セキュリティ修正を含むCPython 3.12.16を使用します（Astral python-build-standalone 20261026）。
https://github.com/astral-sh/python-build-standalone/releases/tag/20261026
Windows x86_64 install_only_strippedアーカイブのSHA-256:
`1f2ab53880fc67ea323398c6388e05af28addc99a8e389209f08a51fdff4b149`
CPython対応ソース: https://github.com/python/cpython/tree/v3.12.16
ビルド定義: https://github.com/astral-sh/python-build-standalone/tree/20261026
