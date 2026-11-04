"""Join audited fit/selection/calibration cohorts; reserved final data stay absent."""
import numpy as np
from .event_data_exact import ExactEventData
from .event_evaluation import interval


class FinalBuildData(ExactEventData):
    def __init__(self,august,september):
        self.parts=[august,september]
        fit_start,fit_stop=interval('final','fit');select_start,_=interval('final','select');_,cal_stop=interval('final','calibrate')
        for part,start,stop in [(august,fit_start,fit_stop),(september,select_start,cal_stop)]:
            if not len(part.ids) or ((part.cutoffs<start)|(part.cutoffs>=stop)).any() or (np.diff(part.cutoffs)<=0).any():raise ValueError('Final-build input cohort outside its frozen dates')
            if (part.starts+15*60*10**9>stop).any():raise ValueError('Targets cross retained source end')
        self.ends=np.cumsum([len(p.ids) for p in self.parts]);self.ids=np.arange(int(self.ends[-1]),dtype=np.int64)
        for name in ['returns','y','cutoffs','starts']:
            setattr(self,name,np.concatenate([getattr(p,name) for p in self.parts]))
        self.hashes={name:p.hashes for name,p in zip(['august_fit','september_selection_calibration'],self.parts)}
    def location(self,j):
        j=int(j)
        if not 0<=j<len(self.ids):raise IndexError('Final-build row outside cohort')
        part=int(np.searchsorted(self.ends,j,side='right'));offset=0 if part==0 else int(self.ends[part-1])
        return self.parts[part],j-offset
    def raw(self,j):
        part,local=self.location(j);return part.raw(local)
    def exact_elapsed(self,j):
        part,local=self.location(j);return part.exact_elapsed(local)
