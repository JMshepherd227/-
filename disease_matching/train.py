# train.py
import os
import torch
from torch.utils.data import DataLoader
from dataset import SyntheticDataset, collate_variable_size
from model import DiseasePointMatcher
from loss import matching_loss
from config import Config
from evaluate import evaluate

# 尝试导入进度条，如果没有则使用普通打印
try:
    from tqdm import tqdm
except ImportError:
    print("建议安装 tqdm 以获得更好的训练可视化：pip install tqdm")
    tqdm = lambda x, **kwargs: x

# ANSI 颜色代码，用于终端高亮
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
    """格式化指标：高于 0.8 用绿色，0.5~0.8 用黄色，低于 0.5 用红色"""
    if val >= 0.8:
        return f"{Colors.GREEN}{val:.2%}{Colors.ENDC}"
    elif val >= 0.5:
        return f"{Colors.YELLOW}{val:.2%}{Colors.ENDC}"
    else:
        return f"{Colors.RED}{val:.2%}{Colors.ENDC}"

def train():
    config = Config()

    # 检查并创建保存目录
    save_dir = "newCheckpoints"
    os.makedirs(save_dir, exist_ok=True)

    model = DiseasePointMatcher(config).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.EPOCHS
    )

    print(f"\n{Colors.HEADER}{Colors.BOLD}🚀 [GNN 拓扑对齐引擎] 训练启动 {Colors.ENDC}")
    print(f"   - 训练轮数: {Colors.CYAN}{config.EPOCHS}{Colors.ENDC} Epochs")
    print(f"   - 样本规模: {Colors.CYAN}{config.TRAIN_SAMPLES}{Colors.ENDC} / Epoch")
    print(f"   - 批次大小: {Colors.CYAN}{config.BATCH_SIZE}{Colors.ENDC}")
    print(f"   - 运算设备: {Colors.BLUE}{next(model.parameters()).device}{Colors.ENDC}\n")

    best_f1 = 0.0
    best_epoch = 0

    for epoch in range(config.EPOCHS):
        model.train()
        total_loss = 0.0
        n_batches = 0

        # 初始化数据集和 DataLoader
        dataset = SyntheticDataset(config, config.TRAIN_SAMPLES)
        loader = DataLoader(
            dataset,
            batch_size=config.BATCH_SIZE,
            shuffle=True,
            collate_fn=collate_variable_size,
            num_workers=4,           # 加快数据生成速度（可根据CPU核数调整）
            pin_memory=True          # 加快 GPU 显存拷贝
        )

        # ---------------- 训练阶段 (带进度条) ----------------
        # 包装 DataLoader，产生进度条
        pbar = tqdm(loader, desc=f"⏳ Epoch {epoch+1:02d}/{config.EPOCHS}", leave=False, dynamic_ncols=True)

        for batch_idx, (P, Q, labels, P_mask, Q_mask) in enumerate(pbar):
            # 将数据推入 GPU
            P, Q = P.cuda(non_blocking=True), Q.cuda(non_blocking=True)
            labels = labels.cuda(non_blocking=True)
            P_mask, Q_mask = P_mask.cuda(non_blocking=True), Q_mask.cuda(non_blocking=True)

            # ---------------- 【注意】：修复参数传递 ----------------
            # 你的旧代码是: pred = model(P, Q)
            # 这会导致 P_mask 丢失！必须把 Mask 传进去！
            pred = model(P, Q, P_mask, Q_mask)

            # Loss 计算
            loss = matching_loss(pred, labels, Q_mask)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)
            optimizer.step()

            current_loss = loss.item()
            total_loss += current_loss
            n_batches += 1

            # 实时更新进度条上的 Loss 显示
            pbar.set_postfix({'Loss': f"{current_loss:.4f}"})

        # ---------------- 评估阶段 ----------------
        avg_loss = total_loss / n_batches
        scheduler.step()

        # 训练完一个 Epoch，开始评估
        pbar.set_description(f"🔍 Epoch {epoch+1:02d}/{config.EPOCHS} (正在评估...)")
        metrics = evaluate(model, config, n_samples=500)

        # 提取指标
        precision = metrics['precision']
        recall = metrics['recall']
        f1 = metrics['f1']
        new_acc = metrics['new_point_acc']

        # ---------------- 打印精美成绩单 ----------------
        # 清除进度条
        pbar.close()

        print(f"🎯 {Colors.BOLD}Epoch {epoch+1:02d}{Colors.ENDC} 完成 | "
              f"Avg Loss: {Colors.CYAN}{avg_loss:.4f}{Colors.ENDC} | "
              f"Precision: {format_metric(precision)} | "
              f"Recall: {format_metric(recall)} | "
              f"F1: {format_metric(f1)} | "
              f"新增识别率: {format_metric(new_acc)}")

        # ---------------- 保存策略 ----------------
        # 1. 保存 Best Model (核心)
        if f1 > best_f1:
            best_f1 = f1
            best_epoch = epoch + 1
            torch.save({
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'config': config,
                'metrics': metrics
            }, f'{save_dir}/best_matcher.pt')
            print(f"   {Colors.YELLOW}🌟 发现更优模型！Best F1 刷新为 {best_f1:.2%} (已保存至 best_matcher.pt){Colors.ENDC}")

        # 2. 每 10 轮保留一个历史快照
        if (epoch + 1) % 10 == 0:
            torch.save({
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'config': config,
            }, f'{save_dir}/matcher_epoch{epoch+1}.pt')
            print(f"   {Colors.BLUE}💾 定期快照已保存: matcher_epoch{epoch+1}.pt{Colors.ENDC}")

        print("-" * 80) # 分割线

    # 训练结束总结
    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 训练圆满结束！{Colors.ENDC}")
    print(f"🏆 历史最强模型出现在第 {Colors.CYAN}{best_epoch}{Colors.ENDC} 轮，F1 巅峰值为 {Colors.YELLOW}{best_f1:.2%}{Colors.ENDC}")
    print(f"📦 请提取 {save_dir}/best_matcher.pt 进行线上部署。")


if __name__ == "__main__":
    train()