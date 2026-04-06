# train.py
import torch
from torch.utils.data import DataLoader
from dataset import SyntheticDataset, collate_variable_size
from model import DiseasePointMatcher
from loss import matching_loss
from config import Config
from evaluate import evaluate

def train():
    config = Config()
    model = DiseasePointMatcher(config).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.EPOCHS
    )

    print(f"开始训练，共 {config.EPOCHS} 个 epoch，每epoch {config.TRAIN_SAMPLES} 个样本")
    print(f"使用设备：{next(model.parameters()).device}")

    for epoch in range(config.EPOCHS):
        model.train()
        total_loss = 0.0
        n_batches = 0

        for batch_idx, (P, Q, labels, P_mask, Q_mask) in enumerate(DataLoader(
                SyntheticDataset(config, config.TRAIN_SAMPLES),
                batch_size=config.BATCH_SIZE,
                shuffle=True,
                collate_fn=collate_variable_size
        )):
            pred = model(P.cuda(), Q.cuda())
            loss = matching_loss(pred, labels.cuda(), Q_mask.cuda())

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1

            # 每100个batch打印一次
            if (batch_idx + 1) % 100 == 0:
                print(f"  Epoch {epoch+1} | Batch {batch_idx+1} | Loss: {loss.item():.4f}")

        avg_loss = total_loss / n_batches
        print(f"Epoch {epoch+1}/{config.EPOCHS} 完成 | 平均Loss: {avg_loss:.4f}")

        scheduler.step()

        metrics = evaluate(model, config, n_samples=500)
        print(
            f"Epoch {epoch+1}/{config.EPOCHS} | "
            f"Loss: {avg_loss:.4f} | "
            f"精确率: {metrics['precision']:.3f} | "
            f"召回率: {metrics['recall']:.3f} | "
            f"F1: {metrics['f1']:.3f} | "
            f"新增点识别率: {metrics['new_point_acc']:.3f}"
        )
        model.train()

        if (epoch + 1) % 10 == 0:
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'config': config,
            }, f'checkpoints/matcher_epoch{epoch+1}.pt')
            print(f"  → 已保存 checkpoints/matcher_epoch{epoch+1}.pt")

if __name__ == "__main__":
    train()