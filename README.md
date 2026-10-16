# operantkit

:jp: [日本語版 README](README.ja.md)

Meta-package for the OperantKit stack. It contains no code of its own; installing it pulls in every OperantKit library and the `operant` command.

## Installation

```bash
pip install operantkit
```

For serial-port hardware (pyserial):

```bash
pip install 'operantkit[hw-serial]'
```

## What gets installed

| Package | Import name | Role |
|---|---|---|
| [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) | `contingency_dsl` | Parser for the contingency-dsl schedule language |
| [contingency-py](https://github.com/OperantKit/contingency-py) | `contingency` | Reinforcement schedule engine (DSL AST → Schedule) |
| [experiment-core](https://github.com/OperantKit/experiment-core) | `experiment_core` | Session lifecycle, ExperimentContext, renewal designs |
| [session-runner](https://github.com/OperantKit/session-runner) | `session_runner` | Session driver that pushes events to an EventSink |
| [session-recorder](https://github.com/OperantKit/session-recorder) | `session_recorder` | OKL v1 event-log writer and reader |
| [session-analyzer](https://github.com/OperantKit/session-analyzer) | `session_analyzer` | Cumulative records, statistics, model fitting |
| [experiment-io](https://github.com/OperantKit/experiment-io) | `experiment_io` | Hardware I/O: virtual / serial / HIL backends |
| [operantkit-cli](https://github.com/OperantKit/operantkit-cli) | `operantkit_cli` | `operant run` command |

## Quick start

```bash
operant run --schedule "FI30s" --output fi30.okl --exit-reinforcers 5
```

This runs a fixed-interval 30-s schedule against the built-in virtual subject until 5 reinforcers are delivered and writes the events to `fi30.okl`. See the operantkit-cli README for the options.

## License

MIT. See [LICENSE](LICENSE).
