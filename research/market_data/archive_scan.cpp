// Our validator, not vendor simulator code. Exact decimal arithmetic, native Arrow IO.
#include <arrow/api.h>
#include <parquet/arrow/reader.h>
#include <parquet/properties.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>

using I = int64_t;
constexpr I SEC = 1000000000LL, SCALE = 100000000LL;
template<class T> T unwrap(arrow::Result<T> r) {
  if (!r.ok()) throw std::runtime_error(r.status().ToString());
  return std::move(r).ValueUnsafe();
}
void check(arrow::Status s) { if (!s.ok()) throw std::runtime_error(s.ToString()); }
bool fixed(std::string_view s, I& out) {
  if (s.empty()) return false;
  __int128 n=0; int decimals=0; bool dot=false, digit=false;
  for (char c:s) {
    if (c=='.' && !dot) { dot=true; continue; }
    if (c<'0'||c>'9') return false;
    digit=true; n=n*10+c-'0'; if(dot) ++decimals;
    if(n>std::numeric_limits<I>::max() || decimals>8) return false;
  }
  if(!digit) return false;
  for(int k=decimals;k<8;++k) n*=10;
  if(n>std::numeric_limits<I>::max()) return false;
  out=static_cast<I>(n); return true;
}
std::string decimal(__int128 n,int scale) {
  bool neg=n<0; if(neg)n=-n; std::string s;
  do {s.push_back('0'+n%10);n/=10;} while(n);
  std::reverse(s.begin(),s.end());
  if(scale) {if(s.size()<=static_cast<size_t>(scale))s.insert(0,scale+1-s.size(),'0');s.insert(s.size()-scale,".");}
  return (neg?"-":"")+s;
}
struct Columns {
  std::shared_ptr<arrow::RecordBatch> b;
  template<class T> std::shared_ptr<T> get(const char* name, arrow::Type::type kind) {
    auto a=b->GetColumnByName(name);
    if(!a || a->type_id()!=kind) throw std::runtime_error(std::string("wrong/missing column ")+name);
    return std::static_pointer_cast<T>(a);
  }
  auto integer(const char* n) {return get<arrow::Int64Array>(n,arrow::Type::INT64);}
  auto text(const char* n) {return get<arrow::StringArray>(n,arrow::Type::STRING);}
};
I val(const std::shared_ptr<arrow::Int64Array>& a,I i) {return a->IsValid(i)?a->Value(i):-1;}
std::string_view str(const std::shared_ptr<arrow::StringArray>& a,I i) {return a->IsValid(i)?a->GetView(i):std::string_view();}

struct Counts {
  std::map<std::string,I> c;
  void add(const std::string& k,I n=1) {c[k]+=n;}
  void json(std::ostream& o) const {
    bool first=true;o<<"{";for(auto& [k,v]:c){if(!first)o<<",";first=false;o<<'"'<<k<<"\":"<<v;}o<<"}";
  }
};
struct Scanner {
  std::string kind; I hour=0, previous_hour=-1, previous_recv=-1, max_recv=-1;
  Counts counts; std::array<int,60> good_seconds{};
  std::map<I,I> bids,asks;
  I last=-1, snapshot=-1,last_update_recv=-1, next_tick=0;
  I bid_floor=0,ask_ceiling=0;
  bool initialized=false, valid=false, event_open=false, apply=false,event_bad=false;
  I er=-1,ee=-1,eu=-1,eU=-1,epu=-1,elast=-1; std::string etype;
  uint64_t snapshot_hash=0, old_snapshot_hash=0; I old_snapshot_id=-1;
  I last_trade=-1;
  I first_trade=-1;
  struct Candle {I n=0,o=0,h=0,l=0,c=0,v=0,min_id=0,max_id=0; __int128 quote=0; bool bad=false;};
  std::map<I,Candle> candles;
  explicit Scanner(std::string k):kind(std::move(k)){}
  void invalidate(){bids.clear();asks.clear();initialized=false;valid=false;last=-1;snapshot=-1;bid_floor=ask_ceiling=0;}
  void clock(I r,I e) {
    if(r<hour || r>=hour+3600*SEC)counts.add("receipt_outside_file_hour_rows");
    if(e<=0 || e<hour/1000000-3600000 || e>(hour/1000000)+7200000)counts.add("invalid_exchange_clock_rows");
    if(e>0 && static_cast<__int128>(e)*1000000>static_cast<__int128>(r)+SEC)counts.add("exchange_ahead_over_1s_rows");
    if(previous_recv>=0 && r<previous_recv)counts.add("backward_receipt_rows");
    previous_recv=r;max_recv=std::max(max_recv,r);
  }
  void ticks(I until, bool inclusive=false) {
    while(next_tick<hour+3600*SEC && (next_tick<until || (inclusive && next_tick==until))) {
      if(valid && last_update_recv>=0 && next_tick>=last_update_recv && next_tick-last_update_recv<=SEC
         && bids.size()>=20 && asks.size()>=20 && bids.rbegin()->first<asks.begin()->first) {
        auto bid=bids.rbegin();auto ask=asks.begin();std::advance(bid,19);std::advance(ask,19);
        if(bid->first>=bid_floor && ask->first<=ask_ceiling)
          ++good_seconds[(next_tick-hour)/(60*SEC)];
        else counts.add("top20_outside_snapshot_bounds_seconds");
      }
      next_tick+=SEC;
    }
  }
  void flush() {
    if(!event_open)return;
    if(event_bad){counts.add("invalid_events");invalidate();}
    else if(etype=="snapshot") {
      counts.add("snapshots");
      if(elast<0 || bids.empty() || asks.empty() || bids.rbegin()->first>=asks.begin()->first) {
        counts.add("invalid_snapshots");invalidate();
      } else {
        if(old_snapshot_id==elast) {
          if(old_snapshot_hash==snapshot_hash)counts.add("duplicate_identical_snapshots");
          else counts.add("conflicting_same_id_snapshots");
        }
        old_snapshot_id=elast;old_snapshot_hash=snapshot_hash;
        initialized=true;last=elast;snapshot=elast;valid=false;
        bid_floor=bids.begin()->first;ask_ceiling=asks.rbegin()->first;
      }
    } else if(apply) {
      if(bids.empty()||asks.empty()||bids.rbegin()->first>=asks.begin()->first) {
        counts.add("empty_or_crossed_events");invalidate();
      } else {last=eu;valid=true;last_update_recv=er;counts.add("accepted_updates");}
    }
    event_open=false;
  }
  void begin_event(I r,I e,std::string_view type,I U,I u,I pu,I sid) {
    flush();ticks(r);
    event_open=true;event_bad=false;er=r;ee=e;eU=U;eu=u;epu=pu;elast=sid;etype=std::string(type);apply=false;
    counts.add("events");
    if(type=="snapshot") {invalidate();snapshot_hash=1469598103934665603ULL;apply=true;return;}
    if(type!="update"){event_bad=true;counts.add("unknown_event_types");return;}
    if(U<0||u<0||pu<0||U>u){event_bad=true;counts.add("invalid_sequence_fields");return;}
    if(!initialized){counts.add("orphan_updates");return;}
    if(u<=last){counts.add("stale_or_duplicate_updates");return;}
    bool bridge=valid ? pu==last : (pu==last || (U<=snapshot && snapshot<=u));
    if(!bridge){counts.add("sequence_gaps");invalidate();return;}
    apply=true;
  }
  void book(const std::shared_ptr<arrow::RecordBatch>& b) {
    Columns x{b};auto recv=x.integer("received_time"),event=x.integer("event_time"),tr=x.integer("transaction_time");
    auto U=x.integer("first_update_id"),u=x.integer("final_update_id"),pu=x.integer("prev_final_update_id"),sid=x.integer("last_update_id");
    auto type=x.text("event_type"),side=x.text("side"),price=x.text("price"),qty=x.text("quantity"),symbol=x.text("symbol");
    for(I i=0;i<b->num_rows();++i) {
      I r=val(recv,i),e=val(event,i),uu=val(u,i),ss=val(sid,i);auto t=str(type,i);
      // Some old provider snapshots interleave two identical copies per level,
      // one with synthetic E*1e6 receipt time. Snapshot identity is its native
      // sequence plus event time, not the alternating receipt clock.
      bool same=event_open&&e==ee&&uu==eu&&ss==elast&&t==etype&&
                (t=="snapshot"||r==er);
      if(!same)begin_event(r,e,t,val(U,i),uu,val(pu,i),ss);
      else if(t=="snapshot") er=std::max(er,r);
      clock(r,e);counts.add("rows");
      if(str(symbol,i)!="BTCUSDT"){counts.add("wrong_symbol_rows");event_bad=true;}
      I p=0,q=0;auto s=str(side,i);
      bool noop=s=="noop" && t=="snapshot";
      if(noop){counts.add("empty_snapshot_markers");event_bad=true;continue;}
      if(!fixed(str(price,i),p)||!fixed(str(qty,i),q)||p<=0||(s!="bid"&&s!="ask")) {
        counts.add("invalid_level_rows");event_bad=true;continue;
      }
      if(same && (val(U,i)!=eU||val(pu,i)!=epu)){counts.add("inconsistent_event_fields");event_bad=true;}
      I trans=val(tr,i);if(trans>0 && (trans<hour/1000000-3600000 || trans>hour/1000000+7200000))counts.add("invalid_transaction_clock_rows");
      if(t=="snapshot") {snapshot_hash^=static_cast<uint64_t>(p);snapshot_hash*=1099511628211ULL;snapshot_hash^=static_cast<uint64_t>(q);snapshot_hash*=1099511628211ULL;snapshot_hash^=s=="bid"?1:2;}
      if(!apply || event_bad)continue;
      auto& levels=s=="bid"?bids:asks;
      if(t=="snapshot") {
        auto existing=levels.find(p);
        if(existing!=levels.end()) {
          if(existing->second!=q){counts.add("conflicting_snapshot_level_rows");event_bad=true;continue;}
          counts.add("duplicate_snapshot_level_rows");
        }
      }
      if(q)levels[p]=q;else levels.erase(p);
    }
  }
  void trade(const std::shared_ptr<arrow::RecordBatch>& b) {
    Columns x{b};auto recv=x.integer("received_time"),event=x.integer("event_time"),tt=x.integer("trade_time"),id=x.integer("trade_id");
    auto price=x.text("price"),qty=x.text("quantity"),symbol=x.text("symbol"),order_type=x.text("order_type");
    auto maker=x.get<arrow::BooleanArray>("is_buyer_maker",arrow::Type::BOOL);
    for(I i=0;i<b->num_rows();++i) {
      I r=val(recv,i),e=val(event,i),t=val(tt,i),tid=val(id,i),p=0,q=0;counts.add("rows");clock(r,e);
      if(first_trade<0)first_trade=tid;
      bool bad=false;
      if(str(symbol,i)!="BTCUSDT"){counts.add("wrong_symbol_rows");bad=true;}
      bool parsed=fixed(str(price,i),p)&&fixed(str(qty,i),q);
      bool non_market=parsed&&p==0&&q==0&&str(order_type,i)=="NA";
      if(!non_market && (!parsed||p<=0||q<=0||maker->IsNull(i))){counts.add("invalid_trade_rows");bad=true;}
      if(t<hour/1000000-3600000 || t>hour/1000000+7200000 ||tid<0){counts.add("invalid_trade_clock_or_id_rows");bad=true;}
      if(last_trade>=0 && tid==last_trade){counts.add("adjacent_duplicate_trade_ids");bad=true;}
      if(last_trade>=0 && tid<last_trade){counts.add("backward_or_duplicate_trade_ids");bad=true;}
      if(last_trade>=0 && tid>last_trade+1){counts.add("trade_id_gap_events");counts.add("missing_trade_ids",tid-last_trade-1);bad=true;}
      last_trade=std::max(last_trade,tid);
      // Exchange NA events occupy trade IDs but are not executions. Preserve sequence,
      // exclude explicitly from OHLC/VWAP/volume/count rather than inventing a zero price.
      if(non_market){counts.add("non_market_zero_events");continue;}
      I minute=t/60000*60000;auto& c=candles[minute];
      if(!c.n){c.o=c.h=c.l=c.c=p;c.min_id=c.max_id=tid;}
      ++c.n;c.h=std::max(c.h,p);c.l=std::min(c.l,p);
      if(tid<c.min_id){c.min_id=tid;c.o=p;}if(tid>c.max_id){c.max_id=tid;c.c=p;}
      c.v+=q;c.quote+=static_cast<__int128>(p)*q;c.bad=c.bad||bad;
    }
  }
  void run(const std::string& path,I h) {
    if(previous_hour>=0 && h!=previous_hour+3600*SEC){invalidate();last_trade=-1;previous_recv=-1;}
    hour=h;next_tick=h;counts=Counts{};good_seconds.fill(0);candles.clear();max_recv=-1;first_trade=-1;
    parquet::ReaderProperties props;props.set_page_checksum_verification(true);
    parquet::ArrowReaderProperties arrow_props;arrow_props.set_batch_size(65536);arrow_props.set_pre_buffer(false);
    parquet::arrow::FileReaderBuilder builder;check(builder.OpenFile(path,false,props));builder.properties(arrow_props);
    auto reader=unwrap(builder.Build());auto batches=unwrap(reader->GetRecordBatchReader());
    while(true) {std::shared_ptr<arrow::RecordBatch> b;check(batches->ReadNext(&b));if(!b)break;if(kind=="book")book(b);else trade(b);}
    flush();if(kind=="book")ticks(hour+3600*SEC);
    previous_hour=h;
    std::cout<<"{\"ok\":true,\"counts\":";counts.json(std::cout);
    std::cout<<",\"last_sequence\":"<<last<<",\"first_trade_id\":"<<first_trade<<",\"last_trade_id\":"<<last_trade<<",\"valid_end\":"<<(valid?"true":"false")<<",\"good_seconds_per_minute\":[";
    for(int i=0;i<60;++i){if(i)std::cout<<",";std::cout<<good_seconds[i];}std::cout<<"],\"candles\":[";
    bool first=true;for(auto& [m,c]:candles){if(!first)std::cout<<",";first=false;
      std::cout<<"{\"minute_ms\":"<<m<<",\"count\":"<<c.n<<",\"open\":\""<<decimal(c.o,8)<<"\",\"high\":\""<<decimal(c.h,8)<<"\",\"low\":\""<<decimal(c.l,8)<<"\",\"close\":\""<<decimal(c.c,8)<<"\",\"volume\":\""<<decimal(c.v,8)<<"\",\"quote_volume\":\""<<decimal(c.quote,16)<<"\",\"first_id\":"<<c.min_id<<",\"last_id\":"<<c.max_id<<",\"bad\":"<<(c.bad?"true":"false")<<"}";}
    std::cout<<"]}"<<std::endl;
  }
};
int main(int argc,char** argv) {
  if(argc!=2 || (std::string(argv[1])!="book"&&std::string(argv[1])!="trades"))return 2;
  Scanner scan(argv[1]);std::string line;
  while(std::getline(std::cin,line)) {
    auto tab=line.find('\t');if(tab==std::string::npos)return 2;
    try{scan.run(line.substr(tab+1),std::stoll(line.substr(0,tab)));}
    catch(const std::exception&){scan.invalidate();scan.last_trade=-1;scan.previous_recv=-1;scan.event_open=false;std::cout<<"{\"ok\":false,\"error\":\"decode_or_schema_failure\"}"<<std::endl;}
  }
}
