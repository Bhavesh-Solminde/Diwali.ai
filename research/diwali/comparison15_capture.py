"""Capture the raw public feeds needed to verify Diwali 1.5 inputs."""
import argparse
import asyncio
from functools import partial
from pathlib import Path
import shutil

import json
from websockets.asyncio.client import connect

from ..market_data.collect import Store, depth_session, rest, retry
from ..market_data.validate_archive import file_hash, save

PUBLIC = 'wss://fstream.binance.com/public/stream?streams=btcusdt@'
DEPTH = PUBLIC + 'depth@0ms'
TRADES = PUBLIC + 'trade'
GIB = 1024**3


async def trade_session(store, connection):
    previous = None
    async with connect(TRADES, open_timeout=12, ping_interval=20, ping_timeout=20) as ws:
        store.save('connection', {'stream': 'individual_trade', 'connection': connection})
        while True:
            event = json.loads(await asyncio.wait_for(ws.recv(), 15)).get('data')
            if (not event or event.get('e') != 'trade' or event.get('s') != 'BTCUSDT'
                    or not {'t', 'E', 'T', 'X', 'm', 'p', 'q'} <= event.keys()):
                raise ValueError('Unexpected individual trade message')
            current = event['t']
            row = store.save('individual_trade', event, connection=connection)
            if previous is not None and current != previous+1:
                store.save('individual_trade_gap', {'previous_id': previous, 'current_id': current,
                           'trade_receipt_utc_ns': row['receipt_utc_ns'], 'connection': connection})
            previous = current


async def health(store, budget):
    while True:
        if (shutil.disk_usage(store.root).free < 20*GIB
                or sum(p.stat().st_size for p in store.root.glob('events-*.jsonl')) >= budget):
            raise RuntimeError('Capture reached its disk safety limit')
        await rest(store, '/fapi/v1/time')
        store.status('recording')
        await asyncio.sleep(60)


async def record(output, seconds, budget):
    store = Store(output)
    tasks = []
    save(output/'capture-protocol.json', {
        'depth': DEPTH, 'trades': TRADES, 'seconds': seconds, 'disk_budget_bytes': budget,
        'purpose': 'Input verification and warmup only',
        'source_hashes': {p.name: file_hash(p) for p in
                          [Path(__file__), Path(__file__).parents[1]/'market_data/collect.py',
                           Path(__file__).parents[1]/'market_data/book.py']}})
    failure = None
    try:
        metadata = await rest(store, '/fapi/v1/exchangeInfo')
        symbol = next(s for s in metadata['symbols'] if s['symbol'] == 'BTCUSDT')
        if symbol['contractType'] != 'PERPETUAL' or symbol['status'] != 'TRADING':
            raise ValueError('Unexpected instrument or trading status')
        tasks = [asyncio.create_task(retry(store, 'depth', partial(depth_session, endpoint=DEPTH))),
                 asyncio.create_task(retry(store, 'individual_trade', trade_session)),
                 asyncio.create_task(health(store, budget))]
        done, _ = await asyncio.wait(tasks, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
            raise RuntimeError('Capture task ended early')
    except Exception as exc:
        failure = str(exc)
        store.save('capture_failure', {'error': type(exc).__name__, 'detail': failure})
        raise
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        store.finish()
        manifest_path = output/'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['state'] = 'failed' if failure else 'stopped'
        manifest['failure'] = failure
        manifest['limitations'] = ['Finite public book coverage.', 'Receipt clocks and trade continuity require audit.']
        manifest['forecasts_issued'] = 0
        save(manifest_path, manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--budget-gib', type=int, default=20)
    args = parser.parse_args()
    if min(args.seconds, args.budget_gib) <= 0:
        parser.error('Duration and disk budget must be positive')
    asyncio.run(record(args.output, args.seconds, args.budget_gib*GIB))
