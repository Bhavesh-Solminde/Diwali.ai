"""Recompute historical UI forecasts and publish only aggregate verification."""
import json
from pathlib import Path
import numpy as np
from .anchored_serve import Engine
from .net_direction import direction_summary
from ..market_data.validate_archive import file_hash


def main():
    root=Path('data/models/diwali1.2');out=Path('results/diwali1.2');out.mkdir(parents=True,exist_ok=True)
    report=json.loads((root/'report.json').read_text());protocol=report['protocol']
    sources={**protocol['dependency_sources'],**protocol['midpoint_transform_sources'],
        'research/diwali/anchored.py':protocol['model_source_sha256'],
        'research/diwali/anchored_train.py':protocol['source_sha256']}
    for name,expected in sources.items():
        if file_hash(Path(name))!=expected:raise ValueError('Changed source: '+name)
    for name,expected in json.loads((root/'parent-hashes.json').read_text()).items():
        if file_hash(Path(name))!=expected:raise ValueError('Changed parent: '+name)
    engine=Engine(root.resolve());engine.ready();saved=np.load(root/f'{engine.mode}-locked_test-predictions.npz')
    ids=np.linspace(0,len(saved['indices'])-1,10,dtype=int);maximum=0.;events=0
    for i,j in enumerate(ids):
        prediction=engine.predict(i);p=np.array([[r['probability'] for r in h['ranges']] for h in prediction['fan']])
        np.testing.assert_allclose(p,saved['bin_probabilities'][j],rtol=1e-5,atol=1e-6)
        maximum=max(maximum,float(np.abs(p-saved['bin_probabilities'][j]).max()))
        np.testing.assert_allclose(p.sum(1),1,atol=1e-8)
        expected=direction_summary(p)
        for key,value in expected.items():assert prediction['overall_direction'][key]==value
        assert prediction['future_actuals_used'] is False and 'actuals' not in prediction
        for lo,hi in [(0,25),(10,15),(13,20)]:
            q=engine.query(prediction['token'],lo,hi)
            assert 0<=q['all15_closes_inside']<=q['at_least_one_close_inside']<=1+1e-9
            events+=1
        actual=engine.reveal(prediction['token'])
        for h,row in enumerate(actual['actuals']):
            assert row['range_index']==saved['bin_labels'][j,h]
            np.testing.assert_allclose(row['assigned_probability'],p[h,row['range_index']],atol=1e-12)
    result={'cases':10,'horizons':150,'joint_event_queries':events,'maximum_cpu_probability_difference':maximum,
        'coherent_net_direction_verified':True,'actuals_separate_until_reveal':True,'future_actuals_used':False}
    (out/'replay-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'source-verification.json').write_text(json.dumps({'training_sources_and_dependencies_unchanged':True,'data_parent_hashes_unchanged':True,'sources':sources},indent=2)+'\n')
    for name in ['report.json','run-protocol.json','selection.json','runs.json','history.json','parent-hashes.json','midpoint-manifest.json']:
        (out/name).write_bytes((root/name).read_bytes())
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
