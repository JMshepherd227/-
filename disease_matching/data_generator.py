# data_generator.py
import numpy as np
from scipy.spatial.distance import cdist

def generate_pair(config):
    """生成一对 (P旧点集, Q新点集, 标签)"""

    # 1. 生成真实病害点
    n = np.random.randint(*config.N_POINTS_RANGE)
    mode = np.random.choice(["uniform", "clustered", "mixed"])
    true_pts = sample_spatial_distribution(n, config.MAP_SIZE, mode)

    # ---------------- 核心策略：高新增点样本策略 ----------------
    # 30% 概率触发极端情况（旧数据全丢/大量漏检，且新病害大爆发）
    is_extreme_new = np.random.rand() < 0.15

    if is_extreme_new:
        det_rate_p = np.random.uniform(0.1, 0.4)     # 旧点几乎检测不到
        det_rate_q = np.random.uniform(0.8, 1.0)     # 新点全检出
        lambda_new = np.random.randint(30, 80)       # 塞入极大量的新增点
    else:
        det_rate_p = np.random.uniform(*config.DETECTION_RATE)
        det_rate_q = np.random.uniform(*config.DETECTION_RATE)
        lambda_new = np.random.poisson(config.NEW_DISEASE_LAMBDA)
    # ------------------------------------------------------------

    # 2. 旧点集（历史采集）
    P_raw = apply_error(true_pts, config, seed=1)
    p_mask = np.random.rand(len(P_raw)) < det_rate_p
    P = P_raw[p_mask]
    P_true_idx = np.where(p_mask)[0]  # 记录旧点对应哪个真实点

    # 3. 新点集（新任务采集）
    Q_raw = apply_error(true_pts, config, seed=2)
    q_mask = np.random.rand(len(Q_raw)) < det_rate_q
    Q_matched = Q_raw[q_mask]
    Q_true_idx = np.where(q_mask)[0]

    # 4. 加入真正新增病害点
    Q_new = sample_spatial_distribution(lambda_new, config.MAP_SIZE, "uniform")
    Q = np.vstack([Q_matched, Q_new]) if lambda_new > 0 else Q_matched

    # 5. 构建标签矩阵
    # labels[i][j] = 1 表示 Q[i] 对应 P[j]
    # labels[i][-1] = 1 表示 Q[i] 是新增点（无匹配）
    n_q, n_p = len(Q), len(P)
    labels = np.zeros((n_q, n_p + 1), dtype=np.float32)

    for qi, true_i in enumerate(Q_true_idx):
        matches = np.where(P_true_idx == true_i)[0]
        if len(matches) > 0:
            labels[qi, matches[0]] = 1.0
        else:
            labels[qi, -1] = 1.0  # 无匹配（旧点漏检）

    for qi in range(len(Q_matched), n_q):
        labels[qi, -1] = 1.0  # 新增病害点

    # 6. 归一化（使用绝对稳定的全局包围盒归一化）
    P_norm, Q_norm, _, _ = normalize(P, Q)

    return P_norm, Q_norm, labels


def normalize(P, Q):
    """全局稳定归一化，防止由于单边漏检导致的质心大幅度偏移"""
    if len(P) == 0 and len(Q) == 0:
        return P, Q, np.zeros(2), 1.0

    # 组合新旧点集，找一个全局稳定的外接矩形中心
    all_pts = np.vstack([P, Q]) if len(P) > 0 and len(Q) > 0 else (P if len(P) > 0 else Q)

    min_pt = all_pts.min(axis=0)
    max_pt = all_pts.max(axis=0)
    center = (min_pt + max_pt) / 2.0

    # 缩放到 [-1, 1] 区间，加 1e-6 防止除以 0
    scale = np.max(max_pt - min_pt) / 2.0 + 1e-6

    P_norm = (P - center) / scale
    Q_norm = (Q - center) / scale

    return P_norm, Q_norm, center, scale


def apply_error(points, config, seed):
    """模拟采集误差（包含全局偏移、旋转、局部噪声）"""
    rng = np.random.RandomState(seed * np.random.randint(1, 9999))
    n = len(points)
    if n == 0:
        return np.zeros((0, 2))

    # 全局偏移
    offset = rng.uniform(-config.GLOBAL_OFFSET_MAX, config.GLOBAL_OFFSET_MAX, 2)

    # 全局旋转
    angle = np.deg2rad(rng.uniform(-config.ROTATION_MAX, config.ROTATION_MAX))
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle),  np.cos(angle)]])

    # 局部噪声 (此处稍微增加一点随机性，让模型见识不同精度的噪声)
    current_noise_std = rng.uniform(0.5, config.LOCAL_NOISE_STD)
    noise = rng.normal(0, current_noise_std, (n, 2))

    return (points @ R.T) + offset + noise


def sample_spatial_distribution(n, size, mode):
    """模拟真实病害在路面上的分布情况"""
    if n == 0:
        return np.zeros((0, 2))

    if mode == "uniform":
        return np.random.rand(n, 2) * size

    elif mode == "clustered":
        n_centers = max(1, n // 10)
        centers = np.random.rand(n_centers, 2) * size
        pts = centers[np.random.randint(0, n_centers, n)]
        return pts + np.random.randn(n, 2) * size * 0.05

    else:  # mixed
        half = n // 2
        return np.vstack([
            sample_spatial_distribution(half, size, "uniform"),
            sample_spatial_distribution(n - half, size, "clustered")
        ])