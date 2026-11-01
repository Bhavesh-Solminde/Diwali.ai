// Original research instrumentation: per-sweep net book changes and explicit
// removal-call provenance. No purchased source, game patches or native app hooks.
using System;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Text.Json;
public static class FlowHost {
 static BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 static object Get(object o,string n)=>o.GetType().GetField(n,flags).GetValue(o);
 static long Num(object o,string n)=>Convert.ToInt64(Get(o,n));
 static void Put(object o,string n,object v)=>o.GetType().GetField(n,flags).SetValue(o,v);
 static Dictionary<int,int> Book(object b,string side) {
  var result=new Dictionary<int,int>();foreach(DictionaryEntry x in (IDictionary)Get(b,side))result.Add(Convert.ToInt32(x.Key),Convert.ToInt32(x.Value));return result;
 }
 static StreamWriter ZipWriter(string file)=>new StreamWriter(new GZipStream(new FileStream(file,FileMode.CreateNew),CompressionLevel.Fastest));
 static int[][] Levels(Dictionary<int,int> b)=>b.OrderBy(x=>x.Key).Select(x=>new[]{x.Key,x.Value}).ToArray();
 static long Changes(StreamWriter w,int candle,int sweep,string cause,string side,Dictionary<int,int> before,Dictionary<int,int> after) {
  long removed=0;
  foreach(int p in before.Keys.Union(after.Keys).OrderBy(x=>x)) {
   int a=before.GetValueOrDefault(p),b=after.GetValueOrDefault(p);if(a==b)continue;
   if(cause!="agent_sweep_net"&&b>a)throw new Exception("removal_call_added_depth");
   if(b<a)removed+=a-b;
   w.WriteLine($"{candle},{sweep},{cause},{side},{p},{a},{b}");
  }
  return removed;
 }
 public static void Run(string managed,string output,string phase) {
  if(phase!="pilot"&&phase!="main")throw new ArgumentException("phase");
  Directory.CreateDirectory(output);OriginalHost.Configure(managed,"04");
  int n=phase=="pilot"?10:30,start=phase=="pilot"?31000:41000;
  for(int seed=start;seed<start+n;seed++) {
   string id="flow-v04-"+seed,prefix=Path.Combine(output,id);
   if(File.Exists(prefix+".manifest.json")||File.Exists(prefix+".candles.jsonl.gz"))throw new IOException("existing_run_"+id);
   string status="running",error="";int completed=0;long randomRemoved=0,pruned=0;
   try {
    using(var rows=ZipWriter(prefix+".candles.jsonl.gz"))
    using(var events=ZipWriter(prefix+".changes.csv.gz")) {
     events.WriteLine("candle,sweep,cause,side,price,before,after");
     var s=OriginalHost.Init(seed);var control=seed==start?OriginalHost.Init(seed):null;
     var originalStep=typeof(OriginalHost).GetMethod("Step",BindingFlags.NonPublic|BindingFlags.Static);var type=s.b.GetType();
     var record=type.GetMethod("RecordTrade");var prune=type.GetMethod("TruncateAroundAnchorEdges");var remove=type.GetMethod("RandomlyRemoveOrders");
     var bid=Book(s.b,"buyBook");var ask=Book(s.b,"sellBook");
     for(int c=0;c<600;c++) {
      for(int sweep=0;sweep<5;sweep++) {
       foreach(var action in s.acts)action(c);
       var b=Book(s.b,"buyBook");var a=Book(s.b,"sellBook");
       Changes(events,c,sweep,"agent_sweep_net","bid",bid,b);Changes(events,c,sweep,"agent_sweep_net","ask",ask,a);bid=b;ask=a;
      }
      var live=Get(s.m,"liveCandlestick");s.last=Num(live,"close");
      long o=Num(live,"open"),h=Num(live,"high"),l=Num(live,"low"),v=Num(live,"volume");
      if(s.last<=0||l<=0||h<Math.Max(o,s.last)||l>Math.Min(o,s.last)||v<0)throw new Exception("invalid_candle");
      Put(s.m,"lastPrice",(int)s.last);record.Invoke(s.b,new object[]{(int)s.last});s.candle++;Put(s.m,"currentCandleIndex",s.candle);
      prune.Invoke(s.b,new object[]{(int)s.last,64});
      var pb=Book(s.b,"buyBook");var pa=Book(s.b,"sellBook");
      pruned+=Changes(events,c,5,"price_pruning","bid",bid,pb)+Changes(events,c,5,"price_pruning","ask",ask,pa);
      remove.Invoke(s.b,new object[]{0.1f,0});
      var rb=Book(s.b,"buyBook");var ra=Book(s.b,"sellBook");
      randomRemoved+=Changes(events,c,6,"random_removal","bid",pb,rb)+Changes(events,c,6,"random_removal","ask",pa,ra);
      bid=rb;ask=ra;
      if(control!=null) {
       originalStep.Invoke(null,new object[]{control});
       if(s.Fingerprint()!=control.Fingerprint())throw new Exception("original_scheduler_fingerprint_mismatch");
       foreach(var field in new[]{"open","high","low","close","volume"})if(Num(live,field)!=Num(Get(control.m,"liveCandlestick"),field))throw new Exception("original_scheduler_candle_mismatch");
       OriginalHost.Reset(control);
      }
      if(bid.Values.Any(x=>x<=0)||ask.Values.Any(x=>x<=0))throw new Exception("nonpositive_level");
      rows.WriteLine(JsonSerializer.Serialize(new {run_id=id,phase,seed,candle=c,observed=c>=100,open=o,high=h,low=l,close=s.last,volume=v,
       best_bid=Num(s.b,"BestBid"),best_ask=Num(s.b,"BestAsk"),counter_bid=Num(s.b,"totalBuyVolume"),counter_ask=Num(s.b,"totalSellVolume"),bids=Levels(bid),asks=Levels(ask)}));
      completed++;OriginalHost.Reset(s);
     }
    }
    status="ok";
   } catch(Exception e) {status="error";error=(e.InnerException??e).GetType().Name+":"+(e.InnerException??e).Message;}
   File.WriteAllText(prefix+".manifest.json",JsonSerializer.Serialize(new {run_id=id,phase,seed,evidence_type="original_DLL_CLR_flow_host",status,error,completed_candles=completed,reference_scheduler_checked=seed==start,random_removed_quantity=randomRemoved,pruned_quantity=pruned}));
   Console.WriteLine(id+" "+status+" candles="+completed+" "+error);
   if(status!="ok")throw new Exception("stopping_after_failed_run_"+id);
  }
 }
}
