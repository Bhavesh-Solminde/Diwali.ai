#include "feature_scan.cpp"

struct TradeEventScanner: FeatureScanner {
  std::ofstream events;
  TradeEventScanner():FeatureScanner("trades"){}
  void on_trade(I receipt,I event,I trade_time,I id,I price,I qty,bool maker,bool bad,bool non_market) override {
    FeatureScanner::on_trade(receipt,event,trade_time,id,price,qty,maker,bad,non_market);
    I fields[]={receipt,event*1000000LL,trade_time*1000000LL,id,price,qty,maker?1:0,bad?1:0,non_market?1:0};
    events.write(reinterpret_cast<char*>(fields),sizeof(fields));
  }
  void extract_events(const std::string& input,I h,const std::string& seconds,const std::string& destination) {
    events.open(destination,std::ios::binary|std::ios::trunc);
    if(!events)throw std::runtime_error("Trade event output unavailable");
    FeatureScanner::extract(input,h,seconds);events.close();
    if(!events)throw std::runtime_error("Trade event write failed");
  }
};
int main() {
  TradeEventScanner scan;std::string line;
  while(std::getline(std::cin,line)) {
    auto a=line.find('\t'),b=line.find('\t',a+1),c=line.find('\t',b+1);
    if(a==std::string::npos||b==std::string::npos||c==std::string::npos)return 2;
    try{scan.extract_events(line.substr(a+1,b-a-1),std::stoll(line.substr(0,a)),line.substr(b+1,c-b-1),line.substr(c+1));}
    catch(const std::exception&){return 3;}
  }
}
