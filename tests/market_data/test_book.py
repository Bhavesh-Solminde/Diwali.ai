import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from research.market_data.book import Book, BookGap
from research.market_data.collect import Store, retry
from research.market_data.quality import audit


def event(u=101, pu=99, first=99, bids=None, asks=None):
    return dict(s='BTCUSDT', U=first, u=u, pu=pu,
                b=bids or [], a=asks or [])


class BookTests(unittest.TestCase):
    def setUp(self):
        self.book = Book()
        self.book.snapshot(dict(lastUpdateId=100, bids=[['100','2'],['99','3']],
                                asks=[['101','4'],['102','5']]))

    def test_bridge_absolute_update_and_unknown_delete(self):
        self.assertTrue(self.book.apply(event(bids=[['100','1'],['98','0']])))
        self.assertEqual(self.book.top()['bids'][0], ['100','1'])
        self.assertTrue(self.book.apply(event(102,101,102,bids=[['100','0']])))
        self.assertEqual(self.book.top()['bids'][0], ['99','3'])

    def test_stale_and_duplicate_do_not_change_state(self):
        self.assertFalse(self.book.apply(event(99,98,98)))
        self.book.apply(event())
        before = self.book.top()
        self.assertFalse(self.book.apply(event(bids=[['100','999']])))
        self.assertEqual(before,self.book.top())

    def test_gap_invalidates_until_new_snapshot(self):
        self.book.apply(event())
        with self.assertRaises(BookGap):
            self.book.apply(event(103,999,102))
        with self.assertRaises(BookGap):
            self.book.top()
        with self.assertRaises(BookGap):
            self.book.apply(event())
        self.setUp()
        self.assertTrue(self.book.apply(event()))

    def test_crossed_nonfinite_or_negative_books_are_rejected(self):
        for bids in [[['102','1']],[['100','-1']],[['NaN','1']],[['100','Infinity']]]:
            self.setUp()
            with self.assertRaises(BookGap):
                self.book.apply(event(bids=bids))
            self.assertFalse(self.book.synced)

    def test_unbridgeable_snapshot_is_rejected(self):
        with self.assertRaises(BookGap):
            self.book.apply(event(200,199,200))


class RecorderTests(unittest.IsolatedAsyncioTestCase):
    async def test_integrity_audit_keeps_training_gate_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'run')
            store.save('rest',[[0,'100','102','99','101','2',59999,'201']],
                       path='/fapi/v1/klines?',request_utc_ns=60_000_000_000)
            store.finish()
            result=audit(store.root)
            self.assertTrue(result['raw_integrity_pass'])
            self.assertEqual(result['official_closed_minutes'],1)
            self.assertFalse(result['training_ready'])
            raw=next(store.root.glob('events-*.jsonl'))
            with raw.open('a') as f:f.write('{}\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):audit(store.root)

    async def test_retry_creates_new_connection_and_preserves_failure(self):
        class Stop(Exception): pass
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'run')
            seen=[]
            async def session(s,c):
                seen.append(c)
                if c==1: raise BookGap('gap')
                raise asyncio.CancelledError()
            with self.assertRaises(asyncio.CancelledError):
                await retry(store,'test',session)
            store.finish()
            self.assertEqual(seen,[1,2])
            manifest=json.loads((store.root/'manifest.json').read_text())
            self.assertEqual(manifest['counts']['connection_error'],1)
            self.assertFalse(manifest['training_ready'])
            self.assertTrue(manifest['raw_sha256'])


if __name__=='__main__': unittest.main()
