import json
from typing import List
import torch
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from torchvision import models, transforms
from ultralytics import YOLO
from PIL import Image
import cv2
import io
import os
import datetime
import uuid
import numpy as np

app = FastAPI()

# 使用相对路径加载模型，确保在不同环境下都能运行
model_path = os.path.join(os.path.dirname(__file__), "best.pt")
model = YOLO(model_path) 

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
reid_model = models.resnet18(pretrained=True)
reid_model = torch.nn.Sequential(*(list(reid_model.children())[:-1]))
reid_model.to(device)
reid_model.eval()

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def extract_hu_feature(crop_bgr: np.ndarray) -> List[float]:
    """
    提取结构特征：Hu 矩
    输入：BGR 格式的裁剪图像
    输出：拼接后的结构特征向量
    """
    # --- 预处理：统一缩放，避免尺寸影响特征 ---
    resized = cv2.resize(crop_bgr, (128, 128))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # --- Canny 边缘检测 ---
    gray = cv2.equalizeHist(gray)
    edges = cv2.Canny(gray, threshold1=50, threshold2=150)

    # --- Hu 矩（7维，对旋转/缩放/平移不变）---
    moments = cv2.moments(edges)
    hu_moments = cv2.HuMoments(moments).flatten()
    # log 变换压缩数值范围，避免数量级差异过大
    hu_moments = -np.sign(hu_moments) * np.log10(np.abs(hu_moments) + 1e-10)
    hu_moments = hu_moments.tolist()

    return hu_moments


def extract_lbp_feature(crop_bgr: np.ndarray) -> List[float]:
    """
    提取 LBP 纹理特征
    使用 uniform LBP，59 维，对光照变化鲁棒
    """
    from skimage.feature import local_binary_pattern

    resized = cv2.resize(crop_bgr, (128, 128))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # 直方图均衡化（消除光照影响）
    gray = cv2.equalizeHist(gray)

    # uniform LBP：P=8邻域，R=1半径
    # uniform 模式将编码归并为 59 类，降低噪声敏感性
    lbp = local_binary_pattern(gray, P=8, R=1, method='uniform')

    # 统计直方图（归一化）
    hist, _ = np.histogram(lbp.ravel(), bins=59, range=(0, 59), density=True)

    return hist.tolist()  # 59 维

def extract_feature(cv2_img: np.ndarray, bbox: List[float]) -> dict:
    x1, y1, x2, y2 = map(int, bbox)
    crop = cv2_img[max(0, y1):y2, max(0, x1):x2]
    if crop.size == 0:
        return ""

    # 深度特征
    crop_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    input_tensor = preprocess(crop_pil).unsqueeze(0).to(device)
    with torch.no_grad():
        deep = reid_model(input_tensor).flatten().cpu().numpy().tolist()

    # 结构特征
    hu  = extract_hu_feature(crop)
    lbp = extract_lbp_feature(crop)

    return {
        "deep": deep,   # 512维
        "hu":   hu,     # 7维
        "lbp":  lbp     # 59维
    }

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
    image_width:int
    image_height:int

@app.post("/predict/")
async def predict(
        file: UploadFile = File(...),
):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        width, height = image.size

        results = model.predict(source=image, save=False, conf=0.25)
        r = results[0]

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        # 使用相对于项目根目录的路径
        base_dir = os.path.dirname(os.path.dirname(__file__))
        save_dir = os.path.join(base_dir, "result", today)
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

            raw_img_cv2 = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            for i in range(detections_num):
                current_bbox = [float(val) for val in boxes_data[i]]

                feature_vec = extract_feature(raw_img_cv2, current_bbox)

                detections.append(
                    DetectionItem(
                        class_id=int(class_ids[i]),
                        class_name=r.names[int(class_ids[i])],
                        confidence=float(confidences[i]),
                        bbox=current_bbox,
                        feature=feature_vec
                    )
                )
        else:
            cv2.imwrite(full_save_path, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))

        # 返回绝对路径，后端会通过 PathUtil 提取相对路径
        return PredictResponse(
            filePath=full_save_path.replace("\\", "/"),
            detections=detections,
            detections_num=detections_num,
            message="Success",
            image_width=width,
            image_height=height
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)