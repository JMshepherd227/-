import torch
import torch.nn.functional as F

def evaluate(model, config, n_samples=500):
    from dataset import SyntheticDataset, collate_variable_size
    from torch.utils.data import DataLoader

    model.eval()
    loader = DataLoader(
        SyntheticDataset(config, n_samples),
        batch_size=config.BATCH_SIZE,
        collate_fn=collate_variable_size,
        num_workers=0
    )

    # 细化状态统计
    total_tp = 0 # True Positive: 正确连线
    total_wm = 0 # Wrong Match: 连错旧点
    total_fn = 0 # False Negative: 本该连线却判为新增 (漏配)
    total_fp = 0 # False Positive: 本该是新增却连了旧点 (虚警)
    total_tn = 0 # True Negative: 正确判为新增

    with torch.no_grad():
        for batch_idx, (P, Q, labels, P_mask, Q_mask) in enumerate(loader):
            P_gpu, Q_gpu, labels_gpu = P.cuda(), Q.cuda(), labels.cuda()
            P_mask_gpu, Q_mask_gpu = P_mask.cuda(), Q_mask.cuda()

            pred_gpu = model(P_gpu, Q_gpu, P_mask_gpu, Q_mask_gpu)

            B, Nq, Np_plus_1 = labels_gpu.shape
            Np = Np_plus_1 - 1

            gt_is_new = (labels_gpu[:, :, Np] > 0.5)
            gt_p_idx = labels_gpu[:, :, :Np].argmax(dim=-1)

            pred_idx = pred_gpu.argmax(dim=-1)
            pred_is_new = (pred_idx == Np)

            valid_mask = Q_mask_gpu

            # 场景 1: GT 是匹配点
            is_match_gt = (~gt_is_new) & valid_mask
            correct_match = (pred_idx == gt_p_idx) & (~pred_is_new) & is_match_gt
            wrong_match = (pred_idx != gt_p_idx) & (~pred_is_new) & is_match_gt
            missed_match = pred_is_new & is_match_gt # 漏配

            total_tp += correct_match.sum().item()
            total_wm += wrong_match.sum().item()
            total_fn += missed_match.sum().item()

            # 场景 2: GT 是新增点
            is_new_gt = gt_is_new & valid_mask
            correct_new = pred_is_new & is_new_gt
            false_match = (~pred_is_new) & is_new_gt # 虚警

            total_tn += correct_new.sum().item()
            total_fp += false_match.sum().item()

    precision = total_tp / (total_tp + total_fp + total_wm + 1e-9)
    recall = total_tp / (total_tp + total_fn + total_wm + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)
    new_point_acc = total_tn / (total_tn + total_fp + 1e-9)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "new_point_acc": new_point_acc,
        "cm_data": {
            "tp": total_tp, "wm": total_wm, "fn": total_fn,
            "fp": total_fp, "tn": total_tn
        }
    }