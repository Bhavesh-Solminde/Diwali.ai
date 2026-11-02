"""Binance USD-M snapshot/diff synchronization using decimal price/quantity."""
from decimal import Decimal


class BookGap(ValueError):
    pass


class Book:
    def __init__(self):
        self.invalidate()

    def invalidate(self):
        self.bids, self.asks = {}, {}
        self.last = None
        self.synced = False
        self.snapshot_id = None

    @staticmethod
    def levels(rows):
        result = {}
        for price, quantity in rows:
            p, q = Decimal(price), Decimal(quantity)
            if not p.is_finite() or not q.is_finite() or p <= 0 or q < 0:
                raise BookGap('invalid depth value')
            if q:
                result[p] = q
        return result

    def snapshot(self, payload):
        self.invalidate()
        try:
            self.bids = self.levels(payload['bids'])
            self.asks = self.levels(payload['asks'])
            self.snapshot_id = int(payload['lastUpdateId'])
        except Exception:
            self.invalidate()
            raise

    def apply(self, event):
        try:
            if self.snapshot_id is None:
                raise BookGap('fresh snapshot required')
            if event.get('s') != 'BTCUSDT' or event['U'] > event['u']:
                raise BookGap('wrong symbol or sequence range')
            if self.synced:
                if event['u'] <= self.last:
                    return False  # Duplicate/old events cannot move the book backward.
                if event['pu'] != self.last:
                    raise BookGap('depth sequence gap')
            else:
                if event['u'] < self.snapshot_id:
                    return False
                if not event['U'] <= self.snapshot_id <= event['u']:
                    raise BookGap('snapshot cannot bridge buffered events')
            for side, key in ((self.bids, 'b'), (self.asks, 'a')):
                self.levels(event[key])  # Validate zero deletions as well as additions.
                for p, q in event[key]:
                    p, q = Decimal(p), Decimal(q)
                    if q:
                        side[p] = q
                    else:
                        side.pop(p, None)
            if not self.bids or not self.asks or max(self.bids) >= min(self.asks):
                raise BookGap('empty or crossed book')
            self.last, self.synced = event['u'], True
            return True
        except Exception:
            self.invalidate()
            raise

    def top(self, count=20):
        if not self.synced:
            raise BookGap('book unavailable')
        return dict(update_id=self.last,
                    bids=[[str(p), str(self.bids[p])] for p in sorted(self.bids, reverse=True)[:count]],
                    asks=[[str(p), str(self.asks[p])] for p in sorted(self.asks)[:count]])
