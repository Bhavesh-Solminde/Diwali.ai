import pytest
from research.diwali.event_study import choose_family
from research.diwali.event_protocol import protocol


def test_complete_fixed_budget_and_control_tie_policy():
    settings=protocol();runs=[]
    for c in settings['neural_candidates']:
        for f in settings['development_folds']:
            for seed in settings['seeds']:
                runs.append({'candidate':c,'fold':f,'seed':seed,'partitions':{'score':{'mean15_bin_log_loss':2. if c!='one_second_temporal_conv' else 2.00005}}})
    assert choose_family(runs,settings)['selected_family']=='one_second_temporal_conv'
    with pytest.raises(ValueError,match='Incomplete or duplicate'):choose_family(runs[:-1],settings)
    with pytest.raises(ValueError,match='Incomplete or duplicate'):choose_family(runs+[runs[0]],settings)
