import json
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

# --- SIFT 接口结构 ---
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

def normalize_coords(P_coords, Q_coords):
    """GNN 全局安全归一化"""
    if len(P_coords) == 0 and len(Q_coords) == 0:
        return P_coords, Q_coords
    all_pts = np.vstack([P_coords, Q_coords]) if len(P_coords)>0 and len(Q_coords)>0 else (P_coords if len(P_coords)>0 else Q_coords)
    min_pt, max_pt = all_pts.min(axis=0), all_pts.max(axis=0)
    center = (min_pt + max_pt) / 2.0
    scale = np.max(max_pt - min_pt) / 2.0 + 1e-6
    P_norm = (P_coords - center) / scale if len(P_coords) > 0 else P_coords
    Q_norm = (Q_coords - center) / scale if len(Q_coords) > 0 else Q_coords
    return P_norm, Q_norm


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
            # 没有旧病害，全员新增
            results = []
            for q in req.new_points:
                cand = Candidate(rank=1, matched_old_id=None, confidence=1.0, is_new_disease=True)
                results.append(MatchResultItem(new_id=q.id, candidates=[cand]))
            return MatchResponse(status="success", message="All considered new (no old points).", results=results)

        # 2. 提取数据
        P_ids = [p.id for p in req.old_points]
        Q_ids = [q.id for q in req.new_points]

        P_coords = np.array([[p.x, p.y] for p in req.old_points], dtype=np.float32)
        Q_coords = np.array([[q.x, q.y] for q in req.new_points], dtype=np.float32)
        P_types = np.array([[p.type] for p in req.old_points], dtype=np.float32)
        Q_types = np.array([[q.type] for q in req.new_points], dtype=np.float32)

        # 3. 归一化并拼接特征 [x_norm, y_norm, type_idx]
        P_norm_c, Q_norm_c = normalize_coords(P_coords, Q_coords)
        P_final = np.hstack([P_norm_c, P_types])
        Q_final = np.hstack([Q_norm_c, Q_types])

        # 4. 转 Tensor 并推入模型
        P_t = torch.tensor(P_final).unsqueeze(0).to(device)
        Q_t = torch.tensor(Q_final).unsqueeze(0).to(device)

        with torch.no_grad():
            logits = point_matcher(P_t, Q_t).squeeze(0)  # (Nq, Np+1)
            probs = torch.softmax(logits, dim=-1).cpu().numpy()

        # 5. 生成 Top-K 候补名单
        results = []
        n_p = len(P_ids)
        TOP_K = min(3, n_p + 1)  # 返回前 3 个最可能的匹配

        for qi, q_id in enumerate(Q_ids):
            sorted_indices = np.argsort(probs[qi])[::-1]
            top_k_indices = sorted_indices[:TOP_K]

            candidates = []
            for rank, idx in enumerate(top_k_indices):
                conf = float(probs[qi, idx])
                is_new = (idx == n_p)
                old_id = None if is_new else P_ids[idx]

                candidates.append(Candidate(
                    rank=rank + 1,
                    matched_old_id=old_id,
                    confidence=conf,
                    is_new_disease=is_new
                ))

            results.append(MatchResultItem(
                new_id=q_id,
                candidates=candidates
            ))

        return MatchResponse(status="success", message="Match completed.", results=results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return MatchResponse(status="error", message=str(e), results=[])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)