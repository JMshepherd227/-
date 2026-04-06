# evaluate.py
import torch
import numpy as np

def evaluate(model, config, n_samples=200):
    from train import SyntheticDataset, collate_variable_size
    from torch.utils.data import DataLoader

    model.eval()
    # 增加 num_workers 可以加快数据生成速度
    loader = DataLoader(
        SyntheticDataset(config, n_samples),
        batch_size=config.BATCH_SIZE,
        collate_fn=collate_variable_size,
        num_workers=0 # 如果你的 CPU 核心多，可以设为 4
    )

    total_tp, total_fp, total_fn = 0, 0, 0
    total_new_correct, total_new_count = 0, 0

    threshold = 1.0 # 独立阈值

    with torch.no_grad():
        for P, Q, labels, P_mask, Q_mask in loader:
            # 1. 移动到 GPU
            P, Q, labels = P.cuda(), Q.cuda(), labels.cuda()
            P_mask, Q_mask = P_mask.cuda(), Q_mask.cuda()

            # pred: (B, Nq, Np+1)
            pred = model(P, Q, P_mask, Q_mask)

            # --- 向量化逻辑开始 ---
            B, Nq, Np_plus_1 = labels.shape
            Np = Np_plus_1 - 1

            # A. 提取 Ground Truth (GT)
            gt_is_new = (labels[:, :, Np] > 0.5)         # (B, Nq) 是否为新增点
            gt_p_idx = labels[:, :, :Np].argmax(dim=-1)  # (B, Nq) 对应的 P 索引

            # B. 提取模型预测 (Prediction)
            p_scores = pred[:, :, :Np]                   # (B, Nq, Np) 匹配分数列
            dustbin_scores = pred[:, :, Np]              # (B, Nq) 垃圾桶分数列

            best_p_val, best_p_idx = p_scores.max(dim=-1) # 每个 Q 对应的最高匹配分和索引

            # 核心判断：预测为“新增”的条件：(最高分没过阈值) OR (垃圾桶分数最高)
            pred_is_new = (pred.argmax(dim=-1) == Np)

            # C. 利用 Mask 过滤 Padding 的无效点
            valid_mask = Q_mask # (B, Nq)

            # --- 分场景统计 ---
            # 场景 1: GT 是匹配对 (not gt_is_new)
            is_match_gt = (~gt_is_new) & valid_mask
            correct_match = (best_p_idx == gt_p_idx) & (~pred_is_new) & is_match_gt

            total_tp += correct_match.sum().item()
            total_fn += (is_match_gt.sum() - correct_match.sum()).item()

            # 场景 2: GT 是新增点 (gt_is_new)
            is_new_gt = gt_is_new & valid_mask
            correct_new = pred_is_new & is_new_gt

            total_new_correct += correct_new.sum().item()
            total_new_count += is_new_gt.sum().item()

            # 场景 3: FP (原本是新增点，却被预测成了匹配对)
            total_fp += (is_new_gt.sum() - correct_new.sum()).item()

    precision = total_tp / (total_tp + total_fp + 1e-9)
    recall = total_tp / (total_tp + total_fn + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)
    new_point_acc = total_new_correct / (total_new_count + 1e-9)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "new_point_acc": new_point_acc
    }