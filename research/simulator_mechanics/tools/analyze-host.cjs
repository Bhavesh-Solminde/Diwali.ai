const fs=require('fs'),path=require('path');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..')),dir=path.join(root,'evidence','original-host');
fs.mkdirSync(path.join(root,'reports'),{recursive:true});
function csv(name){let [head,...rows]=fs.readFileSync(path.join(dir,name),'utf8').trim().split(/\r?\n/);head=head.split(',');return rows.map(l=>Object.fromEntries(l.split(',').map((v,i)=>[head[i],v])));}
function quant(a,p){a=[...a].sort((x,y)=>x-y);const x=(a.length-1)*p,j=Math.floor(x);return a[j]+(a[Math.ceil(x)]-a[j])*(x-j);}
function stats(a){a=a.filter(Number.isFinite);if(!a.length)return {n:0};return{n:a.length,mean:a.reduce((s,x)=>s+x,0)/a.length,median:quant(a,.5),p05:quant(a,.05),p95:quant(a,.95),min:Math.min(...a),max:Math.max(...a)};}
function variancePlan(a){const s=stats(a),variance=a.reduce((t,x)=>t+(x-s.mean)**2,0)/(a.length-1);return{n:a.length,sample_sd_bp:Math.sqrt(variance),illustrative_parents_for_10bp_effect_80pct_normal_power:Math.max(30,Math.ceil(7.84*variance/100)),note:'Future planning illustration from 10 pilot parents; unstable variance estimate; not actual achieved power; no multiplicity correction. Repair systematic defects before expansion.'};}
let state=123456789;function rand(){state=(Math.imul(1664525,state)+1013904223)>>>0;return state/4294967296;}
function estimate(a){let s=stats(a);if(!s.n)return s;const boot=Array.from({length:2000},()=>a.reduce(t=>t+a[Math.floor(rand()*a.length)],0)/a.length);return {...s,mean_ci95:[quant(boot,.025),quant(boot,.975)]};}
const results={environment:'original_DLL_CLR_host',uncertainty:'percentile bootstrap means across 30 seeded main parent states; 2000 resamples, analysis RNG LCG seed123456789. No Unity/live BTC inference.',versions:{}};
let all=[];
for(const v of ['04','05']){
 const runs=csv(`runs-v${v}.csv`),candles=csv(`candles-v${v}.csv`),fills=csv(`fills-v${v}.csv`),main=runs.filter(r=>r.phase==='main'),byId=new Map();
 for(const c of candles){if(!byId.has(c.run_id))byId.set(c.run_id,[]);byId.get(c.run_id).push(c);}
 const base=new Map(main.filter(r=>r.scenario==='baseline').map(r=>[r.parent_id,r]));
 const pilotBase=new Map(runs.filter(r=>r.phase==='pilot'&&r.scenario==='baseline').map(r=>[r.parent_id,r]));
 const rv={attempts:runs.length,main_parents:base.size,status_counts:{},fingerprint_mismatches:runs.filter(r=>r.matched_baseline!=='True').length,scenarios:{}};
 for(const r of runs)rv.status_counts[r.status]=(rv.status_counts[r.status]||0)+1;
 for(const scenario of [...new Set(main.map(r=>r.scenario))]){
  const group=main.filter(r=>r.scenario===scenario&&r.status==='ok'),out={n:group.length,price_return_bp:{},paired_minus_baseline_bp:{}};
  out.pilot_variance_and_future_expansion=variancePlan(runs.filter(r=>r.phase==='pilot'&&r.scenario===scenario&&r.status==='ok').map(r=>+r.return_30_bp-(+pilotBase.get(r.parent_id).return_30_bp)));
  for(const h of [1,5,15,30,34]){
   out.price_return_bp[h]=estimate(group.map(r=>+r[`return_${h}_bp`]));
   out.paired_minus_baseline_bp[h]=estimate(group.map(r=>+r[`return_${h}_bp`]-+base.get(r.parent_id)[`return_${h}_bp`]));
  }
  out.negative_portfolios_at_warmup=group.filter(r=>+r.warmup_negative_cash>0||+r.warmup_negative_coin>0).length;
  out.negative_portfolios_at_end=group.filter(r=>byId.get(r.run_id).some(c=>+c.relative_candle===34&&(+c.negative_cash_agents>0||+c.negative_coin_agents>0))).length;
  out.counter_mismatch_paths=group.filter(r=>byId.get(r.run_id).some(c=>+c.counter_bid!==+c.bid_sum||+c.counter_ask!==+c.ask_sum)).length;
  out.locked_or_crossed_paths=group.filter(r=>byId.get(r.run_id).some(c=>+c.best_bid>0&&+c.best_ask<(v==='04'?2147483647:9223372036854775807)&&+c.best_bid>=+c.best_ask)).length;
  out.horizon_recovery_to_half_impact_censored_30=0;
  let exactSlips=[],immediate=[],recoveries=[];
  for(const r of group){
   const ff=fills.filter(f=>f.run_id===r.run_id),buy=!scenario.startsWith('sell')&&!scenario.endsWith('sell'),side=buy?1:-1;
   const entry=ff.filter(f=>scenario.startsWith('roundtrip')?+f.relative_candle===0:true),q=entry.reduce((s,f)=>s+(+f.filled),0),notional=entry.reduce((s,f)=>s+(+f.notional),0);
   if(q)exactSlips.push(side*10000*(notional/q/(+r.arrival)-1));
   if(ff.length){const im=side*10000*((+ff[0].last_after)/(+r.arrival)-1);immediate.push(im);if(im>0){const found=byId.get(r.run_id).find(c=>+c.relative_candle>=1&&+c.relative_candle<=30&&side*10000*((+c.last_price)/(+r.arrival)-1)<=im/2);if(found)recoveries.push(+found.relative_candle);else out.horizon_recovery_to_half_impact_censored_30++;}}
  }
  if(v==='05'&&scenario!=='baseline'){
   out.exact_fill_slippage_bp=estimate(exactSlips);out.immediate_signed_last_price_impact_bp=estimate(immediate);out.recovery_candle_among_recovered=stats(recoveries);
   out.intended_units=stats(group.map(r=>+r.q_intended));out.partial_entry_paths=group.filter(r=>+r.q_filled<+r.q_intended).length;out.residual_units=stats(group.map(r=>+r.residual_coin));
   if(scenario.startsWith('roundtrip')){out.roundtrip_cash_pnl_dollars=estimate(group.map(r=>(scenario.endsWith('buy')?+r.notional_exit-(+r.notional_entry):+r.notional_entry-(+r.notional_exit))/100));out.positive_roundtrips=group.filter(r=>(scenario.endsWith('buy')?+r.notional_exit-(+r.notional_entry):+r.notional_entry-(+r.notional_exit))>0).length;}
  }
  if(scenario.startsWith('wall')){out.wall_touched_paths=group.filter(r=>byId.get(r.run_id).some(c=>+c.relative_candle>0&&+c.low<=+c.reference_price)).length;out.reference_level_present_at_30=group.filter(r=>byId.get(r.run_id).some(c=>+c.relative_candle===30&&+c.bid_at_reference>0)).length;}
  if(scenario.includes('slice')){out.return_from_original_arrival_after_last_slice_bp={};for(const h of [1,5,15,30])out.return_from_original_arrival_after_last_slice_bp[h]=estimate(group.map(r=>{const c=byId.get(r.run_id).find(c=>+c.relative_candle===h+4);return 10000*((+c.last_price)/(+r.arrival)-1);}));}
  rv.scenarios[scenario]=out;
 }
 if(v==='05'){rv.schedule_paired_slippage_delta_slice_minus_one={};for(const side of ['buy','sell']){const g=main.filter(r=>r.scenario===`${side}_slice10`);rv.schedule_paired_slippage_delta_slice_minus_one[side]=estimate(g.map(r=>{const one=main.find(x=>x.parent_id===r.parent_id&&x.scenario===`${side}_one10`);return(side==='buy'?1:-1)*10000*((+r.notional_entry)/(+r.q_filled)-(+one.notional_entry)/(+one.q_filled))/(+r.arrival);}));}}
 results.versions[v]=rv;all.push(...runs);
}
fs.writeFileSync(path.join(root,'reports','host-statistics.json'),JSON.stringify(results,null,2));
let md='# Original-DLL host: numerical results\n\nThese are controlled algorithm tests outside Unity, using the research profile in PREREGISTRATION.md. All intervals below are 95% bootstrap intervals for means across 30 main parents. Pilot parents are separate. This is exploratory evidence from one parameter profile, not adequate statistical power established in advance.\n\n';
for(const [v,rv]of Object.entries(results.versions)){
 md+=`## v0.${v.slice(1)}\n\n${rv.attempts} attempted scenarios; ${rv.main_parents} main parents. Status ${JSON.stringify(rv.status_counts)}. Warmup fingerprint mismatches: ${rv.fingerprint_mismatches}.\n\n| Condition | Main n | Mean 30-candle return bp | Paired change vs baseline bp [95% CI] |\n|---|---:|---:|---|\n`;
 for(const [name,s]of Object.entries(rv.scenarios)){let a=s.price_return_bp[30],b=s.paired_minus_baseline_bp[30];md+=`| ${name} | ${s.n} | ${a.mean.toFixed(3)} | ${b.mean.toFixed(3)} [${b.mean_ci95.map(x=>x.toFixed(3)).join(', ')}] |\n`;}
 md+='\n';
 if(v==='05'){
 md+='| Condition | Signed immediate impact bp | Exact fill slippage bp | Partial entries / n |\n|---|---:|---:|---:|\n';for(const [name,s]of Object.entries(rv.scenarios)){if(name==='baseline')continue;md+=`| ${name} | ${s.immediate_signed_last_price_impact_bp.mean.toFixed(3)} | ${s.exact_fill_slippage_bp.mean.toFixed(3)} | ${s.partial_entry_paths}/${s.n} |\n`;}
 md+='\n';for(const side of ['buy','sell']){let s=rv.scenarios[`roundtrip_${side}`],p=s.roundtrip_cash_pnl_dollars;md+=`Roundtrip ${side}: mean ledger cash PnL $${p.mean.toFixed(4)} [${p.mean_ci95.map(x=>x.toFixed(4)).join(', ')}], positive ${s.positive_roundtrips}/${s.n}, residual max ${s.residual_units.max}. No modeled fees; source balance defects apply.\n\n`;}
 for(const side of ['buy','sell']){let s=rv.schedule_paired_slippage_delta_slice_minus_one[side];md+=`${side} slices minus one-shot execution slippage: ${s.mean.toFixed(3)} bp [${s.mean_ci95.map(x=>x.toFixed(3)).join(', ')}]. Positive is worse.\n\n`;}
 }
}
md+='All per-candle paths and fills remain in evidence/original-host. host-statistics.json contains all horizons, mean/median/quantiles, uncertainty, path failures, negative balances and recovery censoring. Baseline-relative changes are paired by parent. Multiple exploratory comparisons are not multiplicity-adjusted; use them for hypotheses and defect characterization. No result establishes live BTC profitability.\n';fs.writeFileSync(path.join(root,'reports','NUMERICAL-RESULTS.md'),md);
console.log(md);
