# visualize.py
import os
import matplotlib.pyplot as plt
import numpy as np

def save_matching_plot(P_coords, Q_coords, P_types, Q_types, labels, pred_probs, epoch, batch_idx, save_dir="visualizations"):
    """
    可视化一次点集匹配的结果并保存为图片。
    P_coords, Q_coords: (N, 2) 归一化后的坐标
    labels: (N_q, N_p + 1) 真实的 one-hot 标签
    pred_probs: (N_q, N_p + 1) 模型预测的概率矩阵
    """
    os.makedirs(save_dir, exist_ok=True)

    # 转为 numpy
    if hasattr(P_coords, 'cpu'): P_coords = P_coords.cpu().numpy()
    if hasattr(Q_coords, 'cpu'): Q_coords = Q_coords.cpu().numpy()
    if hasattr(labels, 'cpu'): labels = labels.cpu().numpy()
    if hasattr(pred_probs, 'cpu'): pred_probs = pred_probs.cpu().numpy()

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_title(f"Epoch {epoch} - Batch {batch_idx} Matching Result", fontsize=14)

    # 1. 绘制旧点 P (蓝色叉号)
    ax.scatter(P_coords[:, 0], P_coords[:, 1], c='blue', marker='x', s=100, label='Old Points (P)', zorder=3)
    for i, p in enumerate(P_coords):
        ax.text(p[0]+0.02, p[1]+0.02, f"P{i}(T{int(P_types[i])})", color='blue', fontsize=8)

    # 2. 绘制新点 Q (红色圆点)
    ax.scatter(Q_coords[:, 0], Q_coords[:, 1], c='red', marker='o', s=60, label='New Points (Q)', zorder=3)
    for i, q in enumerate(Q_coords):
        ax.text(q[0]-0.04, q[1]-0.04, f"Q{i}(T{int(Q_types[i])})", color='red', fontsize=8)

    n_p = len(P_coords)

    # 3. 绘制连线
    for qi in range(len(Q_coords)):
        # 真实答案 (Ground Truth)
        true_p_idx = np.argmax(labels[qi])
        is_new_gt = (true_p_idx == n_p)

        # 模型预测 (Prediction)
        pred_p_idx = np.argmax(pred_probs[qi])
        conf = pred_probs[qi, pred_p_idx]
        is_new_pred = (pred_p_idx == n_p)

        q_pt = Q_coords[qi]

        # 场景 A: 真实和预测都是新增 (完全正确) -> 绿色圈圈
        if is_new_gt and is_new_pred:
            circle = plt.Circle((q_pt[0], q_pt[1]), 0.05, color='green', fill=False, linewidth=2, linestyle='--')
            ax.add_patch(circle)
            continue

        # 场景 B: 真实是新增，模型乱连旧点 (错配) -> 红色虚线
        if is_new_gt and not is_new_pred:
            p_pt = P_coords[pred_p_idx]
            ax.plot([q_pt[0], p_pt[0]], [q_pt[1], p_pt[1]], c='red', linestyle=':', linewidth=1.5, alpha=0.7)
            continue

        # 场景 C: 真实是匹配，模型判定新增 (保守漏配) -> 橙色圈圈
        if not is_new_gt and is_new_pred:
            circle = plt.Circle((q_pt[0], q_pt[1]), 0.05, color='orange', fill=False, linewidth=2, linestyle='-.')
            ax.add_patch(circle)
            continue

        # 场景 D: 真实是匹配，模型也判定匹配
        if not is_new_gt and not is_new_pred:
            p_pt_pred = P_coords[pred_p_idx]

            if true_p_idx == pred_p_idx:
                # 连对了！(绿色实线)
                ax.plot([q_pt[0], p_pt_pred[0]], [q_pt[1], p_pt_pred[1]], c='green', linewidth=2.0, alpha=0.8)
                # 在连线中点写上置信度
                mid_x, mid_y = (q_pt[0]+p_pt_pred[0])/2, (q_pt[1]+p_pt_pred[1])/2
                ax.text(mid_x, mid_y, f"{conf:.2f}", color='darkgreen', fontsize=7)
            else:
                # 连错了！(连到了别的旧点，红色实线)
                ax.plot([q_pt[0], p_pt_pred[0]], [q_pt[1], p_pt_pred[1]], c='red', linewidth=2.0, alpha=0.8)

    # 4. 图例和网格
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    ax.set_aspect('equal', adjustable='box') # 保持X和Y比例一致

    # 保存
    save_path = os.path.join(save_dir, f"epoch_{epoch:03d}_batch_{batch_idx:03d}.png")
    plt.savefig(save_path, dpi=200, bbox_inches='tight')
    plt.close(fig)