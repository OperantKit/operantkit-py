# FI スキャロップ

:gb: [English](README.md)

Ferster と Skinner（1957）が記述した定間隔（FI）スケジュールの反応パターンを再現する。強化のたびに反応が休止し、その後は次の強化まで反応率が加速する。累積記録ではこれが「スキャロップ」の形になる。

## 実行

```bash
pip install operantkit
python examples/fi_scallop/run.py
```

スクリプトは `FI 60-s` を強化 30 回（強化子 0.5 秒）まで走らせ、`run.py` と同じフォルダに次を書く。

- `fi_scallop.okl` — OKL v1 のイベントログ
- `fi_scallop.png` — 累積記録（`session-analyzer plot fi_scallop.okl --output fi_scallop.png` でも同じ図になる）

`python examples/fi_scallop/run.py --subject poisson` は、記憶を持たない対照の被験体で走らせる。

被験体は experiment-io の `ScallopSubject`。インストール済みの experiment-io にこれが無い場合は <https://github.com/OperantKit/experiment-io> から experiment-io を入れる。

## 何が動いているか

DSL の文字列を contingency-dsl が解析し、contingency-py の `FI` スケジュールに変換し、session-runner が走らせる。experiment-io の `drive()` が仮想被験体の反応をセッションに渡し、全イベントを session-recorder 経由で OKL ログに書く。このパイプラインに例専用の部分は無く、例に固有なのは被験体だけである。

`ScallopSubject` は、最後の強化からの経過時間 `t` に対してハザード `2 Hz * min(1, (t / 60 s)^2)` で反応する。強化子が `t` を 0 に戻す。被験体はスケジュールについて何も知らず、スケジュールが提示した強化子を受け取るだけである。

## 結果（seed 1957）

![FI 60-s・強化 30 回の累積記録](fi_scallop.png)

| 被験体 | 反応数 | 後半の反応が前半より多い間隔 | quarter-life の中央値 |
|---|---|---|---|
| `ScallopSubject` | 1161 | 30 中 30 | 0.63 |
| ポアソン対照（1 Hz） | 1771 | 30 中 12 | 0.25 |

quarter-life（session-analyzer の `compute_quarter_life`）は、その間隔の反応の 4 分の 1 が出た時点で、間隔のどれだけが過ぎたかの割合である。反応率が一定なら約 0.25、反応が間隔の後ろに寄るほど大きくなる。`tests/test_examples.py` がこれらの指標（`ScallopSubject` は加速した間隔が 30 中 25 以上かつ quarter-life の中央値が 0.5 超、対照は 0.20〜0.30）と、seed を固定すると OKL ログがバイト単位で一致することを検査する。

## 出典

Ferster と Skinner は FI の遂行を、強化後の休止に続いて終端率まで滑らかに加速し、その率を次の強化まで保つものとして記述している（FI 1 分）。

- Ferster, C. B., & Skinner, B. F. (1957). *Schedules of reinforcement*. Appleton-Century-Crofts. https://doi.org/10.1037/10627-000
