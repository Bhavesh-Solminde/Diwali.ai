import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


validation=load('analyze-validation');public=load('validate-public-btc');audit=load('audit-baselines')


class ValidationTests(unittest.TestCase):
    def test_reverse_neutral_and_majority_frozen(self):
        row=dict(momentum=0,book=1,actual=-1)
        self.assertEqual(audit.predict(row,'reversal'),0)
        self.assertEqual(audit.predict(row,'pilot_majority',1),1)
        self.assertEqual(audit.predict(dict(row,momentum=-1),'reversal'),1)

    def test_trigger_barrier_remains_unknown(self):
        rows=[dict(low=10000,high=10000) for _ in range(50)]
        rows[1]=dict(low=9980,high=10020)
        result=validation.entry(rows,0,10000,1)
        self.assertTrue(result['triggered']);self.assertEqual(result['outcome'],'ambiguous')

    def test_untriggered_and_level_denominator(self):
        rows=[dict(low=1002,high=1003) for _ in range(50)]
        self.assertFalse(validation.entry(rows,0,1001,1)['triggered'])
        rows=[dict(low=1001,high=1001) for _ in range(50)]
        rows[1]=dict(low=1000,high=1001)
        self.assertEqual(validation.entry(rows,0,1001,1)['outcome'],'timeout')

    def test_matching_cannot_use_outcomes(self):
        common=dict(profile='standard',side='bid',distance_bp=5,volatility_bp=10,volume_ratio=1,triggered=True)
        events=[dict(common,run_id='a',strength='strong',outcome='win'),dict(common,run_id='b',strength='weak',outcome='loss'),
                dict(common,run_id='c',strength='weak',outcome='win')]
        before=[(p['strong']['run_id'],p['weak']['run_id']) for p in validation.match_events(events)]
        for event in events:event['outcome']='ambiguous'
        self.assertEqual(before,[(p['strong']['run_id'],p['weak']['run_id']) for p in validation.match_events(events)])

    def test_depth_gap_cannot_rebootstrap_old_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir()
            records=[dict(kind='rest',url='/depth?',payload=dict(lastUpdateId=100,bids=[['10','1']],asks=[['11','1']])),
                dict(kind='public',payload=dict(e='depthUpdate',U=99,u=101,pu=98,b=[],a=[])),
                dict(kind='public',payload=dict(e='depthUpdate',U=102,u=103,pu=999,b=[],a=[])),
                dict(kind='public',payload=dict(e='depthUpdate',U=99,u=101,pu=98,b=[],a=[]))]
            with gzip.open(raw/'raw.jsonl.gz','wt') as f:
                for i,r in enumerate(records):
                    r.update(receipt_utc_ns=i,receipt_monotonic_ns=i);f.write(json.dumps(r)+'\n')
            manifest=dict(raw_sha256=hashlib.sha256((raw/'raw.jsonl.gz').read_bytes()).hexdigest(),venue='test',instrument='test')
            (raw/'manifest.json').write_text(json.dumps(manifest));public.validate(raw,root/'quality')
            result=json.loads((root/'quality/quality.json').read_text())
            self.assertEqual(result['counts']['depth_applied'],1)
            self.assertEqual(result['counts']['sequence_gaps'],1)
            self.assertFalse(result['book_currently_synchronized'])


if __name__=='__main__':unittest.main()
