// Separate midpoint sidecar; reuse the exact audited event replay and exclusions.
#define main audit_scanner_main
#include "archive_scan.cpp"
#undef main
#include <fstream>

struct MidpointScanner: Scanner {
  std::ofstream output;
  MidpointScanner():Scanner("book"){}
  void on_tick(I time,bool usable) override {
    usable=usable && er<=time && ee*1000000LL<=time;
    double mid=usable?(bids.rbegin()->first/1e8+asks.begin()->first/1e8)/2:0.;
    I fields[]={time,er,ee*1000000LL,last,time-last_update_recv,usable?1:0};
    output.write(reinterpret_cast<char*>(fields),sizeof(fields));
    output.write(reinterpret_cast<char*>(&mid),sizeof(mid));
  }
  void extract(const std::string& input,I hour,const std::string& destination) {
    output.open(destination,std::ios::binary|std::ios::trunc);
    if(!output)throw std::runtime_error("Midpoint output unavailable");
    std::ostringstream audit;auto* original=std::cout.rdbuf(audit.rdbuf());
    try{run(input,hour);}catch(...){std::cout.rdbuf(original);throw;}
    std::cout.rdbuf(original);output.close();if(!output)throw std::runtime_error("Midpoint write failed");
    std::cout<<audit.str()<<std::flush;
  }
};
int main() {
  MidpointScanner scan;std::string line;
  while(std::getline(std::cin,line)) {
    auto a=line.find('\t'),b=line.find('\t',a+1);
    if(a==std::string::npos||b==std::string::npos)return 2;
    try{scan.extract(line.substr(a+1,b-a-1),std::stoll(line.substr(0,a)),line.substr(b+1));}
    catch(const std::exception&){return 3;}
  }
}
