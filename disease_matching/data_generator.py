import numpy as np
from scipy.spatial.distance import cdist

def generate_pair(config):
    """
    生成一对 (P旧点集, Q新点集, 标签)
    包含动态尺度缩放、类别模拟、拓扑形变
    """

    # 1. 动态选择本次样本的地图尺度 (例如 50m 到 3000m)
    current_map_size = np.random.uniform(*config.MAP_SIZE_RANGE)

    # 2. 生成真实病害点及其类别
    # 点数与地图大小略微正相关，但保持在 N_POINTS_RANGE 内
    n = np.random.randint(*config.N_POINTS_RANGE)
    mode = np.random.choice(["uniform", "clustered", "mixed"])
    true_coords = sample_spatial_distribution(n, current_map_size, mode)
    # 为每个真实点生成初始类别 (0 到 N_CLASSES-1)
    true_types = np.random.randint(0, config.N_CLASSES, n)

    # ---------------- 核心策略：动态新增病害概率 ----------------
    # 30% 概率触发极端情况（漏检多，新增多）
    is_extreme = np.random.rand() < 0.2

    if is_extreme:
        det_rate_p = np.random.uniform(0.3, 0.6)  # 旧点大量漏检
        det_rate_q = np.random.uniform(0.7, 0.9)
        # 新增点数是旧点的 2 倍甚至更多，逼迫模型学会拒绝
        base_lambda = config.NEW_DISEASE_LAMBDA * np.random.uniform(2.0, 5.0)
    else:
        det_rate_p = np.random.uniform(*config.DETECTION_RATE)
        det_rate_q = np.random.uniform(*config.DETECTION_RATE)
        base_lambda = config.NEW_DISEASE_LAMBDA

    # 动态 Lambda：随地图面积/长度线性缩放，保证病害密度合理
    # 以 1000m 为基准单位
    dynamic_lambda = base_lambda * (current_map_size / 1000.0)
    dynamic_lambda = np.clip(dynamic_lambda, 1.0, 50.0) # 保证至少有1个，最多50个
    n_new = np.random.poisson(dynamic_lambda)

    # 3. 生成旧点集 P (历史数据)
    P_raw_coords = apply_error(true_coords, config, seed=1)
    p_mask = np.random.rand(len(P_raw_coords)) < det_rate_p
    P_coords = P_raw_coords[p_mask]
    P_types = true_types[p_mask]
    P_true_idx = np.where(p_mask)[0] # 记录 P 对应的是哪个 GT 点

    # 4. 生成新点集 Q (本次巡检数据)
    Q_raw_coords = apply_error(true_coords, config, seed=2)
    q_mask = np.random.rand(len(Q_raw_coords)) < det_rate_q
    Q_matched_coords = Q_raw_coords[q_mask]
    Q_matched_types = true_types[q_mask]

    # 模拟类型演变：10% 概率类型在两次巡检间发生变化
    Q_matched_types = np.array([
        t if np.random.rand() > 0.1 else np.random.randint(0, config.N_CLASSES)
        for t in Q_matched_types
    ])
    Q_true_idx = np.where(q_mask)[0]

    # 5. 加入真正的新增病害点
    Q_new_coords = sample_spatial_distribution(n_new, current_map_size, "uniform")
    Q_new_types = np.random.randint(0, config.N_CLASSES, n_new)

    Q_coords = np.vstack([Q_matched_coords, Q_new_coords]) if n_new > 0 else Q_matched_coords
    Q_types = np.concatenate([Q_matched_types, Q_new_types]) if n_new > 0 else Q_matched_types

    # 6. 构建标签矩阵 (Nq, Np + 1)
    n_q, n_p = len(Q_coords), len(P_coords)
    labels = np.zeros((n_q, n_p + 1), dtype=np.float32)

    for qi, true_i in enumerate(Q_true_idx):
        matches = np.where(P_true_idx == true_i)[0]
        if len(matches) > 0:
            labels[qi, matches[0]] = 1.0 # 匹配成功
        else:
            labels[qi, -1] = 1.0 # 旧点漏检，新点变新增

    # 填充真正新增点的标签（最后一列）
    for qi in range(len(Q_matched_coords), n_q):
        labels[qi, -1] = 1.0

    # 7. 归一化并拼接类别
    P_norm, Q_norm, _, _ = normalize(P_coords, Q_coords)

    # 最终输出 (N, 3): [x_norm, y_norm, type_idx]
    P_final = np.column_stack([P_norm, P_types])
    Q_final = np.column_stack([Q_norm, Q_types])

    return P_final, Q_final, labels


def normalize(P, Q):
    if len(P) == 0 and len(Q) == 0:
        return P, Q, np.zeros(2), 1.0

    # 1. 安全堆叠
    all_pts = np.vstack([P, Q]) if len(P) > 0 and len(Q) > 0 else (P if len(P) > 0 else Q)

    # 2. 计算质心
    center = (all_pts.min(axis=0) + all_pts.max(axis=0)) / 2.0

    # 3. 动态保底尺度
    # 依然保留你的 500.0 思想，但要防止实际点集跨度远超 1000m 导致坐标过大
    actual_span = np.max(all_pts.max(axis=0) - all_pts.min(axis=0)) / 2.0

    scale = max(actual_span, 500.0)

    P_norm = (P - center) / scale if len(P) > 0 else P
    Q_norm = (Q - center) / scale if len(Q) > 0 else Q

    return P_norm, Q_norm, center, scale


def apply_error(points, config, seed):
    """模拟传感器误差"""
    rng = np.random.RandomState(seed * np.random.randint(1, 9999))
    n = len(points)
    if n == 0: return np.zeros((0, 2))

    # 全局平移偏移
    offset = rng.uniform(-config.GLOBAL_OFFSET_MAX, config.GLOBAL_OFFSET_MAX, 2)

    # 全局旋转偏差
    angle = np.deg2rad(rng.uniform(-config.ROTATION_MAX, config.ROTATION_MAX))
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle),  np.cos(angle)]])

    # 局部噪声（抖动）
    # 随机化噪声强度，增加模型鲁棒性
    current_noise_std = rng.uniform(0.5, config.LOCAL_NOISE_STD)
    noise = rng.normal(0, current_noise_std, (n, 2))

    return (points @ R.T) + offset + noise


def sample_spatial_distribution(n, size, mode):
    """在指定尺度内生成点分布"""
    if n == 0: return np.zeros((0, 2))

    if mode == "uniform":
        return np.random.rand(n, 2) * size
    elif mode == "clustered":
        # 模拟病害成团出现（如坑槽群）
        n_centers = max(1, n // 5)
        centers = np.random.rand(n_centers, 2) * size
        pts = centers[np.random.randint(0, n_centers, n)]
        return pts + np.random.randn(n, 2) * (size * 0.05)
    else: # mixed
        half = n // 2
        return np.vstack([
            sample_spatial_distribution(half, size, "uniform"),
            sample_spatial_distribution(n - half, size, "clustered")
        ])