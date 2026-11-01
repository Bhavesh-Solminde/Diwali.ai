# Controls before experiments — current Windows PC, 1 November 2026

Follow-up: see LIVE-CONTROL-RESULTS-CURRENT-PC.md for the completed paused v0.4 B/S checks, closure of that session, and subsequent v0.5 live controls/accumulation/supply tests. v0.5 scene lot is nominally 100, confirmed by refreshed position and supply panels. Code initializer 10 is not this scene's lot.

The user explicitly replaced the old manual screenshot workflow with direct Computer Use. Captures work after bringing the simulator to the foreground. An occluded capture can show the foreground app instead: inspect the pixels and activate the selected simulator before relying on an image. Screenshots supporting this review are in the chat tool record, not archived PNGs.

Read-only inspection of both installed Assembly-CSharp DLLs scanned declared methods for Unity Input calls and runtime event registration, then checked the relevant callbacks. The inspection tool invokes no game constructors or methods. This is a map of controls found in those scripts; Unity UI navigation and serialized scene wiring may supply additional behavior. No seed, size-entry or numeric export UI is established.

| Control | v0.4 | v0.5 | Current live verification |
|---|---|---|---|
| Buy button / B | Flat→Long; Short→Flat; Long unchanged; hypothetical position, no book order | Marketable buy consuming asks; adds/reduces one nominal lot | v0.4 button transitions observed; keyboard checked separately below |
| Sell button / S | Flat→Short; Long→Flat; Short unchanged | Marketable sell consuming bids; adds/reduces one nominal lot | v0.4 button transitions and repeated Short observed |
| Space | Toggle simulation active | Same | Chart-focused resume observed; second press followed by stable price $10.04, floating 0.64, total 1.28, candles and book across multiple control checks |
| Hold `>>` | Pointer-down sets active=true, timeSpeed=100; pointer-up sets speed=1, leaving active true | Same | Code checked, timed hold not measured. It can resume a paused market; release does not pause |
| Wheel | Horizontal scale about mouse anchor; recalculates chart offset | Same code path | v0.4 verified by changed candle spacing while paused |
| Shift + wheel | Vertical scale about mouse anchor; either Shift key accepted | Same | Code checked; not live verified with current API, which does not document held-modifier scrolling |
| Left-button drag | Pan both axes using world-coordinate mouse displacement | Same | Code checked; not live verified; bundled API omits the DragInput argument definition |
| Show/Hide Order Bars | Toggle historical book bands | Callback exists; scene exposure not yet checked | v0.4 hide/show verified while paused; current right-side depth remains visible |
| MA 25/50/200/800 buttons | Each Indicator_Amigo toggles its showSMA | Same component family; scene labels need inspection | All four labels visible in v0.4; 25 cyan and 50 yellow lines disappeared independently when toggled off. 200/800 curves not verified with this short history |
| 1 (top row) | BackupState | BackupState | Code checked only; v0.5 known snapshot exception; neither supplies validated complete state/RNG restoration |
| 2 (top row) | RestoreState | RestoreState | Code checked only; not used during this continuation |
| 3 (top row) | Toggle replay; replay sets active=true, speed=250 and captures/restores after >40 retained bars beyond saved index | Same general logic | Code checked only; not used; can invalidate an ordinary baseline |
| Esc | Requests windowed mode | Same | Code checked. Physical Escape stops Computer Use, so do not use it as an automated experiment shortcut |
| F11 | Toggle Windowed / FullScreenWindow | Same | One request caused no visible mode change in the immediate capture; outcome unverified |
| Hold I | Not found in v0.4 input handler | Calls AddCapital on every ordinary trader each rendered Update, including while paused | Code checked only; do not use in baseline or whale tests |

## Focus and observation contract

Space can activate the selected UI button as well as toggle the simulation. In the prior live sequence it opened Long after Buy had focus. Before Space, click a blank chart point away from controls and refresh. Verify both simulation movement and position afterward. Do not infer pause from an unchanged price alone: compare newest candles, wick/body, volume, depth and PnL over multiple observations while foregrounded.

Button and keyboard actions are processed outside the `active` simulation gate in both inspected Update methods. v0.4 GUI Buy/Sell also directly call Long/Short, so trading while paused is expected; this does not unpause the agent scheduler. v0.5 GUI actions execute actual book orders even while paused. Scene-specific fill units and parameter overrides remain separate questions.

The prior run's apparent stable-price interval was not enough to establish pause throughout; later candles advanced. Treat those observations as running/uncertain, except the new chart-focused controlled pause above. User-input interference was explicitly reported by the tool twice in the earlier sequence; interrupted actions are not confirmed fills.

## Research restart

Start v0.4 from the verified paused chart above, record current position (Short), last price and PnL, then one action and one verification at a time. Reconcile display totals but do not interpret their units as dollar cash. Current state is not a clean independent baseline: previous trades, MA/toggle and zoom changes are documented. A clean baseline needs a separate restart after preserving the current log. Missing event traces still prevent cancellation-versus-execution, exact wall depth and rigorous absorption claims.

Finish the feasible v0.4 live pass and preserve its evidence/log before closing it; only then launch v0.5. Determine v0.5's visible panel and controls before its first trade. No training is started by this review.
