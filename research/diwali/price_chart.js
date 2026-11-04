// Discrete whole-bin probability mass on a linear price axis, never a density.
function drawPriceChart(){
  if(!current)return;
  const canvas=document.getElementById('price-chart'),ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=420,dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(w*dpr);canvas.height=h*dpr;ctx.scale(dpr,dpr);
  const past=current.past.slice(-40),future=fanPrediction?fanPrediction.fan:[],actual=fanActuals||[];
  canvas.dataset.forecastColumns=future.length;canvas.dataset.actualCandles=actual.length;
  const left=12,right=w-78,top=42,bottom=h-48,first=past[0].time+60000,last=current.target_ms+15*60000;
  const x=t=>left+(t-first)/(last-first)*(right-left),step=(right-left)*60000/(last-first);
  let low=Math.min(...past.map(c=>c.ohlc[2]),current.reference*.998),high=Math.max(...past.map(c=>c.ohlc[1]),current.reference*1.002);
  for(const c of actual){low=Math.min(low,c.ohlc[2]);high=Math.max(high,c.ohlc[1])}
  const pad=Math.max((high-low)*.08,1);low-=pad;high+=pad;
  const y=p=>top+(high-p)/(high-low)*(bottom-top);
  ctx.fillStyle='#121827';ctx.fillRect(0,0,w,h);ctx.font='12px system-ui';ctx.fillStyle='#d3deea';ctx.fillText('BTC / USDT · 1 minute',14,24);
  ctx.fillStyle='#c5b2e4';ctx.textAlign='right';ctx.fillText(actual.length?'Actual candles revealed':'Future close probabilities',w-14,24);ctx.textAlign='left';
  for(let k=0;k<=4;k++){let p=low+(high-low)*k/4;ctx.strokeStyle='#293344';ctx.beginPath();ctx.moveTo(left,y(p));ctx.lineTo(right,y(p));ctx.stroke();ctx.fillStyle='#d3deea';ctx.fillText(p.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}),right+8,y(p)+4)}
  ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
  for(const item of future)for(const r of item.ranges){let hi=Math.min(high,r.upper_price===null?high:r.upper_price),lo=Math.max(low,r.lower_price===null?low:r.lower_price);if(hi<=lo)continue;ctx.fillStyle='rgba(136,101,196,'+Math.min(.95,r.probability*6)+')';ctx.fillRect(x(item.close_ms)-step*.46,y(hi),step*.92,Math.max(.2,y(lo)-y(hi)))}
  const candle=(c,revealed=false)=>{let [o,hi,lo,cl]=c.ohlc,pos=x(c.time+60000),width=Math.max(1.3,step*.62);ctx.strokeStyle=revealed?'#fff':cl>=o?'#12b6a0':'#df6a83';ctx.lineWidth=revealed?1.5:1;ctx.beginPath();ctx.moveTo(pos,y(hi));ctx.lineTo(pos,y(lo));ctx.stroke();ctx.fillStyle=cl>=o?'#12b6a0':'#df6a83';ctx.fillRect(pos-width/2,Math.min(y(o),y(cl)),width,Math.max(1,Math.abs(y(o)-y(cl))));if(revealed)ctx.strokeRect(pos-width/2,Math.min(y(o),y(cl)),width,Math.max(1,Math.abs(y(o)-y(cl))))};
  past.forEach(c=>candle(c));actual.forEach(c=>candle(c,true));
  ctx.setLineDash([4,4]);ctx.strokeStyle='#c5b2e4';ctx.beginPath();ctx.moveTo(x(current.snapshot_ms),top);ctx.lineTo(x(current.snapshot_ms),bottom);ctx.stroke();ctx.setLineDash([]);
  if(future.length){let selected=Number(document.getElementById('horizon').value)||0;ctx.strokeStyle='#c5b2e4';ctx.strokeRect(x(future[selected].close_ms)-step*.49,top,step*.98,bottom-top)}
  ctx.restore();ctx.font='11px system-ui';ctx.fillStyle='#d3deea';ctx.textAlign='center';
  for(let t of [first,current.snapshot_ms,last]){ctx.fillText(new Date(t).toISOString().slice(11,16),Math.max(30,Math.min(right-4,x(t))),bottom+22)}ctx.textAlign='left';ctx.fillText('UTC closing times',14,h-7);
  if(!future.length){ctx.fillStyle='#c5b2e4';ctx.fillText('Click Predict',Math.min(right-100,x(current.target_ms+60000)),top+35)}
  canvas._view={left,right,top,bottom,low,high,first,last};
}
function inspectPriceChart(event){
  if(!fanPrediction)return;
  const c=document.getElementById('price-chart'),rect=c.getBoundingClientRect(),v=c._view,px=event.clientX-rect.left,py=event.clientY-rect.top;
  if(!v||px<v.left||px>v.right||py<v.top||py>v.bottom)return;
  const time=v.first+(px-v.left)/(v.right-v.left)*(v.last-v.first),price=v.high-(py-v.top)/(v.bottom-v.top)*(v.high-v.low);
  let h=Math.round((time-fanPrediction.fan[0].close_ms)/60000);if(h<0||h>=15)return;
  const item=fanPrediction.fan[h],r=item.ranges.find(r=>(r.lower_price===null||price>r.lower_price)&&(r.upper_price===null||price<=r.upper_price));
  if(!r)return;const bounds=r.lower_price===null?'at or below $'+r.upper_price.toFixed(2):r.upper_price===null?'above $'+r.lower_price.toFixed(2):'$'+r.lower_price.toFixed(2)+' to $'+r.upper_price.toFixed(2);
  document.getElementById('price-inspect').textContent=new Date(item.close_ms).toISOString().slice(11,19)+' UTC: '+bounds+', '+(100*r.probability).toFixed(2)+'% whole-bin probability.';
  if(event.type==='click'){document.getElementById('horizon').value=h;selectedHorizon()}
}
const originalDraw=draw;draw=function(real){originalDraw(real);drawPriceChart()};
const originalSelectedHorizon=selectedHorizon;selectedHorizon=function(){originalSelectedHorizon();drawPriceChart()};
const originalMarkFanActuals=markFanActuals;markFanActuals=function(a){originalMarkFanActuals(a);drawPriceChart()};
document.getElementById('horizon').onchange=selectedHorizon;
document.getElementById('price-chart').addEventListener('mousemove',inspectPriceChart);
document.getElementById('price-chart').addEventListener('click',inspectPriceChart);
window.addEventListener('resize',drawPriceChart);
