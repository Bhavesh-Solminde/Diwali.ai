// Original DLL invocation in an explicitly configured CLR host, outside Unity.
// No binary patches, native constructors, UI inputs, chart drawing or bot training.
using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
public static class OriginalHost {
 static Assembly asm; static bool v05; static Type mt,bt,tt,ct,lt; static MethodInfo place,remove,prune,record,attempt;
 static FieldInfo rng; static BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 static object Get(object o,string n)=>o.GetType().GetField(n,flags).GetValue(o);
 static void Set(object o,string n,object x) {var f=o.GetType().GetField(n,flags);f.SetValue(o,Convert.ChangeType(x,f.FieldType,CultureInfo.InvariantCulture));}
 static long L(object o,string n)=>Convert.ToInt64(Get(o,n));
 static object Price(long p)=>v05?(object)p:(object)(int)p;
 static long SumBook(object b,string side)=>((IDictionary)Get(b,side)).Values.Cast<int>().Sum(x=>(long)x);
 public class State {
  public object m,b; public List<object> agents=new List<object>(); public List<Action<int>> acts=new List<Action<int>>();
  public int candle; public long last,referencePrice; public double recentVolume;
  public long Cash()=>agents.Sum(t=>L(t,"USD")); public long Coins()=>agents.Sum(t=>L(t,"BTC"));
  public string Fingerprint() {
   var s=new StringBuilder();s.Append(last).Append('|').Append(candle);
   foreach(string side in new[]{"buyBook","sellBook"}) foreach(DictionaryEntry x in (IDictionary)Get(b,side))s.Append('|').Append(x.Key).Append(':').Append(x.Value);
   if(v05)foreach(var a in agents)s.Append('|').Append(L(a,"USD")).Append(':').Append(L(a,"BTC"));
   return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s.ToString())));
  }
 }
 public static State Init(int seed) {
  var s=new State();s.m=RuntimeHelpers.GetUninitializedObject(mt);s.b=Activator.CreateInstance(bt);s.last=10000;
  mt.GetField("orderBook").SetValue(s.m,s.b);bt.GetField("market").SetValue(s.b,s.m);
  mt.GetField("chart").SetValue(s.m,RuntimeHelpers.GetUninitializedObject(ct));
  Set(s.m,"lastPrice",10000);Set(s.b,"lastTradedPrice",10000);Set(s.b,"proportionMaker",0.1f);Set(s.b,"traderActivityRate",0.1f);
  bt.GetField("rng",flags).SetValue(s.b,new Random(seed));
  var cap=new Random(unchecked(seed*31+17));
  for(int i=0;i<200;i++) {var t=Activator.CreateInstance(tt,new[]{s.b});rng.SetValue(t,new Random(unchecked(seed*1009+i*7919)));if(v05){Set(t,"USD",cap.Next(100000,1000000));Set(t,"BTC",cap.Next(10,100));}s.agents.Add(t);s.acts.Add((Action<int>)attempt.CreateDelegate(typeof(Action<int>),t));}
  Reset(s);return s;
 }
 public static void Reset(State s) {mt.GetField("liveCandlestick").SetValue(s.m,Activator.CreateInstance(lt,new[]{Price(s.last)}));}
 static void Step(State s) {
  for(int j=0;j<5;j++)foreach(var a in s.acts)a(s.candle);
  var live=Get(s.m,"liveCandlestick");s.last=L(live,"close");Set(s.m,"lastPrice",s.last);record.Invoke(s.b,new[]{Price(s.last)});
  s.recentVolume=L(live,"volume");s.candle++;Set(s.m,"currentCandleIndex",s.candle);
  if(!v05)prune.Invoke(s.b,new object[]{(int)s.last,64});remove.Invoke(s.b,new object[]{0.1f,0});
 }
 static long Depth(State s,bool buy) {
  long d=0;foreach(DictionaryEntry x in (IDictionary)Get(s.b,buy?"sellBook":"buyBook")){long p=Convert.ToInt64(x.Key);if(Math.Abs((double)p/s.last-1)<=0.001+1e-12)d+=Convert.ToInt64(x.Value);}return d;
 }
 static double Bp(long p,long arrival)=>10000*((double)p/arrival-1);
 static string F(object x)=>Convert.ToString(x,CultureInfo.InvariantCulture);
 static void Write(StreamWriter w,params object[] fields)=>w.WriteLine(string.Join(",",fields.Select(F)));
 static void Observe(StreamWriter w,State s,string id,string scenario,int relative) {
  var live=Get(s.m,"liveCandlestick");long bid=L(s.b,"BestBid"),ask=L(s.b,"BestAsk");
  int negCash=v05?s.agents.Count(t=>L(t,"USD")<0):0,negCoin=v05?s.agents.Count(t=>L(t,"BTC")<0):0;
  var bids=(IDictionary)Get(s.b,"buyBook");object key=Price(s.referencePrice);int refQty=bids.Contains(key)?Convert.ToInt32(bids[key]):0;
  Write(w,id,scenario,relative,s.candle,L(s.b,"lastTradedPrice"),L(live,"open"),L(live,"high"),L(live,"low"),L(live,"volume"),bid,ask,SumBook(s.b,"buyBook"),SumBook(s.b,"sellBook"),L(s.b,"totalBuyVolume"),L(s.b,"totalSellVolume"),negCash,negCoin,v05?s.Cash():0,v05?s.Coins():0,s.referencePrice,refQty);
 }
 static (int filled,long notional,long vwap) Trade(State s,bool buy,int q) {
  long cash=s.Cash(),coins=s.Coins();long vw=Convert.ToInt64(place.Invoke(s.b,new object[]{buy?long.MaxValue:1L,q,buy,null}));
  return ((int)Math.Abs(s.Coins()-coins),Math.Abs(s.Cash()-cash),vw);
 }
 public static void Configure(string managed,string version) {
  v05=version=="05";
  Assembly.LoadFrom(Path.Combine(managed,"UnityEngine.CoreModule.dll"));asm=Assembly.LoadFrom(Path.Combine(managed,"Assembly-CSharp.dll"));
  string suffix=v05?"":"Real";mt=asm.GetType("MarketSimulator"+suffix);bt=asm.GetType("OrderBook"+suffix);tt=asm.GetType("Trader"+suffix);ct=asm.GetType("GPUCandlestickChart");lt=asm.GetType("LiveCandlestick"+suffix);
  place=bt.GetMethod("PlaceOrder");remove=bt.GetMethod("RandomlyRemoveOrders");prune=bt.GetMethod("TruncateAroundAnchorEdges");record=bt.GetMethod("RecordTrade");attempt=tt.GetMethod("TryPlaceOrders");rng=tt.GetField("rng",flags);
 }
 public static void Run(string managed,string version,string output) {
  Directory.CreateDirectory(output);Configure(managed,version);
  using(var manifest=new StreamWriter(Path.Combine(output,"runs-v"+version+".csv")))
  using(var candles=new StreamWriter(Path.Combine(output,"candles-v"+version+".csv")))
  using(var fills=new StreamWriter(Path.Combine(output,"fills-v"+version+".csv"))) {
   manifest.WriteLine("run_id,parent_id,phase,seed,version,scenario,status,error,initial_fingerprint,matched_baseline,arrival,q_intended,q_filled,notional_entry,notional_exit,residual_coin,return_1_bp,return_5_bp,return_15_bp,return_30_bp,return_34_bp,depth_10bp,baseline_volume_30,warmup_negative_cash,warmup_negative_coin");
   candles.WriteLine("run_id,scenario,relative_candle,candle_index,last_price,open,high,low,reported_volume,best_bid,best_ask,bid_sum,ask_sum,counter_bid,counter_ask,negative_cash_agents,negative_coin_agents,total_agent_cash,total_agent_coin,reference_price,bid_at_reference");
   fills.WriteLine("run_id,scenario,relative_candle,side,intended,filled,notional,integer_vwap,last_after");
   for(int parent=0;parent<40;parent++) {
    int seed=parent<10?10000+parent:20000+parent-10;string phase=parent<10?"pilot":"main",pid="v"+version+"-"+seed;string baselineHash=null;
    var scenarios=v05?new[]{"baseline","buy_d0.1","buy_d0.5","buy_d1","buy_d2","sell_d0.1","sell_d0.5","sell_d1","sell_d2","buy_one10","buy_slice10","sell_one10","sell_slice10","roundtrip_buy","roundtrip_sell"}:new[]{"baseline","wall_weak10","wall_strong100"};
    foreach(var scenario in scenarios) {
     string id=pid+"-"+scenario,status="ok",error="",hash="";bool matched=false;long arrival=0,depth=0,entryN=0,exitN=0;int intended=0,filled=0,residual=0,wnegC=0,wnegB=0;double vol=0;var prices=new Dictionary<int,long>();
     try {
      var s=Init(seed);var volumes=new Queue<double>();for(int c=0;c<100;c++){Step(s);volumes.Enqueue(s.recentVolume);if(volumes.Count>30)volumes.Dequeue();Reset(s);}vol=volumes.Sum();
      arrival=s.last;s.referencePrice=(long)Math.Floor(arrival*0.999);hash=s.Fingerprint();if(scenario=="baseline")baselineHash=hash;matched=hash==baselineHash;if(!matched)throw new Exception("warmup_fingerprint_mismatch");
      if(v05){wnegC=s.agents.Count(t=>L(t,"USD")<0);wnegB=s.agents.Count(t=>L(t,"BTC")<0);}
      bool buy=!scenario.StartsWith("sell")&&!scenario.EndsWith("sell");depth=v05?Depth(s,buy):0;
      if(scenario.StartsWith("wall")){int q=scenario=="wall_weak10"?10:100;place.Invoke(s.b,new object[]{(int)Math.Floor(arrival*0.999),q,true});intended=q;}
      if(scenario.Contains("_d")){double ratio=double.Parse(scenario.Split('_')[1].Substring(1),CultureInfo.InvariantCulture);if(depth<=0)status="unavailable_zero_10bp_depth";else intended=Math.Max(1,(int)Math.Ceiling(depth*ratio));}
      else if(v05&&scenario!="baseline")intended=10;
      int slices=scenario.Contains("slice")?5:1;
      if(v05&&intended>0&&status=="ok") {var f=Trade(s,buy,slices==5?2:intended);filled+=f.filled;entryN+=f.notional;residual+=f.filled;Write(fills,id,scenario,0,buy?"buy":"sell",slices==5?2:intended,f.filled,f.notional,f.vwap,L(s.b,"lastTradedPrice"));}
      Observe(candles,s,id,scenario,0);
      for(int h=1;h<=34;h++) {
       Step(s);prices[h]=s.last;Observe(candles,s,id,scenario,h);Reset(s);
       if(slices==5&&h<=4){var f=Trade(s,buy,2);filled+=f.filled;entryN+=f.notional;residual+=f.filled;Write(fills,id,scenario,h,buy?"buy":"sell",2,f.filled,f.notional,f.vwap,L(s.b,"lastTradedPrice"));}
       if(scenario.StartsWith("roundtrip")&&h==5&&residual>0){int request=residual;var f=Trade(s,!buy,request);exitN+=f.notional;residual-=f.filled;Write(fills,id,scenario,h,buy?"sell":"buy",request,f.filled,f.notional,f.vwap,L(s.b,"lastTradedPrice"));}
      }
     } catch(Exception ex){status="error";error=(ex.InnerException??ex).GetType().Name;}
     Write(manifest,id,pid,phase,seed,version,scenario,status,error,hash,matched,arrival,intended,filled,entryN,exitN,residual,prices.ContainsKey(1)?Bp(prices[1],arrival):double.NaN,prices.ContainsKey(5)?Bp(prices[5],arrival):double.NaN,prices.ContainsKey(15)?Bp(prices[15],arrival):double.NaN,prices.ContainsKey(30)?Bp(prices[30],arrival):double.NaN,prices.ContainsKey(34)?Bp(prices[34],arrival):double.NaN,depth,vol,wnegC,wnegB);
     manifest.Flush();
    }
    Console.WriteLine("Completed "+pid);
   }
  }
 }
}
