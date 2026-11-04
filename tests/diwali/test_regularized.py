import torch
from research.diwali.regularized import parent_kl


def test_parent_kl_zero_at_parent_positive_on_change_and_teacher_detached():
    torch.manual_seed(17)
    parent=torch.randn(4,15,26,requires_grad=True);weights=torch.tensor([.5]+[.5/14]*14)
    same=parent.detach().clone().requires_grad_(True)
    assert abs(parent_kl(same,parent,weights).item())<1e-6
    changed=parent.detach().clone();changed[:,-1,13:]+=2;changed.requires_grad_(True)
    loss=parent_kl(changed,parent,weights)
    assert loss.item()>0
    loss.backward();assert parent.grad is None and changed.grad.abs().sum()>0


def test_parent_kl_averages_examples_not_categories():
    parent=torch.zeros(1,15,26);student=parent.clone();student[:,:,0]=1
    weights=torch.ones(15)/15
    loss=parent_kl(student,parent,weights)
    torch.testing.assert_close(loss,parent_kl(student.repeat(3,1,1),parent.repeat(3,1,1),weights))
