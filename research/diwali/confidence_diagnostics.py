"""Aggregate error localization after selection; never selects a checkpoint."""
import argparse,json
from pathlib import Path
import numpy as np
from ..market_data.validate_archive import save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args();root=args.run
    report=json.loads((root/'report.json').read_text());out=Path('results')/root.name;out.mkdir(parents=True,exist_ok=True)
    rows={};paired={};days=None
    for mode,info in report['models'].items():
        rows[mode]={'endpoint_temperature':info['residual_temperatures'][-1],
            'temperature_grid_boundary':info['endpoint_calibration']['boundary_hit'],
            'partitions':{k:v['overall_direction'] for k,v in info['partitions'].items()}}
        z=np.load(root/f'{mode}-locked_test-predictions.npz');p=z['bin_probabilities'][:,-1,13:].sum(1).astype(float);y=z['bin_labels'][:,-1]>12
        paired[mode]=-np.log(np.clip(np.where(y,p,1-p),1e-15,1))
        day=(z['indices'][:,1].astype('datetime64[ms]')).astype('datetime64[D]').astype(str)
        if days is not None:np.testing.assert_array_equal(days,day)
        days=day
    baseline=paired['epoch0_parent'];daily=[]
    for day in sorted(set(days)):
        keep=days==day
        daily.append({'target_start_UTC_day':day,'origins':int(keep.sum()),'final_binary_log_loss':{k:float(v[keep].mean()) for k,v in paired.items()},
            'difference_from_epoch0':{k:float((v[keep]-baseline[keep]).mean()) for k,v in paired.items()}})
    save(out/'confidence-diagnostics.json',{'scope':'Post-selection descriptive error localization. Calibration scores reuse fitted labels. October benchmark repeatedly inspected; correlated origins, not independent trials. Not used to reselect current model.',
        'model':report['model'],'selected':report['selected_mode'],'variants':rows,'paired_target_days':daily,
        'always_half':{'binary_log_loss':float(np.log(2)),'brier':.25}})
    print('Saved aggregate confidence diagnostics',root.name)


if __name__=='__main__':main()
