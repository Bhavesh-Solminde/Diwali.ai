# Purchased simulator: blank chart investigation

1 November 2026. Read-only inspection of the supplied Mac archives and compiled managed assemblies, plus the current v0.5 runtime log. Original packages and application binaries were not modified by this investigation. No model training was started.

## Findings

The simulation updates its price and portfolio UI, but its GPU chart rendering fails. The v0.5 log explicitly says `Custom/CandlestickGPU_StyleMatch` requires unbound ComputeBuffers at indices 3, 4, 5, 6 and 7 and skips draw calls to avoid crashing. This directly explains missing candles; a zoom adjustment cannot repair missing buffer bindings.

Both archives contain the same named chart shader and the same serialized buffer slot declarations:

| Stage | Buffer | Slot |
|---|---|---:|
| Vertex | Candles | 3 |
| Vertex | Wicks | 4 |
| Vertex | VolumeBars | 5 |
| Vertex | OrderBars | 6 |
| Vertex | TradeMarkers | 7 |
| Vertex | Scale | 8 |
| Fragment | Color | 0 |

The compiled `GPUCandlestickChart.RebuildGPUData` binds Candles/Scale/Color to `mat[0]`, Wicks/Scale/Color to `mat[1]`, and VolumeBars/Scale/Color to `mat[2]`. `DrawLiveCandle` likewise binds only the relevant subset to each material before drawing. The shared shader declares additional buffers even for these paths. This is strong evidence of a shader/material resource-binding mismatch: Metal sees missing resources and refuses the draw. Runtime evidence does not yet identify every material/draw call responsible, so the exact repair still requires validation.

An additional suspicious path binds null as the wick Color buffer when the wick/color history counts differ. Whether that condition is reached in the observed run is not established.

## Version comparison

| Item | v0.4 | v0.5 |
|---|---|---|
| Unity | 6000.0.16f1 | 6000.3.17f1 |
| Assembly-CSharp.dll size | 48,640 bytes | 55,296 bytes |
| Chart shader buffer declarations | Same slots listed above | Same slots listed above |
| Market class | MarketSimulatorReal | MarketSimulator |
| Displayed candle aggregation helpers | Not present under the new names | EffectiveCandleAggregationSize, RebuildDisplayedCandlesFromRaw |
| Runtime tested in this comparison | No | Existing run and log inspected |

The old version is a useful diagnostic test, but is not established as a working fallback. Shared static declarations and partial binding patterns suggest it may have the same problem; the engine change could affect runtime behavior.

Both packages are compiled Unity applications, not complete Unity source projects. No original C# or shader source was supplied in these archives. Assembly inspection exposes method structure and IL; a UnityPy shader export is only a partial representation, explicitly not a compilable replacement shader.

## Display issue

Window resizing changed clipping but did not restore the chart. The earlier 1920x1080 preference edit was not proven to take effect after restart; cached preferences/window restoration can supersede direct file edits. Do not count that attempt as a successful resolution test. The large/clipped UI remains a separate layout problem. The inspected update method handles Escape by switching to windowed mode and F11 by toggling fullscreen/windowed modes. Chart scroll input controls chartScale, which cannot resolve skipped GPU drawing.

## Repair and verification path

1. Test v0.4 separately, preserving v0.5 logs and backing up preferences first because both versions share `com.Krafer.MarketSimulation`.
2. With source access, bind valid resources for every buffer declared by the active shader on every affected material, including valid dummy buffers for unused paths, or split the shader into variants/passes with only the resources each draw needs. Ensure buffer lifetime, indexing and lengths are valid. A blind buffer substitution is not a verified repair.
3. Rebuild for Metal and verify historical/live candles, wicks, volume, order bars/history and trade markers, including empty histories, simulated trades, replay/restore and resizing. Confirm missing-buffer warnings disappear.
4. A compiled-assembly patch is an experimental alternative requiring a separate copy and explicit before/after runtime tests. No such patch has been made.

## Evidence saved alongside this report

- `v05-player.log`: current app log copied before another build can overwrite it.
- `04-shader-bindings.json` and `05-shader-bindings.json`: serialized shader resource declarations.
- `04-selected-il.txt` and `05-selected-il.txt`: selected managed method disassembly for comparison.

Archive SHA-256:

- Kat0-4(Mac).zip: d1b5e77f9ef589473c6fa7933d915101aec224dcb4d22bfa196aa85d974bf093
- Kat-05(Mac).app.zip: 8602f01b15b95310df6341d808cd1416008d9ba9f7b8202228877d551ef68ca3

This investigation diagnoses the rendering failure; it does not establish simulator realism or suitability as a live BTC training distribution.
