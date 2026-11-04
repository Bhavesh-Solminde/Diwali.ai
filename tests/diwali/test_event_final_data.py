import numpy as np
import pytest
from research.diwali.event_final_data import FinalBuildData
from research.diwali.event_evaluation import MINUTE,interval
from research.diwali.event_final_train import selected_family
from research.diwali.event_protocol import protocol


class Part:
    def __init__(self,start):
        self.ids=np.arange(2);self.cutoffs=np.array([start+15*10**9,start+MINUTE+15*10**9]);self.starts=(self.cutoffs//MINUTE+1)*MINUTE
        self.y=np.zeros((2,15),np.int64);self.returns=np.zeros((2,15));self.hashes={'part':str(start)}
    def raw(self,j):return ('part',self.hashes,j)
    def exact_elapsed(self,j):return np.array([j],np.int64)


def test_merge_keeps_fit_selection_separate_and_denies_final_score():
    a=Part(interval('final','fit')[0]);b=Part(interval('final','select')[0]);data=FinalBuildData(a,b)
    assert data.partition('final','fit')[0].tolist()==[0,1]
    assert data.partition('final','select')[0].tolist()==[2,3]
    assert data.raw(2)==b.raw(0) and data.raw(1)==a.raw(1)
    np.testing.assert_array_equal(data.exact_elapsed(3),[1])
    with pytest.raises(ValueError,match='deliberately released'):data.partition('final','score')
    with pytest.raises(IndexError):data.raw(4)


def test_future_final_block_cannot_be_merged_and_incomplete_study_cannot_select():
    with pytest.raises(ValueError,match='outside its frozen dates'):
        FinalBuildData(Part(interval('final','fit')[0]),Part(interval('final','score')[0]))
    with pytest.raises(ValueError,match='incomplete'):selected_family({'state':'development_in_progress'},protocol())
