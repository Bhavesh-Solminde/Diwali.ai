# Handoff for the model-building AI — proposed specification v1.1

Extended research supplement for review: [RESEARCH-REVIEW-EXTENDED.md](RESEARCH-REVIEW-EXTENDED.md). New fixed-rule v0.4 depth diagnostics and v0.5 size-500 schedules use 30 main parents each after 10 pilots. Retain book/persistence and execution-size hypotheses; absorption, universal wall probabilities and repeated-impact weakening remain unsupported. The supplement includes a feature dictionary, all denominators, failures, cost/evaluation formulas and proposed ablations. It does not authorize fitting or substitute host evidence for outstanding native tests.

Current-PC evidence update: LIVE-CONTROL-RESULTS-CURRENT-PC.md adds native tests, including v0.4 same-price display losses, v0.5 nominal scene lot 100, repeated accumulation/reduction, delayed stats and coin-supply reconciliation. Direct capture replaces the older manual workflow by explicit user instruction. These checks support the existing accounting cautions; they do not certify fill-level training labels or authorize fitting. Older capture/no-v0.5-test text below is historical.

For the current cross-PC state and mandatory manual screenshot workflow, first read `CONTINUE-ON-WINDOWS-11.md` and `USER-ASSISTED-v04.md`. Research is still incomplete; no new model training has begun.

Read `EXPERIMENT-REPORT.md`, both operating guides, DATA-DICTIONARY.md and RESEARCH-TO-MODEL-CHANGELOG.md before implementing. This handoff adds measured simulator findings to the repository's 1 November frozen specification. It does not authorize training or live execution. Present this revision for user review first.

## What the simulator research establishes

v0.4 demonstrates stateful price-level liquidity, consumption, replenishment through new requests, and removal/pruning effects under random agent flow. It also contains locked-market matching behavior, incorrect aggregate counters and a removal rule favoring large levels. v0.5 demonstrates FIFO level consumption, depth-dependent slippage, repeated player accumulation and ordinary-agent cash/coin transfer, but its reservation, partial-fill position, PnL, volume, OHLC and replay behavior have concrete defects. Preserve the mechanisms as hypotheses; do not copy the artifacts or vendor bot feature/label builder.

720 original-DLL host scenarios are diagnostic research, not 720 independent parent states: v0.4 has 40 parents including pilot, v0.5 40. Every sibling condition from one parent stays together. Automated native capture failed. Later user-uploaded screenshots establish v0.4 chart/depth rendering and Long-to-Flat/Flat-to-Short outcomes; scene parameters, frame timing and v0.5 live accounting remain unverified. All numerical effects are conditional on the declared 200-agent profile and CLR host.

## Target and observable information

Retain the independent target: Binance USD-margined BTCUSDT perpetual, one-minute UTC buckets, next completed trade-price OHLCV distribution and entry-quality probabilities. Do not substitute the existing spot prototype or unidentified-venue 2023 midpoint benchmark for this task. No real market data were acquired in this simulator research.

At forecast origin t, use 1,440 completed one-minute candles, synchronized last-60-second public book/trade features at one-second resolution and current top-20 bid/ask levels where actually available. Store exchange timestamp, local receipt timestamp, cutoff, issuance time and sequence status. Book distances relative to current mid; sizes in base BTC; depth within 1/5/10/25 bp only where feed covers it. Missing/gapped feed is masked and resynchronized, not interpreted as empty liquidity. The simulator's price/depth units and five-sweep candles are not BTC minutes.

Candidate candle inputs: log returns, gaps, ranges, body, upper/lower wicks and log1p base volume. Candidate book inputs: spread, multi-depth imbalance, distance to concentrated visible depth, level persistence, additions/removals/refill and depth gaps. Candidate trade inputs: aggressor signed flow, count/quantity/notional, effective spread and causal impact/absorption estimates. Candle/volume absorption is an estimate, never proof of a hidden reserve or whale identity. Event-level feature availability must be verified before inclusion.

UTC cyclic calendar/session context remains useful to test on real timestamps. No real-world session is inferred from the simulator's three sinusoids. Point-in-time news is a later gated feature; consensus before release and surprise after release have different availability times. Privileged agent portfolios, RNG state, player identity, future book and hidden inventory are simulator-only diagnostics. If used, label an oracle experiment separately.

## Labels and accounting contract

Build candles from every executed trade with exact time, price, base quantity and notional. Test O=first, C=last, H=max and L=min across all fills; no negative volume and no terminal-sweep shortcut. The next open is not forcibly the previous close. Represent positive O/C with log gap/body, nonnegative upper/lower excursions and volume with constrained transforms. Representative candles and every sampled candle must satisfy H>=max(O,C), L<=min(O,C), positive prices and nonnegative volume.

Direction is up/neutral/down versus origin close with ±1 bp neutral band. Entry label retains the frozen policy: 1 ATR14 stop, 2 ATR14 target, 15-minute timeout. Establish target-before-stop using trades where available; otherwise ambiguous same-candle crossings remain ambiguous. Wait alerts require a new forecast at trigger time; nonarrival is untriggered, not a win.

Maintain a ledger of intended quantity, achieved fills, VWAP, residual position, cash, paid fees, funding and executable mark price. Realized PnL is cash transfer matched to closed quantity; unrealized PnL marks remaining inventory. Price movement is not PnL. Test partial/zero fills, crossing at equality, FIFO, order reservation, cancellation unlock, negative-balance rejection, round trips, overflow bounds and complete state/RNG restoration before synthetic labels are accepted.

## Models, splits and evaluation

Start with last-close/rolling-candle and simple book-imbalance baselines. Then compare a small MLP (candidate hidden widths 256/128/64) with a causal sequence model using identical observable information and cutoff. Parameter count follows the actual input tensor; roughly 7M is a comparison budget, not verified Tiger architecture. Larger 15–20M candidates remain optional after measured hardware capacity. Do not run built-in BotBatchManager training as a shortcut.

Do not start a synthetic pretraining dataset from these uncorrected outputs. If approved later, build an independent event-instrumented engine or obtain a corrected supported export. Split synthetic data by complete parent/run AND scenario family, holding out sizes/settings; never split overlapping windows or siblings across partitions. Normalizers fit only on training data. Compare candles-only, candles+book, candles+book+trades and real-only versus synthetic-pretrained under the same real held-out evaluation.

Retain chronological historical candle/trade versus prospective book tracks from frozen v1. The existing 2023 book test is already observed, unverified in venue/units and only midpoint direction. The 2024 spot Kronos example is an inference check with unknown pretraining overlap. Neither certifies an unseen perpetual OHLC benchmark. Proposed future real dates/data must be acquired, verified and frozen before fitting; no model trained on later observations can claim an earlier period as chronological unseen data.

Required panels: training error; locked past unseen-data error; recent matured forward-prediction error (24h plus 7-day context); internal validation separate. Price MAE/RMSE in USDT and bp; raw MSE in USDT²; component OHLC/volume errors; train-scaled combined HLCV; direction confusion/class balance; distribution proper loss, interval coverage and width; target/stop/timeout Brier/log loss and reliability. No conversion of MSE or move-fulfillment into accuracy. Show pending/late/ambiguous counts. No simulator segment is a recent live record.

Paper policy only after review: use observed executable bid/ask, latency, fees, slippage and funding where available; preserve the frozen stress assumptions as assumptions. Evaluate forecasting improvement separately from entry net expectancy. Report uncertainty by day for real data and parent for synthetic data. Freeze tuning/calibration before locked test; changes prompted by test outcomes need a later test interval.

Profile the actual 1,440-candle combined input on the intended machine before scaling. This session observed Windows 10 / RTX 3060 and driver 32.0.15.8129, not Mac M5 throughput. Prior 12 GB process target and batch 16 are planning constraints to revisit against measured Windows resources after review. No hardware training pilot was run here.

## Next actions for the other AI

1. Read the evidence and user review of v1.1; retain explicit unknowns about Tiger and vendor scene parameters.
2. Validate the independent matching/event ledger before generating any synthetic training windows.
3. Implement causal real-feed acquisition, sequence/gap checks and immutable forecast cutoffs only within the reviewed plan.
4. Run the agreed model/hardware comparison after authorization; provide measured failures as well as successes.

Do not promise a profitable model, a calibrated 80% signal or a known hidden-order total. This research gives the next AI a mechanism map, reproducible diagnostics and constraints on valid data—not a trained predictor.
