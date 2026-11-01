# User-assisted v0.4 observations — 1 November 2026

Evidence: two user-supplied desktop screenshots, saved under `results/simulator_research/windows-2026-11-01/evidence/user-assisted-v04/`. The assistant did not operate the simulator. The previous capture limitation persists; these images are a separate user-assisted evidence source.

| Observation | 01-flat.png | 02-long.png |
|---|---|---|
| Taskbar clock (user desktop) | 18:53 | 18:54 |
| Position text | `Position:` with no value | `Position: Long` |
| Last price | $10.45 | $10.51 |
| Floating | 0.00 | 0.23 |
| Total PnL | 0.00 | 0.23 |
| Historical depth overlay | Not visible across candle history | Visible green/red horizontal segments across history |
| Order-bar button | Show/Hide Order Bars | Hide Order Bars |

The assistant requested Space to pause, then one Buy click. The subsequent screenshot shows Long and a green upward triangle below the chart, but does not independently establish exact inputs, entry time, entry price, or pause state. Candle history and last price changed between images. Do not treat the first image's $10.45 as the entry price. The order-bar control also changed, so this is not an isolated single-variable comparison.

The second screenshot establishes that the running scene can display the historical depth overlay, a long position and positive floating/total PnL. Equality of the displayed PnLs is consistent with no realized PnL, within display rounding. It does not establish a cash profit or reconciled portfolio.

Code cross-check: v0.4 `MarketSimulatorReal.UpdateUI_Once` computes total as realized plus floating. Long floating is `(lastTradedPrice * (1 - commissionRate) - entryPrice) * positionSize`; displayed Last Price divides raw price by 100, while displayed PnL does not perform that division here. Scene quantity/commission are not verified. Do not infer entry price by subtracting 0.23 from $10.51.

Next controlled observation: with the market paused, record a pre-action screenshot, click Sell once from Long, then record a post-action screenshot. Code predicts Flat, zero floating and realization of the closing result. Pause status and unchanged market price must be verified, rather than assumed. Order-book impact and precise accounting remain unverified by this pair.

## Verified keyboard intervention: Long to Flat

Manual screenshot 03 (desktop clock 18:56) shows Long, last $10.54, floating 0.51 and total 0.51. The assistant selected the unique running v0.4 window using Computer Use, observed accessibility without capture, sent lowercase `s` exactly once, and refreshed accessibility without capture. The input API returned without error, but accessibility exposes no trading fields.

Manual screenshot 04 (18:57) subsequently shows Flat, last $10.71, floating 0.00 and total 1.88, plus a red downward chart marker. This verifies the observed Long-to-Flat result after the assistant keyboard intervention and is consistent with the inspected close-long behavior. It does not isolate execution price, timing, quantity, fee or book impact: the market advanced between screenshots. Do not interpret $10.71 as the exact exit price, or the increase from 0.51 to 1.88 as an effect caused by selling. Total 1.88 is a simulator display value, not yet a reconciled dollar cash profit.

The earlier proposed paused test was not established. This is a running-market functional test. No automatic screenshot capture was requested. The next single action is `s` from the observed Flat state; code predicts Short. Outcome remains pending manual verification.

## Verified keyboard intervention: Flat to Short

After the next single assistant `s` input, screenshot 05 (desktop clock 18:58) shows Short, last $10.89, floating -1.75 and total 0.13. This verifies the observed Flat-to-Short outcome. Display accounting reconciles: previous flat total 1.88 plus current floating -1.75 equals 0.13. It supports the code finding that v0.4 total includes floating PnL. It does not establish entry price or quantity, nor causal order-book impact. The continuing price advance is compatible with negative short floating PnL but is not an isolated controlled price test.

Next action: assistant sends Space once to request a pause. A pause indicator is not exposed in accessibility, so verify using two manually supplied screenshots separated by several seconds, comparing latest candle, last price, depth and PnL. Pause remains unverified until those observations arrive.
