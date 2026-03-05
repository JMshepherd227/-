from typing import List
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from ultralytics import YOLO
from PIL import Image
import cv2
import io
import os
import datetime
import uuid

app = FastAPI()

model = YOLO("D:/work(work only)/python/UAVRoadDetection/ai-service/best.pt")

class DetectionItem(BaseModel):
    class_id: int
    class_name: str
    confidence: float

class PredictResponse(BaseModel):
    filePath: str
    detections: List[DetectionItem]
    detections_num: int
    message: str

@app.post("/predict/")
async def predict(
        file: UploadFile = File(...),
):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

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
        print(detections_num)

        if len(results) > 0:
            result_img = r.plot()
            cv2.imwrite(full_save_path, result_img)
            class_ids = r.boxes.cls.cpu().numpy().astype(int)
            confidences = r.boxes.conf.cpu().numpy()
            for cid, conf in zip(class_ids, confidences):
                detections.append(
                    DetectionItem(
                        class_id=int(cid),
                        class_name=r.names[int(cid)],
                        confidence=float(conf),
                    )
                )
        else:
            import numpy as np
            cv2.imwrite(full_save_path, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))

        relative_path = f"{dir_name}/{today}/{filename}"

        return PredictResponse(
            filePath=relative_path,
            detections=detections,
            detections_num=detections_num,
            message="Success"
        )

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)