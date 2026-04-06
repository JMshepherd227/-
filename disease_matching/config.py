class Config:
    # 区域与误差参数（根据你的设备标定）
    MAP_SIZE = 1000.0          # 模拟区域大小（归一化前，米）
    GLOBAL_OFFSET_MAX = 10.0   # 全局偏移最大值（米）
    LOCAL_NOISE_STD = 2.0      # 局部噪声标准差（米）
    ROTATION_MAX = 5.0         # 全局旋转最大角度（度）
    DETECTION_RATE = (0.7, 0.95)# 检测率范围
    NEW_DISEASE_LAMBDA = 10     # 新增病害点泊松参数

    # 点集参数
    N_POINTS_RANGE = (20, 150) # 每个样本的点数范围
    K_NEIGHBORS = 8            # 局部特征的邻居数

    # 模型参数
    FEATURE_DIM = 64
    N_HEADS = 4
    N_LAYERS = 4

    # 训练参数
    BATCH_SIZE = 32
    EPOCHS = 50
    LR = 1e-4
    TRAIN_SAMPLES = 10000
    VAL_SAMPLES = 500