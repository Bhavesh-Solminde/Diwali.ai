// Local DOM/canvas harness. This checks behaviour, not visual browser rendering.
// Start research.diwali.event_serve on port 8754 before running with Node.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.style={};this.dataset={};this.value='0';this.clientWidth=1100;this.clientHeight=440;this.disabled=false;this.textContent=''}
  append(...xs){for(const x of xs)this.children.push(...(x.tag==='fragment'?x.children:[x]))}
  replaceChildren(...xs){this.children=[];this.append(...xs)}
  setAttribute(k,v){this[k]=v}
  addEventListener(k,v){this['on'+k]=v}
  getContext(){return new Proxy({}, {get:()=>()=>{},set:()=>true})}
}
const els=new Map(),document={getElementById(id){if(!els.has(id))els.set(id,new Element(id));return els.get(id)},createElement:t=>new Element(t),createDocumentFragment:()=>new Element('fragment')};
const ctx=vm.createContext({document,window:{devicePixelRatio:1,addEventListener(){}},fetch:(path,opts)=>fetch('http://127.0.0.1:8754'+path,opts),setInterval(){},console,Date,Math,JSON,Error,Number});
vm.runInContext(fs.readFileSync('research/diwali/event_dashboard.js','utf8'),ctx);
const sleep=t=>new Promise(r=>setTimeout(r,t));
(async()=>{
  for(let i=0;i<100;i++){if(vm.runInContext('current !== null && !busy',ctx)&&els.get('development').children.length)break;await sleep(100)}
  assert.equal(els.get('chart').dataset.actualCloses,0);assert.equal(els.get('chart').dataset.forecastColumns,0);
  await els.get('predict').onclick();assert.equal(els.get('chart').dataset.forecastColumns,15);assert.equal(els.get('chart').dataset.actualCloses,0);assert.equal(els.get('grid').children.length,27);
  assert(!els.get('grid').children.some(tr=>tr.children.some(td=>td.className==='actual')));
  assert(vm.runInContext('inRange(prediction.fan[0].ranges[16].lower_price,prediction.fan[0].ranges[16])',ctx));
  assert(!vm.runInContext('inRange(prediction.fan[0].ranges[15].upper_price,prediction.fan[0].ranges[15])',ctx));
  const frozen=vm.runInContext('JSON.stringify(prediction.fan)',ctx);
  await els.get('reveal').onclick();assert.equal(els.get('chart').dataset.actualCloses,15);assert.equal(vm.runInContext('JSON.stringify(prediction.fan)',ctx),frozen);
  assert.equal(els.get('grid').children.reduce((n,tr)=>n+tr.children.filter(td=>td.className==='actual').length,0),15);
  els.get('case').value='5';await els.get('case').onchange();assert.equal(els.get('chart').dataset.actualCloses,0);assert.equal(els.get('grid').children.length,0);assert.equal(els.get('reveal').disabled,true);
  assert.equal(els.get('error').textContent,'');
  console.log('Dashboard checks passed: predict/reveal/reset, 15 columns, hidden answers, immutable fan, exact +2bp band, 15 actual markers.');
})().catch(e=>{console.error(e);process.exitCode=1});
