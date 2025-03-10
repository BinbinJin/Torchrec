import copy
from torch.utils.data import DataLoader
from torchrec.data.dataset import MFDataset, SeqDataset, SortedDataSampler
import torch
class ALSDataset(MFDataset):
    def build(self, ratio_or_num, shuffle=True, split_mode='user_entry'):
        datasets = self._build(ratio_or_num, shuffle, split_mode, True, False)
        data_index = datasets[0].inter_feat_subset
        user_ids = self.inter_feat.get_col(self.fuid)[data_index]
        user_uniq, count_train = torch.unique_consecutive(user_ids, return_counts=True)
        cumsum = torch.hstack([torch.tensor([0]), count_train.cumsum(-1)])
        datasets[0].data_index = torch.tensor([[u, data_index[st], data_index[en-1]+1] for u, st, en in zip(user_uniq, cumsum[:-1], cumsum[1:])])
        return datasets
    
    def transpose(self):
        output = copy.copy(self)
        item_ids = self.inter_feat.get_col(self.fiid)
        data_index = self.inter_feat_subset
        indicator = torch.zeros_like(item_ids, dtype=torch.bool).scatter(0, data_index, True)
        sort_idx = (item_ids * 2 + ~indicator).sort().indices
        output.inter_feat = self.inter_feat.reindex(sort_idx)
        item_uniq, count_toal = torch.unique_consecutive(item_ids[sort_idx], return_counts=True)
        count_train = [_.sum() for _ in torch.split(indicator[sort_idx], tuple(count_toal))]
        cumsum = torch.hstack([torch.tensor([0]), count_toal.cumsum(-1)])
        output.data_index = torch.tensor([[i, st, st+c] for i, st, c in zip(item_uniq, cumsum[:-1], count_train)])
        output.fuid = self.fiid
        output.fiid = self.fuid
        output.user_feat = self.item_feat
        output.item_feat = self.user_feat
        return output
    
    def loader(self, batch_size, shuffle=True, num_workers=1, drop_last=False):
        sampler = SortedDataSampler(self, batch_size, drop_last)
        output = DataLoader(self, sampler=sampler, batch_size=None, shuffle=False, num_workers=num_workers)
        return output
    
    
    def save(self, file_name=None):
        import scipy.sparse as ssp
        import scipy.io as sio
        import os
        users, items, ratings = [], [], []
        for data in self.loader(batch_size=100, shuffle=True):
            uid, iid, rating = data[self.fuid], data[self.fiid], data[self.frating]
            for u, ids, rs in zip(uid, iid, rating):
                for id, r in zip(ids, rs):
                    if u>0 and id>0:
                        if 'user' in self.fuid:
                            users.append(u)
                            items.append(id)
                        else:
                            users.append(id)
                            items.append(u)
                        ratings.append(r)
        users = (torch.stack(users) - 1).numpy()
        items = (torch.stack(items) - 1).numpy()
        ratings = torch.stack(ratings).numpy()
        shape = [self.num_users-1, self.num_items-1]
        shape = shape if 'user' in self.fuid else shape.reverse()
        mat = ssp.csc_matrix((ratings, (users, items)), shape)
        #sio.savemat(os.path.join('datasets', file_name+'.mat'), {file_name:mat}, format='4')
        return mat



class SessionDataset(SeqDataset):
    pass