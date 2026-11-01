"""Exact transfer checks and parent-grouped statistics; never model fitting."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location('flow_analysis', Path(__file__).with_name('analyze-flow.py'))
flow = module_from_spec(spec)
spec.loader.exec_module(flow)


def read(path):
    with gzip.open(path, 'rt') as f:
        return [json.loads(line) for line in f]


def bp(price, ref):
    return 10000*(price/ref-1)


def analyze(raw, output):
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    paths = {}
    for p in sorted(raw.glob('*.manifest.json')):
        r = json.loads(p.read_text())
        candles = read(raw/(r['run_id']+'.candles.jsonl.gz'))
        fills = read(raw/(r['run_id']+'.fills.jsonl.gz'))
        r['fill_records'] = fills
        r['observations'] = len(candles)
        r['intended'] = sum(f['intended'] for f in fills)
        r['achieved'] = sum(f['filled'] for f in fills)
        r['partial_orders'] = sum(f['filled'] < f['intended'] for f in fills)
        r['warmup_matched'] = r['matched_baseline']
        if r['status'] == 'ok':
            assert r['warmup_matched'] and len(candles) == 51
            assert [c['relative'] for c in candles] == list(range(51))
            buy = r['scenario'].startswith('buy')
            side = 1 if buy else -1
            for f in fills:
                assert 0 < f['filled'] <= f['intended']
                assert f['coin_delta'] == -side*f['filled']
                assert f['cash_delta'] == side*f['notional']
                assert f['integer_vwap'] == f['notional']//f['filled']
            for c in candles:
                achieved = sum(f['filled'] for f in fills if f['relative'] <= c['relative'])
                notional = sum(f['notional'] for f in fills if f['relative'] <= c['relative'])
                assert c['coins'] - c['initial_coins'] == -side*achieved
                assert c['cash'] - c['initial_cash'] == side*notional
            origin = candles[0]['original_arrival']
            r['cash_coin_ledger_pass'] = True
            r['return_from_original_arrival_bp'] = {str(h): bp(candles[h]['last'], origin) for h in (1, 5, 15, 30, 50)}
            r['final_negative_cash_agents'] = candles[-1]['negative_cash_agents']
            r['final_negative_coin_agents'] = candles[-1]['negative_coin_agents']
            if fills:
                r['exact_total_vwap'] = sum(f['notional'] for f in fills)/r['achieved']
                r['total_signed_slippage_bp'] = side*bp(r['exact_total_vwap'], origin)
                for f in fills:
                    f['signed_impact_bp'] = side*bp(f['last_after'], f['arrival'])
                    f['signed_slippage_bp'] = side*bp(f['notional']/f['filled'], f['arrival'])
                    f['intended_over_depth10'] = f['intended']/f['opposite_depth10'] if f['opposite_depth10'] else None
                last = fills[-1]
                horizon0 = last['relative']
                r['after_final_fill_return_from_original_arrival_bp'] = {str(h): bp(candles[horizon0+h]['last'], origin) for h in (1, 5, 15, 30)}
                impact = last['signed_impact_bp']
                recovery = next((h for h in range(1,31) if side*bp(candles[horizon0+h]['last'], last['arrival']) <= impact/2), None) if impact > 0 else None
                r['last_order_half_impact_recovery_candle'] = recovery
                r['recovery_censored_or_nonpositive_impact'] = recovery is None
                if len(fills) > 1:
                    r['last_minus_first_impact_bp'] = fills[-1]['signed_impact_bp']-fills[0]['signed_impact_bp']
            paths[r['run_id']] = candles
        runs.append(r)
    summaries = {}
    for phase in ('pilot', 'main'):
        selected = [r for r in runs if r['phase'] == phase]
        summary = dict(parents=len({r['seed'] for r in selected}), attempts=len(selected),
            failures=[r['run_id'] for r in selected if r['status'] != 'ok'], scenarios={}, paired_schedule={})
        baseline = {r['seed']: r for r in selected if r['scenario'] == 'baseline' and r['status'] == 'ok'}
        for scenario in ('baseline','buy_one500','sell_one500','buy_repeat100','sell_repeat100'):
            group = [r for r in selected if r['scenario'] == scenario and r['status'] == 'ok']
            result = dict(completed=len(group), partial_orders=sum(r['partial_orders'] for r in group),
                achieved=flow.stats([r['achieved'] for r in group]),
                baseline_relative_return_bp={str(h): flow.interval([r['return_from_original_arrival_bp'][str(h)]-baseline[r['seed']]['return_from_original_arrival_bp'][str(h)] for r in group if r['seed'] in baseline]) for h in (1,5,15,30,50)},
                negative_cash_parent_count=sum(r['final_negative_cash_agents']>0 for r in group),
                negative_coin_parent_count=sum(r['final_negative_coin_agents']>0 for r in group))
            if scenario != 'baseline':
                result['total_signed_slippage_bp'] = flow.interval([r['total_signed_slippage_bp'] for r in group])
                result['first_order_impact_bp'] = flow.interval([r['fill_records'][0]['signed_impact_bp'] for r in group])
                result['last_order_impact_bp'] = flow.interval([r['fill_records'][-1]['signed_impact_bp'] for r in group])
                result['after_final_fill_return_from_original_arrival_bp'] = {str(h): flow.interval([r['after_final_fill_return_from_original_arrival_bp'][str(h)] for r in group]) for h in (1,5,15,30)}
                result['recovery_censored_or_nonpositive_impact'] = sum(r['recovery_censored_or_nonpositive_impact'] for r in group)
                result['recovered_candle'] = flow.stats([r['last_order_half_impact_recovery_candle'] for r in group if r['last_order_half_impact_recovery_candle'] is not None])
            if 'repeat' in scenario:
                result['last_minus_first_impact_bp'] = flow.interval([r['last_minus_first_impact_bp'] for r in group])
                result['per_order_impact_bp'] = {str(i+1): flow.interval([r['fill_records'][i]['signed_impact_bp'] for r in group]) for i in range(5)}
            summary['scenarios'][scenario] = result
        for side in ('buy','sell'):
            repeated = [r for r in selected if r['scenario'] == side+'_repeat100' and r['status'] == 'ok']
            immediate = {r['seed']:r for r in selected if r['scenario'] == side+'_one500' and r['status'] == 'ok'}
            pairs = [(r,immediate[r['seed']]) for r in repeated if r['seed'] in immediate]
            summary['paired_schedule'][side] = dict(parents=len(pairs),
                slippage_repeat_minus_one_bp=flow.interval([a['total_signed_slippage_bp']-b['total_signed_slippage_bp'] for a,b in pairs]),
                common_origin_return50_repeat_minus_one_bp=flow.interval([a['return_from_original_arrival_bp']['50']-b['return_from_original_arrival_bp']['50'] for a,b in pairs]))
        summaries[phase] = summary
    (output/'statistics.json').write_text(json.dumps(dict(evidence_type='original_DLL_CLR_repeated_intervention_host', runs=runs, summaries=summaries), indent=2))
    (output/'raw-sha256.json').write_text(json.dumps({str(p.relative_to(raw)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.glob('*'))}, indent=2))
    print(json.dumps({phase: dict(parents=d['parents'], attempts=d['attempts'], failures=d['failures'],
          paired_schedule=d['paired_schedule']) for phase,d in summaries.items()}, indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('raw',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    analyze(args.raw,args.output)
