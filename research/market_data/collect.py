"""Reconnect/resnapshot public BTCUSDT recorder; raw append-only provenance."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

from websockets.asyncio.client import connect
from .book import Book, BookGap


REST = 'https://fapi.binance.com'
DEPTH = 'wss://fstream.binance.com/public/stream?streams=btcusdt@depth@100ms'
MARKET = 'wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade/btcusdt@kline_1m'


class Store:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True, exist_ok=False)
        self.file = None
        self.hour = None
        self.counts = Counter()
        self.started = time.time_ns()
        self.previous_clock = None

    def save(self, kind, payload, **extra):
        utc, mono = time.time_ns(), time.monotonic_ns()
        hour = datetime.fromtimestamp(utc / 1e9, timezone.utc).strftime('%Y%m%dT%H')
        if hour != self.hour:
            if self.file:
                self.file.flush(); os.fsync(self.file.fileno()); self.file.close()
            self.file = (self.root / f'events-{hour}.jsonl').open('a', encoding='utf-8')
            self.hour = hour
        if self.previous_clock:
            du, dm = utc-self.previous_clock[0], mono-self.previous_clock[1]
            if abs(du-dm) > 100_000_000:
                extra['clock_step_ns'] = du-dm
                self.counts['clock_steps'] += 1
        self.previous_clock = utc, mono
        row = dict(kind=kind, receipt_utc_ns=utc, receipt_monotonic_ns=mono, payload=payload, **extra)
        self.file.write(json.dumps(row, separators=(',', ':'))+'\n')
        self.file.flush()
        self.counts[kind] += 1
        return row

    def status(self, state):
        if self.file:
            self.file.flush(); os.fsync(self.file.fileno())
        tmp = self.root / 'status.tmp'
        tmp.write_text(json.dumps(dict(state=state, start_utc_ns=self.started,
            updated_utc_ns=time.time_ns(), counts=dict(self.counts)), indent=2)+'\n')
        tmp.replace(self.root / 'status.json')

    def finish(self):
        self.status('stopped')
        if self.file:
            self.file.close()
        hashes = {}
        for p in self.root.glob('events-*.jsonl'):
            with p.open('rb') as f:
                hashes[p.name] = hashlib.file_digest(f, 'sha256').hexdigest()
        (self.root/'manifest.json').write_text(json.dumps(dict(
            venue='Binance USD-M', symbol='BTCUSDT', start_utc_ns=self.started,
            end_utc_ns=time.time_ns(), counts=dict(self.counts), raw_sha256=hashes,
            credentials_used=False, orders_placed=False, training_ready=False,
            limitations=['Finite snapshot depth and public-order coverage only.',
                'Aggregated trades are not certified complete executions.',
                'Trade/candle stream gaps require separate coverage validation.',
                'Receipt lag includes clock offset; no latency guarantee.']), indent=2)+'\n')


async def rest(store, path, **context):
    sent, mono = time.time_ns(), time.monotonic_ns()
    def fetch():
        with urllib.request.urlopen(REST+path, timeout=12) as response:
            return json.load(response)
    payload = await asyncio.to_thread(fetch)
    store.save('rest', payload, path=path, request_utc_ns=sent,
               request_monotonic_ns=mono, **context)
    return payload


def verified_top(book):
    levels=book.top()
    if not levels['top20_within_snapshot_bounds']:
        # Price can leave a finite REST snapshot even when diff IDs stay continuous.
        # Unknown untouched levels beyond its bounds cannot be reconstructed safely.
        raise BookGap('top20 outside verified snapshot bounds; fresh snapshot required')
    return levels


async def depth_session(store, connection, *, endpoint=DEPTH):
    book = Book()
    snapshot_task = None
    pending = []
    try:
        async with connect(endpoint, open_timeout=12, ping_interval=20, ping_timeout=20) as ws:
            store.save('connection', dict(stream='depth', connection=connection))
            while True:
                raw = await asyncio.wait_for(ws.recv(), 15)
                event = json.loads(raw).get('data')
                if not event or event.get('e') != 'depthUpdate':
                    raise BookGap('unexpected depth payload')
                row = store.save('depth', event, connection=connection)
                if snapshot_task is None:
                    snapshot_task = asyncio.create_task(rest(store,
                        '/fapi/v1/depth?symbol=BTCUSDT&limit=1000', connection=connection))
                if book.snapshot_id is None:
                    pending.append(row)
                    if len(pending) > 10000:
                        raise BookGap('bootstrap buffer overflow')
                    if not snapshot_task.done():
                        continue
                    book.snapshot(snapshot_task.result())
                    events, pending = pending, []
                else:
                    events = [row]
                for item in events:
                    if book.apply(item['payload']):
                        store.save('book', verified_top(book), connection=connection,
                            exchange_event_ms=item['payload'].get('E'),
                            source_receipt_utc_ns=item['receipt_utc_ns'],
                            snapshot_id=book.snapshot_id)
    finally:
        book.invalidate()
        store.save('book_invalidated', dict(connection=connection))
        if snapshot_task:
            snapshot_task.cancel()
            await asyncio.gather(snapshot_task, return_exceptions=True)


async def market_session(store, connection):
    previous = None
    async with connect(MARKET, open_timeout=12, ping_interval=20, ping_timeout=20) as ws:
        store.save('connection', dict(stream='market', connection=connection))
        while True:
            event = json.loads(await asyncio.wait_for(ws.recv(), 15)).get('data')
            if not event or event.get('s') != 'BTCUSDT':
                raise ValueError('unexpected market payload')
            if event.get('e') == 'aggTrade':
                current = event['a']
                if previous is not None and current != previous+1:
                    store.save('trade_gap_or_reorder', dict(previous=previous, current=current,
                                                           connection=connection))
                previous = current
            store.save('market', event, connection=connection)


async def retry(store, name, session):
    connection, delay = 0, 1
    while True:
        connection += 1
        began = time.monotonic()
        try:
            await session(store, connection)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            store.save('connection_error', dict(stream=name, connection=connection,
                error=type(exc).__name__, detail=str(exc), backoff_seconds=delay))
            store.status('reconnecting')
            await asyncio.sleep(delay)
            delay = 1 if time.monotonic()-began > 60 else min(delay*2, 30)


async def housekeeping(store):
    while True:
        for path in ['/fapi/v1/time', '/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=1500']:
            try:
                await rest(store, path)
            except Exception as exc:
                store.save('rest_error', dict(path=path, detail=str(exc)))
        store.status('recording')
        await asyncio.sleep(60)


async def record(output, seconds, snapshot_every=None):
    if snapshot_every is not None:
        from .frozen_inputs import SnapshotStore
        store = SnapshotStore(output)
    else:
        store = Store(output)
    tasks = []
    try:
        metadata = await rest(store, '/fapi/v1/exchangeInfo')
        symbol = next(x for x in metadata['symbols'] if x['symbol'] == 'BTCUSDT')
        if symbol['contractType'] != 'PERPETUAL' or symbol['status'] != 'TRADING':
            raise ValueError('unexpected instrument/status')
        tasks = [asyncio.create_task(retry(store, 'depth', depth_session)),
                 asyncio.create_task(retry(store, 'market', market_session)),
                 asyncio.create_task(housekeeping(store))]
        if snapshot_every is not None:
            tasks.append(asyncio.create_task(store.snapshots(snapshot_every)))
        store.status('recording')
        await asyncio.sleep(seconds)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        store.finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--snapshot-every', type=int, default=None,
        help='Freeze actual-receipt input requests at this interval; no model/trading')
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('seconds must be positive')
    if args.snapshot_every is not None and args.snapshot_every < 1:
        parser.error('snapshot interval must be positive')
    asyncio.run(record(args.output, args.seconds, args.snapshot_every))
