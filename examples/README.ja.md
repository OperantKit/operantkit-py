# 例: 古典実験

:gb: [English](README.md)

各例は、古典実験の行動パターンを仮想被験体で再現する。使うのは OperantKit の公開パイプラインだけである: contingency-dsl の文字列、それを変換した contingency-py のスケジュール、session-runner、experiment-io の `drive()`、session-analyzer で解析する OKL v1 ログ。例ごとに固有なのは被験体だけで、被験体はスケジュールが提示した強化子を受け取るだけで、スケジュールそのものについては何も知らない。

## 実行

```bash
pip install operantkit
python examples/<name>/run.py
```

各 `run.py` は引数なしで動き、OKL ログと図を同じフォルダに書く。セッション時間は模擬なので数秒で終わり、seed を固定すると OKL ログがバイト単位で一致する。被験体は experiment-io にある。インストール済みの experiment-io に無い場合は <https://github.com/OperantKit/experiment-io> から入れる。`tests/test_examples.py` が全部の例を走らせてパターンを検査する。

## 例の一覧

| 例 | 実験 | 一次ソース | DSL | コマンド | 図 |
|---|---|---|---|---|---|
| [fi_scallop](fi_scallop/README.ja.md) | 定間隔スキャロップ: 強化のたびに休止し、その後反応が加速する | Ferster & Skinner (1957) | `FI 60-s` | `python examples/fi_scallop/run.py` | 累積記録 |
| [concurrent_vi_matching](concurrent_vi_matching/README.ja.md) | 並立 VI VI のマッチング: 相対反応頻度が相対強化頻度に一致する | Herrnstein (1961) | `Conc(VI 180-s, VI 180-s, COD=1.5-s)` ほか 3 対 | `python examples/concurrent_vi_matching/run.py` | 相対強化頻度に対する相対反応頻度（対角線付き） |
| [drl_irt](drl_irt/README.ja.md) | 低反応率分化強化: IRT が延び、反応率が下がる | Ferster & Skinner (1957) | `DRL 10-s` | `python examples/drl_irt/run.py` | IRT ヒストグラム（最初と最後の 600 秒）、IRT で色分けした累積記録 |

## 出典

- Ferster, C. B., & Skinner, B. F. (1957). *Schedules of reinforcement*. Appleton-Century-Crofts. https://doi.org/10.1037/10627-000
- Herrnstein, R. J. (1961). Relative and absolute strength of response as a function of frequency of reinforcement. *Journal of the Experimental Analysis of Behavior*, *4*(3), 267–272. https://doi.org/10.1901/jeab.1961.4-267
