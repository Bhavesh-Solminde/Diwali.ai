# Order concepts for the first model

User supplied an explanatory document on 2 November 2026. Its six video summaries are supplied interpretations, not videos independently reviewed in this update. The useful distinctions below refine the existing candles/book/trades scope; no news, hidden-book estimation or entry-calibration work is added.

| Concept | Candidate representation | Boundary |
|---|---|---|
| Resting liquidity versus executed aggression | Separate spread/depth inputs from signed trade quantities | More buyer-initiated volume does not mean executions lack sellers |
| Marketable limit orders | Treat taking activity as aggressive regardless of submitted order type | Public executions do not necessarily reveal original order type or motive |
| Delta | Buyer-initiated base quantity minus seller-initiated base quantity over fixed past windows | Trade-side methodology and missing coverage must be recorded |
| CVD | Causal rolling signed volume over fixed lookbacks | Fixed reset/window policy; incomplete history must be flagged rather than silently continued |
| Effort versus result | Signed executed volume alongside contemporaneous return, range and depth changes | Absorption candidate, not identified hidden reserve or guaranteed reversal |
| Replenishment and disappearing depth | Observed net quantity changes alongside reported executions | Aggregate depth changes do not uniquely identify cancellation, gross refill or individual orders |
| Context dependence | Past volatility, trend/reversal and depth regimes | Evaluate on unseen origins; do not assign a manually guaranteed signal |
| Footprint/profile | Optional aggregate executions by causal price bins | Historical traded volume is not current resting liquidity; not necessary for initial feature set |

For Binance USD-M aggregate trades, preserve the buyer-maker flag, aggregate ID, first/last trade IDs, quantity, price and timestamps. With this documented flag convention, buyer maker means aggressive selling; buyer taker means aggressive buying. Aggregate messages are not all individual orders/fills. Use exchange classification rather than infer taker side from candle color. The signed-volume interpretation must be tested explicitly in the feature builder.

A large candle can reflect aggressive executions, thin depth, withdrawal of liquidity or combinations. A wick can suggest a reaction but cannot reconstruct a unique order book. A large displayed wall may be canceled or consumed. Positive delta can coexist with falling price; price response must be measured separately. Do not classify every disappearing wall as spoofing or every large trade as a directional whale.

First-model feature priority remains modest: past candle behavior; spread and measured-depth imbalance; net book changes; fixed-window buy/sell initiated quantity, delta and price response. Add derived features only with causal availability, units, masks and held-out baseline comparisons. No fixed 3:1 imbalance or 70% value-area convention is assumed predictive without testing.

Official feed reference checked for schema: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams .
