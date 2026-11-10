"""Build the complete 0.8B / 2B report from actual CLI outputs."""
import json
from pathlib import Path


def main():
    folder=Path(__file__).resolve().parent
    read=lambda path:json.loads(path.read_text(encoding="utf-8"))
    small=read(folder/"lightweight_cli_results.json")
    large=read(folder/"quality_cli_results.json")
    samples=read(folder.parent/"samples.json")
    reviews=read(folder/"meaning_reviews.json")
    cases={"small":{r["id"]:r for r in small["results"]},"large":{r["id"]:r for r in large["results"]}}
    expected={s["id"] for s in samples}
    assert expected==set(cases["small"])==set(cases["large"])==set(reviews)
    assert small["conditions"]==large["conditions"]
    assert small["gpu"]==large["gpu"]
    def speed(data,generation):
        row=next(r for r in data["speed_benchmark"] if (r["n_gen"]>0)==generation)
        assert row["backends"]=="Vulkan" and len(row["samples_ts"])==3
        return row
    sp,sg=speed(small,False),speed(small,True)
    lp,lg=speed(large,False),speed(large,True)
    ratio=sg["avg_ts"]/lg["avg_ts"]
    lines=["# PLaMo 3 Translate：0.8B / 2B GGUF 比較", "", "実行日：2026-11-08（日本時間）", "",
        "## 結果", "",
        "**今回の文章では、2Bに意味の正確さの改善が見られました。速度と軽さは0.8Bが有利です。**", "",
        "- 中国語ZH06の『うまくいかないとは断言できない』を、0.8Bは『うまくいくと断言できない』と反転。2Bは正しく訳しました。ただし末尾の催促する側・される側の曖昧さは残っています。",
        "- 中国語ZH08の『便利さのために情報管理を犠牲にしてはいけない』も、2Bでは『犠牲』の関係が正しく表現されています。",
        "- 英語EN06の『ひとまず好意的に受け止める』は、2Bの方が暫定的な判断を表現しています。",
        "- ただしEN04のbrotherを『兄』と断定する補完は両方に残り、EN05では2Bが『保存できる』を『保存されたまま』に変える注意点もありました。**2Bがすべての文章で上位という結果ではありません。**",
        "- 評価はエージェントが原文と出力を読み比べたものです。自然さの点数は付けていません。16文章で一般的な誤訳率を推定するものではありません。", "",
        "## 速度・メモリ", "",
        f"環境：{small['gpu']}。両方ともllama.cpp b12140、Vulkan、Q4_K_M、GPU全層オフロード。", "",
        "| 項目 | 0.8B | 2B |", "|---|---:|---:|",
        f"| ファイル容量（10進GB） | {small['file_bytes']/1e9:.2f} | {large['file_bytes']/1e9:.2f} |",
        f"| 入力処理・128トークン（tokens/s） | {sp['avg_ts']:,.0f} ± {sp['stddev_ts']:,.0f} | {lp['avg_ts']:,.0f} ± {lp['stddev_ts']:,.0f} |",
        f"| 生成・128トークン（tokens/s） | {sg['avg_ts']:,.1f} ± {sg['stddev_ts']:,.1f} | {lg['avg_ts']:,.1f} ± {lg['stddev_ts']:,.1f} |",
        f"| 観測したGPU全体のVRAM増加（GiB・参考） | 約{small['vram_peak_delta_mib']/1024:.2f} | 約{large['vram_peak_delta_mib']/1024:.2f} |", "",
        f"生成スループットは0.8Bが2Bの**約{ratio:.2f}倍**でした。同じ出力トークン数なら、2Bは生成部分に約{ratio:.2f}倍の時間がかかる計算です。アプリの総応答時間が必ずこの比率になるという意味ではありません。", "",
        "速度は公式llama-benchによるウォームアップあり・各3回の平均±標準偏差です。入力処理pp128と生成tg128はそれぞれ別のテストで、実際の16文章の翻訳速度ではありません。",
        "翻訳文の取得にはモデルを毎回読み込むCLIを使っているため、その起動から終了までの秒数は生JSONに残すだけとし、アプリの常駐時レイテンシの比較には使っていません。CPUでの速度は今回は測っていません。", "",
        "VRAMはnvidia-smiでGPU全体を約0.5秒間隔で観測し、各モデルの実行前との差を取った概算です。他アプリや表示処理の変動を含み、モデル単体の正確な使用量や瞬間的な最大値ではありません。長大入力や別GPUでも同じ値になる保証はありません。", "",
        f"- 0.8B：実行前 {small['vram_baseline_mib']} MiB → 観測ピーク {small['vram_peak_observed_mib']} MiB。",
        f"- 2B：実行前 {large['vram_baseline_mib']} MiB → 観測ピーク {large['vram_peak_observed_mib']} MiB。", "",
        "## 比較条件と注意点", "",
        "- 以前の比較で使った自作の英語8件・中国語8件（簡体字7件、繁体字1件）を再利用。外部記事や公式ベンチマークからの転載ではありません。",
        "- 日本語への翻訳。原文言語は自動判定、PFML3プロンプト、temperature=0、seed=42、コンテキスト8192、生成上限2048トークン。文章間の履歴はありません。",
        "- OCRの誤認識を混ぜず、原文テキストを直接入力。両方とも公式GGUFのSHA256を照合済み。",
        "- ローカルHTTP接続がWinError 10013で拒否されたため、ネットワークを使わない公式llama-completionで取得。アプリのHTTP経由の完全な応答時間テストではありません。",
        "- 訳文は生成した全文です。CLIが付ける終了表示 `[end of text]` を取り除き、改行コードを統一した以外は修正していません。生の標準出力もJSONに保存しています。",
        "- 意味の評価は今回の出力だけを対象にしています。CPUや異なる実行系では丸め誤差によって出力が変わる可能性があります。", "",
        "## 文章別の評価", "",
        "| ID | 内容 | 比較結果 |", "|---|---|---|",
    ]
    for sample in samples:
        lines.append(f"| [{sample['id']}](#{sample['id'].lower()}) | {sample['topic']} | {reviews[sample['id']]['judgment']} |")
    for sample in samples:
        case=sample["id"]
        lines += ["",f'<a id="{case.lower()}"></a>',f"## {case}：{sample['topic']}","",
                  f"原文言語：{sample['language']}","","### 原文（全文）","",sample["source"],"",
                  "### 0.8B Q4_K_M（全文）","",cases["small"][case]["output"],"",
                  "### 2B Q4_K_M（全文）","",cases["large"][case]["output"],"",
                  "### 意味の評価","",reviews[case]["note"],"",
                  "### 自然さのメモ（ユーザー用）","","- 0.8B：","- 2B："]
    lines += ["","## 再現と生データ","",
              "- [0.8Bの生データ](lightweight_cli_results.json)",
              "- [2Bの生データ](quality_cli_results.json)",
              "- [原文](../samples.json)",
              "- [意味の評価データ](meaning_reviews.json)","",
              "プロジェクトルートで実行します。モデルのパスはスクリプトに明記しています。", "",
              "```powershell",
              ".\\.venv\\Scripts\\python.exe docs/comparison/size_0_8b_vs_2b/run_cli_benchmark.py --profile lightweight",
              ".\\.venv\\Scripts\\python.exe docs/comparison/size_0_8b_vs_2b/run_cli_benchmark.py --profile quality",
              ".\\.venv\\Scripts\\python.exe docs/comparison/size_0_8b_vs_2b/build_report.py",
              "```","",
              "意味の評価は自動採点ではありません。再実行後に出力が変わった場合は評価を見直してください。", "",
              "## 帰属・ライセンス","",
              "**Built with PLaMo**。両モデルの訳文はPreferred NetworksのPLaMo 3 Translateによる生成物です。原文・比較手順・評価文はエージェントが作成しました。",
              "[PLaMo Community Licenseのコピー](../../licenses/PLaMo-ja.txt)と[第三者ライセンスの案内](../../THIRD_PARTY_NOTICES.md)を確認してください。", ""]
    output=folder/"comparison_report_ja.md"
    report="\n".join(lines)
    output.write_text(report,encoding="utf-8")
    for sample in samples:
        assert sample["source"] in report
        for data in cases.values(): assert data[sample["id"]]["output"] in report
    print(f"Saved {output}; verified all 16 originals and 32 full translations.")


if __name__=="__main__": main()
