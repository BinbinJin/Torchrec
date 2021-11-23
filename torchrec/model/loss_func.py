import torch
import torch.nn.functional as F
class FullScoreLoss(torch.nn.Module):
    def forward(self, label, pos_score, all_score):
        pass

class PairwiseLoss(torch.nn.Module):
    def forward(self, label, pos_score, log_pos_prob, neg_score, log_neg_prob):
        pass

class PointwiseLoss(torch.nn.Module):
    def forward(self, label, pos_score):
        raise NotImplementedError(f'{type(self).__name__} is an abstrat class, this method would not be implemented' )

class SquareLoss(PointwiseLoss):
    def forward(self, label, pos_score):
        return torch.sum(torch.square(label - pos_score), dim=-1)

class SoftmaxLoss(FullScoreLoss):
    def forward(self, label, pos_score, all_score):
        if all_score.dim() > pos_score.dim():
            return torch.sum(torch.logsumexp(all_score, dim=-1) - pos_score)
        else:
            return torch.sum(torch.nan_to_num(torch.logsumexp(all_score, dim=-1, keepdim=True) - pos_score, neginf=0))

class BPRLoss(PairwiseLoss):
    def __init__(self, dns=False):
        super().__init__()
        self.dns = dns
    def forward(self, label, pos_score, log_pos_prob, neg_score, log_neg_prob):
        if not self.dns:
            loss = F.logsigmoid(pos_score.unsqueeze(-1) - neg_score)
            weight = F.softmax(torch.ones_like(neg_score), -1)
            return -torch.sum(loss * weight)
        else:
            loss = -F.logsigmoid(pos_score - torch.max(neg_score, dim=-1)).sum()


class SampledSoftmaxLoss(PairwiseLoss):
    def forward(self, label, pos_score, log_pos_prob, neg_score, log_neg_prob):
        new_pos = pos_score - log_pos_prob
        new_neg = neg_score - log_neg_prob
        if new_pos.dim() < new_neg.dim():
            new_pos.sequeeze_(-1)
        new_neg = torch.cat([new_pos, new_neg], dim=-1)
        return torch.sum(torch.nan_to_num(torch.logsumexp(new_neg, dim=-1, keepdim=True) - new_pos, neginf=0))

class WeightedBPRLoss(PairwiseLoss):
    def forward(self, label, pos_score, log_pos_prob, neg_score, log_neg_prob):
        loss = F.logsigmoid(pos_score.unsqueeze(-1) - neg_score)
        weight = F.softmax(neg_score - log_neg_prob, -1)
        return -torch.sum(loss * weight)

class BinaryCrossEntropyLoss(PairwiseLoss):
    def __init__(self, dns=False):
        super().__init__()
        self.dns = dns
    def forward(self, label, pos_score, log_pos_prob, neg_score, log_neg_prob):
        if not self.dns or pos_score.dim() > 1:
            weight = F.softmax(torch.ones_like(neg_score), -1)
            return torch.sum(-F.logsigmoid(pos_score) + torch.sum(F.softplus(neg_score) * weight, dim=-1))
        else:
            return torch.sum(-F.logsigmoid(pos_score) + F.softplus(torch.max(neg_score, dim=-1)))
    
class WightedBinaryCrossEntropyLoss(PairwiseLoss):
    def forward(self, label, pos_score, log_pos_prob, neg_score, log_neg_prob):
        weight = F.softmax(neg_score - log_neg_prob, -1)
        return torch.sum(-F.logsigmoid(pos_score) + torch.sum(F.softplus(neg_score) * weight, dim=-1))

class HingeLoss(PairwiseLoss):
    def __init__(self, margin=2, num_items=None):
        super().__init__()
        self.margin = margin
        self.n_items = num_items

    def forward(self, label, pos_score, log_pos_prob, neg_score, neg_prob):
        loss = torch.max(torch.max(neg_score, dim=-1) - pos_score + self.margin, 0).sum()
        if self.n_items is not None:
            impostors = neg_score - pos_score.view(-1, 1) + self.margin > 0
            rank = torch.mean(impostors, -1) * self.n_items
            return loss * torch.log(rank + 1)
        else:
            return loss
