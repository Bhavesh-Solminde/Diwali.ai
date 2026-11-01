"""Decision report from frozen validation artifacts; no training or simulation."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'results/simulator_research/validation-2026-11-01'
D=ROOT/'docs/planning/windows-simulator-findings-2026-11-01'
audit=json.loads((R/'baseline-audit.json').read_text())
v04=json.loads((R/'analysis-final/v04-statistics.json').read_text())
v05=json.loads((R/'analysis-final/v05-statistics.json').read_text())
real=json.loads((R/'real-data-quality-final/quality.json').read_text())


def ci(value,scale=1,kind='ci'):
    low,high=value[kind]
    mean=value.get('mean',value.get('parent_mean_delta'))
    return f'{mean*scale:.2f} [{low*scale:.2f}, {high*scale:.2f}]'


spec=importlib.util.spec_from_file_location('validation',Path(__file__).with_name('analyze-validation.py'))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
with gzip.open(R/'analysis-final/entry-signals.jsonl.gz','rt') as f:events=[json.loads(line) for line in f]
balances={}
for profile in ('standard','sparse','maker30'):
    ev=[e for e in events if e['profile']==profile];pairs=mod.match_events(ev);balances[profile]={}
    for side in ('bid','ask'):
        strong=[e for e in ev if e['side']==side and e['strength']=='strong'];weak=[e for e in ev if e['side']==side and e['strength']=='weak']
        matched=[p for p in pairs if p['strong']['side']==side]
        result={}
        for field in ('distance_bp','volatility_bp','volume_ratio'):
            a=np.array([e[field] for e in strong]);b=np.array([e[field] for e in weak]);sd=float(np.sqrt((a.var(ddof=1)+b.var(ddof=1))/2))
            result[field]=dict(before_mean_difference=float(a.mean()-b.mean()),before_smd=float((a.mean()-b.mean())/sd) if sd else None,
                after_mean_difference=float(np.mean([p['strong'][field]-p['weak'][field] for p in matched])) if matched else None,
                after_smd=float(np.mean([p['strong'][field]-p['weak'][field] for p in matched])/sd) if matched and sd else None)
        balances[profile][side]=dict(strong=len(strong),weak=len(weak),matched_pairs=len(matched),covariates=result)
(R/'analysis-final/entry-balance.json').write_text(json.dumps(balances,indent=2))

lines=['# Validation decision report — 1 November 2026','',
       'This report answers reviewer commit `cb2ae3fd1b69f6afa814af3b50c54016ac2bf393` and the user’s focused validation request. Existing runs and original conclusions are preserved. The reversal audit is explicitly post hoc; fresh-seed results use the separately frozen VALIDATION-PREREGISTRATION.md. No model was trained, no real trades placed, no vendor binaries patched and no replacement engine built.', '',
       '## Stage-specific decision','',
       '| Stage | Decision | Required next evidence |','|---|---|---|',
       '| A. Data-pipeline implementation | Ready to proceed; bounded engineering recorder implemented and tested | Durable reconnect/resnapshot, storage, clock monitoring and complete-candle/coverage validation before production collection |',
       '| B. Small real-data baseline | Conditionally ready as the next reviewed experiment; no training started | Acquire sufficient same-venue data; freeze chronology, preprocessing and baselines; pass leakage/label checks. Does not need every simulator question solved |',
       '| C. Synthetic pretraining | Not ready; reject current vendor outputs as trusted training records | Supported corrected exporter or separately reviewed independent event engine with matching, collateral, fill, candle and replay invariants |',
       '| D. Entry-probability calibration | Not ready | Executable triggers, ordered executions or useful ambiguity bounds, enough independent out-of-sample predictions and coverage/calibration |',
       '| E. Forward paper evaluation | Infrastructure planning ready; measured evaluation deferred | A frozen real-data forecast/baseline, immutable issuance/cutoff log and matured outcomes with costs. No forward forecasts exist yet |', '',
       'Simulator robustness does not certify BTC transfer or profitability. A real-only baseline may move forward after its own gates and review, rather than waiting for a synthetic engine.', '',
       '## Corrected existing baseline audit — post hoc','',
       'Selection is phase=main, group=all, book prediction available; exactly one record per run/candle. Pattern-stratum copies are excluded. There are 10,168 unique origins from 30 independent parents, versus 14,100 candidate origins: 445 locked/absent-book exclusions and 3,487 missing-10-bp-depth exclusions. Common-grid coverage is 72.11%. Rules make a prediction on 100% of that eligible grid; this is not 100% feed coverage.', '',
       '| Rule | Accuracy | Balanced accuracy | Recall down / neutral / up |','|---|---:|---:|---|']
for rule in ('up','down','momentum','reversal','book','pilot_majority','neutral'):
    s=audit['rules'][rule];rec=s['per_class_recall']
    lines.append(f"| {rule} | {100*s['accuracy']:.4f}% | {100*s['balanced_accuracy']:.4f}% | {' / '.join(f'{100*rec[str(k)]:.2f}%' for k in (-1,0,1))} |")
lines += ['', f"All five reviewer figures reproduce. Book-minus-reversal origin-weighted difference is {100*audit['book_minus_reversal']['origin_weighted_delta']:.4f} percentage points. Equal-parent paired mean difference is {ci(audit['book_minus_reversal'],100,'bootstrap_ci')} pp (95% parent bootstrap). The majority class is frozen UP from earlier pilot counts: 1,652 up / 1,644 down / 41 neutral, not selected from the final test. Reversal was suggested after outcomes were reviewed, so this audit is not confirmatory. The previous 13.87-point comparison against momentum remains its original, weaker-comparator exploratory result.", '',
       '## Fresh-seed v0.4 confirmation','',
       'Three host profiles were frozen: standard=(200 agents, .10 activity, .10 maker); sparse=(100, .05, .10); maker30=(200, .10, .30). Sparse changes two settings, so it tests a joint profile rather than identifying their isolated causal contributions. Each has 60 new independent parents, 100 warmup plus 500 observation base candles. Profile/seed ranges, primary contrasts and sample-size reasoning are in the preregistration. Total: 180 untouched scenarios and 108,000 raw candle boundaries, including warmup. No extra scenarios were added after results.', '',
       'All rules use identical origins and the next completed base-candle last-trade label, ±1 bp neutral. Inputs stop at the origin. Parent IDs, not overlapping candles, are bootstrap units. Three primary book-minus-reversal comparisons use Bonferroni-adjusted 98.333% intervals; other scores are descriptive.', '',
       '| Profile | Eligible / candidates | Coverage | Book / reversal / momentum accuracy | Book − reversal, pp [adjusted CI] |','|---|---:|---:|---|---:|']
for name,s in v04.items():
    scores=' / '.join(f"{100*s['rules'][k]['accuracy']:.2f}%" for k in ('book','reversal','momentum'))
    lines.append(f"| {name} | {s['origins']:,} / {s['candidate_origins']:,} | {100*s['coverage']:.2f}% | {scores} | {ci(s['book_minus_reversal_adjusted'],100,'bootstrap_ci')} |")
lines += ['', 'The frozen book rule beats reversal within all three declared host profiles after this familywise adjustment. The effect is smaller than comparison against momentum and differs by profile. This confirms a limited simulator association, not a calibrated entry probability or real-market effect. Source matching/removal artifacts still contaminate path history even after invalid-origin exclusion.', '',
       '| Profile | Locked/absent exclusions | Missing-depth exclusions | Book balanced accuracy | Book recall down / neutral / up |','|---|---:|---:|---:|---|']
for name,s in v04.items():
    rec=s['rules']['book']['per_class_recall']
    lines.append(f"| {name} | {s['exclusions'].get('locked_or_absent',0)} | {s['exclusions'].get('missing_depth',0)} | {100*s['rules']['book']['balanced_accuracy']:.2f}% | {' / '.join(f'{100*rec[str(k)]:.2f}%' for k in (-1,0,1))} |")
lines += ['', 'Full constant-rule, pilot-majority, momentum, reversal and book per-class recalls, predicted-class counts and origin counts are in analysis-final/v04-statistics.json. Low neutral recall and changing class balance matter; ordinary accuracy must not replace balanced/class-conditional reporting.', '',
       '## v0.5 size/depth and schedule robustness','',
       'Three profiles × 40 parents × 9 conditions = 1,080 scenario identities, with an untouched baseline in each parent/profile. All 1,080 completed and matched their warmed baseline fingerprint; exact aggregate cash/coin transfers reconcile at every recorded boundary. Both schedules achieved their intended quantities; no partial/zero-fill failures occurred in this finite study, which does not eliminate the confirmed boundary defects. There are 120 independent v0.5 parents, not 1,080 independent samples.', '',
       'Totals target 0.5× and 2× initial opposite-side depth within 10 bp, rounded upward to a multiple of five (minimum five). Actual ratios are reported because the small minimum/multiple materially changes low-depth sizes. One shot at origin versus five equal slices at 0/5/10/15/20. Cost is achieved-quantity VWAP versus the original arrival, signed by side. Twelve profile/side/size primary contrasts use Bonferroni-adjusted 99.583% intervals. Negative five-minus-one is cheaper.', '',
       '| Profile / side / target | Paired parents | Mean quantity / achieved depth ratio | Five − one cost, bp [adjusted CI] |','|---|---:|---|---:|']
for profile,d in v05['profiles'].items():
    for name,s in d['contrasts'].items():
        lines.append(f"| {profile} / {name} | {s['complete_pairs']} | {s['quantity']['mean']:.2f} / {s['actual_ratio']['mean']:.3f}× | {ci(s['slippage_adjusted'])} |")
lines += ['', 'Ten of twelve adjusted intervals include zero. Only the two maker30 / 2× contrasts exclude zero in favor of slicing, with endpoints near zero; finite-bootstrap Monte Carlo precision and the limited profile budget warrant caution. Therefore the earlier fixed-500-unit slicing result is not a universal execution rule. Preserve it as the original size/profile-specific finding; the new normalized-size study limits its generalization.', '',
       'Deadline outcomes are recorded at common origin +1/+5/+15/+30/+50, and at +1/+5/+15/+30 after the last fill. Common +50 uses 50 candles after the one-shot fill and 30 after the final slice; elapsed exposure is explicit. The +50 mark-to-market sensitivity is not an actual unwind. No fees, funding, latency, spread decomposition or opportunity-cost penalty is modeled. Total VWAP cost and actual fill quantity are separate from price movement and vendor display PnL. Baseline-relative outcomes can be reconstructed from the retained common-parent rows; no unmatched/native equality is claimed.', '',
       '## Triggered entry labels and matching','',
       'Walls were defined before the event using trailing quantity thresholds, five-boundary persistence and strictly positive distance within 10 bp. First eligible event per parent/side/strength only. Trigger is the earliest next-15-candle OHLC range spanning the frozen level; this is a touch proxy, not proof that a limit order fills. Target/stop are ±10 bp from that level, with a 30-candle horizon after touch. Untriggered events are retained.', '',
       'If either barrier appears in the trigger candle, its timing relative to touch is unknown, so the primary label is ambiguous. Subsequent same-candle double crossings also remain ambiguous. No wins are assigned from convenient OHLC ordering. A separately labeled complete-bar-after-touch sensitivity is recorded, but it is a different policy and cannot repair missing execution ordering.', '',
       '| Profile / level group | Signals / 60 parents | Triggered / untriggered | Win / loss / ambiguous / timeout | Success-probability bounds among triggered |','|---|---:|---:|---|---|']
for profile,s in v04.items():
    for name,e in s['entry'].items():
        o=e['outcomes'];b=e['success_bounds'];bounds=f'{100*b[0]:.2f}%–{100*b[1]:.2f}%' if b else 'unavailable'
        lines.append(f"| {profile} / {name} | {e['signals']} / 60 | {e['triggered']} / {e['untriggered']} | {' / '.join(str(o.get(k,0)) for k in ('win','loss','ambiguous','timeout'))} | {bounds} |")
lines += ['', 'The bounds are nearly [0,1]; these data cannot calibrate entry quality. A near-perfect result in the complete-bar sensitivity would not change that verdict: it discards the unobserved trigger-bar ordering and changes the policy.', '',
       'Strong/weak matching used no future outcomes: same profile and side, distance difference ≤2 bp, volatility ratio .8–1.25 and normalized-volume difference ≤.25. Greedy ties are deterministic and weak events are not reused. Before/after standardized covariate balance and unmatched counts are in entry-balance.json. Parent components are used because cross-parent matching can correlate pairs.', '',
       '| Profile | Matched pairs | Both triggered | Independent matching components | Paired success-difference bounds |','|---|---:|---:|---:|---|']
for profile,s in v04.items():
    m=s['matched_entry'];lines.append(f"| {profile} | {m['pairs']} | {m['both_triggered']} | {m['parent_components']} | {m.get('success_difference_bounds')} |")
lines += ['', 'Only 1–2 connected parent components remain per profile, so no reliable matched-pair bootstrap CI is claimed. Bounds remain [-1,1]. Matching reduces observable covariate differences but neither resolves ordered executions nor proves an effect. There is no 80% entry claim.', '',
       '## Native versus host and label acceptance','',
       'NATIVE-HOST-EQUIVALENCE.md documents initialization, five-sweep scheduler, frame-time differences, CLR/Mono randomness, manually seeded portfolios, profile selection and bypassed chart/bot/audio lifecycle. A fresh native v0.5 process supplied archived original screenshots for untouched baseline, one buy, repeated buy, reduction/close, one sell and close. Nominal lot 100 and net supply reconciliation agree behaviorally with prior checks. Exact native/host trajectories are not compared because state, RNG and scene parameters cannot be matched.', '',
       'Fresh native baseline paused at $102.96. Two paused buys moved last to $103.39 and $104.00. A documented resume refreshed +200 nominal units and supply fell by 200. Subsequent opposite actions closed both lots; another sell opened short, and a buy closed it. Final refreshed nominal size and worth are zero, supply returned to 1,787,178, and the app is verified paused/flat at $103.80, total display PnL −3.11. Stats refresh intervals advanced the market. These are behavioral observations, not equivalent-state execution-cost trials. Images and a numeric transcription are retained; full native cash/VWAP remains unavailable.', '',
       'TRAINING-DATA-DEFECT-REGISTER.md distinguishes confirmed code/fixture behavior from suspected consequences, including intratrade extrema, player-volume weighting, partial/zero fills and nominal positions, reservations/negative balances, unverified cancellation unlock, v0.4 equality/removal/pruning/counters and incomplete state/RNG restoration. **Current vendor outputs are rejected for trusted synthetic pretraining.** Exact diagnostic level arrays/ledgers do not repair unobserved trades or defective economy rules. No historical records were silently repaired.', '',
       '## Real BTC bridge: acquisition actually started','',
       'Public Binance USD-M BTCUSDT REST and routed WebSocket endpoints were reachable. A bounded 300-second engineering sample collected raw depth, aggregate executions, kline events, a depth snapshot, server time, instrument metadata and 1,500 recent one-minute exchange klines. No keys, signed/account requests or orders were used. Raw capture is preserved locally and a copy is included with these research artifacts for reviewer reproduction.', '',
       f"Captured {real['counts']['depthUpdate']:,} depth events and {real['counts']['aggTrade']:,} aggregate-trade events. Two pre-snapshot stale events were dropped; {real['counts']['depth_applied']:,} updates were applied, with zero detected pu gaps or crossed books. Top-20 snapshots retain exchange event/transaction and local receipt timestamps. Four complete captured minutes matched official OHLC; three also matched base volume exactly, while one differed by 0.001 BTC. Partial first/last minutes are explicitly excluded from completeness claims.", '',
       'This demonstrates feasible engineering acquisition, not a training dataset or a complete execution feed. The official aggregate stream groups market fills and excludes insurance/ADL trades; visible public depth excludes RPI orders. A finite depth snapshot also cannot certify every outside level. The volume discrepancy is retained, not patched. Raw messages retain first/last trade identifiers and aggregate IDs for subsequent coverage analysis.', '',
       '### Acquisition contract for the next pipeline stage','',
       '- One venue/instrument: Binance USD-M BTCUSDT perpetual. Verify exchange symbol status, contractType, base/quote/margin assets and quantity/price filters. Keep the spot prototype and 2023 unidentified-venue midpoint dataset separate.',
       '- Bootstrap by buffering routed public depth, fetching REST snapshot, dropping older events and requiring the documented U/u overlap. Thereafter require each pu to equal previous u. A gap or invalid/crossed state invalidates the segment until a fresh snapshot bridges buffered events. Never forward-fill a broken book as real liquidity. The bounded recorder has no daemon/reconnect/resnapshot loop; implement that before durable recording.',
       '- Store original payload, exchange event E and transaction/trade T, receive UTC nanoseconds, receive monotonic nanoseconds, connection/sequence/segment IDs, snapshot request/response times and clock-offset diagnostics. Base quantity in BTC; quote notional in USDT; use decimal arithmetic. Preserve local clock uncertainty and out-of-order/duplicate flags.',
       '- Build UTC minute candles from verified ordered executions: first/last trade, every price extreme, sum base and quote quantity. Do not force next open to prior close. Reconcile closed candles against the exchange; distinguish missing trade coverage, timestamp aggregation and source-specific excluded events. Official closed klines may support a separate candle-only experiment with explicit provenance; aggregate-derived volume is not silently substituted.',
       '- At forecast origin, save immutable exchange cutoff, maximum sequence/trade IDs, actual issuance and all input availability times. Inputs must be both exchange-time eligible and received by issuance. Late messages/revisions cannot retroactively alter stored forecasts. Score only matured targets; no real-market error panel exists before actual forward predictions.',
       '- Freeze historical same-venue candle/trade splits and a separate prospective book split. The existing proposal is 60/15/15 usable days for book fitting/validation/test with selection/calibration separated. A candle-only baseline can use independently acquired verified history sooner. Preserve entire days/segments, gaps and embargoes, fit scalers only on training data, and never choose a majority class from final test labels.', '',
       'Sources checked 1 November 2026: [Binance local-book sequencing](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly), [routed stream endpoints](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect), [public depth schema](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/public), [aggregate trade stream](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/market). These protocol facts are separate from the measured capture counts.', '',
       '## Updated feature dictionary and development gates','',
       '| Candidate | Live availability | Current decision |','|---|---|---|',
       '| Completed candle returns, body, range, wicks, base/quote volume | Same-venue verified candles/executions | Eligible after gap, unit and reconstruction checks; vendor v0.5 OHLC/volume rejected |',
       '| Spread, depth imbalance, distance to visible liquidity | Sequenced public book within covered depth | Candidate supported in declared simulator profiles; not demonstrated BTC skill |',
       '| Level persistence, additions/removals | Causal book history | Observable net-level feature; no individual order age, cancellation reason or hidden reserve implied |',
       '| Signed aggressive flow and impact | Public executions plus synchronized arrival book | Aggregated/excluded-trade coverage must be flagged; own exact costs require actual fills or a documented simulation |',
       '| Absorption/refill estimates | Book plus executions | Hypothesis with uncertainty; no calibrated hidden quantity or whale identity |',
       '| Agent inventory, RNG, player identity | Simulator internal only | Diagnostic/oracle fields, excluded from deployable predictor |',
       '| News, exact hidden liquidity, liquidation mechanics | Not supplied by these experiments | Deferred; do not invent labels from candle shape |', '',
       'The proposed 1,440-minute context and MLP baseline remain independent design choices. Next approved implementation can build the causal data pipeline and dataset validator. Before a small real-only baseline: enough valid origins, frozen target/horizon/splits, strongest frozen same-information baselines, leakage tests and metric units. Before synthetic pretraining: new valid event labels and economic invariants. Before entry calibration: triggered, cost-aware ordered outcomes and out-of-sample reliability. Before forward paper reporting: immutable real forecasts and matured outcomes. No training is started by this report.', '',
       '## Evidence integrity, deviations and coordination','',
       '- Fresh raw seeds/manifests are in v04/ and v05/; analysis-final contains unique origins, entry signals, paired summaries, balance and raw SHA256 catalogs. The earlier post-hoc baseline audit has its own file. All attempted runs are retained; the fixed budget has ended.',
       '- An initial derived analysis used low-price rather than entry-level denominator for trigger-bar lower-bound detection; this was corrected to the registered level-based threshold and retained as analysis/ versus authoritative analysis-final/. Primary direction and schedule results were unchanged. This is a documented arithmetic correction, not a new threshold selected for favorable outcomes.',
       '- Five new tests cover neutral reversal/frozen majority, trigger-bar ambiguity, level-denominator boundary and untriggered cases, outcome-blind matching, and sequence-gap invalidation until a fresh snapshot. Existing four analysis tests and preserved-evidence checks are also run. No native exact-state/RNG or clean synthetic-label claim is inferred from passing these tests.',
       '- Reviewer commit cb2ae3f was inspected and fast-forwarded while this work proceeded. The user authorized pushing the completed findings. A thread watcher checks incoming commits every 30 minutes, uses SHA tracking rather than author names and stays quiet when unchanged. It must not execute arbitrary incoming scripts or cross the training/trading/vendor-patch gates.', '',
       'Stop before training and present this plan for review. The handoff should request a bounded real-pipeline/dataset-validation stage, not another unlimited simulator scenario search.', '']
(D/'VALIDATION-DECISION.md').write_text('\n'.join(lines),encoding='utf-8')

# Manual transcription is linked to original native captures, not exact fills.
native=[('03-baseline-pause-verified','none',102.96,0,0),('04-buy-one','B',103.39,.22,0),('05-buy-repeat','B',104,1.16,0),
        ('06-refresh-two-lots','Space resume',103.80,.76,0),('07-pause-two-lots','Space pause',102.98,-.88,0),
        ('08-sell-reduce','S',102.43,-.99,-.81),('09-sell-close','S',102.13,0,-1.98),('10-sell-open-short','S',101.89,.12,-1.98),
        ('11-buy-close-short','B',103.29,0,-3.11),('12-final-stats-refresh','Space resume',103.40,0,-3.11),('14-final-verified','none',103.80,0,-3.11)]
(R/'native-v05/observations.json').write_text(json.dumps([dict(image=name+'.jpg',action=action,last_price_display=price,floating_display=floating,total_pnl_display=total,
     evidence_type='manual_transcription_of_native_capture',fill_quantity=None,fill_vwap=None) for name,action,price,floating,total in native],indent=2))

fig,axes=plt.subplots(1,2,figsize=(12,5.8),layout='constrained')
colors={'standard':'#167c80','sparse':'#a87538','maker30':'#746096'}
for i,(profile,s) in enumerate(v04.items()):
    x=s['book_minus_reversal_adjusted'];mean=x['parent_mean_delta']*100;lo,hi=np.array(x['bootstrap_ci'])*100
    axes[0].errorbar(mean,i,xerr=[[mean-lo],[hi-mean]],fmt='o',capsize=4,color=colors[profile])
axes[0].set(yticks=range(3),yticklabels=list(v04),xlabel='Book − reversal accuracy (percentage points)',title='v0.4: 60 fresh parents/profile\n98.333% parent-bootstrap intervals',ylim=(-.7,2.7))
labels=[];i=0
for profile,s in v05['profiles'].items():
    for contrast,c in s['contrasts'].items():
        x=c['slippage_adjusted'];mean=x['mean'];lo,hi=x['ci'];labels.append(profile+' '+contrast)
        axes[1].errorbar(mean,i,xerr=[[mean-lo],[hi-mean]],fmt='o',capsize=3,color=colors[profile]);i+=1
axes[1].set(yticks=range(i),yticklabels=labels,xlabel='Five slices − one shot execution cost (bp)',title='v0.5: 40 paired parents/profile\n99.583% parent-bootstrap intervals')
axes[1].invert_yaxis()
for ax in axes:
    ax.axvline(0,color='#8893a5',linestyle='--');ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15)
fig.suptitle('Frozen fresh-seed host validation — not native trajectory equivalence or BTC performance',fontsize=12)
fig.savefig(R/'analysis-final/validation-summary.png',dpi=160);plt.close(fig)
(R/'stage-decisions.json').write_text(json.dumps(dict(A='ready_for_data_pipeline_implementation',B='conditional_on_real_dataset_chronology_and_leakage_checks',
    C='not_ready_uncorrected_synthetic_labels',D='not_ready_ordering_and_calibration',E='deferred_until_frozen_forecasts_and_matured_outcomes',training_authorized=False),indent=2))
print(D/'VALIDATION-DECISION.md')
