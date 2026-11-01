# Direct live control results — 1 November 2026

Evidence is direct Computer Use screenshots inspected in the chat, with one action and refreshed observation per step. Images are not independently archived; current log is preserved locally under results/simulator_research/windows-2026-11-01/evidence/current-pc/. This is functional/accounting verification, not a randomized market experiment.

## v0.4 paused price experiment

With blank chart focus, Space resumed candle formation; another Space stopped it. Candle shapes, last price $10.04, depth and volume stayed fixed through wheel, order-history and MA tests and the following keyboard sequence. No fast-forward, save/restore, replay or capital-injection controls were used.

| Action | Position afterward | Floating | Total PnL | Last price |
|---|---|---:|---:|---:|
| Initial existing short | Short | 0.64 | 1.28 | $10.04 |
| B: close existing short | Flat | 0.00 | 1.03 | $10.04 |
| B: open long | Long | -0.25 | 0.78 | $10.04 |
| B: repeat | Long | -0.25 | 0.78 | $10.04 |
| S: close long | Flat | 0.00 | 0.53 | $10.04 |
| S: open short | Short | -0.25 | 0.28 | $10.04 |
| S: repeat (after user Continue; fresh foreground observation) | Short | -0.25 | 0.28 | $10.04 |
| B: close short | Flat | 0.00 | 0.03 | $10.04 |

Both new same-price round trips reduced displayed realized total by 0.50. Repeated same-side shortcuts left position, PnL and chart unchanged; the opposite shortcut closed without reversing. Buy/Sell markers appeared without any visible change in paused candles/current depth. This supports the installed-code finding that v0.4 player actions mark hypothetical positions rather than consume book liquidity. Pixel comparison cannot prove exact per-level quantities.

At Short before closing, 1.28 - 0.64 = 0.64 displayed realized component, while after closing total became 1.03. Closing therefore did not simply preserve the previous total: 0.25 was lost at close. The same-price new long and short each showed -0.25 on opening and another -0.25 effect on close. These are display-unit observations consistent with entry/exit costs; the scene commission, raw price and PnL-unit mapping have not been independently extracted. Do not call the 0.50 a verified dollar fee or infer live BTC costs from it.

## Controls and scope

See CONTROLS-CURRENT-PC.md. Order-history hide/show, current depth persistence, 25/50 MA removal, horizontal zoom and focused Space were verified. Shift-wheel, drag, a timed fast-forward hold, long-history MA curves, full scene parameters and native export remain unverified. The API reference lacks held-modifier scrolling and a defined DragInput argument shape; no guessed API calls were used.

This closes the bounded v0.4 position/accounting check in Flat state. It does not complete the prospective persistent-wall, cancellation/absorption or pattern-versus-book studies: screenshots supply neither exact event ledgers nor independent sample denominators. Existing host results retain their separate evidence type. The v0.4 log was copied before switching builds. Overall research remains incomplete, and no training was started.

## v0.5 controls and measured intervention sequence

v0.4 was closed and fresh window enumeration confirmed its absence before launching the installed v0.5 executable. The v0.5 window exposes Buy/Sell, price/floating/total PnL, current depth, candles/volume, and market-cap/supply/portfolio/position statistics. No fast-forward, MA, historical-depth toggle or size input is visible in this captured layout. Their presence in code does not establish scene exposure.

Blank chart focus plus Space paused native agent flow at last $102.09, zero floating/total PnL. Two captures showed unchanged candle/depth state. B/S remained operative while paused. Every trade below is one keyboard press, followed by an inspected capture. The three explicit resume intervals are not part of isolated paused comparisons.

| Step | Action / flow state | Last price | Floating | Total PnL | Position evidence |
|---|---|---:|---:|---:|---|
| 0 | Paused untouched origin | $102.09 | 0.00 | 0.00 | Refreshed size 0 |
| 1 | B while paused | $102.38 | 0.13 | 0.00 | Stats still show 0; stale |
| 2 | B again while paused | $102.77 | 0.72 | 0.00 | Stats still show 0; stale |
| 3 | Space resume; stats refresh | $102.54 | 0.26 | 0.00 | Size +200, worth $20.48K |
| 4 | Space pause | $101.55 | -1.72 | 0.00 | +200 carried from refreshed panel |
| 5 | S while paused | $101.29 | -1.12 | -1.01 | One long nominal lot remains per code; panel still +200 |
| 6 | S while paused | $100.95 | 0.00 | -2.32 | No entry line, flat per sequence; panel stale |
| 7 | S while paused | $100.69 | 0.15 | -2.32 | Short entry line appears |
| 8 | Space resume; stats refresh | $101.36 | -0.52 | -2.32 | Size -100, worth -$10.08K |
| 9 | Space pause | $100.87 | -0.03 | -2.32 | Short |
| 10 | B while paused | $101.27 | 0.00 | -2.60 | Entry line disappears; short closed |
| 11 | B while paused | $101.72 | 0.29 | -2.60 | New long entry line |
| 12 | S while paused | $100.45 | 0.00 | -3.44 | Entry line disappears; long closed |
| 13 | Space resume; stats refresh | $100.76 | 0.00 | -3.44 | Size 0, worth $0.00 |
| 14 | Space pause, then verification capture | $101.68 | 0.00 | -3.44 | Size 0; final capture stable |

The two opening buys moved last trade +0.29 and +0.39 dollars with native agent flow paused, and visibly depleted ask depth. Their cumulative last-price movement is approximately +66.6 bp relative to $102.09. This is last-trade movement, not VWAP slippage, an effect per unit of visible depth, or a population impact estimate. Repeated same-side inputs accumulate in v0.5, unlike v0.4. Opposite-side inputs unwind one nominal lot at a time before opening the other direction.

### Scene size and inventory reconciliation

Initial ordinary trader coin supply was 1,783,531; diluted/burned supply equaled it; max-short supply was 1,793,531. After the two buys and a completed base candle: trader supply 1,783,331; diluted supply 1,783,131; max-short supply 1,793,331; nominal player size +200. Thus ordinary supply fell by 200 while nominal exposure rose by 200. Under the inspected code's conservation behavior and with no I input, this is consistent with 200 achieved coins across the two requests, not a verified per-fill ledger. The +10,000 max-short convention and +200 after two actions both identify nominal lot 100 in this scene, rather than field initializer 10.

After the third sell and refresh: trader supply 1,783,631; diluted supply 1,783,731; max-short supply 1,793,631; size -100. After all unwinds and refresh: trader supply returned to 1,783,531, diluted supply matched it, and player size/worth were zero. This reconciles net coin transfer at those observation points. Ordinary-agent cash is shown only in rounded average form, so exact cash transfer/PnL cannot be reconciled from this screen.

Total PnL stayed zero despite nonzero floating after two buys. It changed on closing portions and remained -2.32 while short floating varied. This live behavior supports realized-only total PnL in v0.5. In the isolated paused final long round trip (steps 10–12), total declined by 0.84 display units even though immediately after buying floating was +0.29. The displayed last-price excursion differs from VWAP and book impact; exact fills and quantity-correct cash PnL remain unavailable. The source-diagnosed missing-quantity defect means -0.84 is not a reconciled cash loss on 100 coins. No claim of profitable whale manipulation follows.

### Live conclusions and remaining work

Verified: native chart rendering, current depth, focused pause/resume, B/S while paused, accumulation/reduction/crossing flat, nominal scene lot, lagging statistics, net coin-supply reconciliation and realized-only total PnL. Not verified: fill-level VWAP/slippage, fees/cash conservation, negative agent balances in this scene, partial/zero fills, scene trader count, retention/aggregation, a numeric export or 1/5/15/30-candle outcome measurement. No I or snapshot/replay inputs were sent. These are one-session functional observations, not new independent scenario replications or a training dataset.

Final state: v0.5 open, paused and flat; last $101.68, floating 0, total -3.44, ordinary supply 1,783,531. Both purchased binaries remain unchanged. The original research plan's uncompleted event-level studies stay open; additional screenshots cannot supply missing order IDs, fills or cancellation reasons.
