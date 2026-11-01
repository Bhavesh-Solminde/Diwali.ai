"""Build review artifacts from recorded diagnostics, without fitting or simulation."""
import gzip
import json
import re
from collections import Counter
from pathlib import Path
import importlib.util

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
FLOW = ROOT/'results/simulator_research/flow-2026-11-01'
REPEAT = ROOT/'results/simulator_research/repeat-2026-11-01'
DOCS = ROOT/'docs/planning/windows-simulator-findings-2026-11-01'
spec=importlib.util.spec_from_file_location('flow',Path(__file__).with_name('analyze-flow.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
f=json.loads((FLOW/'main-analysis/statistics.json').read_text())
r=json.loads((REPEAT/'main-analysis/statistics.json').read_text())
main=f['summaries']['main']
rep=r['summaries']['main']


def ci(x, scale=1):
    if not x.get('n'):
        return 'unavailable'
    bounds=x.get('parent_bootstrap_mean_ci95')
    return f"{x['mean']*scale:.2f}"+(f" [{bounds[0]*scale:.2f}, {bounds[1]*scale:.2f}]" if bounds else '')


with gzip.open(FLOW/'main-analysis/origins.jsonl.gz','rt') as stream:
    origins=[json.loads(line) for line in stream]
volume_results={}
for stratum in ('low','middle','high'):
    group=[x for x in origins if x['phase']=='main' and x['group']=='all' and x['book'] is not None and x['volume_stratum']==stratum]
    parents=sorted({x['run_id'] for x in group})
    delta=[np.mean([int(x['book']==x['actual'])-int(x['momentum']==x['actual']) for x in group if x['run_id']==p]) for p in parents]
    volume_results[stratum]=dict(origins=len(group),parents=len(parents),book_minus_momentum=module.interval(delta))
(FLOW/'main-analysis/volume-strata.json').write_text(json.dumps(volume_results,indent=2))

fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
names=['No signal\n(neutral)','Recent\ndirection','Depth\nimbalance']
for i,key in enumerate(('neutral','momentum','book')):
    stat=main['rule_comparisons']['all']['scores'][key]['parent_accuracy']
    mean=100*stat['mean'];low,high=np.array(stat['parent_bootstrap_mean_ci95'])*100
    axes[0].bar(i,mean,color=['#8893a5','#b58953','#167c80'][i],width=.6)
    axes[0].errorbar(i,mean,yerr=[[mean-low],[high-mean]],fmt='none',ecolor='#202733',capsize=5)
axes[0].set(xticks=range(3),xticklabels=names,ylabel='Mean parent accuracy (%)',ylim=(0,70),title='v0.4: fixed next-candle rules')
for i,side in enumerate(('buy','sell')):
    stat=rep['paired_schedule'][side]['slippage_repeat_minus_one_bp'];mean=stat['mean'];low,high=stat['parent_bootstrap_mean_ci95']
    axes[1].errorbar(mean,i,xerr=[[mean-low],[high-mean]],fmt='o',color='#167c80',capsize=5,markersize=8)
axes[1].axvline(0,color='#8893a5',linestyle='--')
axes[1].set(yticks=[0,1],yticklabels=['Buy','Sell'],xlabel='Slippage: five slices minus one shot (bp)',title='v0.5: equal intended quantity 500',ylim=(-.6,1.6))
for ax in axes:
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='x' if ax==axes[1] else 'y',alpha=.15)
fig.suptitle('Original-DLL host diagnostics — 30 main parents per version\n95% parent bootstrap intervals; not native Unity or BTC results',fontsize=12)
fig.savefig(FLOW/'main-analysis/research-summary.png',dpi=170)
plt.close(fig)

doc=['# Research review: extended experiments before model training',
     '', '1 November 2026. No model fitting, trading or binary modification. The new experiments are **original-DLL CLR diagnostics outside Unity**, separate from the earlier native control observations. Native activation failed twice on this continuation (including refreshed selection); no new app inputs were sent. No fresh native screenshot/recording was obtained. This report does not mark the full native research request complete.',
     '', '## Evidence and environment', '',
     '- Existing evidence:720 host scenarios/25,200 observations and separate native control pass. New evidence:40 untouched v0.4 parents and200 v0.5 scenarios from40 parents. Ten pilot andthirty main parents per version. Sibling v0.5 conditions share a parent.',
     '- v0.4 new raw records:24,000 base-candle rows (100warmup+500observed per parent;20,000post-warmup rows). v0.5 new raw records:10,200observations (51 per scenario). These counts include pilots; analysis uses separate phases. There are80 new parent states, not240 independent scenarios plus parents.',
     '- Build identity: preserved Windows Assembly-CSharp SHA256 v0.4 `F1F99D934A6F8AE98360C931F90F8E1294E1B9384F5E914A2970F7C2B9FA8024`; v0.5 `067EB14F626E4E5B33A8BA9D2551A1B343246AB300F2D49635471F9604E4A56C`. Complete executable/player hashes remain in the existing evidence manifest and were rechecked.',
     '- Native logs previously verify v0.4 Unity6000.0.16f1 and v0.5 Unity6000.3.17f1 on this PC; rendering and controls were observed previously. Host scene:200agents, maker/request .1, activity/sweep .1, drop/candle .1, startprice10000raw cents, five sweeps/base candle. These are declared research settings, not extracted native scene parameters. Current native nominal lot100 was separately observed; trader count, aggregation and retention remain unmeasured.',
     '- Price unit raw cents; bp=10000*(future/reference−1). v0.4 volume is executed quantity from original code; it has no BTC calibration. v0.5 source volume weights player quantity100x and source OHLC omits intratrade extremes, so the new v0.5 analysis uses last trade and exact cash/coin transfers, not those labels. A base candle is five agent sweeps, never automatically a minute.',
     '- Protocols:PREREGISTRATION-B.md and PREREGISTRATION-C.md precede collection. No thresholds tuned using main outcomes. Mean intervals use2000parent bootstrap samples. Multiple exploratory comparisons are not multiplicity-adjusted.',
     '', '## v0.4: predefined observable-book rules', '',
     f"Main candidate origins:14,100 (470 per parent, preserving30future candles). Locked/absent-book exclusions:{sum(x['excluded_locked_or_absent_origins'] for x in f['runs'] if x['phase']=='main')}. Common fixed-rule grid:{main['rule_comparisons']['all']['origins']}; the remaining valid origins lack measurable10-bp depth and are excluded from the shared rule comparison. All outcomes are next completed base-candle last-trade direction, neutral within±1bp.", '',
     '| Fixed rule | Origin-weighted accuracy | Balanced accuracy | Mean parent accuracy [95% CI] |', '|---|---:|---:|---:|']
for name,key in [('No signal:always neutral','neutral'),('Previous candle direction','momentum'),('10-bp imbalance ±0.2','book')]:
    s=main['rule_comparisons']['all']['scores'][key]
    doc.append(f"| {name} | {s['accuracy']*100:.2f}% | {s['balanced_accuracy']*100:.2f}% | {ci(s['parent_accuracy'],100)}% |")
doc += ['', f"Book minus recent-direction mean parent accuracy:{ci(main['rule_comparisons']['all']['book_minus_momentum_parent_accuracy'],100)} percentage points. This supports testing observable depth in this simulator. It does not establish real BTC forecast skill, calibrated entry odds or an incremental trained-model improvement. Missing-depth exclusions reduce coverage; the source's locked-book, quantity/removal artifacts and random anchoring can generate this association.", '',
        '| Predetermined pattern stratum | Origins / parents | Book minus recent direction, pp [95% CI] |', '|---|---:|---:|']
for pattern in ('range','triangle','flag'):
    s=main['rule_comparisons'][pattern]
    doc.append(f"| {pattern} | {s['origins']} / {s['parents']} | {ci(s['book_minus_momentum_parent_accuracy'],100)} |")
doc += ['', 'These compare fixed rules within pattern strata. They are not a candle-pattern classifier or a complete matched shape-only versus book ablation. In particular, the flag-stratum interval includes no benefit; no universal claim about patterns follows.', '',
        '| Trailing-volume stratum | Origins / parents | Book minus recent direction, pp [95% CI] |','|---|---:|---:|']
for name,s in volume_results.items():
    doc.append(f"| {name} | {s['origins']} / {s['parents']} | {ci(s['book_minus_momentum'],100)} |")
doc += ['', 'Volume thresholds use only the prior100completed candles. These strata do not identify a real session or isolate the three built-in sinusoidal quantity phases. Maker choice is per request; prior code finds triangular placement, not normal placement, and no individual order-aging clock. No real-world session timezone is inferred.', '',
        '## v0.4: naturally persistent levels, failures and removal', '',
        'A wall requires5sampled boundaries of persistence, within10bp, and quantity above the trailing90th percentile. Weak levels use the trailing median cutoff. First eligible event per side/strength per parent only. Target/stop are±10bp from **origin**, not first-touch entries. Both barriers in one future OHLC candle remain ambiguous. Strong/weak events occur at different times; distance, volatility and volume are not matched. These are observational reaction diagnostics.', '',
        '| Level group | Parents | Target / stop / ambiguous / timeout | Mean side-favorable30-candle return bp [95% CI] |','|---|---:|---|---:|']
for key,s in main['walls'].items():
    o=s['outcomes'];counts=' / '.join(str(o.get(k,0)) for k in ('target','stop','ambiguous','timeout'))
    doc.append(f"| {key} | {s['parents']} | {counts} | {ci(s['returns']['30'])} |")
totals=Counter()
large=Counter()
for run in f['runs']:
    if run['phase']=='main':
        audit=f['audits'][run['run_id']];totals.update(audit['changes']);large.update(audit['removal_events_pre_quantity_over30'])
doc += ['', f"Across30main parents (including their100warmup boundaries), the recorder attributed {totals['random_removal_removed_qty']:,} units / {totals['random_removal_changed_levels']:,} changed levels to random-removal calls and {totals['price_pruning_removed_qty']:,} units / {totals['price_pruning_changed_levels']:,} changed levels to pruning. Random-removal events with pre-removal level quantity>30:{large.get('random_removal',0)}. This supports the documented large-level exemption. Call provenance distinguishes these removals; ordinary sweep changes remain **net** changes, so individual fill sizes, gross refill and same-sweep disappear/reappear histories are unavailable.",
        '', 'Large-bid positive outcomes coexist with failed long-horizon cases; ask results do not show a symmetric favorable mean. Large within-candle ambiguity prevents turning target counts into an80%entry probability. Level persistence is a history feature, not individual order age. Within-sweep persistence and causal history dependence remain unresolved.', '',
        '| Candle proxy | Events / parents | Mean parent next-candle return bp [95% CI] |','|---|---:|---:|']
for key,s in main['proxies'].items():
    doc.append(f"| {key} | {s['events']} / {s['parents']} | {ci(s['parent_mean_return_1_bp'])} |")
doc += ['', 'Sweep proxy means high range plus high volume, not a verified single aggressive sweep. Absorption candidate means high volume, small body and low range, not known hidden reserve. Both next-return intervals cross zero. Net depth replenishment can be inspected in the raw changes; gross refill/execution decomposition needs finer event capture. No directional absorption edge is established.', '',
        '## v0.5: equal total quantity, repeated interventions and recovery','',
        'New main comparisons:30parents×5conditions=150scenario identities. Untouched baseline plus buy/sell500atonce or five100-unit orders atbasecandles0/5/10/15/20. All requested500units filled in every completed intervention scenario; no partial fills or execution errors occurred in this profile. Partial/zero-fill defects remain established by earlier fixtures, not removed by these successes. Warmup fingerprints matched baseline for every sibling. Exact per-order notional/quantity and all followup horizons are retained.', '',
        '| Condition | Main parents | Mean total slippage bp [95% CI] | First→last100-unit impact, bp | Censored half-impact recovery /30 |','|---|---:|---:|---|---:|']
for name in ('buy_one500','sell_one500','buy_repeat100','sell_repeat100'):
    s=rep['scenarios'][name]
    impact=f"{s['first_order_impact_bp']['mean']:.2f}→{s['last_order_impact_bp']['mean']:.2f}" if 'repeat' in name else 'single500-unit order'
    doc.append(f"| {name} | {s['completed']} | {ci(s['total_signed_slippage_bp'])} | {impact} | {s['recovery_censored_or_nonpositive_impact']} |")
doc += ['', '| Paired repeated-minus-one-shot contrast | Slippage bp [95% CI]; negative is cheaper | Common-origin+50return difference bp [95% CI] |','|---|---:|---:|']
for side,s in rep['paired_schedule'].items():
    doc.append(f"| {side} | {ci(s['slippage_repeat_minus_one_bp'])} | {ci(s['common_origin_return50_repeat_minus_one_bp'])} |")
doc += ['', 'The larger500-unit study supports cheaper average execution for this five-slice schedule in this profile. Earlier equal-total10-unit tests had intervals including zero; the new result does not overturn those smaller-size findings or establish a universal schedule. Time exposure differs: the final repeated order is20candles after origin. Full results report both common-origin and last-fill horizons. No fee or opportunity-cost model is included.', '',
        f"Last-minus-first100-unit impact:buy {ci(rep['scenarios']['buy_repeat100']['last_minus_first_impact_bp'])}bp; sell {ci(rep['scenarios']['sell_repeat100']['last_minus_first_impact_bp'])}bp. Both intervals include zero. This does not establish systematic weakening/strengthening or identify inventory as the cause. Recovery is measured relative to the **last order's own arrival and impact**, censored at30candles. One-shot and repeated final-order recovery involve different quantities and elapsed time and are not a fair efficacy comparison.", '',
        f"Ordinary untouched main baselines ended with negative-cash agents in {rep['scenarios']['baseline']['negative_cash_parent_count']}/30parents and negative-coin agents in {rep['scenarios']['baseline']['negative_coin_parent_count']}/30; categories may overlap. All200pilot+main scenarios passed synchronous player-transfer and ordinary-only conservation checks at every recorded boundary. Aggregate conservation coexists with invalid individual collateral. Neither finite initial balances nor conserved totals establish a realistic closed economy under unlimited-player interventions.", '',
        'Existing round-trip evidence remains separate:exact-ledger size10main buy/sell roundtrips had negative mean cash PnL, with buy uncertainty including zero. New500-unit tests did not unwind; favorable movement is not realized profit. Native display PnL is quantity-defective and cannot substitute for either ledger.', '',
        '## Data dictionary and export verdict','',
        '| Field family | Availability | Valid use / restriction |','|---|---|---|',
        '| OHLC/base volume | Numeric host v0.4; visual native only | Source artifacts persist; no minute/BTC calibration |',
        '| Last-trade returns at1/5/15/30 | Numeric in both hosts | Future labels only; no future feature leakage |',
        '| bids/asks price–quantity boundary arrays | Numeric diagnostic host | Recompute totals; reject crossed/absent books; real-feed observable analog |',
        '| Level persistence/distance | Boundary-array derived | Causal observable feature, not individual age or identity |',
        '| cause-tagged net changes | Host wrapper call provenance | Random/pruning exact; agent-sweep net only; not native export |',
        '| Volume/shape absorption or sweep proxy | Prior/current completed candles | Hypothesis only; cannot expose hidden quantity or participant |',
        '| Intended,filled,notional,VWAP,arrival | Synchronous v0.5 host ledger | Actual transfers; include partial/zero-fill failures; no fee inferred |',
        '| Agent cash/coins/negative balances,RNG | Simulator-only | Diagnostic/oracle only; exclude deployable predictor |',
        '| Individual order IDs,age,cancellations,gross refill | Unavailable here | Do not fabricate from net bars |',
        '| Exchange timestamps,funding,news,hidden reserves,liquidations | Unavailable in these experiments | No invented labels or live-minute mapping |',
        '', 'No supported native numeric export, seed UI, complete replay or headless interface has been verified. v0.5 backup throws in isolated original methods; both snapshots omit sufficient state/RNG. Reinitializing seeded host objects supplies paired research states; it is not app restore. The new host records improve diagnostic coverage but are **not certified training records**. Full serialized scene parameters remain unavailable. Current visual recordings can measure displayed price/PnL/nominal position and approximate geometry, not exact fills/depth/event causes.', '',
        '## Research-to-model changes and review proposal','',
        '| Previous assumption | Evidence | Revised decision |','|---|---|---|',
        '| Shape alone describes the next candle | Fixed imbalance beats recent direction in this host; flag result uncertain | Compare candles-only,book-added,book+executions on identical real held-out origins; no claimed real advantage |',
        '| Persistent wall means reliable support/resistance | Failed long paths, ambiguous barriers, removal exemption | Keep distance/persistence with uncertainty; test source-rule sensitivity; no80%entry label |',
        '| High-volume wick identifies absorption/whale |33candidates across21parents; return interval crosses zero | Treat as observable proxy only; require signed trades and gross refill before causal interpretation |',
        '| Small and large execution schedules behave alike | Larger500unit slicing contrast differs from earlier10unit inconclusive result | Include size/depth and schedule interactions; test unseen sizes and parameter families |',
        '| Repeated impact necessarily weakens as agents deplete | First-last intervals include zero; collateral invalid | No enforced exhaustion/recovery assumption; independently validate reservations and balances |',
        '| Native lot equals code initializer10 | Prior native panel confirms nominal100 | Separate scene overrides from host configuration and physical achieved quantity |',
        '| Better simulator direction score means profitable BTC entries | No real-market or cost-aware entry test; source defects | Retain simple baselines and train/evaluate only after separate review and data validation |',
        '', 'Retain the1,440completed-minute context and MLP/sequence comparisons as independent design proposals, not verified Tiger architecture. No model has been fitted in this work. A corrected independent event engine needs equality/FIFO,collateral,cancel-unlock,zero/partialfill,per-tradeOHLC/volume and full-state/RNG tests before synthetic pretraining. Calibrate only from training-period real observations.', '',
        'Split synthetic data by whole parent and scenario family, keeping all windows/siblings together; hold out sizes/settings. Fit normalizers on training data only. Compare real-only against synthetic-pretrained on the same untouched realBTCUSDTperpetual test. Simulator-only portfolios/RNG remain oracle diagnostics. Proposed real data periods and acquisition gates remain in the frozen protocol.', '',
        '| Evaluation panel | Required computation |','|---|---|',
        '| Training | Fitted origins only; separate synthetic/real; loss and component errors; not generalization |',
        '| Past unseen | Frozen chronological real test after validation/calibration; USDT MAE/RMSE,MSE in USDT²,bp=10000*error/origin; component OHLC/base-volume; strongest fixed-direction/last-close baselines |',
        '| Recent real-market | Only matured immutable real forward predictions;24h plus7day context; pending/late/gapped counts; no simulator segment relabeled as live |',
        '| Probability/interval | Proper log/Brier loss;50/80/90%coverage and width; reliability with denominators; no accuracy conversion from MSE |',
        '| Entry | Target-before-stop within fixed expiry;timeouts,ambiguoussides,coverage; realized cash/achievedquantity; executable bid/ask,latency,fees,slippage,funding; mean net return with day-block uncertainty |',
        '', 'Do not interpret this fixed-rule simulator accuracy as a calibrated probability or release candidate. Keep forecast quality and paper-entry expectancy separate. Retain frozen1ATR14stop/2ATR14target/15minute expiry and cost stress assumptions as proposals until reviewed; no live orders.', '',
        '## Reproducibility, failures and remaining blockers','',
        '- Per-run manifests,seeds,raw compressed book arrays/net changes,fill ledgers,derived event/origin files,statistics and SHA256 catalogs are under the two new results directories. Existing evidence is preserved. Native control screenshots remain in the earlier chat record; no new native visual evidence accompanies these host runs.',
        '- Flow attempt `raw/flow-v04-31000` failed before candle0because of IDictionary enumeration conversion. `raw-v2` retains the corrected ten-parent pilot. `raw-validated` repeats the same pilot seeds with additional reference-scheduler validation and adds the30main parents. Those reruns are the **same** pilot parents, not extra samples. Earlier pilot-analysis used a bid-distance denominator corrected to origin price before main analysis; both analyses remain preserved. This was an implementation correction, not outcome-based threshold selection.',
        '- All40final flow runs reconstructed every boundary book exactly from change records and passed candle invariants. The first pilot/main parent also matched the original scheduler fingerprint and candle values for600steps. All200new v0.5scenarios passed fill/transfer checks; no execution failures/partialfills in this profile. Four analysis tests passed:future-invariant pattern inputs,neutral boundaries,ambiguous same-candle barriers,and short/timeout outcomes.',
        '- Pilot SD of parent book-minus-momentum accuracy difference:3.68percentagepoints. Rough normal80%power planning for a5ppdifference gives~5parents before clustering/regime/multiplicity concerns;30was retained. Pilot paired schedule-slippage SD:10.50bp buy/11.87bp sell; a5bpcontrast gives~35/~45parents under an approximate normal formula. Thus30main parents are an initial result, not blanket adequate power; future confirmatory multi-profile study should budget at least these counts plus regime/multiplicity allowance.',
        '- Remaining blockers:current native window activation; no verified native numeric exporter; exact per-fill native accounting; natural first-touchmatched wall/bounce test; individual cancellation/age/gross refill; finer signed flow; source-defect sensitivity and broader scene profiles; real-market transfer. The new diagnostics do not silently close those requirements. A supported creator export or separately approved corrected instrumentation is needed for rigorous native datasets.',
        '', 'Stop before training. Review the evidence, limits and independent-engine/real-data proposal first.', '',
        '![Research diagnostics](../../../results/simulator_research/flow-2026-11-01/main-analysis/research-summary.png)', '']
text='\n'.join(doc)
for old,new in {
    'andthirty':'and thirty','and200':'and 200','from40':'from 40','There are80':'There are 80','not240':'not 240',
    'Unity6000':'Unity 6000','startprice10000raw':'starting price 10,000 raw','lot100':'lot 100','quantity100x':'quantity 100x',
    'use2000parent':'use 2,000 parent','preserving30future':'preserving 30 future','measurable10-bp':'measurable 10-bp',
    'within±1bp':'within ±1 bp','requires5sampled':'requires 5 sampled','within10bp':'within 10 bp',
    'trailing90th':'trailing 90th','are±10bp':'are ±10 bp','Across30main':'Across 30 main','their100warmup':'their 100 warmup',
    'an80%entry':'an 80% entry','side-favorable30-candle':'side-favorable 30-candle',
    'buy/sell500atonce':'buy/sell 500 at once','five100-unit':'five 100-unit','atbasecandles0/5/10/15/20':'at base candles 0/5/10/15/20',
    'requested500units':'requested 500 units','First→last100-unit':'First→last 100-unit','single500-unit':'single 500-unit',
    'Common-origin+50return':'Common-origin +50 return','larger500-unit':'larger 500-unit','equal-total10-unit':'equal-total 10-unit',
    'is20candles':'is 20 candles','Last-minus-first100-unit':'Last-minus-first 100-unit',
    'All200pilot+main':'All 200 pilot + main','size10main':'size 10 main','New500-unit':'New 500-unit',
    'the1,440completed-minute':'the 1,440 completed-minute','realBTCUSDTperpetual':'real BTCUSDT perpetual',
    'separate synthetic/real; loss':'separate synthetic/real; loss','24h plus7day':'24h plus 7-day',
    'USDT MAE/RMSE,MSE':'USDT MAE/RMSE, MSE','50/80/90%coverage':'50/80/90% coverage',
    'ambiguoussides':'ambiguous sides','1ATR14stop/2ATR14target/15minute':'1 ATR14 stop / 2 ATR14 target / 15-minute',
    'before candle0because':'before candle 0 because','first pilot/main parent':'first pilot/main parent',
    'Thirty':'Thirty','fixed901':'fixed 901','normal80%power':'normal 80% power','a5ppdifference':'a 5 pp difference',
    'gives~5parents':'gives ~5 parents','30was':'30 was','a5bpcontrast':'a 5 bp contrast','500unit':'500 unit',
    'no80%entry':'no 80% entry','33candidates':'33 candidates','across21':'across 21','Larger500':'Larger 500',
    'earlier10':'earlier 10','initializer10':'initializer 10','nominal100':'nominal 100','frozen1':'frozen 1',
    'adds the30':'adds the 30','All40final':'All 40 final','for600':'for 600','All200new':'All 200 new',
    '3.68percentagepoints':'3.68 percentage points','Thus30':'Thus 30','gives~35':'gives ~35',
    'partialfills':'partial fills','partialfill':'partial fill','per-tradeOHLC':'per-trade OHLC',
    'achievedquantity':'achieved quantity','first-touchmatched':'first-touch matched',
}.items():
    text=text.replace(old,new)
text=re.sub(r'(?<=\d)(?=(?:agents|parents|parent|units|unit|observations|future|completed|post-warmup|warmup|observed|sampled|bp\b|candles|candle|main\b|pilot\b|scenario|conditions|steps|next|day\b|independent|coin|stop|target|minute|records))',' ',text)
text=re.sub(r':(?=[A-Za-z0-9])',': ',text)
text=re.sub(r',(?=[A-Za-z])',', ',text)
text=re.sub(r';(?=[A-Za-z0-9])','; ',text)
text=text.replace('100 warmup+500 observed','100 warmup + 500 observed').replace('30 parents×5 conditions=150 scenario','30 parents × 5 conditions = 150 scenario')
text=text.replace('return bp','return bp').replace('impact: buy','impact: buy')
text=text.replace('## Reproducibility, failures and remaining blockers',
    'Metric definitions for the proposed real-data evaluation: MAE = mean(|prediction − actual|), MSE = mean((prediction − actual)²), and RMSE = sqrt(MSE). Prices use USDT, squared USDT for MSE, and 10,000 × error / origin-close for bp. Combined HLCV = mean of absolute errors in log(H/origin), log(L/origin), log(C/origin), and log(1 + base-volume), each divided by its training-only standard deviation (floor 1e−8). Multiclass Brier = mean(sum_k(p_k − 1[y=k])²); log loss = −mean(log(p_actual)); interval coverage = matured targets inside the interval / all eligible matured targets. Direction uses the fixed ±1 bp neutral band. Entry outcomes must retain target-first, stop-first, timeout and unresolved same-candle ambiguity; net cash PnL = closed-quantity proceeds minus matching entry cost, fees, slippage and funding, with residual inventory marked separately. No entry probability or live recent-error panel has been measured by these simulator experiments.\n\n## Reproducibility, failures and remaining blockers')
text=text.replace('All200new','All 200 new').replace('All 200 new v0.5 scenarios passed','All 200 new v0.5 scenarios passed')
text=text.replace('Four analysis tests passed:', 'A compatibility rerun of the original 720-scenario host reproduced all six prior CSV hashes after the small API refactor; those are not additional independent samples. Four analysis tests passed:')
(DOCS/'RESEARCH-REVIEW-EXTENDED.md').write_text(text,encoding='utf-8')
print(DOCS/'RESEARCH-REVIEW-EXTENDED.md')
