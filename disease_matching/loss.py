import torch
import torch.nn.functional as F

def matching_loss(pred_scores, labels, Q_mask=None, dustbin_weight=1.0):
    """
    dustbin_weight: 调整对“无匹配/新增点”的重视程度
    """
    log_probs = F.log_softmax(pred_scores, dim=-1)

    # 构建权重矩阵：普通匹配列权重为 1.0，最后一列(dustbin)权重放大
    # labels 形状: (B, Nq, Np+1)
    weights = torch.ones_like(labels)
    weights[:, :, -1] = dustbin_weight  # 把最后一列的权重调大

    # 计算加权的交叉熵
    weighted_labels = labels * weights
    point_loss = -(weighted_labels * log_probs).sum(dim=-1)

    if Q_mask is not None:
        loss = point_loss[Q_mask].mean()
    else:
        loss = point_loss.mean()
    return loss