// Reuse the tested exact-decimal event replay; no vendor code or hidden inputs.
#define main audit_scanner_main
#include "archive_scan.cpp"
#undef main
#include <cmath>
#include <fstream>

constexpr int BOOK_N=87, TRADE_N=8;
struct FeatureScanner: Scanner {
  std::ofstream features;
  std::map<I,I> candle_available;
  struct Flow {I max_receipt=0,max_event=0,max_id=0;bool bad=false;std::array<double,8> x{};};
  std::array<Flow,3600> flow;
  explicit FeatureScanner(std::string kind):Scanner(kind){}
  void write(I time,I receipt,I event,I sequence,I age,bool ok,const float* x,int n) {
    I fields[]={time,receipt,event,sequence,age,ok?1:0};
    features.write(reinterpret_cast<char*>(fields),sizeof(fields));
    features.write(reinterpret_cast<const char*>(x),n*sizeof(float));
  }
  void on_tick(I time,bool usable) override {
    std::array<float,BOOK_N> x{};
    // The latest applied event's receipt and exchange times must precede the grid.
    usable=usable && er<=time && ee*1000000LL<=time;
    if(usable) {
      double mid=(bids.rbegin()->first/1e8+asks.begin()->first/1e8)/2;
      auto bid=bids.rbegin();auto ask=asks.begin();double bs=0,as=0,b1=0,a1=0,b5=0,a5=0;
      for(int i=0;i<20;++i,++bid,++ask) {
        double bq=bid->second/1e8,aq=ask->second/1e8;
        x[i*4]=(bid->first/1e8-mid)/mid*10000;x[i*4+1]=std::log1p(bq);
        x[i*4+2]=(ask->first/1e8-mid)/mid*10000;x[i*4+3]=std::log1p(aq);
        bs+=bq;as+=aq;if(i==0){b1=bq;a1=aq;}if(i==4){b5=bs;a5=as;}
      }
      x[80]=(asks.begin()->first-bids.rbegin()->first)/1e8/mid*10000;
      x[81]=(b1-a1)/(b1+a1);x[82]=(b5-a5)/(b5+a5);x[83]=(bs-as)/(bs+as);
      x[84]=std::log1p(bs);x[85]=std::log1p(as);
      double micro=(asks.begin()->first/1e8*b1+bids.rbegin()->first/1e8*a1)/(b1+a1);
      x[86]=(micro-mid)/mid*10000;
    }
    write(time,er,ee*1000000LL,last,time-last_update_recv,usable,x.data(),BOOK_N);
  }
  void on_trade(I receipt,I event,I trade_time,I id,I price,I qty,bool maker,bool bad,bool non_market) override {
    // Finalized source-minute candles are usable as inputs only once every row used
    // to reconstruct them has arrived. Keep NA IDs but omit NA price/volume.
    if(!non_market)candle_available[trade_time/60000*60000]=std::max(
        candle_available[trade_time/60000*60000],receipt);
    if(receipt<hour || receipt>=hour+3600*SEC)return;
    auto& f=flow[(receipt-hour)/SEC];f.max_receipt=std::max(f.max_receipt,receipt);
    f.max_event=std::max(f.max_event,std::max(event,trade_time)*1000000LL);f.max_id=std::max(f.max_id,id);f.bad|=bad;
    if(non_market||bad)return;
    double q=qty/1e8,n=price/1e8*q;
    int side=maker?1:0;f.x[side]+=q;f.x[side+2]+=n;f.x[4]+=1;f.x[side+5]+=1;
  }
  void extract(const std::string& input,I h,const std::string& output) {
    candle_available.clear();flow={};features.open(output,std::ios::binary|std::ios::trunc);
    if(!features)throw std::runtime_error("Feature output unavailable");
    // Publish completion only after BOTH audit JSON and feature bytes are complete.
    std::ostringstream audit_json;
    auto* original=std::cout.rdbuf(audit_json.rdbuf());
    try {run(input,h);} catch(...) {std::cout.rdbuf(original);throw;}
    std::cout.rdbuf(original);
    if(kind=="trades") {
      for(int i=0;i<3600;++i) {
        auto& f=flow[i];std::array<float,TRADE_N> x{};
        for(int j=0;j<7;++j)x[j]=f.x[j];
        x[7]=f.x[0]+f.x[1]>0?(f.x[2]+f.x[3])/(f.x[0]+f.x[1]):0;
        write(h+i*SEC,f.max_receipt,f.max_event,f.max_id,0,!f.bad,x.data(),TRADE_N);
      }
      std::ofstream availability(output+".availability.json");availability<<"{";
      bool first=true;for(auto& [minute,receipt]:candle_available){if(!first)availability<<",";first=false;availability<<'"'<<minute<<"\":"<<receipt;}
      availability<<"}\n";
    }
    features.close();if(!features)throw std::runtime_error("Feature write failed");
    std::cout<<audit_json.str()<<std::flush;
  }
};
int main(int argc,char** argv) {
  if(argc!=2)return 2;FeatureScanner scan(argv[1]);std::string line;
  while(std::getline(std::cin,line)) {
    auto first=line.find('\t'),second=line.find('\t',first+1);
    if(first==std::string::npos||second==std::string::npos)return 2;
    try{scan.extract(line.substr(first+1,second-first-1),std::stoll(line.substr(0,first)),line.substr(second+1));}
    catch(const std::exception&){return 3;}
  }
}
