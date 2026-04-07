import torch
import torch.nn as nn

class PointEncoder(nn.Module):
    """把每个点的坐标+局部特征编码成向量"""
    def __init__(self, config):
        super().__init__()
        dim = config.FEATURE_DIM
        # 坐标投影
        self.coord_proj = nn.Linear(2, dim)
        # 类型嵌入：把类型索引转成向量
        self.type_embedding = nn.Embedding(config.N_CLASSES, dim)

        self.mlp = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            nn.Linear(dim, dim),
        )

    def forward(self, x_with_type):
        # x_with_type: (B, N, 3) -> [x, y, type_idx]
        coords = x_with_type[:, :, :2]
        types = x_with_type[:, :, 2].long()

        # 特征融合：坐标特征 + 类型特征
        feat = self.coord_proj(coords) + self.type_embedding(types)
        return self.mlp(feat)


class AttentionalGNN(nn.Module):
    """交替做自注意力（同集合内）和交叉注意力（跨集合）"""
    def __init__(self, dim, n_heads, n_layers):
        super().__init__()
        self.self_layers = nn.ModuleList([
            nn.MultiheadAttention(dim, n_heads, batch_first=True)
            for _ in range(n_layers)
        ])
        self.cross_layers = nn.ModuleList([
            nn.MultiheadAttention(dim, n_heads, batch_first=True)
            for _ in range(n_layers)
        ])
        self.norms = nn.ModuleList([
            nn.LayerNorm(dim) for _ in range(n_layers * 2)
        ])

    def forward(self, P_feat, Q_feat, P_mask=None, Q_mask=None):
        p_key_padding_mask = ~P_mask if P_mask is not None else None
        q_key_padding_mask = ~Q_mask if Q_mask is not None else None

        for i in range(len(self.self_layers)):
            # 自注意力
            P2, _ = self.self_layers[i](P_feat, P_feat, P_feat, key_padding_mask=p_key_padding_mask)
            Q2, _ = self.self_layers[i](Q_feat, Q_feat, Q_feat, key_padding_mask=q_key_padding_mask)
            P_feat = self.norms[2*i](P_feat + P2)
            Q_feat = self.norms[2*i](Q_feat + Q2)

            # 交叉注意力 (P查询Q, 因此 key 是 Q)
            P2, _ = self.cross_layers[i](P_feat, Q_feat, Q_feat, key_padding_mask=q_key_padding_mask)
            Q2, _ = self.cross_layers[i](Q_feat, P_feat, P_feat, key_padding_mask=p_key_padding_mask)
            P_feat = self.norms[2*i+1](P_feat + P2)
            Q_feat = self.norms[2*i+1](Q_feat + Q2)

        return P_feat, Q_feat


class DiseasePointMatcher(nn.Module):
    def __init__(self, config):
        super().__init__()
        dim = config.FEATURE_DIM
        #in_dim = 2 + config.K_NEIGHBORS  # 坐标 + 局部距离特征
        in_dim = 2

        self.encoder = PointEncoder(config)
        self.gnn = AttentionalGNN(dim, config.N_HEADS, config.N_LAYERS)

        #self.dustbin = nn.Parameter(torch.randn(dim))
        #self.dustbin_score = nn.Parameter(torch.tensor(0.0))
        self.dustbin = nn.Parameter(torch.ones(dim) * -1.0)

    def forward(self, P, Q, P_mask=None, Q_mask=None):
        P_feat = self.encoder(P)
        Q_feat = self.encoder(Q)

        P_feat, Q_feat = self.gnn(P_feat, Q_feat, P_mask, Q_mask)

        # 构建匹配分数矩阵 (B, Nq, Np)
        scores = torch.einsum('bqd,bpd->bqp', Q_feat, P_feat)
        scores = scores / (P_feat.shape[-1] ** 0.5)

        # 重点：把 Padding 掉的 P 的分数值设为极小值（负无穷），这样 Softmax 后概率为 0
        if P_mask is not None:
            # P_mask shape: (B, Np) -> 扩展为 (B, 1, Np) 适配 scores (B, Nq, Np)
            scores = scores.masked_fill(~P_mask.unsqueeze(1), -1e9)

        # 加入 dustbin 列 (B, Nq, 1)
        dustbin_scores = torch.einsum('bqd,d->bq', Q_feat, self.dustbin).unsqueeze(-1)

        full_scores = torch.cat([scores, dustbin_scores], dim=-1)
        return full_scores