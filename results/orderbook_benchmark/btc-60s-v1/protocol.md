# BTC order-book comparison: frozen before model training and scoring

Requested models: TLOB, original-author DeepLOB, LOBERT, LOBS5. The four are
audited individually. An unavailable model receives no predictions, score or
rank. Substitutes or paper reimplementations are not silently called the original.

Input is the public BTC perpetual order-book snapshot dataset linked by TLOB:
`siavashraz/bitcoin-perpetualbtcusdtp-limit-order-book-data`, January 9–20, 2023.
This is a third-party historical dataset, not a direct exchange-certified feed.
Ten bid/ask levels are genuine snapshots, not reconstructed from candles.
Epoch-millisecond timestamps are used; the accompanying strings lose milliseconds.
States are the last snapshot strictly before each UTC second boundary. No empty
seconds are forward filled. Sampling activity counts recorded snapshots, not
necessarily every exchange event. Venue provenance will be reported as supplied.

The common prediction is **midpoint direction exactly 60 seconds ahead**, with
up > +1 basis point, down < -1 basis point, otherwise flat. The midpoint is the
average of best bid and ask; it is not a trade price or an OHLC candle. Classifiers
will be charted as direction predictions, never fabricated OHLC price forecasts.

Chronological split by observed UTC dates: first 80% training, next 10%
validation, remaining days test. The future target and the complete 128-second
input window must lie in a consecutive sequence. Training labels must end before
validation, validation labels before test. Every eligible minute boundary is a
candidate. Windows overlap in past observations; targets are 60 seconds apart.
There is no random cross-period split. No target smoothing and no thresholds
fitted on holdout labels are used.

Each trainable model uses 128 one-second snapshots, all 40 book fields, a new
3-class target and a fresh random initialization (seed 42). Price inputs are
log-ratios in basis points relative to the final observed midpoint in that input
window. Sizes use log1p and a training-only pooled mean/std. This adaptation
removes outright price-level drift. It is an architecture comparison for this
task, not replication of either paper's benchmark numbers or published weights.
Use full published TLOB configuration (width 40, 4 dual-attention blocks, 1 head,
sinusoidal positions) and original DeepLOB network. Both train three epochs with
Adam at 0.0001, batch size 32, equal training windows, no class weighting or
hyperparameter search. Select epoch by validation cross-entropy only. Maximum
8,000 evenly spaced training windows and 1,500 validation windows. Runtime CPU
compatibility changes must preserve architecture math and be recorded.

The 10 examples are selected **before training and prediction** from eligible
test minute boundaries using past-only measurements, at least 10 minutes apart:

1. Largest preceding five-minute rise.
2. Largest preceding five-minute fall.
3. Smallest absolute preceding five-minute move (sideways).
4. Highest preceding five-minute one-second return volatility.
5. Lowest preceding five-minute one-second return volatility.
6. Strongest current ten-level bid-volume imbalance.
7. Strongest current ten-level ask-volume imbalance.
8. Widest average spread over the preceding minute.
9. Lowest current ten-level combined depth.
10. Highest count of observed midpoint changes over the preceding minute.

Pre-training availability correction: snapshots are recorded at approximately
four per second regardless of market activity. Recorded snapshot count therefore
does not measure exchange message activity. Case 10 uses observed midpoint
changes instead. The original unscored selection is preserved as
`frozen-cases-recording-rate-v1.json`; this revision precedes training and scores.

These are different selection criteria and different times. Market properties
can coexist; they are not claimed mutually exclusive. No examples may be replaced
after viewing predictions or outcomes. Report the selecting measurements.

Score each model on all 10 examples and separately the full eligible test grid:
accuracy, class-balanced accuracy, macro F1, confusion counts, multiclass Brier
score, class distribution and coverage. Include always-flat, training-majority,
past-minute momentum and depth-imbalance baselines. Rank runnable models by full
test balanced accuracy, with macro F1 and baseline comparisons shown. Ten charts
are illustrative; a 10-case score cannot establish a generally best model.

LOBERT: no official code or weights identified in paper/author sources; confirm
this before marking unavailable. LOBS5: inspect author source/checkpoints and its
individual-order message requirement. L2 snapshots cannot recover order IDs,
individual cancellations, executions or hidden orders; never invent these.
No paper's equity accuracy is used as a BTC score. Any unavailable entry prevents
claiming an empirical winner across all four.
