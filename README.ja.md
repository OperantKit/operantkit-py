# operantkit

:gb: [English README](README.md)

OperantKit 一式をまとめて入れるためのメタパッケージです。自身のコードは持たず、install すると OperantKit の全ライブラリと `operant` コマンドが入ります。

## Installation

```bash
pip install operantkit
```

シリアルポートの実機（pyserial）を使う場合:

```bash
pip install 'operantkit[hw-serial]'
```

## What gets installed

| パッケージ | import 名 | 役割 |
|---|---|---|
| [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) | `contingency_dsl` | スケジュール記述言語 contingency-dsl のパーサー |
| [contingency-py](https://github.com/OperantKit/contingency-py) | `contingency` | 強化スケジュールエンジン（DSL の AST → Schedule） |
| [experiment-core](https://github.com/OperantKit/experiment-core) | `experiment_core` | セッションのライフサイクル、ExperimentContext、復活（renewal）デザイン |
| [session-runner](https://github.com/OperantKit/session-runner) | `session_runner` | イベントを EventSink に流すセッション駆動 |
| [session-recorder](https://github.com/OperantKit/session-recorder) | `session_recorder` | OKL v1 イベントログの書き出しと読み込み |
| [session-analyzer](https://github.com/OperantKit/session-analyzer) | `session_analyzer` | 累積記録・統計・モデルの当てはめ |
| [experiment-io](https://github.com/OperantKit/experiment-io) | `experiment_io` | 実機入出力: virtual / serial / HIL バックエンド |
| [operantkit-cli](https://github.com/OperantKit/operantkit-cli) | `operantkit_cli` | `operant run` コマンド |

## Quick start

```bash
operant run --schedule "FI30s" --output fi30.okl --exit-reinforcers 5
```

組み込みの仮想被験体に固定時隔 30 秒スケジュールをかけ、強化子が 5 回提示されるまで走らせて、イベントを `fi30.okl` に書き出します。オプションは operantkit-cli の README を参照してください。

## License

MIT。[LICENSE](LICENSE) を参照。
