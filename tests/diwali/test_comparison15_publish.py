from research.diwali.comparison15_publish import aggregate_only


def test_small_groups_are_suppressed_under_both_count_conventions():
    evidence = {'origins': 100, 'loss': 2.8, 'reliability': {
        'rare': {'count': 1, 'mean_confidence': .73, 'correct_fraction': 1.},
        'large': {'count': 10, 'mean_confidence': .6}},
        'daily': [{'origins': 3, 'log_loss': .8}]}
    published = aggregate_only(evidence)
    assert published['loss'] == evidence['loss']
    assert published['reliability']['large'] == evidence['reliability']['large']
    assert 'mean_confidence' not in published['reliability']['rare']
    assert 'log_loss' not in published['daily'][0]
    assert evidence['reliability']['rare']['mean_confidence'] == .73
