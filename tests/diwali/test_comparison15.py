import numpy as np
import torch
from torch import nn
import pytest

from research.diwali.comparison15 import CandleAttentionModel, loss_terms, protocol
from research.diwali.event_model import EventModel
from research.diwali.comparison15_study import aggregate, public_metrics


def args():
    return (torch.randn(2, 60, 103), torch.ones(2, 60, dtype=torch.bool), torch.randn(2, 1440, 8),
            torch.randn(2, 80), torch.arange(60)[None].expand(2, -1),
            torch.ones(2, 1440, dtype=torch.bool), torch.randn(2, 1))


def test_direction_penalty_is_consistent_with_price_mass_and_zero_weight_control():
    torch.manual_seed(17); z = torch.randn(2, 15, 26, requires_grad=True); y = torch.randint(0, 26, (2, 15))
    total, price, binary = loss_terms(z, y, .25)
    p = z.softmax(-1)[..., 13:].sum(-1)
    expected = nn.functional.binary_cross_entropy(p, (y >= 13).float())
    torch.testing.assert_close(binary, expected)
    torch.testing.assert_close(total, price+.25*expected)
    torch.testing.assert_close(loss_terms(z, y, 0)[0], price)
    total.backward(); assert torch.isfinite(z.grad).all()


def test_only_candle_mixing_distinguishes_architecture_with_identity_adapter():
    torch.manual_seed(17); a = EventModel(width=16)
    torch.manual_seed(17); c = CandleAttentionModel(width=16)
    assert all(torch.equal(v, c.state_dict()[k]) for k, v in a.state_dict().items())
    c.candle_mixer = nn.Identity(); c.candle_position.zero_()
    inputs = args(); a.eval(); c.eval()
    torch.testing.assert_close(a(*inputs), c(*inputs), rtol=0, atol=0)


def test_transformer_branch_masks_unavailable_candles_and_trains_all_parameters():
    torch.manual_seed(29); c = CandleAttentionModel(width=16); inputs = list(args()); inputs[5][:, 20:25] = False
    other = list(inputs); other[2] = inputs[2].clone(); other[2][:, 20:25] = float('nan')
    torch.testing.assert_close(c(*inputs), c(*other))
    c(*inputs).square().mean().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in c.parameters())


def test_equal_neural_tuning_budget_and_primary_target_retained():
    p = protocol()
    assert {f: sum(c['family'] == f for c in p['configurations'].values()) for f in ['A', 'B', 'C']} == {'A': 2, 'B': 2, 'C': 2}
    assert 'mean15-bin' in p['primary_selection']
    assert p['max_epochs'] == 12 and p['seeds'] == [17, 29]


def fake_runs():
    rows = []
    for f in ['A', 'B', 'C']:
        for name in list(protocol()['configurations'])+['D_binary_logistic']:
            for seed in ([17] if name == 'D_binary_logistic' else [17, 29]):
                score = {'calibrated_range': {'mean15_bin_log_loss': 3.},
                         'calibrated_direction': {'final': {'log_loss': .7, 'roc_auc': .5, 'brier': .25}}}
                if name.startswith('B_'):
                    score['calibrated_range']['mean15_bin_log_loss'] = 3.1
                    score['calibrated_direction']['final']['log_loss'] = .5
                rows.append({'fold': f, 'configuration': name, 'seed': seed, 'partitions': {'score': score}})
    return rows


def test_range_primary_wins_over_direction_gain_and_duplicate_folds_fail():
    runs = fake_runs()
    assert aggregate(runs)['selected_neural_configuration'] == 'A_original'
    duplicate = [r.copy() for r in runs]
    for r in duplicate:
        if r['configuration'] == 'D_binary_logistic':
            r['fold'] = 'A'
    with pytest.raises(ValueError):
        aggregate(duplicate)


def test_publication_does_not_expose_single_origin_metrics():
    assert public_metrics({'daily': {'origins': 1, 'mean_up_probability': .47}})['daily'] == {
        'origins': 1, 'metrics_suppressed': 'Fewer than ten origins; complete metrics stay private.'}
