import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import seaborn as sns
from collections import defaultdict

class TrainingVisualizer:
    def __init__(self, save_base_dir="visualizations"):
        self.save_base_dir = save_base_dir
        self.metrics = defaultdict(list)
        self.confidences_match = []
        self.confidences_dustbin = []

    def update_metrics(self, epoch, train_loss, eval_results):
        self.metrics['epoch'].append(epoch)
        self.metrics['train_loss'].append(train_loss)
        self.metrics['f1'].append(eval_results['f1'])
        self.metrics['precision'].append(eval_results['precision'])
        self.metrics['recall'].append(eval_results['recall'])
        self.metrics['new_acc'].append(eval_results['new_point_acc'])

        cm = eval_results['cm_data']
        total_pts = cm['tp'] + cm['wm'] + cm['fn'] + cm['fp'] + cm['tn'] + 1e-9
        self.metrics['err_wrong_match'].append(cm['wm'] / total_pts)
        self.metrics['err_missed'].append(cm['fn'] / total_pts)
        self.metrics['err_false_alarm'].append(cm['fp'] / total_pts)

    def update_confidences(self, pred_probs, labels):
        if hasattr(pred_probs, 'cpu'): pred_probs = pred_probs.detach().cpu().numpy()
        if hasattr(labels, 'cpu'): labels = labels.detach().cpu().numpy()

        n_p = pred_probs.shape[-1] - 1
        for qi in range(len(pred_probs)):
            true_idx = np.argmax(labels[qi])
            conf = pred_probs[qi, true_idx]
            if true_idx == n_p:
                self.confidences_dustbin.append(conf)
            else:
                self.confidences_match.append(conf)

    def plot_all(self, epoch, cm_data):
        epoch_dir = os.path.join(self.save_base_dir, f"epoch_{epoch:03d}")
        metrics_dir = os.path.join(epoch_dir, "metrics")
        os.makedirs(metrics_dir, exist_ok=True)

        self._plot_curves(metrics_dir)
        self._plot_histograms(epoch, metrics_dir)
        self._plot_custom_confusion_matrix(cm_data, epoch, metrics_dir)

    def _plot_curves(self, save_dir):
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(22, 6))
        epochs = self.metrics['epoch']

        ax1.plot(epochs, self.metrics['train_loss'], label='Train Loss', marker='o', color='#ef5350', lw=2)
        ax1.set_title("Training Loss", fontsize=14)
        ax1.set_xlabel("Epoch")
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.legend()

        ax2.plot(epochs, self.metrics['f1'], label='F1 Score', marker='s', color='#42a5f5', lw=2)
        ax2.plot(epochs, self.metrics['precision'], label='Precision', linestyle='--', color='#26a69a')
        ax2.plot(epochs, self.metrics['recall'], label='Recall', linestyle='--', color='#ab47bc')
        ax2.plot(epochs, self.metrics['new_acc'], label='New Point Acc', marker='^', color='#66bb6a')
        ax2.set_title("Accuracy Metrics", fontsize=14)
        ax2.set_xlabel("Epoch")
        ax2.set_ylim(0, 1.05)
        ax2.grid(True, linestyle='--', alpha=0.6)
        ax2.legend(loc='lower right')

        ax3.plot(epochs, self.metrics['err_wrong_match'], label='Wrong Match (WM)', color='#d32f2f', lw=2)
        ax3.plot(epochs, self.metrics['err_missed'], label='False New (FN)', color='#f57c00', lw=2)
        ax3.plot(epochs, self.metrics['err_false_alarm'], label='False Match (FP)', color='#7b1fa2', lw=2)
        ax3.set_title("Error Type Distribution (Lower is Better)", fontsize=14)
        ax3.set_xlabel("Epoch")
        ax3.set_ylabel("Rate per Point")
        ax3.grid(True, linestyle='--', alpha=0.6)
        ax3.legend()

        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, "training_curves.png"), dpi=200)
        plt.close(fig)

    def _plot_histograms(self, epoch, save_dir):
        if not self.confidences_match and not self.confidences_dustbin: return
        fig, ax = plt.subplots(figsize=(8, 6))
        if self.confidences_match:
            ax.hist(self.confidences_match, bins=20, alpha=0.6, color='#42a5f5', label='Match Conf', density=True)
        if self.confidences_dustbin:
            ax.hist(self.confidences_dustbin, bins=20, alpha=0.6, color='#ffb300', label='New Point Conf', density=True)
        ax.set_title(f"Confidence Distribution (Epoch {epoch})")
        ax.set_xlabel("Confidence Score")
        ax.set_ylabel("Density")
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend()
        plt.savefig(os.path.join(save_dir, "confidence_hist.png"), dpi=200)
        plt.close(fig)
        self.confidences_match.clear()
        self.confidences_dustbin.clear()

    def _plot_custom_confusion_matrix(self, cm, epoch, save_dir):
        matrix = np.array([
            [cm['tp'], cm['wm'], cm['fn']],
            [0,        cm['fp'], cm['tn']]
        ])
        row_labels = ['True: Old Point', 'True: New Point']
        col_labels = ['Pred: Correct Match', 'Pred: Wrong Match', 'Pred: New Point']
        fig, ax = plt.subplots(figsize=(9, 6))
        sns.heatmap(matrix, annot=True, fmt='d', cmap='Blues',
                    xticklabels=col_labels, yticklabels=row_labels,
                    linewidths=1, linecolor='white', ax=ax)
        ax.set_title(f"Confusion Matrix (Epoch {epoch})", pad=20)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, "confusion_matrix.png"), dpi=200)
        plt.close(fig)

# =========================================================================
# 修复与增强的单样本可视化函数 (带有完整的统计面板与特效)
# =========================================================================
def save_matching_plot(P_coords, Q_coords, P_types, Q_types, labels, pred_probs, epoch, batch_idx, sample_idx=0, save_dir="visualizations"):
    epoch_dir = os.path.join(save_dir, f"epoch_{epoch:03d}", "match_samples")
    os.makedirs(epoch_dir, exist_ok=True)

    if hasattr(P_coords, 'cpu'): P_coords = P_coords.detach().cpu().numpy()
    if hasattr(Q_coords, 'cpu'): Q_coords = Q_coords.detach().cpu().numpy()
    if hasattr(labels, 'cpu'): labels = labels.detach().cpu().numpy()
    if hasattr(pred_probs, 'cpu'): pred_probs = pred_probs.detach().cpu().numpy()

    fig, ax = plt.subplots(figsize=(12, 10)) # 加宽了一点点，方便放右侧的统计面板
    ax.set_title(f"Epoch {epoch} | Batch {batch_idx} | Sample {sample_idx}", fontsize=15, pad=15)

    # 画出所有的新旧基础点
    ax.scatter(P_coords[:, 0], P_coords[:, 1], c='dodgerblue', marker='X', s=120, label='Old (P)', zorder=3, edgecolors='white', linewidths=0.5)
    ax.scatter(Q_coords[:, 0], Q_coords[:, 1], c='tomato', marker='o', s=80, label='New (Q)', zorder=3, edgecolors='white', linewidths=0.5)

    n_p = len(P_coords)
    n_q = len(Q_coords)

    x_range = P_coords[:, 0].max() - P_coords[:, 0].min() if len(P_coords) > 0 else 0.1
    y_range = P_coords[:, 1].max() - P_coords[:, 1].min() if len(P_coords) > 0 else 0.1
    dynamic_radius = max(min(x_range, y_range) * 0.05, 0.003)

    # 统计计数器
    stats = {'tp': 0, 'wm': 0, 'fp': 0, 'fn': 0, 'tn': 0}

    for qi in range(n_q):
        true_p_idx = np.argmax(labels[qi])
        is_new_gt = (true_p_idx == n_p)
        pred_p_idx = np.argmax(pred_probs[qi])
        is_new_pred = (pred_p_idx == n_p)
        q_pt = Q_coords[qi]

        # 场景 A: 真实和预测都是新增 (Correct New / TN) -> 绿色圈圈
        if is_new_gt and is_new_pred:
            stats['tn'] += 1
            circle = plt.Circle((q_pt[0], q_pt[1]), dynamic_radius, color='forestgreen', fill=False, linewidth=2.5, linestyle='--', zorder=4)
            ax.add_patch(circle)

        # 场景 B: 真实是新增，模型乱连旧点 (False Match / FP) -> 紫色虚线 (与其他线区分)
        elif is_new_gt and not is_new_pred:
            stats['fp'] += 1
            ax.plot([q_pt[0], P_coords[pred_p_idx][0]], [q_pt[1], P_coords[pred_p_idx][1]], c='purple', linestyle=':', linewidth=2, alpha=0.8, zorder=2)

        # 场景 C: 真实是匹配，模型判定新增 (False New / FN) -> 橙色点划线圈圈
        elif not is_new_gt and is_new_pred:
            stats['fn'] += 1
            circle = plt.Circle((q_pt[0], q_pt[1]), dynamic_radius, color='darkorange', fill=False, linewidth=2.5, linestyle='-.', zorder=4)
            ax.add_patch(circle)

        # 场景 D: 真实是匹配，模型也判定匹配
        elif not is_new_gt and not is_new_pred:
            p_pt_pred = P_coords[pred_p_idx]
            if true_p_idx == pred_p_idx:
                stats['tp'] += 1
                ax.plot([q_pt[0], p_pt_pred[0]], [q_pt[1], p_pt_pred[1]], c='forestgreen', linewidth=2.5, alpha=0.8, zorder=1)
            else:
                stats['wm'] += 1
                ax.plot([q_pt[0], p_pt_pred[0]], [q_pt[1], p_pt_pred[1]], c='crimson', linewidth=2.5, alpha=0.8, zorder=2)

    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle='--', alpha=0.3)

    # ================= 制作高精度统计面板 (Legend) =================
    legend_elements = [
        Line2D([0], [0], marker='X', color='w', markerfacecolor='dodgerblue', markersize=11, label=f'Old Points Total: {n_p}'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='tomato', markersize=9, label=f'New Points Total: {n_q}'),
        Line2D([0], [0], color='w', label=''), # 空白占位符，分隔用
        Line2D([0], [0], color='forestgreen', lw=3, label=f'Correct Match (TP): {stats["tp"]}'),
        Line2D([0], [0], color='crimson', lw=3, label=f'Wrong Match (WM): {stats["wm"]}'),
        Line2D([0], [0], color='purple', lw=2, linestyle=':', label=f'False Match (FP): {stats["fp"]}'),
        Line2D([0], [0], marker='o', color='w', markeredgecolor='forestgreen', markerfacecolor='none', markersize=12, markeredgewidth=2.5, linestyle='--', label=f'Correct New (TN): {stats["tn"]}'),
        Line2D([0], [0], marker='o', color='w', markeredgecolor='darkorange', markerfacecolor='none', markersize=12, markeredgewidth=2.5, linestyle='-.', label=f'Missed Match (FN): {stats["fn"]}')
    ]

    # 将 Legend 放在图表外侧右边，带有半透明背景，不会遮挡数据点
    ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.02, 0.5),
              fontsize=11, framealpha=0.9, edgecolor='#cccccc', title="Sample Statistics", title_fontsize=13)

    plt.tight_layout()
    filename = f"sample_{sample_idx:03d}.png"
    plt.savefig(os.path.join(epoch_dir, filename), dpi=200, bbox_inches='tight')
    plt.close(fig)