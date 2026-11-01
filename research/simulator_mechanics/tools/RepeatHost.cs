// Repeated original-DLL interventions; exact synchronous aggregate transfer ledger.
// Separate transient CLR objects. No app attachment, patched binaries or training.
using System;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Collections;
using System.Collections.Generic;
using System.Text.Json;
public static class RepeatHost {
 static BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 static long Num(object o,string n)=>Convert.ToInt64(o.GetType().GetField(n,flags).GetValue(o));
 static long Depth(OriginalHost.State s,bool buy,long price) {
  long d=0;foreach(DictionaryEntry x in (IDictionary)s.b.GetType().GetField(buy?"sellBook":"buyBook").GetValue(s.b)) {
   long p=Convert.ToInt64(x.Key);double dist=(buy?1:-1)*10000.0*(p-price)/price;if(dist>=0&&dist<=10+1e-10)d+=Convert.ToInt64(x.Value);
  }return d;
 }
 static StreamWriter Zip(string file)=>new StreamWriter(new GZipStream(new FileStream(file,FileMode.CreateNew),CompressionLevel.Fastest));
 public static void Run(string managed,string output,string phase) {
  if(phase!="pilot"&&phase!="main")throw new ArgumentException("phase");
  Directory.CreateDirectory(output);OriginalHost.Configure(managed,"05");
  var step=typeof(OriginalHost).GetMethod("Step",BindingFlags.Static|BindingFlags.NonPublic);
  int start=phase=="pilot"?32000:42000,n=phase=="pilot"?10:30;
  for(int seed=start;seed<start+n;seed++) {
   string baseline=null;
   foreach(string scenario in new[]{"baseline","buy_one500","sell_one500","buy_repeat100","sell_repeat100"}) {
    string id="repeat-v05-"+seed+"-"+scenario,prefix=Path.Combine(output,id);string status="running",error="",fingerprint="";
    if(File.Exists(prefix+".manifest.json")||File.Exists(prefix+".candles.jsonl.gz"))throw new IOException("existing_run_"+id);
    int filledTotal=0,completed=0;long notionalTotal=0;bool matched=false;
    try {
     using(var candles=Zip(prefix+".candles.jsonl.gz"))using(var fills=Zip(prefix+".fills.jsonl.gz")) {
      var s=OriginalHost.Init(seed);for(int c=0;c<100;c++){step.Invoke(null,new object[]{s});OriginalHost.Reset(s);}
      fingerprint=s.Fingerprint();if(scenario=="baseline")baseline=fingerprint;matched=baseline==fingerprint;if(!matched)throw new Exception("fingerprint_mismatch");
      long originalArrival=Num(s.b,"lastTradedPrice");long initialCash=s.Cash(),initialCoin=s.Coins();bool buy=scenario.StartsWith("buy");
      var place=s.b.GetType().GetMethod("PlaceOrder");
      for(int relative=0;relative<=50;relative++) {
       if(relative>0)step.Invoke(null,new object[]{s});
       if(scenario!="baseline"&&(relative==0||(scenario.Contains("repeat")&&relative<=20&&relative%5==0))) {
        int request=scenario.Contains("repeat")?100:500;long before=Num(s.b,"lastTradedPrice"),cash=s.Cash(),coin=s.Coins(),depth=Depth(s,buy,before);
        long returned=Convert.ToInt64(place.Invoke(s.b,new object[]{buy?long.MaxValue:1L,request,buy,null}));
        int filled=(int)Math.Abs(s.Coins()-coin);long notional=Math.Abs(s.Cash()-cash);filledTotal+=filled;notionalTotal+=notional;
        if(filled>request||filled<0)throw new Exception("invalid_fill_quantity");
        fills.WriteLine(JsonSerializer.Serialize(new {run_id=id,phase,seed,scenario,relative,side=buy?"buy":"sell",intended=request,filled,notional,integer_vwap=returned,
         arrival=before,last_after=Num(s.b,"lastTradedPrice"),opposite_depth10=depth,cash_delta=s.Cash()-cash,coin_delta=s.Coins()-coin}));
       }
       long last=Num(s.b,"lastTradedPrice"),bid=Num(s.b,"BestBid"),ask=Num(s.b,"BestAsk");
       candles.WriteLine(JsonSerializer.Serialize(new {run_id=id,phase,seed,scenario,relative,original_arrival=originalArrival,last,
        best_bid=bid,best_ask=ask,buy_depth10=Depth(s,true,last),sell_depth10=Depth(s,false,last),
        cash=s.Cash(),coins=s.Coins(),initial_cash=initialCash,initial_coins=initialCoin,
        negative_cash_agents=s.agents.Count(t=>Num(t,"USD")<0),negative_coin_agents=s.agents.Count(t=>Num(t,"BTC")<0)}));
       completed++;OriginalHost.Reset(s);
      }
     }
     status="ok";
    }catch(Exception e){status="error";error=(e.InnerException??e).GetType().Name+":"+(e.InnerException??e).Message;}
    File.WriteAllText(prefix+".manifest.json",JsonSerializer.Serialize(new {run_id=id,phase,seed,scenario,evidence_type="original_DLL_CLR_repeated_intervention_host",status,error,
     fingerprint,matched_baseline=matched,completed_observations=completed,filled_total=filledTotal,notional_total=notionalTotal}));
    Console.WriteLine(id+" "+status+" "+error);
   }
  }
 }
}
