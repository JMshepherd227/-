#infer.py
import torch
import numpy as np

from data_generator import normalize
from model import DiseasePointMatcher


def load_model(pt_path):
    checkpoint = torch.load(pt_path, map_location='cpu')
    config = checkpoint['config']
    model = DiseasePointMatcher(config)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    return model

def match(model, P_raw, Q_raw, prob_threshold=0.5, raw_score_threshold=1.0):
    """
    prob_threshold: Softmax 相对概率的底线
    raw_score_threshold: 特征绝对相似度的底线
    """
    if len(Q_raw) == 0: return [], []
    if len(P_raw) == 0: return [], list(range(len(Q_raw)))

    P_norm, Q_norm, center, scale = normalize(P_raw, Q_raw)

    with torch.no_grad():
        P_t = torch.tensor(P_norm, dtype=torch.float32).unsqueeze(0)
        Q_t = torch.tensor(Q_norm, dtype=torch.float32).unsqueeze(0)

        # 取出预测的 logit 分数
        scores = model(P_t, Q_t).squeeze(0)  # (Nq, Np+1)
        probs = torch.softmax(scores, dim=-1).numpy()
        raw_scores = scores.numpy()

    matched_pairs, new_points = [], []

    for qi in range(len(Q_raw)):
        # 1. 如果模型明确将其扔进垃圾桶，直接判定为新增
        best_idx = probs[qi].argmax()
        if best_idx == len(P_raw):
            new_points.append(qi)
            continue

        # 2. 【核心逻辑】模型虽然给了一个匹配点 best_idx，我们进行双重审查！
        best_p_prob = probs[qi, best_idx]         # 相对概率
        best_p_raw_score = raw_scores[qi, best_idx] # 绝对特征相似度

        # 只有在“概率说得过去”且“绝对相似度达标”时，才承认配对
        if best_p_prob > prob_threshold and best_p_raw_score > raw_score_threshold:
            matched_pairs.append((qi, best_idx))
        else:
            # 否则，打回原形，作为新增点
            new_points.append(qi)

    return matched_pairs, new_points


# 使用示例
if __name__ == "__main__":
    model = load_model("checkpoints/matcher_epoch100.pt")

    P = np.array([[116.391, 39.901], [116.392, 39.903]])  # 旧点
    Q = np.array([[116.391, 39.902], [116.395, 39.910]])  # 新点

    pairs, new_pts = match(model, P, Q)
    print("匹配对（新点idx → 旧点idx）：", pairs)
    print("新增病害点idx：", new_pts)