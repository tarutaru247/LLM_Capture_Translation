"""Assemble complete, unedited model outputs and separately authored reviews."""
import json
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    read = lambda name: json.loads((directory / name).read_text(encoding="utf-8"))
    samples = read("samples.json")
    gguf, bf16 = read("gguf_results.json"), read("bf16_results.json")
    reviews = read("meaning_reviews.json")
    outputs = {"gguf": {r["id"]: r for r in gguf["results"]}, "bf16": {r["id"]: r for r in bf16["results"]}}
    ids = {sample["id"] for sample in samples}
    assert ids == set(outputs["gguf"]) == set(outputs["bf16"]) == set(reviews)
    lines = [
        "# PLaMo 3 Translate 0.8B：GGUF Q4_K_M / BF16 翻訳比較",
        "", "実行日：2026-11-06（日本時間）", "",
        "英語8件・中国語8件（簡体字7件、繁体字1件）を、それぞれ日本語へ翻訳しました。",
        "原文は比較用にエージェントが作成した架空の文章です。外部記事の転載や公式ベンチマークではありません。",
        "日常案内だけでなく、数字、否定、条件、人物関係、皮肉、長文の手続き説明を含めています。", "",
        "**各モデルの訳文は実出力の全文です。誤字・不自然な表現・誤訳も修正していません。**",
        "意味の評価は原文と出力を読み比べたエージェントの判断です。自然さ・読みやすさの点数や優劣は付けず、ユーザーの判断用に訳文を掲載しています。", "",
        "## 先に分かったこと", "",
        "- ZH06では、**両方に同じ明確な意味反転**があります。『うまくいかないとは断言できない』が『うまくいくと断言できない』になりました。",
        "- EN04では両方が、兄か弟か不明なbrotherを『兄』と断定しています。EN06とZH08にも両方に共通する細部の意味のずれがあります。",
        "- EN08では、BF16の末尾に『恒久的な変更と考えるべきでない』から『そう考える必要はない』への弱まりがあります。",
        "- 数字・割引・条件を含む他の多くの例では、両方が主要情報を保持しています。**この16例では、BF16が一貫して意味に忠実という結果にはなりませんでした。**",
        "- 小規模な一回ずつの比較であり、一般的な優劣や誤訳率を確定するものではありません。共通の誤訳を量子化だけのせいにはできません。", "",
        "## 比較条件", "",
        "| 項目 | GGUF | BF16 |", "|---|---|---|",
        "| モデル | PLaMo 3 Translate 0.8B Q4_K_M | PLaMo 3 Translate 0.8B BF16 |",
        f"| 実行系 | {gguf['runtime']} | Transformers {bf16['transformers']} / PyTorch {bf16['torch']} |",
        f"| デバイス | {gguf['device']} | {bf16['device']} |",
        "| 翻訳先 | 日本語（ja） | 日本語（ja） |",
        "| 元言語指定 | 指定なし・モデルが自動判定 | 指定なし・モデルが自動判定 |",
        "| プロンプト | アプリと同じPFML3形式 | アプリと同じPFML3形式 |",
        "| 生成 | temperature=0（greedy） | do_sample=False（greedy） |",
        "| 入出力の上限 | 8192トークン、出力最大2048 | 8192トークン、出力最大2048 |",
        "| 停止トークン | `<\u007cplamo:tag\u007c>` / `<\u007cplamo:bos\u007c>` | 同左 |",
        "| 文章間の履歴 | なし | なし |", "",
        "各文章は独立したリクエストです。OCRの誤認識を混ぜないため、画像ではなく原文テキストを直接渡しています。外部の翻訳APIは利用していません。",
        "形式だけでなく実行系も異なる比較なので、差のすべてを量子化単独の影響とは断定できません。CPU/GPUや初回準備の差があるため、速度の優劣も判定しません。実測時間は生データJSONに残しています。", "",
        "モデル重みのSHA256：", "",
        f"- GGUF：`{gguf['model_sha256']}`",
        f"- BF16：`{bf16['model_sha256']}`", "",
        "## 意味の評価一覧", "",
        "『保持』はこの文章の主要情報・条件・否定に明確な意味の誤りを見つけなかったという判断です。完璧な訳文という保証ではありません。",
        "『要注意』は情報の補完、意味の強まり・弱まり、関係のずれなどです。『意味反転あり』は文の判断内容が逆になる明確な誤りです。", "",
        "| ID | 原文言語 | 内容 | GGUF | BF16 |", "|---|---|---|---|---|",
    ]
    for sample in samples:
        review = reviews[sample["id"]]
        lines.append(f"| [{sample['id']}](#{sample['id'].lower()}) | {sample['language']} | {sample['topic']} | {review['gguf_rating']} | {review['bf16_rating']} |")
    for sample in samples:
        case_id = sample["id"]
        review = reviews[case_id]
        lines += ["", f'<a id="{case_id.lower()}"></a>', f"## {case_id}：{sample['topic']}", "",
                  f"原文言語：{sample['language']}", "", "### 原文（全文）", "", sample["source"], "",
                  "### GGUF Q4_K_M の訳文（全文・無修正）", "", outputs["gguf"][case_id]["output"], "",
                  "### BF16 の訳文（全文・無修正）", "", outputs["bf16"][case_id]["output"], "",
                  "### 意味の確認", "", f"原文の確認ポイント：{sample['checkpoints']}。", "",
                  f"**GGUF：{review['gguf_rating']}** — {review['gguf']}", "",
                  f"**BF16：{review['bf16_rating']}** — {review['bf16']}", "",
                  "### 自然さ・読みやすさのメモ（ユーザー用）", "",
                  "- GGUF：", "- BF16：", "- 好み・気になる箇所："]
    lines += ["", "## 生データと再現手順", "",
              "- [原文と確認ポイント](samples.json)",
              "- [GGUFの全出力・実測値](gguf_results.json)",
              "- [BF16の全出力・実測値](bf16_results.json)",
              "- [意味の評価データ](meaning_reviews.json)", "",
              "プロジェクトルートで、モデルとランタイム・BF16依存ライブラリを用意して実行します。モデルのパスは実行スクリプト内に明記しています。", "",
              "```powershell", ".\\.venv\\Scripts\\python.exe docs/comparison/run_comparison.py --backend gguf",
              ".\\.venv\\Scripts\\python.exe docs/comparison/run_comparison.py --backend bf16",
              ".\\.venv\\Scripts\\python.exe docs/comparison/build_report.py", "```", "",
              "再実行で出力が変わった場合、既存の意味評価が引き続き妥当か確認してください。評価データは実行のたびに自動採点されるものではありません。", "",
              "## 出力の帰属とライセンス", "",
              "**Built with PLaMo** — 本書の『GGUFの訳文』『BF16の訳文』は、いずれもPreferred NetworksのPLaMo 3 Translate 0.8Bが生成した出力です。",
              "原文・比較手順・意味の評価文はエージェントが作成しています。",
              "PLaMoの出力の提供・公開・利用には[PLaMo Community Licenseのコピー](../licenses/PLaMo-ja.txt)および[第三者ライセンスの案内](../THIRD_PARTY_NOTICES.md)を確認してください。", ""]
    report = directory / "plamo_gguf_bf16_comparison_ja.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    rendered = report.read_text(encoding="utf-8")
    for sample in samples:
        assert sample["source"] in rendered
        for backend in outputs:
            assert outputs[backend][sample["id"]]["output"] in rendered
    print(f"Saved {report}; verified 16 complete sources and 32 complete translations.")


if __name__ == "__main__":
    main()
