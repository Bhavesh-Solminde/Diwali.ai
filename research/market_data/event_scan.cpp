// Compile against a generated observer-enabled copy of our frozen replay source.
// The original validator and feature scanner remain unchanged.
#include "feature_scan.cpp"

struct EventScanner: FeatureScanner {
  std::ofstream events;
  I ordinal=0;
  EventScanner():FeatureScanner("book"){}
  void on_book_event() override {
    bool usable=valid && !event_bad && bids.size()>=20 && asks.size()>=20;
    if(usable) {
      auto b=bids.rbegin();auto a=asks.begin();std::advance(b,19);std::advance(a,19);
      usable=bids.rbegin()->first<asks.begin()->first && b->first>=bid_floor && a->first<=ask_ceiling;
    }
    // A whole provider batch becomes available atomically. Snapshot receipt is
    // the maximum receipt across its rows, as in the parent replay.
    I metadata[]={er,ee*1000000LL,std::max(er,ee*1000000LL),last,
      etype=="snapshot"?elast:eu,etype=="snapshot"?1:0,
      etype=="update"&&apply&&!event_bad&&valid?1:0,usable?1:0,ordinal++};
    std::array<I,80> levels{};
    if(usable) {
      auto b=bids.rbegin();auto a=asks.begin();
      for(int j=0;j<20;++j,++b,++a){levels[j*4]=b->first;levels[j*4+1]=b->second;levels[j*4+2]=a->first;levels[j*4+3]=a->second;}
    }
    events.write(reinterpret_cast<char*>(metadata),sizeof(metadata));
    events.write(reinterpret_cast<char*>(levels.data()),sizeof(levels));
  }
  void extract_events(const std::string& input,I h,const std::string& seconds,const std::string& destination) {
    ordinal=0;events.open(destination,std::ios::binary|std::ios::trunc);
    if(!events)throw std::runtime_error("Event output unavailable");
    FeatureScanner::extract(input,h,seconds);
    events.close();if(!events)throw std::runtime_error("Event write failed");
  }
};
int main() {
  EventScanner scan;std::string line;
  while(std::getline(std::cin,line)) {
    auto a=line.find('\t'),b=line.find('\t',a+1),c=line.find('\t',b+1);
    if(a==std::string::npos||b==std::string::npos||c==std::string::npos)return 2;
    try{scan.extract_events(line.substr(a+1,b-a-1),std::stoll(line.substr(0,a)),line.substr(b+1,c-b-1),line.substr(c+1));}
    catch(const std::exception&){return 3;}
  }
}
