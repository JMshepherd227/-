import numpy as np

def generate_pair(config):
    """
    业务级场景化数据生成器
    覆盖：纯净、日常、极限偏移、极限密集、孤立海量新增、混淆海量新增
    """
    # 1. 场景轮盘赌 (Roulette Selection)
    rand_val = np.random.rand()
    if rand_val < 0.10:   scenario = "CLEAN"                 # 10% 纯净
    elif rand_val < 0.40: scenario = "NORMAL"                # 30% 日常
    elif rand_val < 0.55: scenario = "DRIFT_15M"             # 15% 极限偏移
    elif rand_val < 0.70: scenario = "DENSE_05M"             # 15% 极限密集
    elif rand_val < 0.85: scenario = "MASSIVE_NEW_ISOLATED"  # 15% 孤立海量新增
    else:                 scenario = "MASSIVE_NEW_MIXED"     # 15% 混淆海量新增

    # 2. 基础参数初始化
    current_map_size = np.random.uniform(*config.MAP_SIZE_RANGE)
    n = np.random.randint(*config.N_POINTS_RANGE)

    det_rate_p, det_rate_q = config.DETECTION_RATE
    rel_offset_x, rel_offset_y = 0.0, 0.0
    local_noise_std = config.LOCAL_NOISE_STD
    n_new = 0
    type_change_prob = 0.05
    mode = "mixed"

    # --- 3. 场景化参数定制 (核心逻辑) ---
    if scenario == "CLEAN":
        det_rate_p, det_rate_q = 1.0, 1.0
        local_noise_std = 0.0
        type_change_prob = 0.0

    elif scenario == "NORMAL":
        rel_offset_x = np.random.uniform(-4, 4)
        rel_offset_y = np.random.uniform(-4, 4)
        n_new = np.random.poisson(config.NEW_DISEASE_LAMBDA)

    elif scenario == "DRIFT_15M":
        # 强制制造 10m ~ 15m 的极大偏移
        sign_x = np.random.choice([-1, 1])
        sign_y = np.random.choice([-1, 1])
        rel_offset_x = sign_x * np.random.uniform(10, 15)
        rel_offset_y = sign_y * np.random.uniform(10, 15)
        n_new = np.random.poisson(config.NEW_DISEASE_LAMBDA)

    elif scenario == "DENSE_05M":
        # 将地图强行缩小到 20~40 米，但点数依然保持 50~140 个，制造 < 0.5m 的间距
        current_map_size = np.random.uniform(20.0, 40.0)
        local_noise_std = 0.2  # 局部噪声必须变小，否则点全乱套了
        rel_offset_x = np.random.uniform(-2, 2)
        rel_offset_y = np.random.uniform(-2, 2)
        mode = "clustered" # 强制成团

    elif scenario == "MASSIVE_NEW_ISOLATED":
        rel_offset_x = np.random.uniform(-3, 3)
        rel_offset_y = np.random.uniform(-3, 3)
        n_new = np.random.randint(40, 80) # 强行生成几十个新增点

    elif scenario == "MASSIVE_NEW_MIXED":
        rel_offset_x = np.random.uniform(-3, 3)
        rel_offset_y = np.random.uniform(-3, 3)
        n_new = np.random.randint(40, 80)

    # 4. 生成基础坐标与类型 (Ground Truth)
    true_coords = sample_spatial_distribution(n, current_map_size, mode)
    true_types = np.random.randint(0, config.N_CLASSES, n)

    # 5. 生成旧点集 P
    P_coords = true_coords + np.random.normal(0, 0.1, (n, 2))
    p_mask = np.random.rand(n) < det_rate_p
    P_final_coords = P_coords[p_mask]
    P_final_types = true_types[p_mask]
    P_true_idx = np.where(p_mask)[0]

    # 6. 生成新点集 Q (加入偏移与局部噪声)
    angle = np.deg2rad(np.random.uniform(-config.ROTATION_MAX, config.ROTATION_MAX) if scenario != "CLEAN" else 0)
    R = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])

    Q_coords = (true_coords @ R.T) + np.array([rel_offset_x, rel_offset_y])
    Q_coords += np.random.normal(0, local_noise_std, (n, 2))

    q_mask = np.random.rand(n) < det_rate_q
    Q_matched_coords = Q_coords[q_mask]

    Q_matched_types = np.array([
        t if np.random.rand() > type_change_prob else np.random.randint(0, config.N_CLASSES)
        for t in true_types[q_mask]
    ])
    Q_true_idx = np.where(q_mask)[0]

    # 7. 生成定制化的新增病害
    if n_new > 0:
        if scenario == "MASSIVE_NEW_ISOLATED":
            # 孤立生成：给新增点加上一个极大的平移（例如地图尺寸的 1.5 倍），确保不与老点重合
            shift_vector = np.array([current_map_size * 1.5, current_map_size * 1.5])
            Q_new_coords = sample_spatial_distribution(n_new, current_map_size, "clustered") + shift_vector
        elif scenario == "MASSIVE_NEW_MIXED":
            # 混淆生成：直接在老点 (Q_matched_coords) 附近加微小噪声生成，实现完美混合
            base_idx = np.random.randint(0, len(Q_matched_coords), n_new) if len(Q_matched_coords) > 0 else np.zeros(n_new, dtype=int)
            Q_new_coords = Q_matched_coords[base_idx] + np.random.normal(0, 2.0, (n_new, 2))
        else:
            # 常规生成：全图随机散布
            Q_new_coords = sample_spatial_distribution(n_new, current_map_size, "uniform")

        Q_new_types = np.random.randint(0, config.N_CLASSES, n_new)
        Q_final_coords = np.vstack([Q_matched_coords, Q_new_coords])
        Q_final_types = np.concatenate([Q_matched_types, Q_new_types])
    else:
        Q_final_coords = Q_matched_coords
        Q_final_types = Q_matched_types

    # 8. 构建标签矩阵
    n_q, n_p = len(Q_final_coords), len(P_final_coords)
    labels = np.zeros((n_q, n_p + 1), dtype=np.float32)

    for qi, true_i in enumerate(Q_true_idx):
        matches = np.where(P_true_idx == true_i)[0]
        if len(matches) > 0:
            labels[qi, matches[0]] = 1.0
        else:
            labels[qi, -1] = 1.0

    for qi in range(len(Q_matched_coords), n_q):
        labels[qi, -1] = 1.0

    # 9. 归一化 (使用固定的 500.0)
    P_norm, Q_norm, _, _ = normalize(P_final_coords, Q_final_coords)

    return np.column_stack([P_norm, P_final_types]), \
        np.column_stack([Q_norm, Q_final_types]), \
        labels

def sample_spatial_distribution(n, size, mode):
    if n == 0: return np.zeros((0, 2))
    if mode == "uniform":
        return np.random.rand(n, 2) * size
    elif mode == "clustered":
        n_centers = max(1, n // 5)
        centers = np.random.rand(n_centers, 2) * size
        pts = centers[np.random.randint(0, n_centers, n)]
        return pts + np.random.randn(n, 2) * (size * 0.05)
    else: # mixed
        part = n // 2
        return np.vstack([
            sample_spatial_distribution(part, size, "uniform"),
            sample_spatial_distribution(n - part, size, "clustered")
        ])

def normalize(P, Q):
    if len(P) == 0 and len(Q) == 0:
        return P, Q, np.zeros(2), 1.0
    all_pts = np.vstack([P, Q]) if len(P) > 0 and len(Q) > 0 else (P if len(P) > 0 else Q)
    center = (all_pts.min(axis=0) + all_pts.max(axis=0)) / 2.0
    fixed_scale = 500.0
    return (P - center) / fixed_scale, (Q - center) / fixed_scale, center, fixed_scale