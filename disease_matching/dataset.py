# dataset.py
import torch
from torch.utils.data import Dataset
from data_generator import generate_pair


class SyntheticDataset(Dataset):
    def __init__(self, config, n_samples):
        self.config = config
        self.n_samples = n_samples

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        P, Q, labels = generate_pair(self.config)
        return (
            torch.tensor(P, dtype=torch.float32),
            torch.tensor(Q, dtype=torch.float32),
            torch.tensor(labels, dtype=torch.float32),
        )


def collate_variable_size(batch):
    """
    每个样本的 Np、Nq 不同，无法直接 stack。
    用 padding 对齐，同时返回 mask 告诉模型哪些是填充位。
    """
    Ps, Qs, labels_list = zip(*batch)

    max_p = max(p.shape[0] for p in Ps)
    max_q = max(q.shape[0] for q in Qs)
    feat_dim = Ps[0].shape[1]

    B = len(Ps)
    P_batch = torch.zeros(B, max_p, feat_dim)
    Q_batch = torch.zeros(B, max_q, feat_dim)
    label_batch = torch.zeros(B, max_q, max_p + 1)
    P_mask = torch.zeros(B, max_p, dtype=torch.bool)
    Q_mask = torch.zeros(B, max_q, dtype=torch.bool)

    for i, (p, q, lab) in enumerate(zip(Ps, Qs, labels_list)):
        np_, nq_ = p.shape[0], q.shape[0]
        P_batch[i, :np_] = p
        Q_batch[i, :nq_] = q
        P_mask[i, :np_] = True
        Q_mask[i, :nq_] = True

        # lab 形状是 (nq_, np_+1)
        # dustbin 列放到第 max_p 列
        label_batch[i, :nq_, :np_] = lab[:, :-1]   # 匹配列
        label_batch[i, :nq_, max_p] = lab[:, -1]   # dustbin 列

    return P_batch, Q_batch, label_batch, P_mask, Q_mask