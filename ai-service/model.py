import math
import torch
import torch.nn as nn

class PointEncoder(nn.Module):
    def __init__(self, config):
        super().__init__()
        dim = config.FEATURE_DIM
        self.num_pos_feats = dim // 4

        self.register_buffer('freq_bands', 2.0 ** torch.linspace(0, 6, self.num_pos_feats))

        self.pos_mlp = nn.Sequential(
            nn.Linear(self.num_pos_feats * 4, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            nn.Linear(dim, dim)
        )
        self.type_embedding = nn.Embedding(config.N_CLASSES, dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            nn.Linear(dim, dim),
        )

    def forward(self, x_with_type):
        coords = x_with_type[:, :, :2]

        # 应用温和的高频编码
        pts_freq = coords.unsqueeze(-1) * self.freq_bands.view(1, 1, 1, -1) * math.pi
        pos_enc = torch.cat([torch.sin(pts_freq), torch.cos(pts_freq)], dim=-1)
        pos_enc = pos_enc.reshape(coords.shape[0], coords.shape[1], -1)

        coord_feat = self.pos_mlp(pos_enc)
        types = x_with_type[:, :, 2].long()
        types = torch.clamp(types, 0, self.type_embedding.num_embeddings - 1)

        feat = coord_feat + self.type_embedding(types)
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
        self.temperature = nn.Parameter(torch.tensor(1.0))

    def forward(self, P, Q, P_mask=None, Q_mask=None):
        P_feat = self.encoder(P)
        Q_feat = self.encoder(Q)
        P_feat, Q_feat = self.gnn(P_feat, Q_feat, P_mask, Q_mask)

        # 相似度缩放
        scores = torch.einsum('bqd,bpd->bqp', Q_feat, P_feat) / (P_feat.shape[-1] ** 0.5)

        temp = torch.clamp(self.temperature, min=0.1, max=1.5)
        scores = scores / temp

        if P_mask is not None:
            scores = scores.masked_fill(~P_mask.unsqueeze(1), -100.0)

        dustbin_scores = torch.einsum('bqd,d->bq', Q_feat, self.dustbin).unsqueeze(-1)
        dustbin_scores = (dustbin_scores / (P_feat.shape[-1] ** 0.5)) / temp

        full_scores = torch.cat([scores, dustbin_scores], dim=-1)

        # 将截断范围从 20 放大到 50，允许模型表达更强的置信度
        return torch.clamp(full_scores, min=-50, max=50)