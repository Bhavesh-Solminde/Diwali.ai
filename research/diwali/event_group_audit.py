"""Count natural same-time groups in prepared inputs; no targets or model tuning."""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--features',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=json.loads((a.features/'report.json').read_text())
    if report['state']!='complete':raise ValueError('Incomplete inputs')
    ledger=a.features/'inputs.json'
    if file_hash(ledger)!=report['ledger_sha256']:raise ValueError('Changed input ledger')
    total=Counter();sizes=Counter();origins_multi=0;maximum=0
    for row in json.loads(ledger.read_text()):
        path=a.features/row['file']
        if file_hash(path)!=row['sha256']:raise ValueError('Changed input features')
        with np.load(path) as z:
            x=z['events'];groups=z['time_groups']
            if groups.shape!=(len(x),) or not len(x):raise ValueError('Invalid timestamp group array')
            n=int(groups[-1])+1;market=(x[:,81]>0)&(x[:,82]==0)
            trades=np.bincount(groups[market],minlength=n);books=np.bincount(groups[x[:,80]>0],minlength=n);multi=trades>=2
            total.update({'origins':1,'input_rows':len(x),'availability_groups':n,'market_trade_rows':int(market.sum()),
                          'groups_with_market_trades':int((trades>0).sum()),'groups_with_multiple_market_trades':int(multi.sum()),
                          'market_trade_rows_in_multiple_trade_groups':int(trades[multi].sum()),
                          'same_time_cross_stream_groups':int(((trades>0)&(books>0)).sum())})
            origins_multi+=int(multi.any());maximum=max(maximum,int(trades.max()))
            for lo,hi,label in [(1,2,'1'),(2,3,'2'),(3,6,'3-5'),(6,11,'6-10'),(11,51,'11-50'),(51,np.iinfo(np.int64).max,'51+')]:
                sizes[label]+=int(((trades>=lo)&(trades<hi)).sum())
    result={'state':'complete','counts':dict(total),'origins_with_multiple_trade_groups':origins_multi,'market_trade_group_size_histogram':dict(sizes),
            'maximum_same_time_market_trade_count':maximum,
            'fraction_market_trades_in_multi_trade_groups':total['market_trade_rows_in_multiple_trade_groups']/max(total['market_trade_rows'],1),
            'source_feature_report_sha256':file_hash(a.features/'report.json'),'audit_source_sha256':file_hash(Path(__file__)),
            'target_labels_loaded':False,'model_weights_changed':False,
            'interpretation':('No multi-trade equal-availability groups were found. The synthetic set-pooling multiplicity counterexample is not activated by this retained cohort and cannot explain its measured forecast errors.' if total['groups_with_multiple_market_trades']==0 else 'Natural multiplicity exists. These counts do not prove count loss or predictive harm in every such group.')}
    save(a.output,result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
