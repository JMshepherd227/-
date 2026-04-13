import json
import math
import time
from typing import List, Tuple, Optional
import torch
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from torchvision import transforms
from torchvision.models import resnet18, ResNet18_Weights
from ultralytics import YOLO
from PIL import Image
import cv2
import io
import os
import datetime
import uuid
import numpy as np

import kornia as K
import kornia.feature as KF

from model import DiseasePointMatcher
import config

app = FastAPI()

# ======================== 1. 模型加载与初始化 ========================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Server starting, using device: {device}")

# 加载 YOLO
model = YOLO("D:/work(work only)/python/UAVRoadDetection/ai-service/model/best.pt")

# 加载 Reid ResNet18
reid_model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)

reid_model = torch.nn.Sequential(*(list(reid_model.children())[:-1]))
reid_model.to(device)
reid_model.eval()

# 加载 GNN 拓扑匹配模型
MATCHER_PATH = "D:/work(work only)/python/UAVRoadDetection/ai-service/model/best_matcher.pt"
try:
    matcher_checkpoint = torch.load(MATCHER_PATH, map_location=device, weights_only=False)
    matcher_config = matcher_checkpoint['config']
    point_matcher = DiseasePointMatcher(matcher_config).to(device)
    point_matcher.load_state_dict(matcher_checkpoint['model_state_dict'])
    point_matcher.eval()
    print("GNN Point Matcher loaded successfully!")
except Exception as e:
    print(f"Warning: Failed to load GNN Point Matcher. Please check the path '{MATCHER_PATH}'. Error: {e}")
    point_matcher = None

# 延迟加载 LoFTR 模型（首次调用接口时自动下载权重）
_loftr_matcher = None

def get_loftr_matcher():
    """懒加载 LoFTR 模型，避免启动时占用过多显存"""
    global _loftr_matcher
    if _loftr_matcher is None:
        print("Loading LoFTR model (outdoor weights)...")
        _loftr_matcher = KF.LoFTR(pretrained='outdoor').to(device)
        _loftr_matcher.eval()
        print("LoFTR model loaded successfully!")
    return _loftr_matcher

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


# ======================== 2. 接口数据结构定义 (Pydantic) ========================
# --- 目标检测接口结构 ---
class DetectionItem(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]
    feature: dict = {}

class PredictResponse(BaseModel):
    filePath: str
    detections: List[DetectionItem]
    detections_num: int
    message: str
    image_width: int
    image_height: int

# --- SIFT / LoFTR 接口共用结构 ---
class HomographyResponse(BaseModel):
    status: str
    message: str
    inliers: int
    processing_time_ms: float
    homography_matrix: Optional[List[List[float]]] = None

# --- GNN 匹配接口结构 ---
class PointReq(BaseModel):
    id: str         # 数据库病害ID
    x: float        # X坐标
    y: float        # Y坐标
    type: int       # 病害类型索引

class MatchRequest(BaseModel):
    old_points: List[PointReq]
    new_points: List[PointReq]

class Candidate(BaseModel):
    rank: int
    matched_old_id: Optional[str]
    confidence: float
    is_new_disease: bool

class MatchResultItem(BaseModel):
    new_id: str
    candidates: List[Candidate]

class MatchResponse(BaseModel):
    status: str
    message: str
    results: List[MatchResultItem]

# ======================== 3. 工具与特征提取函数 ========================
def extract_hu_feature(crop_bgr: np.ndarray) -> List[float]:
    resized = cv2.resize(crop_bgr, (128, 128))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    edges = cv2.Canny(gray, threshold1=50, threshold2=150)
    moments = cv2.moments(edges)
    hu_moments = cv2.HuMoments(moments).flatten()
    hu_moments = -np.sign(hu_moments) * np.log10(np.abs(hu_moments) + 1e-10)
    return hu_moments.tolist()

def extract_lbp_feature(crop_bgr: np.ndarray) -> List[float]:
    from skimage.feature import local_binary_pattern
    resized = cv2.resize(crop_bgr, (128, 128))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    lbp = local_binary_pattern(gray, P=8, R=1, method='uniform')
    hist, _ = np.histogram(lbp.ravel(), bins=59, range=(0, 59), density=True)
    return hist.tolist()

def extract_feature(cv2_img: np.ndarray, bbox: List[float]) -> dict:
    x1, y1, x2, y2 = map(int, bbox)
    crop = cv2_img[max(0, y1):y2, max(0, x1):x2]
    if crop.size == 0:
        return ""
    crop_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    input_tensor = preprocess(crop_pil).unsqueeze(0).to(device)
    with torch.no_grad():
        deep = reid_model(input_tensor).flatten().cpu().numpy().tolist()
    hu  = extract_hu_feature(crop)
    lbp = extract_lbp_feature(crop)
    return {"deep": deep, "hu": hu, "lbp": lbp}

def latlon_to_meters(lat, lon, center_lat, center_lon):
    """将经纬度转换为以 center 为原点的局部平面坐标（单位：米）"""
    R = 6378137.0
    d_lat = math.radians(lat - center_lat)
    d_lon = math.radians(lon - center_lon)
    y = d_lat * R
    x = d_lon * R * math.cos(math.radians(center_lat))
    return x, y

def normalize_coords_fixed(P_coords, Q_coords):
    """
    【同步训练逻辑】：使用 500.0 的固定尺标进行归一化。
    这保证了模型眼中 0.02 的距离永远等于地球上的 10 米。
    """
    if len(P_coords) == 0 and len(Q_coords) == 0:
        return P_coords, Q_coords

    # 合并所有点找到质心
    all_pts = np.vstack([P_coords, Q_coords]) if len(P_coords)>0 and len(Q_coords)>0 else (P_coords if len(P_coords)>0 else Q_coords)
    center = (all_pts.min(axis=0) + all_pts.max(axis=0)) / 2.0

    # 严格使用训练时的固定比例尺 500.0
    fixed_scale = 500.0

    P_norm = (P_coords - center) / fixed_scale if len(P_coords) > 0 else P_coords
    Q_norm = (Q_coords - center) / fixed_scale if len(Q_coords) > 0 else Q_coords
    return P_norm, Q_norm

def sinkhorn(logits, iterations=3):
    """
    Sinkhorn 算法：通过迭代归一化实现全局最优分配（一对一约束）。
    """
    # 转换为概率空间
    P = torch.exp(logits)

    for _ in range(iterations):
        # 行归一化 (每个 Q 选 P 的概率之和为 1)
        P = P / (P.sum(dim=1, keepdim=True) + 1e-8)

        # 列归一化 (每个 P 被选的概率之和为 1，不约束最后一列垃圾桶)
        col_sum = P[:, :-1].sum(dim=0, keepdim=True)
        P[:, :-1] = P[:, :-1] / (col_sum + 1e-8)

    return P


def _decode_to_loftr_tensor(contents: bytes) -> torch.Tensor:
    """
    将上传的图片字节流解码并转为 LoFTR 所需格式：
    灰度图 Tensor，shape (1, 1, H, W)，值域 [0, 1]，分辨率统一为 480x640。
    """
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError("图像解码失败，请确认文件格式正确")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    # 转为 Tensor (B, C, H, W)
    img_tensor = K.image_to_tensor(img_rgb, keepdim=False).float() / 255.0
    img_tensor = img_tensor.to(device)
    # 统一缩放至 640x480（W x H）
    img_tensor = K.geometry.resize(img_tensor, (480, 640))
    # 转为灰度 (1, 1, H, W)
    img_gray = K.color.rgb_to_grayscale(img_tensor)
    return img_gray


# ======================== 4. 路由接口定义 ========================

@app.post("/get_homography/", response_model=HomographyResponse)
async def get_homography(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    start_time = time.time()
    try:
        contents1 = await file1.read()
        contents2 = await file2.read()

        nparr1 = np.frombuffer(contents1, np.uint8)
        nparr2 = np.frombuffer(contents2, np.uint8)

        img1 = cv2.imdecode(nparr1, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imdecode(nparr2, cv2.IMREAD_GRAYSCALE)

        if img1 is None or img2 is None:
            return HomographyResponse(status="error", message="图像解码失败", inliers=0, processing_time_ms=0)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img1, img2 = clahe.apply(img1), clahe.apply(img2)
        sift = cv2.SIFT_create(nfeatures=3000, contrastThreshold=0.04, edgeThreshold=10)

        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)

        if des1 is None or des2 is None or len(des1) < 20 or len(des2) < 20:
            return HomographyResponse(status="failed", message="纹理过弱", inliers=0, processing_time_ms=0)
        bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
        matches = sorted(bf.match(des1, des2), key=lambda x: x.distance)
        good_matches = matches[:100]
        if len(good_matches) < 15:
            return HomographyResponse(status="failed", message="有效匹配点过少", inliers=0, processing_time_ms=0)

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 4.0)
        cost_ms = round((time.time() - start_time) * 1000, 2)

        if H is not None:
            return HomographyResponse(status="success", message="匹配成功", inliers=int(np.sum(mask)), processing_time_ms=cost_ms, homography_matrix=H.tolist())
        else:
            return HomographyResponse(status="failed", message="矩阵计算失败", inliers=0, processing_time_ms=cost_ms)
    except Exception as e:
        return HomographyResponse(status="error", message=str(e), inliers=0, processing_time_ms=0)


@app.post("/get_homography_loftr/", response_model=HomographyResponse)
async def get_homography_loftr(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    """
    基于 LoFTR 的图像匹配接口。

    与 /get_homography/ 参数及返回结构完全一致，算法替换为
    Transformer 特征匹配 + USAC_MAGSAC 几何校验，适合无显著角点、
    纹理重复或光照变化较大的路面图像场景。

    Args:
        file1: 参考帧图片（第一次巡检）
        file2: 待匹配图片（第二次巡检）

    Returns:
        HomographyResponse:
            - status:             "success" | "failed" | "error"
            - message:            人类可读状态说明
            - inliers:            MAGSAC 几何校验后的内点数
            - processing_time_ms: 端到端耗时（毫秒）
            - homography_matrix:  3x3 单应矩阵（列表形式），失败时为 null
    """
    start_time = time.time()
    try:
        contents1 = await file1.read()
        contents2 = await file2.read()

        # ---------- 图像预处理 ----------
        try:
            img1_gray = _decode_to_loftr_tensor(contents1)
            img2_gray = _decode_to_loftr_tensor(contents2)
        except ValueError as ve:
            return HomographyResponse(
                status="error", message=str(ve),
                inliers=0, processing_time_ms=0
            )

        # ---------- LoFTR 特征匹配 ----------
        matcher = get_loftr_matcher()
        input_dict = {"image0": img1_gray, "image1": img2_gray}
        with torch.inference_mode():
            correspondences = matcher(input_dict)

        mkpts1 = correspondences['keypoints0'].cpu().numpy()  # (N, 2)
        mkpts2 = correspondences['keypoints1'].cpu().numpy()  # (N, 2)

        total_matches = len(mkpts1)
        if total_matches < 10:
            cost_ms = round((time.time() - start_time) * 1000, 2)
            return HomographyResponse(
                status="failed",
                message=f"有效匹配点过少（仅 {total_matches} 个），请检查图像质量",
                inliers=0,
                processing_time_ms=cost_ms
            )

        # ---------- USAC_MAGSAC 几何校验 ----------
        H_mat, mask = cv2.findHomography(mkpts1, mkpts2, cv2.USAC_MAGSAC, 3.0)
        cost_ms = round((time.time() - start_time) * 1000, 2)

        if H_mat is None:
            return HomographyResponse(
                status="failed",
                message="单应矩阵计算失败，匹配点可能退化",
                inliers=0,
                processing_time_ms=cost_ms
            )

        inlier_count = int(mask.ravel().sum()) if mask is not None else total_matches
        print(f"[LoFTR] 初始匹配: {total_matches}  几何过滤后内点: {inlier_count}  耗时: {cost_ms}ms")

        return HomographyResponse(
            status="success",
            message="匹配成功",
            inliers=inlier_count,
            processing_time_ms=cost_ms,
            homography_matrix=H_mat.tolist()
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        cost_ms = round((time.time() - start_time) * 1000, 2)
        return HomographyResponse(
            status="error",
            message=str(e),
            inliers=0,
            processing_time_ms=cost_ms
        )


@app.post("/predict/")
async def predict(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        width, height = image.size
        results = model.predict(source=image, save=False, conf=0.25)
        r = results[0]
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        dir_name = "D:/work(work only)/python/UAVRoadDetection/result"
        save_dir = os.path.join(dir_name, today)
        os.makedirs(save_dir, exist_ok=True)
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{unique_id}.jpg"
        full_save_path = os.path.join(save_dir, filename)

        detections = []
        detections_num = len(r.boxes)
        if detections_num > 0:
            result_img = r.plot()
            cv2.imwrite(full_save_path, result_img)
            boxes_data = r.boxes.xyxy.cpu().numpy()
            class_ids = r.boxes.cls.cpu().numpy().astype(int)
            confidences = r.boxes.conf.cpu().numpy()
            for i in range(detections_num):
                current_bbox = [float(val) for val in boxes_data[i]]
                detections.append(DetectionItem(class_id=int(class_ids[i]), class_name=r.names[int(class_ids[i])], confidence=float(confidences[i]), bbox=current_bbox))
        else:
            cv2.imwrite(full_save_path, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))

        relative_path = f"{dir_name}/{today}/{filename}"
        return PredictResponse(filePath=relative_path, detections=detections, detections_num=detections_num, message="Success", image_width=width, image_height=height)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ---------------- GNN 病害时空匹配接口 ----------------
@app.post("/match_points/", response_model=MatchResponse)
async def match_points(req: MatchRequest):
    if point_matcher is None:
        return MatchResponse(status="error", message="Matcher model is not loaded.", results=[])

    try:
        # 1. 拦截空数据
        if len(req.new_points) == 0:
            return MatchResponse(status="success", message="No new points to match.", results=[])

        if len(req.old_points) == 0:
            results = [MatchResultItem(new_id=q.id, candidates=[Candidate(rank=1, matched_old_id=None, confidence=1.0, is_new_disease=True)]) for q in req.new_points]
            return MatchResponse(status="success", message="All new (no history).", results=results)

        # 2. 安全拦截：防止 type 越界（配合模型层的 clamp 使用）
        max_class_idx = matcher_config.N_CLASSES - 1
        for p in req.old_points: p.type = max(0, min(p.type, max_class_idx))
        for q in req.new_points: q.type = max(0, min(q.type, max_class_idx))

        # 3. 统一坐标基准（锚定原点）
        # 使用新旧点集整体的第一个点作为经纬度转平面的参考原点
        ref_lon = req.old_points[0].x
        ref_lat = req.old_points[0].y

        P_ids = [p.id for p in req.old_points]
        Q_ids = [q.id for q in req.new_points]

        # 4. 经纬度转米级平面坐标
        P_m = np.array([latlon_to_meters(p.y, p.x, ref_lat, ref_lon) for p in req.old_points], dtype=np.float32)
        Q_m = np.array([latlon_to_meters(q.y, q.x, ref_lat, ref_lon) for q in req.new_points], dtype=np.float32)

        # 5. 【同步训练逻辑】：固定 500m 尺度归一化
        P_norm_c, Q_norm_c = normalize_coords_fixed(P_m, Q_m)

        # 拼接类型特征 [x, y, type]
        P_types = np.array([[p.type] for p in req.old_points], dtype=np.float32)
        Q_types = np.array([[q.type] for q in req.new_points], dtype=np.float32)
        P_final = np.hstack([P_norm_c, P_types])
        Q_final = np.hstack([Q_norm_c, Q_types])

        # 6. 推理与 Sinkhorn 优化
        P_t = torch.tensor(P_final).unsqueeze(0).to(device)
        Q_t = torch.tensor(Q_final).unsqueeze(0).to(device)

        with torch.no_grad():
            # 这里的 logits 内部已经包含了温度系数和 clamp 处理
            logits = point_matcher(P_t, Q_t).squeeze(0)

            # 使用 Sinkhorn 代替 Softmax，解决“抢亲”问题
            probs = sinkhorn(logits, iterations=3).cpu().numpy()

        # 7. 生成结果
        results = []
        n_p = len(P_ids)
        TOP_K = min(3, n_p + 1)

        for qi, q_id in enumerate(Q_ids):
            # 按概率降序排列
            sorted_indices = np.argsort(probs[qi])[::-1]
            top_k_indices = sorted_indices[:TOP_K]

            candidates = []
            for rank, idx in enumerate(top_k_indices):
                conf = float(probs[qi, idx])
                is_new = (idx == n_p)

                # 【策略干预】：如果最高置信度都低于 0.3，我们更倾向于认为它是新增
                # 这一行可以根据你训练后的表现决定是否开启
                # if rank == 0 and not is_new and conf < 0.3: is_new = True

                candidates.append(Candidate(
                    rank=rank + 1,
                    matched_old_id=None if is_new else P_ids[idx],
                    confidence=conf,
                    is_new_disease=is_new
                ))

            results.append(MatchResultItem(new_id=q_id, candidates=candidates))

        return MatchResponse(status="success", message="Match completed.", results=results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return MatchResponse(status="error", message=str(e), results=[])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)