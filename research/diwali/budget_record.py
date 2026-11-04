"""Record native public-market messages with an explicit immutable time budget."""
import argparse,asyncio,json
from pathlib import Path
from .prospective import capture,exclusive_json
from ..market_data.validate_archive import file_hash


async def record(output,run,seconds):
    task=asyncio.create_task(capture(output,run,seconds))
    try:
        while not (output/'status.json').exists():
            if task.done():await task;raise ValueError('Receiver ended before recording')
            await asyncio.sleep(.01)
        status=json.loads((output/'status.json').read_text())
        if status['state']!='recording':await task;raise ValueError('Receiver not recording')
        exclusive_json(output/'capture-budget.json',{'seconds':seconds,'start_utc_ns':status['start_utc_ns'],'native_model_run':str(run),'recorder_source_sha256':file_hash(Path('research/diwali/prospective.py')),'budget_wrapper_sha256':file_hash(Path(__file__))})
        await task
    finally:
        if not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--run',type=Path,default=Path('data/models/diwali0.5'));p.add_argument('--seconds',type=int,default=7200);a=p.parse_args()
    if a.seconds<=0:raise ValueError('Positive receiver budget required')
    asyncio.run(record(a.output,a.run,a.seconds))
