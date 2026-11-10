"""Assemble actual-receipt inputs with the historical feature definitions."""
from collections import deque
from decimal import Decimal

import numpy as np

from ..market_data.candle_tape import CandleTape, MINUTE, SCALE, SECOND
from ..market_data.event_features_fast import build
from ..market_data.event_replay import DTYPE as BOOK
from ..market_data.event_windows import window
from ..market_data.trade_events import DTYPE as TRADE


def units(value):
    scaled = Decimal(value)*SCALE
    if not scaled.is_finite() or scaled != scaled.to_integral_value() or not 0 <= scaled < 2**63:
        raise ValueError('Unsupported exchange price or quantity precision')
    return int(scaled)


class NativeInputs:
    def __init__(self):
        self.tape = CandleTape()
        self.pending = deque()
        self.trades = deque()
        self.books = deque()
        self.trade_watermark = -1
        self.last_receipt = -1
        self.last_clock = -1
        self.trade_continuous_since = None
        self.first_trade_minute = None
        self.last_pruned_minute = None

    def ingest(self, row):
        at = row['receipt_utc_ns']
        mono = row['receipt_monotonic_ns']
        if row.get('clock_step_ns') or at < self.last_receipt or mono < self.last_clock:
            raise ValueError('Recorder clock discontinuity requires a fresh warmup')
        self.last_receipt, self.last_clock = at, mono
        kind, event = row['kind'], row['payload']
        if kind == 'book_invalidated':
            self.books.clear()
        elif kind == 'book':
            levels = np.array([[units(bp), units(bq), units(ap), units(aq)]
                               for (bp, bq), (ap, aq) in zip(event['bids'], event['asks'])],
                              dtype=np.int64)
            if levels.shape != (20, 4) or not event['top20_within_snapshot_bounds']:
                raise ValueError('Unverified native top20')
            self.books.append((at, row['exchange_event_ms']*10**6, 0, 0, event['update_id'],
                               0, 1, 1, 0, levels))
        elif kind == 'connection_error' and event['stream'] == 'individual_trade':
            self.trade_continuous_since = None
        elif kind == 'connection' and event['stream'] == 'individual_trade':
            self.trade_continuous_since = at
        elif kind == 'individual_trade_gap':
            self.trade_continuous_since = at
        elif kind == 'individual_trade':
            price, qty = units(event['p']), units(event['q'])
            nonmarket = event['X'] in ('INSURANCE_FUND', 'ADL') or (
                event['X'] == 'NA' and price == qty == 0)
            if not nonmarket and (not price or not qty or type(event['m']) is not bool):
                raise ValueError('Invalid native market trade')
            trade = (at, event['E']*10**6, event['T']*10**6, event['t'], price, qty,
                     int(bool(event['m'])), 0, int(nonmarket))
            available = max(self.trade_watermark, *trade[:3])
            self.trade_watermark = available
            self.pending.append((available, trade))
        self.advance(at)
        while self.books and self.books[0][0] < at-120*SECOND:
            self.books.popleft()
        while self.trades and self.trades[0][0] < at-120*SECOND:
            self.trades.popleft()
        minute = at//MINUTE*MINUTE
        if minute != self.last_pruned_minute:
            self.tape.minutes = {t: bar for t, bar in self.tape.minutes.items() if t >= minute-1460*MINUTE}
            self.last_pruned_minute = minute

    def advance(self, cutoff):
        while self.pending and self.pending[0][0] < cutoff:
            at, values = self.pending.popleft()
            trade = np.array(values, dtype=TRADE)
            self.tape.ingest(trade, at)
            minute = int(trade['trade_ns'])//MINUTE*MINUTE
            if self.first_trade_minute is None:
                self.first_trade_minute = minute
            if minute == self.first_trade_minute:
                self.tape.minutes.setdefault(minute, {'n': 0})['bad'] = True
            self.trades.append((at, values))

    def event_window(self, cutoff):
        start = cutoff-60*SECOND
        if self.trade_continuous_since is None or self.trade_continuous_since >= start:
            raise ValueError('Insufficient continuous native trade history')
        book = np.array(list(self.books), dtype=BOOK)
        trades = np.array([row for _, row in self.trades], dtype=TRADE)
        if not len(book) or not len(trades):
            raise ValueError('Native book or trade window is empty')
        selected = window(book, trades, start, cutoff, trade_previous_release=self.trades[0][0])
        return build(book, trades, selected, start, cutoff), selected

    def freeze(self, cutoff):
        if cutoff % MINUTE != 15*SECOND or self.last_receipt >= cutoff:
            raise ValueError('Expected a strict-before-cutoff view at second 15')
        self.advance(cutoff)
        features, selection = self.event_window(cutoff)
        context = self.tape.snapshot(cutoff, mask_context=True)
        reference = np.array([(context['reference']/features['anchor']-1)*10000], np.float32)
        raw = (features['features'], features['time_groups'], context['candles'],
               context['candle_mask'], features['seed_features'], reference)
        return raw, selection['events']['available_ns']-(cutoff-60*SECOND), context
