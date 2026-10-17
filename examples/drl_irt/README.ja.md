# DRL の反応間時間

:gb: [English](README.md)

Ferster と Skinner（1957）が記述した低反応率分化強化（DRL）の効果の向きを再現する。前の反応から十分な時間が経っていなければ強化しないと、反応間時間（IRT）が延び、全体の反応率が下がる。

## 実行

```bash
pip install operantkit
python examples/drl_irt/run.py
```

スクリプトは `DRL 10-s` をセッション時間 1800 秒（強化子 0.5 秒）走らせ、`run.py` と同じフォルダに次を書く。

- `drl_irt.okl` — OKL v1 のイベントログ
- `drl_irt_histogram.png` — 最初の 600 秒と最後の 600 秒の IRT ヒストグラム（10 秒の基準に縦線）
- `drl_irt_cumulative.png` — IRT で色分けした累積記録（`session-analyzer diff-plot drl_irt.okl --threshold 10 --output drl_irt_cumulative.png` でも同じ図になる）

`python examples/drl_irt/run.py --subject poisson` は、記憶を持たない 1 Hz の対照の被験体で走らせる。

被験体は experiment-io の `SpacedRespondingSubject`。インストール済みの experiment-io にこれが無い場合は <https://github.com/OperantKit/experiment-io> から experiment-io を入れる。

## 何が動いているか

DSL の文字列を contingency-dsl が解析し、contingency-py の `DRL` スケジュールに変換し、session-runner が走らせる。contingency-py の `DRL` は、前の反応から 10 秒以上経った反応を強化する（セッション最初の反応も強化する）。experiment-io の `drive()` が仮想被験体の反応をセッションに渡し、全イベントを session-recorder 経由で OKL ログに書く。このパイプラインに例専用の部分は無く、例に固有なのは被験体だけである。

`SpacedRespondingSubject` は、各 IRT を平均 `mu`・変動係数 0.3 の正規分布から引く（正になるまで引き直す）。初期値は `mu = 1 秒`。強化されなかった反応の後は、`mu` をその反応の IRT の 2 倍へ寄せ（`mu += 0.1 * (2 * irt - mu)`）、強化された反応の後は `mu` を 2% 縮める（`mu *= 0.98`）。被験体はスケジュールについて何も知らず、スケジュールが提示した強化子を受け取るだけである。

## 結果（seed 1953）

![DRL 10-s の最初と最後の 600 秒の IRT ヒストグラム](drl_irt_histogram.png)

![DRL 10-s の IRT で色分けした累積記録](drl_irt_cumulative.png)

| 被験体 | 反応数 | 強化数 | 10 秒以上の IRT の割合（最初の 600 秒） | 同（最後の 600 秒） | 反応率（最初の 600 秒） | 反応率（最後の 600 秒） |
|---|---|---|---|---|---|---|
| `SpacedRespondingSubject` | 186 | 98 | 0.34 | 0.71 | 0.133 /秒 | 0.085 /秒 |
| ポアソン対照（1 Hz） | 1796 | 2 | 0.002 | 0.000 | 1.028 /秒 | 0.973 /秒 |

各 IRT は、それを終わらせた反応の時刻の区間に数える。seed 1950〜1959 では、最後の 600 秒の 10 秒以上の割合は 0.58〜0.72 で、いずれも最初の 600 秒より大きく、反応率はいずれも下がった。`tests/test_examples.py` は、最後の 600 秒の割合が 0.5 以上かつ最初の 600 秒より大きいこと、反応率が下がること、対照の割合が 0.05 未満であること、seed を固定すると OKL ログがバイト単位で一致することを検査する。

被験体の更新は `mu` を強化されなかった IRT の 2 倍へ寄せる。この係数を 1.2 にすると、強化されないのは基準より短い IRT だけなので `mu` は 10 秒の手前で止まり、最後の 600 秒で基準に届く IRT は 3 分の 1 未満になる（seed 1950〜1959 で 0.17〜0.29）。

## 出典

Ferster と Skinner は drl を、前の反応から設定時間が経った反応だけを強化する随伴性として定義し、VI 1 分に drl 6 秒を加えると全体の反応率が毎秒約 1.1 から約 0.35 に下がったと報告している。下の 2 本はこの随伴性での反応の間隔と IRT 分布を調べた研究で、この例では文脈として書誌を挙げるだけで、数値は引用していない。

- Ferster, C. B., & Skinner, B. F. (1957). *Schedules of reinforcement*. Appleton-Century-Crofts. https://doi.org/10.1037/10627-000
- Wilson, M. P., & Keller, F. S. (1953). On the selective reinforcement of spaced responses. *Journal of Comparative and Physiological Psychology*, *46*(3), 190–193. https://doi.org/10.1037/h0057705
- Kelleher, R. T., Fry, W., & Cook, L. (1959). Inter-response time distribution as a function of differential reinforcement of temporally spaced responses. *Journal of the Experimental Analysis of Behavior*, *2*(2), 91–106. https://doi.org/10.1901/jeab.1959.2-91
