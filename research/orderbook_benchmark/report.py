"""Render ten actual-versus-predicted direction charts and an offline report."""
import argparse
import base64
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from .data import ROOT, CLASSES

COLORS = {"TLOB": "#5B4AE6", "DeepLOB": "#E17135"}
LABELS = ["UP", "FLAT", "DOWN"]
CLASS_COLORS = ["#13846D", "#67748A", "#C74553"]
BG = "#F7F8FC"
INK = "#19243B"


def pretty_time(value):
    return pd.Timestamp(value).tz_convert("Asia/Kolkata").strftime("%d %b %Y · %H:%M IST")


def draw_path(ax, book, position, compact=False):
    past = book.mid.iloc[position - 300:position + 1].to_numpy()
    future = book.mid.iloc[position:position + 61].to_numpy()
    current = past[-1]
    past_bps, future_bps = np.log(past / current) * 1e4, np.log(future / current) * 1e4
    ax.axhspan(-1, 1, color="#E7EAF2", alpha=.8, zorder=0)
    ax.axvspan(0, 1, color="#E5EBF7", alpha=.5, zorder=0)
    ax.axvspan(-127 / 60, 0, color="#F3F5F9", zorder=0)
    ax.plot(np.arange(-300, -126) / 60, past_bps[:174], color="#B7C0D0", lw=1.5)
    ax.plot(np.arange(-127, 1) / 60, past_bps[-128:], color="#8B97AD", lw=1.5)
    ax.plot(np.arange(61) / 60, future_bps, color=INK, lw=2.2)
    ax.axvline(0, color="#687995", ls="--", lw=.9)
    ax.scatter([1], [future_bps[-1]], color=CLASS_COLORS[0 if future_bps[-1] > 1 else 2 if future_bps[-1] < -1 else 1],
               s=35, zorder=5, edgecolors="white", linewidths=.8)
    ax.axhline(0, color="#C6CDDC", lw=.7)
    ax.set_xlim(-5, 1.15)
    ax.grid(axis="y", color="#E2E6EE", lw=.7)
    ax.set_xlabel("Minutes from prediction", fontsize=8 if compact else 10, color="#68748B")
    ax.set_ylabel("Price change (basis points)", fontsize=8 if compact else 10, color="#68748B")
    ax.tick_params(labelsize=8 if compact else 9, colors="#68748B")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#D8DFEB")
    ax.set_facecolor("white")
    return float(future_bps[-1])


def prediction_text(row, name):
    pred, actual = int(row[f"{name}_prediction"]), int(row.actual)
    confidence = row[f"{name}_p_{CLASSES[pred]}"]
    return f"{name}: {LABELS[pred]} {confidence:.0%} · {'RIGHT' if pred == actual else 'WRONG'}"


def render(output):
    output = Path(output)
    summary = json.loads((output / "summary.json").read_text())
    cases = pd.read_csv(output / "cases.csv")
    frozen = json.loads((output / "frozen-cases.json").read_text())
    book = pd.read_parquet(ROOT / "seconds.parquet", columns=["mid"])
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK, "axes.titlecolor": INK,
                         "savefig.facecolor": BG, "figure.facecolor": BG})
    charts = output / "charts"
    charts.mkdir(exist_ok=True)
    for number, row in enumerate(cases.itertuples(index=False), 1):
        # Use Series to preserve column access with model names.
        r = cases.iloc[number - 1]
        position = int(r.position)
        fig = plt.figure(figsize=(10.5, 7.2), layout="constrained")
        grid = fig.add_gridspec(2, 1, height_ratios=[2.5, 1.25])
        ax, bars = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
        change = draw_path(ax, book, position)
        fig.suptitle(f"{number:02d}  {r.title}\n{pretty_time(r.timestamp)}", x=.06, ha="left", fontsize=16, fontweight="bold")
        ax.set_title(f"Actual next-minute move: {LABELS[int(r.actual)]}  ({change:+.2f} bps)  |  Midpoint {r.current_mid:,.2f} → {r.actual_mid_60s:,.2f}",
                     loc="left", fontsize=10, pad=13)
        ax.legend(handles=[Line2D([0], [0], color="#8B97AD", lw=2, label="Observed history"),
                           Line2D([0], [0], color=INK, lw=2, label="Real next minute"),
                           Patch(facecolor="#E7EAF2", label="Flat band: ±1 bp")], loc="upper left", fontsize=8, frameon=False)
        centers = np.arange(3)
        for offset, name in [(-.18, "TLOB"), (.18, "DeepLOB")]:
            p = np.array([r[f"{name}_p_{cls}"] for cls in CLASSES])
            bars.bar(centers + offset, p, width=.32, label=prediction_text(r, name), color=COLORS[name], zorder=3)
        bars.set_xticks(centers, LABELS)
        bars.set_ylim(0, 1)
        bars.set_ylabel("Model probability", fontsize=10, color="#68748B")
        bars.grid(axis="y", color="#E2E6EE", zorder=0)
        bars.legend(loc="upper right", fontsize=9, frameon=False)
        bars.tick_params(colors="#68748B")
        for spine in bars.spines.values():
            spine.set_visible(False)
        bars.set_facecolor("white")
        fig.supxlabel("Five-minute case context shown; models use only the last 128 seconds. LOBERT / LOBS5: unavailable.",
                      fontsize=9, color="#68748B")
        fig.savefig(charts / f"{number:02d}-{r['case']}.png", dpi=160)
        plt.close(fig)
    fig, axes = plt.subplots(5, 2, figsize=(14, 17), layout="constrained")
    fig.suptitle("BTC order-book forecasts · 10 different cases", fontsize=22, fontweight="bold", x=.06, ha="left")
    for number, ax in enumerate(axes.flat, 1):
        r = cases.iloc[number - 1]
        change = draw_path(ax, book, int(r.position), compact=True)
        ax.set_title(f"{number:02d}  {r.title}\n{pretty_time(r.timestamp)}", loc="left", fontsize=11, fontweight="bold", pad=8)
        text = (f"REAL: {LABELS[int(r.actual)]} ({change:+.2f} bps)\n"
                f"{prediction_text(r, 'TLOB')}\n{prediction_text(r, 'DeepLOB')}")
        ax.text(.025, .97, text, transform=ax.transAxes, ha="left", va="top", fontsize=8,
                bbox={"boxstyle": "round,pad=.5", "fc": "white", "ec": "#DFE4ED", "alpha": .94})
    fig.supxlabel("Gray: observed history · Black: real next minute · Shaded horizontal band: FLAT (±1 bp)\n"
                  "Five-minute case context shown; models use only the last 128 seconds. Predictions are direction classes.\n"
                  "LOBERT and LOBS5 were audited but could not be run. Historical demonstration; no profitability claim.",
                  fontsize=10, color="#68748B")
    fig.savefig(output / "ten-cases.png", dpi=160)
    plt.close(fig)
    write_reports(output, summary, cases, frozen)


def write_reports(output, summary, cases, frozen):
    ranked = summary["ranking_of_runnable_models"]
    rows = []
    for name in ranked:
        m = summary["models"][name]
        rows.append({"model": name, "status": "Trained and tested", "cases": f"{m['cases']['correct']}/10",
            "test": f"{m['test']['accuracy']:.2%}", "balanced": f"{m['test']['balanced_accuracy']:.2%}",
            "f1": f"{m['test']['macro_f1']:.3f}"})
    for name in ("LOBERT", "LOBS5"):
        rows.append({"model": name, "status": "Unavailable", "cases": "—", "test": "—", "balanced": "—", "f1": "—"})
    table = "| Model | Status | Right in 10 cases | Full-test accuracy | Balanced accuracy | Macro F1 |\n|---|---|---:|---:|---:|---:|\n"
    table += "\n".join(f"| {r['model']} | {r['status']} | {r['cases']} | {r['test']} | {r['balanced']} | {r['f1']} |" for r in rows)
    baselines = "| Baseline | Full-test accuracy | Balanced accuracy |\n|---|---:|---:|\n"
    baselines += "\n".join(f"| {name} | {m['test']['accuracy']:.2%} | {m['test']['balanced_accuracy']:.2%} |"
                           for name, m in summary["baselines"].items())
    case_table = "| Case | Actual next minute | TLOB | DeepLOB |\n|---|---|---|---|\n"
    for _, r in cases.iterrows():
        case_table += f"| {r.title} | {LABELS[int(r.actual)]} | {prediction_text(r, 'TLOB')} | {prediction_text(r, 'DeepLOB')} |\n"
    best = ranked[0]
    best_score = summary["models"][best]["test"]["balanced_accuracy"]
    best_baseline_name = max(summary["baselines"], key=lambda n: summary["baselines"][n]["test"]["balanced_accuracy"])
    best_baseline_score = summary["baselines"][best_baseline_name]["test"]["balanced_accuracy"]
    verdict = (f"{best} ranks first among the two runnable models by full-test balanced accuracy ({best_score:.2%}). "
               f"The strongest simple baseline, {best_baseline_name}, scores {best_baseline_score:.2%}. "
               + ("The top model beats these baselines in this run. " if best_score > best_baseline_score else "The top model does not beat the strongest baseline. ")
               + "There is no tested winner across all four: LOBERT and LOBS5 have no comparable results.")
    report = f"""# BTC order-book model comparison

{verdict}

## What was actually tested

Real BTCUSDT perpetual L2 snapshots from January 9–20, 2023: {summary['dataset']['raw_snapshots']:,} raw snapshots.
Training uses January 9–17; validation January 18; testing January 19–20.
Both published architectures were trained from scratch for this new task with equal budgets:
8,000 training windows, three epochs, seed 42, Adam 0.0001 and 128 one-second states.
An epoch was selected using validation loss only. Published event-horizon checkpoints
were not used. This is a small architecture experiment, not a paper replication or a
claim about the best possible training of either model.

The prediction is the midpoint's direction **60 seconds ahead**, with movements
within ±1 basis point counted as flat. One basis point is 0.01%, about $2.10 at
$21,000. This is neither trade-price OHLC generation nor simulated trading.

All 10 examples use different rules and timestamps separated by at least ten minutes.
They were frozen before training and prediction, using past-only measurements.
Examples include trends, sideways movement, contrasting volatility, opposite book
imbalances, wider spreads, thin depth and rapid midpoint updates. Market properties
can coexist. The snapshot recording rate is nearly fixed, so the activity case uses
observed midpoint changes, not a fabricated exchange-message count.

## Results

{table}

Full test contains {summary['models'][best]['test']['count']:,} eligible minute decisions.
Actual labels: {json.dumps(summary['models'][best]['test']['actual_counts'])}.
Balanced accuracy gives equal weight to each class; always predicting the most
common class can inflate ordinary accuracy. Raw model probabilities are not calibrated.

{baselines}

## The 10 cases

{case_table}

![Ten contrasting cases](ten-cases.png)

Black lines show the actual next-minute path. Predicted classes and probabilities
are written on each chart; no exact price path was generated by these classifiers.
The detailed charts include probability bars for all three classes.

## All four requested models accounted for

- **TLOB:** actual published source, pinned revision `{summary['models']['TLOB']['provenance']['source_revision']}`.
  Trainable model definitions loaded without plotting/tracking side effects. BiN
  mixing weights are clamped positive to avoid its CUDA-only parameter replacement
  branch on this CPU. The network configuration is preserved.
- **DeepLOB:** actual original-author PyTorch notebook class, extracted without
  executing notebook training/download cells. Added channel axis; native softmax
  trained with log-probability loss. Window length adapted to 128 states.
- **LOBERT:** {summary['unavailable']['LOBERT']['reason']}
- **LOBS5:** {summary['unavailable']['LOBS5']['reason']}

The original DeepLOB repository's FI-2010 weights are not BTC training. TLOB does
publish BTC TLOB/DeepLOB checkpoints, but their event-count target is a different
task from this one-minute benchmark. Downloaded checkpoints are retained separately.
No arbitrary checkpoint objects were deserialized to run this experiment.

## Limits

"""
    report += "\n".join(f"- {line}." for line in summary["limitations"])
    report += "\n- Dataset venue is not independently certified; quantities are reported source units. Gaps are rejected, never filled.\n"
    report += "\nSources: [TLOB](https://github.com/LeonardoBerti00/TLOB), [original DeepLOB](https://github.com/zcakhaa/DeepLOB-Deep-Convolutional-Neural-Networks-for-Limit-Order-Books), [LOBERT paper](https://arxiv.org/abs/2511.12563), [author project](https://www.tuni.fi/fi/tau/tutkimus/ai-lob-advanced-limit-order-book-modeling-ai), [LOBS5](https://github.com/GereonFranken/LOBS5), [BTC dataset](https://www.kaggle.com/datasets/siavashraz/bitcoin-perpetualbtcusdtp-limit-order-book-data).\n"
    (output / "report.md").write_text(report)
    header = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTC order-book model comparison</title><style>
body{margin:0;background:#f7f8fc;color:#19243b;font:16px/1.6 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:40px 24px}
h1{font-size:42px;line-height:1.1;letter-spacing:-1.5px}h2{margin-top:44px}p{max-width:900px}.muted{color:#68748b}.badge{font-size:13px;color:#5b4ae6;font-weight:700;text-transform:uppercase;letter-spacing:1px}
table{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden;font-size:14px}th,td{text-align:left;padding:14px;border-bottom:1px solid #e4e8f0}th{color:#68748b}article{background:white;border:1px solid #e1e6ef;border-radius:18px;overflow:hidden;margin:24px 0}article img{width:100%;display:block}summary{cursor:pointer;padding:18px;font-weight:600}article p{padding:0 22px}a{color:#5b4ae6}code{font-size:13px}footer{color:#68748b;font-size:13px;padding:40px 0}
@media(max-width:650px){h1{font-size:31px}main{padding:24px 12px}th,td{padding:8px;font-size:12px}}
</style></head><body><main>"""
    parts = [header, '<div class="badge">Historical research · BTC perpetual · 60-second horizon</div>',
        '<h1>Can the order book<br>predict the next minute?</h1>', f'<p>{html.escape(verdict)}</p>',
        '<p class="muted">3.73 million real snapshots · 10 contrasting examples frozen before training · '
        '2,367 test minutes · 2 models runnable, 2 unavailable</p>', '<h2>Results</h2>',
        '<table><tr><th>Model</th><th>Status</th><th>Right / 10</th><th>Full test</th><th>Balanced</th><th>Macro F1</th></tr>']
    for r in rows:
        parts.append('<tr>' + ''.join(f'<td>{html.escape(str(r[k]))}</td>' for k in ("model", "status", "cases", "test", "balanced", "f1")) + '</tr>')
    parts += ['</table>', '<p>UP means more than +1 bp; DOWN means less than −1 bp; FLAT means within ±1 bp. '
        'One basis point is 0.01%. Predictions concern the average best bid/ask price, not trade candles.</p>',
        '<h2>Simple comparisons</h2>', '<table><tr><th>Baseline</th><th>Accuracy</th><th>Balanced accuracy</th></tr>']
    for name, m in summary["baselines"].items():
        parts.append(f'<tr><td>{html.escape(name)}</td><td>{m["test"]["accuracy"]:.2%}</td><td>{m["test"]["balanced_accuracy"]:.2%}</td></tr>')
    parts += ['</table>', '<h2>Ten different cases</h2>', '<p>Gray is the history the models could see. Black is what actually happened afterward. '
              'Probability bars are the predictions; these models do not output exact future price paths.</p>']
    for i, (_, r) in enumerate(cases.iterrows(), 1):
        image = base64.b64encode((output / "charts" / f"{i:02d}-{r['case']}.png").read_bytes()).decode()
        measurement = frozen["cases"][i - 1]["measurements"]
        parts += [f'<article><img src="data:image/png;base64,{image}" alt="{html.escape(r.title)} prediction and actual outcome">',
            '<details><summary>Why this case was chosen</summary>',
            f'<p>{html.escape(frozen["cases"][i - 1]["rule"])}. Five-minute move: {measurement["trend_5m_bps"]:+.2f} bp; '
            f'volatility: {measurement["volatility_5m_bps"]:.3f} bp; imbalance: {measurement["imbalance"]:+.3f}; '
            f'mean spread: {measurement["spread_1m_bps"]:.3f} bp; depth: {measurement["depth_btc"]:.3f} source units; '
            f'midpoint changes in preceding minute: {measurement["midpoint_changes_1m"]:.0f}. '
            'Selection used only preceding observations.</p></details></article>']
    parts += ['<h2>What is missing</h2>', '<p><b>LOBERT:</b> no official runnable release found in the paper/author sources. '
        '<b>LOBS5:</b> requires individual-order message history and compatible weights; aggregate BTC snapshots do not supply order IDs or individual cancellations. '
        'Neither receives a score or a fabricated forecast.</p>', '<h2>How to interpret this</h2>',
        '<p>Both networks were trained from scratch for three epochs with the same 8,000 historical training windows. '
        'January 9–17 trained the models, January 18 selected the epoch, January 19–20 tested them. '
        'This limited run cannot establish a generally best model or a profitable strategy.</p>',
        '<footer>All times on charts are IST. Source timestamps are UTC. The report embeds its charts and works offline. '
        'Detailed scores, source hashes and every prediction are saved alongside this file.</footer></main></body></html>']
    (output / "report.html").write_text("\n".join(parts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    render(parser.parse_args().output)
