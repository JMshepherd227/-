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

model = YOLO("D:/work(work only)/python/UAVRoadDetection/ai-service/best.pt")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
reid_model = models.resnet18(pretrained=True)
reid_model = torch.nn.Sequential(*(list(reid_model.children())[:-1])) # 移除最后的全连接层
reid_model.to(device)
reid_model.eval()

# 图片预处理逻辑（缩放到模型需要的大小）
preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

class DetectionItem(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]
    feature: List[float] = []

class PredictResponse(BaseModel):
    filePath: str
    detections: List[DetectionItem]
    detections_num: int
    message: str
    image_width:int
    image_height:int

def extract_feature(cv2_img, bbox):
    """
    根据坐标抠图并提取特征向量
    """
    x1, y1, x2, y2 = map(int, bbox)
    # 抠图
    crop = cv2_img[max(0, y1):y2, max(0, x1):x2]
    if crop.size == 0:
        return []

    # 转换格式并进行推理
    crop_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    input_tensor = preprocess(crop_pil).unsqueeze(0).to(device)

    with torch.no_grad():
        feature = reid_model(input_tensor)

    # 压平并转为 Python list
    return feature.flatten().cpu().numpy().tolist()

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

        relative_path = f"{dir_name}/{today}/{filename}"
        return PredictResponse(
            filePath=relative_path,
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