import os
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from dataset import SyntheticDataset, collate_variable_size
from model import DiseasePointMatcher
from loss import matching_loss
from config import Config
from evaluate import evaluate
from visualize import TrainingVisualizer, save_matching_plot

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def format_metric(val):
    if val >= 0.8: return f"{Colors.GREEN}{val:.2%}{Colors.ENDC}"
    elif val >= 0.5: return f"{Colors.YELLOW}{val:.2%}{Colors.ENDC}"
    return f"{Colors.RED}{val:.2%}{Colors.ENDC}"

def train():
    config = Config()
    save_dir = "newCheckpoints"
    vis_dir = "visualizations"
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(vis_dir, exist_ok=True)

    visualizer = TrainingVisualizer(save_base_dir=vis_dir)
    model = DiseasePointMatcher(config).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=config.EPOCHS)

    print(f"\n{Colors.HEADER}{Colors.BOLD}🚀 训练启动 {Colors.ENDC}\n")

    best_f1 = 0.0

    for epoch in range(config.EPOCHS):
        model.train()
        total_loss, n_batches = 0.0, 0

        # 判断当前是否为记录和生成报告的轮次 (每10轮或最后一轮)
        is_log_epoch = (epoch + 1) % 10 == 0 or (epoch + 1) == config.EPOCHS

        dataset = SyntheticDataset(config, config.TRAIN_SAMPLES)
        loader = DataLoader(dataset, batch_size=config.BATCH_SIZE, shuffle=True, collate_fn=collate_variable_size, num_workers=4)

        pbar = tqdm(loader, desc=f"⏳ Epoch {epoch+1:02d}/{config.EPOCHS}", leave=False)

        for batch_idx, (P, Q, labels, P_mask, Q_mask) in enumerate(pbar):
            P, Q = P.cuda(non_blocking=True), Q.cuda(non_blocking=True)
            labels, P_mask, Q_mask = labels.cuda(), P_mask.cuda(), Q_mask.cuda()

            pred = model(P, Q, P_mask, Q_mask)
            loss = matching_loss(pred, labels, Q_mask)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1
            pbar.set_postfix({'Loss': f"{loss.item():.4f}"})

            # --------- 仅在指定轮次收集可视化数据 ---------
            if is_log_epoch and batch_idx < 3: # 取前三个 batch 画连线图和收集置信度
                with torch.no_grad():
                    probs = F.softmax(pred, dim=-1)

                    # 1. 保存连线图样本
                    b = 0
                    valid_p, valid_q = int(P_mask[b].sum().item()), int(Q_mask[b].sum().item())
                    if valid_p > 0 and valid_q > 0:
                        sliced_probs = torch.cat([probs[b, :valid_q, :valid_p], probs[b, :valid_q, -1:]], dim=-1)
                        sliced_labels = torch.cat([labels[b, :valid_q, :valid_p], labels[b, :valid_q, -1:]], dim=-1)
                        save_matching_plot(
                            P[b, :valid_p, :2], Q[b, :valid_q, :2], P[b, :valid_p, 2], Q[b, :valid_q, 2],
                            sliced_labels, sliced_probs, epoch+1, batch_idx, sample_idx=batch_idx, save_dir=vis_dir
                        )

                    # 2. 收集置信度用于直方图
                    for i in range(probs.shape[0]):
                        v_p, v_q = int(P_mask[i].sum().item()), int(Q_mask[i].sum().item())
                        if v_p > 0 and v_q > 0:
                            visualizer.update_confidences(
                                torch.cat([probs[i, :v_q, :v_p], probs[i, :v_q, -1:]], dim=-1),
                                torch.cat([labels[i, :v_q, :v_p], labels[i, :v_q, -1:]], dim=-1)
                            )

        avg_loss = total_loss / n_batches
        scheduler.step()

        # --------- 评估阶段 ---------
        pbar.set_description(f"🔍 Epoch {epoch+1:02d} (评估...)")
        metrics = evaluate(model, config, n_samples=500)
        pbar.close()

        print(f"🎯 Epoch {epoch+1:02d} | Loss: {Colors.CYAN}{avg_loss:.4f}{Colors.ENDC} | "
              f"Prec: {format_metric(metrics['precision'])} | Rec: {format_metric(metrics['recall'])} | "
              f"F1: {format_metric(metrics['f1'])} | 新增识别: {format_metric(metrics['new_point_acc'])}")

        visualizer.update_metrics(epoch+1, avg_loss, metrics)

        # --------- 触发完整的可视化图表生成 ---------
        if is_log_epoch:
            visualizer.plot_all(epoch+1, metrics['cm_data'])
            print(f"   {Colors.BLUE}📊 已生成第 {epoch+1} 轮可视化评估报告至 visualizations/epoch_{epoch+1:03d}{Colors.ENDC}")

        # --------- 保存策略 ---------
        if metrics['f1'] > best_f1:
            best_f1 = metrics['f1']
            torch.save({'model_state_dict': model.state_dict(), 'config': config}, f'{save_dir}/best_matcher.pt')
            print(f"   {Colors.YELLOW}🌟 Best F1 刷新为 {best_f1:.2%}{Colors.ENDC}")

if __name__ == "__main__":
    train()