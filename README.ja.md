# operantkit

:gb: [English README](README.md)

`operantkit` は、[OperantKit](https://github.com/OperantKit) の中核ライブラリと `operant` コマンドをまとめて入れるパッケージです。このリポジトリ（operantkit-py）には、古典実験を仮想被験体で再現する例も入っています。パッケージ自身のコードはありません。個々のパッケージを使う前に、よく知られた結果で OperantKit が何をするかを見たいときは、ここから始めてください。

- **古典的な結果を最初から最後まで再現します。** FI スキャロップ、DRL 下の反応、並立 VI VI のマッチングを、スケジュールの式からイベントログと図まで通しで走らせます。
- **すべて公開のパイプラインです。** 例ごとに固有なのは仮想被験体だけです。
- **再現できます。** セッション時間は模擬時計で進み、乱数はすべて seed で固定されるので、何度実行しても同じログが書かれます。

## インストール

Python 3.11 以上が必要です。OperantKit の各パッケージはまだ PyPI に登録されていないので、`pip install operantkit` も `pip install git+https://github.com/OperantKit/operantkit-py` も依存の解決で失敗します。GitHub から依存の解決なしでライブラリを入れ、その後で必要な外部ライブラリ 3 つを入れます:

```bash
G=git+https://github.com/OperantKit
pip install --no-deps $G/contingency-dsl-py $G/contingency-py $G/experiment-core \
  $G/session-recorder $G/session-runner $G/session-analyzer $G/experiment-io $G/operantkit-cli
pip install numpy scipy matplotlib
```

これはメタパッケージが依存する組とちょうど同じです。`pip check` はこれら開発版どうしのバージョンの食い違いを報告しますが、例の動作には影響しません。シリアルポートの機器を使う場合は `pip install pyserial` も入れます。

## 例

このリポジトリを clone し、Herrnstein (1961) の並立 VI VI の条件を再現します:

```bash
git clone https://github.com/OperantKit/operantkit-py
cd operantkit-py
python examples/concurrent_vi_matching/run.py
```

変動時隔（VI）スケジュールの組 4 つを、それぞれ 1.5 秒の切替遅延付きで（例: `Conc(VI 135-s, VI 270-s, COD=1.5-s)`）、強化の多いキーへ反応を移していく仮想被験体に対して走らせます。条件ごとに OKL（OperantKit Log）形式のイベントログを 1 つと、`concurrent_vi_matching.png`（強化の相対頻度に対する反応の相対頻度と対角線の図）を書き出し、条件ごとの件数と一般化マッチング法則の当てはめを表示します。出力の末尾:

```
  "sensitivity": 0.941,
  "bias": -0.09,
  "r_squared": 0.953,
  "max_deviation": 0.057
}
```

実行には約 20 秒かかりました。被験体はこの例のために書いたモデルなので、この当てはめが示すのは、スケジュール・切替遅延・ログ・分析が一緒に正しく動くことであって、動物についての証拠ではありません。

## 例の一覧

| 例 | 実験 | スケジュール |
|---|---|---|
| [fi_scallop](examples/fi_scallop/README.md) | 固定時隔スキャロップ: 強化子の後に休止し、その後反応が加速する（Ferster & Skinner, 1957） | `FI 60-s` |
| [concurrent_vi_matching](examples/concurrent_vi_matching/README.md) | 反応の相対頻度が強化の相対頻度に従う（Herrnstein, 1961） | `Conc(VI 180-s, VI 180-s, COD=1.5-s)` ほか 3 組 |
| [drl_irt](examples/drl_irt/README.md) | 低反応率分化強化: 反応間時間が伸び、反応率が下がる（Ferster & Skinner, 1957） | `DRL 10-s` |
| [paper_procedure](examples/paper_procedure/README.md) | 公刊論文の手続きを DOI から走らせ、論文の質的なパターンと照合する | 論文の方法セクションから抽出 |

各例は、ログと図を自分の `run.py` の隣に書き出します。詳しくは [examples/README.md](examples/README.md) を参照してください。`tests/test_examples.py` はすべての例を実行してパターンを確かめ、`tests/laws/` は模擬した FI・並立 VI VI・比率と時隔の比較の反応を、原論文が報告した値と比べます（出典は各テストファイルにあります）。

## 入るもの

| パッケージ | import 名 | 役割 |
|---|---|---|
| [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) | `contingency_dsl` | スケジュール記述言語 contingency-dsl のパーサ |
| [contingency-py](https://github.com/OperantKit/contingency-py) | `contingency` | 強化スケジュールのエンジン |
| [experiment-core](https://github.com/OperantKit/experiment-core) | `experiment_core` | セッションの開始から終了までの管理、実験の文脈、リニューアルのデザイン |
| [session-runner](https://github.com/OperantKit/session-runner) | `session_runner` | セッションを進め、イベントを受け渡す |
| [session-recorder](https://github.com/OperantKit/session-recorder) | `session_recorder` | OKL イベントログの書き出しと読み込み |
| [session-analyzer](https://github.com/OperantKit/session-analyzer) | `session_analyzer` | 累積記録・統計・モデルの当てはめ |
| [experiment-io](https://github.com/OperantKit/experiment-io) | `experiment_io` | 機器の入出力: 仮想・シリアルポート・HIL（hardware-in-the-loop）のバックエンド |
| [operantkit-cli](https://github.com/OperantKit/operantkit-cli) | `operantkit_cli` | `operant run` コマンド |

含まれないもの: 方法セクションの道具（[contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure)、[contingency-procedure2dsl](https://github.com/OperantKit/contingency-procedure2dsl)）、アシスタントとの連携（[operantkit-mcp](https://github.com/OperantKit/operantkit-mcp)）、[schedule-writer](https://github.com/OperantKit/schedule-writer) や [session-visualizer](https://github.com/OperantKit/session-visualizer) などの作成・表示の道具。これらは別に入れてください。

## 制限

- **まだ PyPI にありません。** 公開までは、上の `--no-deps` のインストールを使ってください。
- **被験体はモデルです。** 各例の被験体は、その実験のパターンを出すように書かれています。例が示すのは、OperantKit が書いたとおりに随伴性を提示することであり、あなたの動物がどう振る舞うかの予測ではありません。

## 参考文献

Ferster, C. B., & Skinner, B. F. (1957). *Schedules of reinforcement*. Appleton-Century-Crofts. https://doi.org/10.1037/10627-000

Herrnstein, R. J. (1961). Relative and absolute strength of response as a function of frequency of reinforcement. *Journal of the Experimental Analysis of Behavior*, *4*(3), 267–272. https://doi.org/10.1901/jeab.1961.4-267

## ライセンス

MIT。[LICENSE](LICENSE) を参照してください。
