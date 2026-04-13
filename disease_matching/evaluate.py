# evaluate.py
import torch
import torch.nn.functional as F

try:
    from visualize import save_matching_plot
except ImportError:
    save_matching_plot = None
    print("Warning: visualize.py not found. Plotting disabled.")

def evaluate(model, config, n_samples=200, epoch_idx=0):
    from dataset import SyntheticDataset, collate_variable_size
    from torch.utils.data import DataLoader

    model.eval()
    loader = DataLoader(
        SyntheticDataset(config, n_samples),
        batch_size=config.BATCH_SIZE,
        collate_fn=collate_variable_size,
        num_workers=0  # 在 Windows 下建议设为 0 防止多进程挂起
    )

    total_tp, total_fp, total_fn = 0, 0, 0
    total_new_correct, total_new_count = 0, 0

    threshold = 1.0 # 独立阈值
    saved_plot = False

    with torch.no_grad():
        for batch_idx, (P, Q, labels, P_mask, Q_mask) in enumerate(loader):
            # 1. 全部推入 GPU
            P_gpu, Q_gpu, labels_gpu = P.cuda(), Q.cuda(), labels.cuda()
            P_mask_gpu, Q_mask_gpu = P_mask.cuda(), Q_mask.cuda()

            # 2. 模型推理 (在 GPU 上)
            pred_gpu = model(P_gpu, Q_gpu, P_mask_gpu, Q_mask_gpu)

            # --- 3. 可视化逻辑 (安全切片并拉回 CPU) ---
            if save_matching_plot is not None and not saved_plot:
                # 算一次概率矩阵
                probs_gpu = F.softmax(pred_gpu, dim=-1)

                b = 0 # 取 Batch 里第一个样本
                valid_p = int(P_mask_gpu[b].sum().item())
                valid_q = int(Q_mask_gpu[b].sum().item())

                if valid_p > 0 and valid_q > 0:
                    # 剥离出真实的坐标和类型，并拉回 CPU
                    P_valid_cpu = P[b, :valid_p, :2].numpy()
                    Q_valid_cpu = Q[b, :valid_q, :2].numpy()
                    P_types_cpu = P[b, :valid_p, 2].numpy()
                    Q_types_cpu = Q[b, :valid_q, 2].numpy()

                    # 剥离出真实的标签和预测的概率
                    labels_valid = torch.cat([labels_gpu[b, :valid_q, :valid_p], labels_gpu[b, :valid_q, -1:]], dim=-1)
                    probs_valid = torch.cat([probs_gpu[b, :valid_q, :valid_p], probs_gpu[b, :valid_q, -1:]], dim=-1)

                    labels_valid_cpu = labels_valid.cpu().numpy()
                    probs_valid_cpu = probs_valid.cpu().numpy()

                    save_matching_plot(
                        P_valid_cpu, Q_valid_cpu, P_types_cpu, Q_types_cpu,
                        labels_valid_cpu, probs_valid_cpu,
                        epoch_idx, batch_idx
                    )
                    saved_plot = True

            # --- 4. 向量化统计指标 (必须全部使用 _gpu 结尾的变量) ---
            B, Nq, Np_plus_1 = labels_gpu.shape
            Np = Np_plus_1 - 1

            # A. 提取 Ground Truth
            gt_is_new = (labels_gpu[:, :, Np] > 0.5)
            gt_p_idx = labels_gpu[:, :, :Np].argmax(dim=-1)

            # B. 提取预测
            p_scores = pred_gpu[:, :, :Np]
            dustbin_scores = pred_gpu[:, :, Np]

            best_p_val, best_p_idx = p_scores.max(dim=-1)

            # 判新条件：最高分没过阈值 OR 垃圾桶分最高
            pred_is_new = (best_p_val < threshold) | (pred_gpu.argmax(dim=-1) == Np)

            # C. Mask 过滤
            valid_mask = Q_mask_gpu

            # --- 场景统计 ---
            # 场景 1: GT 是匹配
            is_match_gt = (~gt_is_new) & valid_mask
            correct_match = (best_p_idx == gt_p_idx) & (~pred_is_new) & is_match_gt

            total_tp += correct_match.sum().item()
            total_fn += (is_match_gt.sum() - correct_match.sum()).item()

            # 场景 2: GT 是新增
            is_new_gt = gt_is_new & valid_mask
            correct_new = pred_is_new & is_new_gt

            total_new_correct += correct_new.sum().item()
            total_new_count += is_new_gt.sum().item()

            # 场景 3: FP (本该是新增却配对了)
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