import math
import torch
import torch.nn as nn

class PointEncoder(nn.Module):
    def __init__(self, config):
        super().__init__()
        dim = config.FEATURE_DIM
        # 进一步降低位置编码的敏感度，改用更平稳的投影
        self.coord_proj = nn.Linear(2, dim)
        self.type_embedding = nn.Embedding(config.N_CLASSES, dim)

        self.mlp = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            nn.Linear(dim, dim),
        )

    def forward(self, x_with_type):
        coords = x_with_type[:, :, :2]
        types = x_with_type[:, :, 2].long()
        types = torch.clamp(types, 0, self.type_embedding.num_embeddings - 1)

        # 暂时放弃复杂的 Sinusoidal PE，改用 Linear+LayerNorm
        # 这是最稳定的特征提取方式，先保证模型能跑通
        feat = self.coord_proj(coords) + self.type_embedding(types)
        return self.mlp(feat)


class AttentionalGNN(nn.Module):
    def __init__(self, dim, n_heads, n_layers):
        super().__init__()
        self.layers = nn.ModuleList([
            nn.MultiheadAttention(dim, n_heads, batch_first=True) for _ in range(n_layers * 2)
        ])
        self.norms = nn.ModuleList([
            nn.LayerNorm(dim) for _ in range(n_layers * 2)
        ])

    def forward(self, P_feat, Q_feat, P_mask=None, Q_mask=None):
        # 核心修复：防止全被屏蔽导致的 NaN
        if P_mask is not None:
            # 如果某一行全是 False，强制把第一个点设为 True
            all_false = ~(P_mask.any(dim=-1))
            P_mask[all_false, 0] = True
        if Q_mask is not None:
            all_false = ~(Q_mask.any(dim=-1))
            Q_mask[all_false, 0] = True

        p_key_padding_mask = ~P_mask if P_mask is not None else None
        q_key_padding_mask = ~Q_mask if Q_mask is not None else None

        for i in range(len(self.layers) // 2):
            # 自注意力 (Self-Attention)
            p_res, _ = self.layers[2*i](P_feat, P_feat, P_feat, key_padding_mask=p_key_padding_mask)
            q_res, _ = self.layers[2*i](Q_feat, Q_feat, Q_feat, key_padding_mask=q_key_padding_mask)
            P_feat = self.norms[2*i](P_feat + torch.nan_to_num(p_res))
            Q_feat = self.norms[2*i](Q_feat + torch.nan_to_num(q_res))

            # 交叉注意力 (Cross-Attention)
            p_res, _ = self.layers[2*i+1](P_feat, Q_feat, Q_feat, key_padding_mask=q_key_padding_mask)
            q_res, _ = self.layers[2*i+1](Q_feat, P_feat, P_feat, key_padding_mask=p_key_padding_mask)
            P_feat = self.norms[2*i+1](P_feat + torch.nan_to_num(p_res))
            Q_feat = self.norms[2*i+1](Q_feat + torch.nan_to_num(q_res))

        return P_feat, Q_feat


class DiseasePointMatcher(nn.Module):
    def __init__(self, config):
        super().__init__()
        dim = config.FEATURE_DIM
        self.encoder = PointEncoder(config)
        self.gnn = AttentionalGNN(dim, config.N_HEADS, config.N_LAYERS)
        self.dustbin = nn.Parameter(torch.zeros(dim))
        # 锁定温度，绝对不让它参与训练
        self.register_buffer('temperature', torch.tensor(1.0))

    def forward(self, P, Q, P_mask=None, Q_mask=None):
        P_feat = self.encoder(P)
        Q_feat = self.encoder(Q)
        P_feat, Q_feat = self.gnn(P_feat, Q_feat, P_mask, Q_mask)

        # 相似度缩放
        scores = torch.einsum('bqd,bpd->bqp', Q_feat, P_feat) / (P_feat.shape[-1] ** 0.5)

        if P_mask is not None:
            # 修复：不要用 -1e9 或 -1e4，用一个足以让 Softmax 归零但不会让导数爆炸的值
            scores = scores.masked_fill(~P_mask.unsqueeze(1), -20.0)

        dustbin_scores = torch.einsum('bqd,d->bq', Q_feat, self.dustbin).unsqueeze(-1)
        dustbin_scores = dustbin_scores / (P_feat.shape[-1] ** 0.5)

        full_scores = torch.cat([scores, dustbin_scores], dim=-1)

        # 核心修复：强制截断，保命
        return torch.clamp(full_scores, min=-20, max=20)