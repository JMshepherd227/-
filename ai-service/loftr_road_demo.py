import cv2
import torch
import kornia as K
import kornia.feature as KF
import numpy as np
import matplotlib.pyplot as plt

def load_image_opencv(path, device):
    """使用 OpenCV 加载图片并转为 Tensor"""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"无法读取图片，请检查路径: {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # 转换为 Tensor (B, C, H, W)，并归一化到 [0, 1]
    img_tensor = K.image_to_tensor(img, keepdim=False).float() / 255.0
    return img_tensor.to(device)

def simulate_second_inspection(img_tensor):
    """
    适配新版 Kornia 的模拟巡检函数
    """
    B, C, H, W = img_tensor.shape
    device = img_tensor.device

    # 1. 构造中心点 (B, 2)
    center = torch.tensor([[W / 2.0, H / 2.0]], device=device)

    # 2. 构造旋转角度 (B) -> 旋转 2 度
    angle = torch.tensor([2.0], device=device)

    # 3. 构造缩放比例 (B, 2) -> X和Y方向均缩放 0.95
    # 注意：新版 Kornia 要求这里是 (B, 2)
    scale = torch.tensor([[0.95, 0.95]], device=device)

    # 得到仿射变换矩阵
    M = K.geometry.get_rotation_matrix2d(center, angle, scale)

    # 4. 添加微小平移 (dx=15, dy=10)
    M[:, 0, 2] += 15.0
    M[:, 1, 2] += 10.0

    # 执行变换
    img_warped = K.geometry.warp_affine(img_tensor, M, dsize=(H, W))

    # 5. 模拟光照变化 (调暗并增加一点随机增益)
    img_warped = img_warped * 0.8

    return torch.clamp(img_warped, 0, 1), M[0]

def run_loftr_verification(img_path1, img_path2=None):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"实际使用设备: {device}")

    # 1. 加载图片
    try:
        img1_raw = load_image_opencv(img_path1, device)
        # 统一缩放到 640x480
        img1_raw = K.geometry.resize(img1_raw, (480, 640))
        img1_gray = K.color.rgb_to_grayscale(img1_raw)
    except Exception as e:
        print(f"加载出错: {e}")
        return

    if img_path2 is None:
        print("未提供对比图，进入模拟模式...")
        img2_raw, _ = simulate_second_inspection(img1_raw)
        img2_gray = K.color.rgb_to_grayscale(img2_raw)
    else:
        img2_raw = load_image_opencv(img_path2, device)
        img2_raw = K.geometry.resize(img2_raw, (480, 640))
        img2_gray = K.color.rgb_to_grayscale(img2_raw)

    # 2. 初始化 LoFTR
    # 第一次运行会自动下载权重，请保持网络通畅
    matcher = KF.LoFTR(pretrained='outdoor').to(device)

    # 3. 推理
    input_dict = {"image0": img1_gray, "image1": img2_gray}
    with torch.inference_mode():
        correspondences = matcher(input_dict)

    mkpts1 = correspondences['keypoints0'].cpu().numpy()
    mkpts2 = correspondences['keypoints1'].cpu().numpy()

    # 4. 几何校验 (RANSAC / MAGSAC)
    if len(mkpts1) > 10:
        # 使用 USAC_MAGSAC 过滤误匹配，它是目前 OpenCV 中最稳健的 RANSAC 变体
        H_mat, mask = cv2.findHomography(mkpts1, mkpts2, cv2.USAC_MAGSAC, 3.0)
        if mask is not None:
            mask = mask.ravel() == 1
            inliers1 = mkpts1[mask]
            inliers2 = mkpts2[mask]
        else:
            inliers1, inliers2 = mkpts1, mkpts2
    else:
        inliers1, inliers2 = mkpts1, mkpts2

    print(f"初始匹配点: {len(mkpts1)}, 几何过滤后: {len(inliers1)}")

    # 5. 可视化
    img1_np = K.utils.tensor_to_image(img1_raw[0].cpu())
    img2_np = K.utils.tensor_to_image(img2_raw[0].cpu())
    canvas = np.hstack((img1_np, img2_np))

    plt.figure(figsize=(20, 10))
    plt.imshow(canvas)

    # 【核心改动】：随机打乱索引，确保能看到全图的匹配分布
    indices = np.arange(len(inliers1))
    np.random.shuffle(indices)  # 随机打乱
    num_draw = min(200, len(inliers1)) # 可以多画一点，比如200个

    for i in range(num_draw):
        idx = indices[i] # 使用随机索引
        p1 = inliers1[idx]
        p2 = inliers2[idx] + [640, 0]
        plt.plot([p1[0], p2[0]], [p1[1], p2[1]], color='lime', linewidth=0.8, alpha=0.5)
        plt.scatter(p1[0], p1[1], color='blue', s=1)

    plt.axis('off')
    plt.title(f"LoFTR Robustness Test\nTotal Inliers: {len(inliers1)}")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # 替换为你实际的图片路径
    IMAGE_PATH = r"D:\work(work only)\python\UAVRoadDetection\ai-service\photo\test_new.jpg"
    PATH = r"D:\work(work only)\python\UAVRoadDetection\ai-service\photo\test_newnew.jpg"
    run_loftr_verification(IMAGE_PATH, PATH)