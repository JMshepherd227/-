import numpy as np

def generate_pair(config):
    """生成一对 (P旧点集, Q新点集, 标签)，包含类别信息"""

    # 1. 生成真实病害点及其类别
    n = np.random.randint(*config.N_POINTS_RANGE)
    mode = np.random.choice(["uniform", "clustered", "mixed"])
    true_coords = sample_spatial_distribution(n, config.MAP_SIZE, mode)
    # 为每个真实点生成一个初始类别 (0 到 N_CLASSES-1)
    true_types = np.random.randint(0, config.N_CLASSES, n)

    # ---------------- 核心策略：高新增点样本策略 ----------------
    is_extreme_new = np.random.rand() < 0.15
    if is_extreme_new:
        det_rate_p, det_rate_q = np.random.uniform(0.1, 0.4), np.random.uniform(0.8, 1.0)
        lambda_new = np.random.randint(30, 80)
    else:
        det_rate_p = np.random.uniform(*config.DETECTION_RATE)
        det_rate_q = np.random.uniform(*config.DETECTION_RATE)
        lambda_new = np.random.poisson(config.NEW_DISEASE_LAMBDA)

    # 2. 旧点集 P
    P_raw_coords = apply_error(true_coords, config, seed=1)
    p_mask = np.random.rand(len(P_raw_coords)) < det_rate_p
    P_coords = P_raw_coords[p_mask]
    P_types = true_types[p_mask]
    P_true_idx = np.where(p_mask)[0]

    # 3. 新点集 Q (含匹配部分和新增部分)
    Q_raw_coords = apply_error(true_coords, config, seed=2)
    q_mask = np.random.rand(len(Q_raw_coords)) < det_rate_q
    Q_matched_coords = Q_raw_coords[q_mask]
    Q_matched_types = true_types[q_mask]
    # 模拟类型演变：10% 概率类型发生突变
    Q_matched_types = np.array([t if np.random.rand() > 0.1 else np.random.randint(0, config.N_CLASSES) for t in Q_matched_types])
    Q_true_idx = np.where(q_mask)[0]

    # 4. 加入真正新增病害点
    Q_new_coords = sample_spatial_distribution(lambda_new, config.MAP_SIZE, "uniform")
    Q_new_types = np.random.randint(0, config.N_CLASSES, lambda_new)

    Q_coords = np.vstack([Q_matched_coords, Q_new_coords]) if lambda_new > 0 else Q_matched_coords
    Q_types = np.concatenate([Q_matched_types, Q_new_types]) if lambda_new > 0 else Q_matched_types

    # 5. 构建标签矩阵 (逻辑不变)
    n_q, n_p = len(Q_coords), len(P_coords)
    labels = np.zeros((n_q, n_p + 1), dtype=np.float32)
    for qi, true_i in enumerate(Q_true_idx):
        matches = np.where(P_true_idx == true_i)[0]
        if len(matches) > 0: labels[qi, matches[0]] = 1.0
        else: labels[qi, -1] = 1.0
    for qi in range(len(Q_matched_coords), n_q):
        labels[qi, -1] = 1.0

    # 6. 归一化并拼接类别信息
    # 重点：normalize 只处理坐标，不处理类型
    P_norm_coords, Q_norm_coords, _, _ = normalize(P_coords, Q_coords)

    # 拼接成 (N, 3) 形状： [x_norm, y_norm, type_idx]
    P_final = np.column_stack([P_norm_coords, P_types])
    Q_final = np.column_stack([Q_norm_coords, Q_types])

    return P_final, Q_final, labels

def normalize(P, Q):
    if len(P) == 0 and len(Q) == 0: return P, Q, np.zeros(2), 1.0
    all_pts = np.vstack([P, Q]) if len(P) > 0 and len(Q) > 0 else (P if len(P) > 0 else Q)
    min_pt, max_pt = all_pts.min(axis=0), all_pts.max(axis=0)
    center = (min_pt + max_pt) / 2.0
    scale = np.max(max_pt - min_pt) / 2.0 + 1e-6
    return (P - center) / scale, (Q - center) / scale, center, scale

def apply_error(points, config, seed):
    rng = np.random.RandomState(seed * np.random.randint(1, 9999))
    if len(points) == 0: return np.zeros((0, 2))
    offset = rng.uniform(-config.GLOBAL_OFFSET_MAX, config.GLOBAL_OFFSET_MAX, 2)
    angle = np.deg2rad(rng.uniform(-config.ROTATION_MAX, config.ROTATION_MAX))
    R = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle),  np.cos(angle)]])
    noise = rng.normal(0, rng.uniform(0.5, config.LOCAL_NOISE_STD), (len(points), 2))
    return (points @ R.T) + offset + noise

def sample_spatial_distribution(n, size, mode):
    if n == 0: return np.zeros((0, 2))
    if mode == "uniform": return np.random.rand(n, 2) * size
    elif mode == "clustered":
        n_centers = max(1, n // 10)
        centers = np.random.rand(n_centers, 2) * size
        pts = centers[np.random.randint(0, n_centers, n)]
        return pts + np.random.randn(n, 2) * size * 0.05
    else:
        half = n // 2
        return np.vstack([sample_spatial_distribution(half, size, "uniform"),
                          sample_spatial_distribution(n - half, size, "clustered")])