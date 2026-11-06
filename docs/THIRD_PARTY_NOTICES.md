# Third-party notices / 公開・配布時の条件

確認日: 2026-11-06

## PLaMo — Built with PLaMo

このアプリは Preferred Networks の PLaMo 3 Translate 0.8B をローカルで利用します。
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
公式ソース: https://github.com/ggml-org/llama.cpp/tree/b12140

## 既存のGUI依存: PyQt5 / Qt

PyQt5はGPLv3またはRiverbank商用ライセンスです。LGPL版のPyQt5はありません。
このリポジトリの独自コードのMIT表記だけでは、PyQt5を含むexe全体を
MITの条件だけで配布できることにはなりません。
GPL版を使う配布物はGPLv3に従い、対応するソース・ビルド手順・ライセンス表示を提供する必要があります。
GPL非互換の条件で配布する場合は適切な商用ライセンス等が必要です。
モデルは別プロセスで実行し、PLaMoのコードや重みをGUIバイナリにリンク・内包しません。

Qt本体には別のライセンスが適用され、GPL版PyQtのwheelに含まれるQtは通常LGPLです。
Qtの再リンク・差し替え等の条件も満たす配布方式を選んでください。
既存のonefile版を含め、公開バイナリの配布条件が解消済みという意味ではありません。
本変更ではプロジェクト全体のライセンス変更や商用契約を代行していません。

- https://www.riverbankcomputing.com/software/pyqt/
- https://www.riverbankcomputing.com/commercial/license-faq

## その他のライブラリ

Google GenAI (Apache-2.0)、Pillow (HPND等)、pynput (LGPL-3.0)、
過去のBF16比較用のPyTorch (BSD系)、Transformers / Accelerate (Apache-2.0)、Numba (BSD系) 等は
それぞれの配布物のライセンスが適用されます。再配布する依存物と推移的依存物の表示も保持してください。
現在のアプリはBF16を使わず、これらBF16用ライブラリを配布物に含めません。
