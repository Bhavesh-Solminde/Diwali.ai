"""Fit the single attention challenger declared before forward evaluation."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn.functional import cross_entropy

from .comparison15 import ROOT, CandleAttentionModel, ComparisonData, protocol, source_hashes
from .event_data_exact import ExactEventData
from .event_final_data import FinalBuildData
from .event_train import calibrate, infer, nll, probabilities
from ..market_data.validate_archive import file_hash, save

CONFIG = 'C_attention_lower_lr'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    data_root = ROOT/'data/btc-perp'
    audit_root = ROOT/'results/event-joined-cohort'
    model_root = ROOT/'data/models/diwali1.4-final-v1'
    selected = json.loads((ROOT/'results/diwali1.5/selected-artifact.json').read_text())
    transforms_path = model_root/'fit-transforms.json'
    if file_hash(transforms_path) != selected['artifacts']['fit-transforms.json']:
        raise ValueError('Changed control transforms')
    transforms = json.loads(transforms_path.read_text())
    august = ExactEventData(data_root/'event-month-cohort-august-v1',
                            data_root/'event-inputs-august-fast-v1', audit_root/'august-month-audit.json')
    september = ExactEventData(data_root/'event-month-cohort-september-selection-v1',
                               data_root/'event-inputs-september-selection-fast-v1',
                               audit_root/'september-selection-audit.json')
    data = FinalBuildData(august, september)
    cache = ComparisonData(data_root/'diwali15-comparison-inputs-v1', 'A')
    if (data.hashes != transforms['source_hashes'] or cache.report['source_data_hashes'] != august.hashes
            or transforms['representation'] != 'one_second'):
        raise ValueError('Challenger inputs differ from the matched source cohorts')
    fit, select, cal = (data.partition('final', part)[0] for part in ('fit', 'select', 'calibrate'))
    if (len(fit), len(select), len(cal)) != (5391, 862, 1476):
        raise ValueError('Changed frozen training partitions')
    np.testing.assert_array_equal(cache.ids, august.ids)
    np.testing.assert_array_equal(cache.y, data.y[fit])
    np.testing.assert_array_equal(cache.cutoffs, data.cutoffs[fit])
    for j in np.linspace(0, len(fit)-1, 10, dtype=int):
        cached, _ = cache.batch([j], transforms['moments'], 'cpu')
        exact, _ = data.batch([j], transforms, 'cpu')
        if not all(torch.equal(a, b) for a, b in zip(cached, exact)):
            raise ValueError('Cached fit tensors differ')

    settings = protocol()
    conf = settings['configurations'][CONFIG]
    seed = settings['final_build_seed']
    out.mkdir(parents=True, exist_ok=False)
    provenance = {'configuration': CONFIG, 'settings': conf, 'seed': seed,
                  'fit_origins': len(fit), 'selection_origins': len(select), 'calibration_origins': len(cal),
                  'fit_dates': ['2026-08-01', '2026-08-31'],
                  'selection_dates': ['2026-09-01', '2026-09-07'],
                  'calibration_dates': ['2026-09-08', '2026-09-14'],
                  'data_hashes': data.hashes, 'source_hashes': source_hashes(),
                  'trainer_sha256': file_hash(Path(__file__)),
                  'reserved_september_data_read': False}
    save(out/'protocol.json', provenance)
    save(out/'fit-transforms.json', transforms)
    torch.manual_seed(seed)
    torch.set_num_threads(4)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    model = CandleAttentionModel().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=conf['lr'], weight_decay=settings['weight_decay'])
    rng = np.random.default_rng(seed)
    batch_size = settings['batch_size']
    best = float('inf')
    wait = 0
    history = []
    for epoch in range(1, settings['max_epochs']+1):
        model.train()
        order = rng.permutation(fit)
        for start in range(0, len(order), batch_size):
            x, y = cache.batch(order[start:start+batch_size], transforms['moments'], device)
            opt.zero_grad(set_to_none=True)
            loss = cross_entropy(model(*x).reshape(-1, 26), y.reshape(-1))
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite challenger loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), settings['gradient_clip'], error_if_nonfinite=True)
            opt.step()
        score = nll(data.y[select], probabilities(infer(model, data, select, transforms, device, batch_size)))
        history.append({'epoch': epoch, 'selection_loss': score})
        if score < best-1e-10:
            best, chosen, wait = score, epoch, 0
            torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, out/'weights.pt')
        else:
            wait += 1
        save(out/'history.json', history)
        print('attention checkpoint selection', epoch, score, flush=True)
        if wait >= settings['patience']:
            break
    model.load_state_dict(torch.load(out/'weights.pt', weights_only=True, map_location='cpu'))
    logits = infer(model, data, cal, transforms, device, batch_size)
    temps = calibrate(data.y[cal], logits)
    sample = cal[np.linspace(0, len(cal)-1, 10, dtype=int)]
    on_device = probabilities(infer(model, data, sample, transforms, device, batch_size), temps)
    on_cpu = probabilities(infer(model.cpu(), data, sample, transforms, 'cpu', batch_size), temps)
    np.testing.assert_allclose(on_cpu, on_device, atol=2e-6, rtol=0)
    save(out/'calibration.json', {'temperatures': temps, 'origins': len(cal)})
    save(out/'report.json', {'state': 'fitted_calibrated_reload_verified', **provenance,
                           'best_epoch': chosen, 'selection_loss': best,
                           'cpu_probability_max_difference': float(np.abs(on_cpu-on_device).max()),
                           'artifact_hashes': {p.name: file_hash(p) for p in out.iterdir()}})


if __name__ == '__main__':
    main()
