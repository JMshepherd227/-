import requests
import time
import math
import json

# ================= 配置区 =================
BACKEND_URL = "http://localhost:8080"
TASK_ID = 10      # 假设我们在执行 ID 为 10 的任务
DRONE_ID = 0      # 无人机编号 M300-01
TELEMETRY_INTERVAL = 0.1  # 遥测发送间隔 (100ms)
IMAGE_INTERVAL = 2.0      # 图片发送间隔 (2s)

# 假设前端画了一条线，包含两个真实坐标点 (这里以一段常见的街道坐标为例)
# 起点
START_POINT = {"lng": 116.397428, "lat": 39.909230}
# 终点
END_POINT = {"lng": 116.407428, "lat": 39.909230}

# 预计飞行总时间 (秒)
FLIGHT_DURATION = 20.0
# ==========================================

def calculate_heading(lng1, lat1, lng2, lat2):
    """
    计算从点1到点2的机头朝向角 (0度为正北，顺时针为正，适配高德地图)
    """
    dx = lng2 - lng1
    dy = lat2 - lat1
    # math.atan2 算出来是弧度，转成角度
    angle = math.degrees(math.atan2(dy, dx))
    # 转换为高德地图的 heading 体系 (正北为0，正东为90)
    heading = (90 - angle) % 360
    return heading

def generate_flight_path(start, end, duration, interval):
    """
    根据起点、终点和飞行时间，插值生成密集的 100ms 飞行轨迹序列
    """
    steps = int(duration / interval)
    path = []

    lng_step = (end["lng"] - start["lng"]) / steps
    lat_step = (end["lat"] - start["lat"]) / steps

    heading = calculate_heading(start["lng"], start["lat"], end["lng"], end["lat"])

    for i in range(steps + 1):
        current_lng = start["lng"] + (lng_step * i)
        current_lat = start["lat"] + (lat_step * i)
        path.append({
            "lng": round(current_lng, 6),
            "lat": round(current_lat, 6),
            "heading": round(heading, 2)
        })
    return path

def run_simulation():
    print(f"🚀 [无人机 {DRONE_ID}] 启动引擎，开始执行任务 #{TASK_ID}...")

    # 1. 生成平滑的飞行轨迹
    flight_path = generate_flight_path(START_POINT, END_POINT, FLIGHT_DURATION, TELEMETRY_INTERVAL)
    print(f"🗺️ 航线已生成，共计 {len(flight_path)} 个插值航点。预计飞行时间 {FLIGHT_DURATION} 秒。")

    # 2. 模拟飞行循环
    tick = 0
    for point in flight_path:
        # 准备要发送的数据体
        payload = {
            "taskId": TASK_ID,
            "droneId": DRONE_ID,
            "lng": point["lng"],
            "lat": point["lat"],
            "heading": point["heading"]
        }

        try:
            # 动作 A: 发送高频遥测数据 (100ms/次)
            response = requests.post(
                f"{BACKEND_URL}/api/v1/drones/telemetry",
                json=payload,
                timeout=1 # 防止请求卡死阻塞循环
            )

            if tick % int(IMAGE_INTERVAL / TELEMETRY_INTERVAL) == 0:
                print(f"📸[无人机 {DRONE_ID}] 咔嚓！在坐标 ({point['lng']}, {point['lat']}) 拍了一张照片，正在上传...")

                # 构造文件和参数发送给 SpringBoot 的 /upload 接口
                files = {'file': ('test.jpg', open('test.jpg', 'rb'), 'image/jpeg')}
                data = {
                    "taskId": TASK_ID,
                    "droneId": DRONE_ID,
                    "lng": point["lng"],
                    "lat": point["lat"]
                }

                upload_res = requests.post(f"{BACKEND_URL}/api/v1/drones/upload", data=data, files=files)
                print(f"☁️ 上传结果: {upload_res.text}")

        except Exception as e:
            print(f"⚠️ 网络请求异常: {e}")

        tick += 1
        time.sleep(TELEMETRY_INTERVAL) # 严格等待 100ms

    print(f"🛬 [无人机 {DRONE_ID}] 抵达终点，航线飞行完毕！")

    # 3. 呼叫后端，任务完成！
    try:
        finish_res = requests.put(f"{BACKEND_URL}/api/v1/tasks/{DRONE_ID}/finish")
        print(f"✅ 任务结束信号已发送: {finish_res.text}")
    except Exception as e:
        print(f"⚠️ 结束任务请求异常: {e}")

if __name__ == "__main__":
    run_simulation()