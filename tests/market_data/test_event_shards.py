from datetime import datetime,timezone
import numpy as np
import pytest
from research.market_data.event_replay import DTYPE as BOOK
from research.market_data.trade_events import DTYPE as TRADE
from research.market_data.event_shards import store_events,read_events,allowed


def test_exact_integer_compression_roundtrip(tmp_path):
    rng=np.random.default_rng(17)
    for dtype in [BOOK,TRADE]:
        data=np.zeros(31,dtype=dtype)
        for name in dtype.names:data[name]=rng.integers(0,2**54,size=data[name].shape,dtype=np.int64)
        path=tmp_path/(str(dtype.itemsize)+'.parquet');store_events(path,data)
        assert read_events(path,dtype).tobytes()==data.tobytes()


def test_reserved_final_dates_cannot_be_prepared():
    def at(x):return datetime.fromisoformat(x).replace(tzinfo=timezone.utc)
    allowed(at('2026-08-01'),at('2026-08-03'))
    with pytest.raises(ValueError,match='final period denied'):allowed(at('2026-09-14'),at('2026-09-16'))
