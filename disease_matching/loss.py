import torch
import torch.nn.functional as F

def matching_loss(pred_scores, labels, Q_mask=None):
    """
    pred_scores: (B, Nq, Np+1)
    labels:      (B, Nq, Np+1)
    Q_mask:      (B, Nq)
    """
    # 1. 强制数值修正：如果在 pred_scores 里是 -20 (被屏蔽位)，
    # 但 labels 却要在那里算 Loss，这会产生极大梯度。
    # 我们在这里做一个安全截断
    log_probs = F.log_softmax(pred_scores, dim=-1)

    # 2. 只计算有效点
    loss_matrix = -(labels * log_probs)

    # 3. 拦截异常大的单点 Loss (阈值设为 15.0)
    loss_matrix = torch.clamp(loss_matrix, max=15.0)

    loss_per_point = loss_matrix.sum(dim=-1)

    if Q_mask is not None:
        num_valid = Q_mask.sum()
        if num_valid > 0:
            return loss_per_point[Q_mask].sum() / num_valid
        else:
            return pred_scores.sum() * 0.0
    return loss_per_point.mean()