"""Training-only KL anchor; inference remains the exact anchored price model."""
import torch
from torch.nn import functional as F


def endpoint_log_probabilities(logits):
    z=logits[:,-1]
    return F.log_softmax(torch.stack([torch.logsumexp(z[:,:13],-1),torch.logsumexp(z[:,13:],-1)],-1),-1)


def parent_kl(logits,parent_logits,weights):
    """KL(parent || corrected), weighted price bins plus final net direction.

    Sum categories before averaging examples; do not divide by26 categories.
    Parent targets are detached so this term cannot change the frozen teacher.
    """
    teacher=F.log_softmax(parent_logits.detach(),-1)
    by_horizon=F.kl_div(F.log_softmax(logits,-1),teacher,reduction='none',log_target=True).sum(-1)
    ranges=(by_horizon*weights).sum(-1).mean()
    endpoint=F.kl_div(endpoint_log_probabilities(logits),endpoint_log_probabilities(parent_logits.detach()),reduction='batchmean',log_target=True)
    return ranges+endpoint
