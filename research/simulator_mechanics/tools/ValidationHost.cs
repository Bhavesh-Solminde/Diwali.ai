// Bounded fresh-seed profile validation of original methods; not a replacement engine.
using System;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Collections;
using System.Collections.Generic;
using System.Text.Json;
public static class ValidationHost {
 static BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 static object Get(object o,string n)=>o.GetType().GetField(n,flags).GetValue(o);
 static long Num(object o,string n)=>Convert.ToInt64(Get(o,n));
 static void Put(object o,string n,object v)=>o.GetType().GetField(n,flags).SetValue(o,v);
 static MethodInfo step=typeof(OriginalHost).GetMethod("Step",BindingFlags.NonPublic|BindingFlags.Static);
 static StreamWriter Zip(string file)=>new StreamWriter(new GZipStream(new FileStream(file,FileMode.CreateNew),CompressionLevel.Fastest));
 static int[][] Levels(object b,string name) {
  var a=new List<int[]>();foreach(DictionaryEntry x in (IDictionary)Get(b,name))a.Add(new[]{Convert.ToInt32(x.Key),Convert.ToInt32(x.Value)});return a.OrderBy(x=>x[0]).ToArray();
 }
 static OriginalHost.State Init(int seed,string profile) {
  var s=OriginalHost.Init(seed);
  // Keep original initialization for first N agents; never mutate running app objects.
  if(profile=="sparse"){s.agents.RemoveRange(100,100);s.acts.RemoveRange(100,100);}
  Put(s.b,"proportionMaker",profile=="maker30"?0.3f:0.1f);
  Put(s.b,"traderActivityRate",profile=="sparse"?0.05f:0.1f);
  return s;
 }
 static long Depth(OriginalHost.State s,bool buy,long last) {
  long total=0;foreach(DictionaryEntry x in (IDictionary)Get(s.b,buy?"sellBook":"buyBook")) {
   long p=Convert.ToInt64(x.Key);double d=(buy?1:-1)*10000.0*(p-last)/last;if(d>=0&&d<=10+1e-10)total+=Convert.ToInt64(x.Value);
  }return total;
 }
 public static void Run(string managed,string output,string version) {
  Directory.CreateDirectory(output);OriginalHost.Configure(managed,version);
  string[] profiles={"standard","sparse","maker30"};
  foreach(string profile in profiles) {
   int pi=Array.IndexOf(profiles,profile),count=version=="04"?60:40,start=(version=="04"?51000:61000)+pi*1000;
   for(int seed=start;seed<start+count;seed++) {
    string baseline=null;
    string[] scenarios=version=="04"?new[]{"baseline"}:new[]{"baseline","buy_d0.5_one","buy_d0.5_five","buy_d2_one","buy_d2_five","sell_d0.5_one","sell_d0.5_five","sell_d2_one","sell_d2_five"};
    foreach(string scenario in scenarios) {
     string id="validation-v"+version+"-"+profile+"-"+seed+"-"+scenario,prefix=Path.Combine(output,id);
     if(File.Exists(prefix+".manifest.json")||File.Exists(prefix+".rows.jsonl.gz"))throw new IOException("existing_run_"+id);
     string status="running",error="",fingerprint="";bool matched=false;int completed=0,totalRequested=0,totalFilled=0;long totalNotional=0,depth0=0;
     try {
      using(var rows=Zip(prefix+".rows.jsonl.gz"))using(var fills=Zip(prefix+".fills.jsonl.gz")) {
       var s=Init(seed,profile);
       if(version=="04") {
        for(int c=0;c<600;c++) {
         step.Invoke(null,new object[]{s});var live=Get(s.m,"liveCandlestick");
         long o=Num(live,"open"),h=Num(live,"high"),l=Num(live,"low"),v=Num(live,"volume"),last=Num(live,"close");
         if(last<=0||l<=0||h<Math.Max(o,last)||l>Math.Min(o,last)||v<0)throw new Exception("invalid_candle");
         rows.WriteLine(JsonSerializer.Serialize(new {run_id=id,profile,seed,candle=c,open=o,high=h,low=l,close=last,volume=v,
          best_bid=Num(s.b,"BestBid"),best_ask=Num(s.b,"BestAsk"),bids=Levels(s.b,"buyBook"),asks=Levels(s.b,"sellBook")}));
         completed++;OriginalHost.Reset(s);
        }
        matched=true;
       }else {
        for(int c=0;c<100;c++){step.Invoke(null,new object[]{s});OriginalHost.Reset(s);}
        fingerprint=s.Fingerprint();if(scenario=="baseline")baseline=fingerprint;matched=baseline==fingerprint;if(!matched)throw new Exception("warmup_mismatch");
        bool buy=scenario.StartsWith("buy");long arrival=Num(s.b,"lastTradedPrice"),initialCash=s.Cash(),initialCoin=s.Coins();
        depth0=Depth(s,buy,arrival);
        double ratio=scenario.Contains("d0.5")?0.5:2.0;
        int quantity=scenario=="baseline"?0:Math.Max(5,5*(int)Math.Ceiling(ratio*depth0/5.0));
        if(scenario!="baseline"&&depth0==0){status="unavailable_zero_depth";quantity=0;}
        var place=s.b.GetType().GetMethod("PlaceOrder");
        for(int c=0;c<=50;c++) {
         if(c>0)step.Invoke(null,new object[]{s});
         if(quantity>0&&(c==0||(scenario.EndsWith("five")&&c<=20&&c%5==0))) {
          int request=scenario.EndsWith("five")?quantity/5:quantity;
          long before=Num(s.b,"lastTradedPrice"),cash=s.Cash(),coin=s.Coins(),depth=Depth(s,buy,before);totalRequested+=request;
          long returned=Convert.ToInt64(place.Invoke(s.b,new object[]{buy?long.MaxValue:1L,request,buy,null}));
          int achieved=(int)Math.Abs(s.Coins()-coin);long notional=Math.Abs(s.Cash()-cash);totalFilled+=achieved;totalNotional+=notional;
          if(achieved>request||achieved<0)throw new Exception("invalid_fill");
          fills.WriteLine(JsonSerializer.Serialize(new {run_id=id,profile,seed,scenario,relative=c,side=buy?"buy":"sell",intended=request,filled=achieved,notional,
           integer_vwap=returned,arrival=before,last_after=Num(s.b,"lastTradedPrice"),opposite_depth10=depth,cash_delta=s.Cash()-cash,coin_delta=s.Coins()-coin}));
         }
         rows.WriteLine(JsonSerializer.Serialize(new {run_id=id,profile,seed,scenario,relative=c,original_arrival=arrival,last=Num(s.b,"lastTradedPrice"),
          cash=s.Cash(),coins=s.Coins(),initial_cash=initialCash,initial_coins=initialCoin,
          negative_cash_agents=s.agents.Count(t=>Num(t,"USD")<0),negative_coin_agents=s.agents.Count(t=>Num(t,"BTC")<0)}));
         completed++;OriginalHost.Reset(s);
        }
        if(status=="running")status="ok";
       }
      }
      if(status=="running")status="ok";
     }catch(Exception e){status="error";error=(e.InnerException??e).GetType().Name+":"+(e.InnerException??e).Message;}
     File.WriteAllText(prefix+".manifest.json",JsonSerializer.Serialize(new {run_id=id,profile,seed,scenario,version,status,error,
      evidence_type="original_DLL_CLR_validation_host",agents=profile=="sparse"?100:200,activity=profile=="sparse"?.05:.1,maker=profile=="maker30"?.3:.1,
      fingerprint,matched_baseline=matched,completed_observations=completed,total_requested=totalRequested,total_filled=totalFilled,total_notional=totalNotional,initial_depth10=depth0}));
     if(status=="error"&&version=="04")throw new Exception("stopped_profile_after_"+id+"_"+error);
    }
   }
   Console.WriteLine("Completed validation v"+version+" "+profile+" parents="+count);
  }
 }
}
