import requests
import time
import math
import json
import argparse
import websocket
import threading
import os

# ================= 配置区 =================
BACKEND_HTTP_URL = "http://localhost:8080"
BACKEND_WS_URL = "ws://localhost:8080/ws/telemetry"

TELEMETRY_INTERVAL = 0.1  # 遥测发送间隔 (100ms)
IMAGE_INTERVAL = 2.0      # 拍照上传间隔 (2秒)
FLIGHT_SPEED = 5.0        # 飞行速度 (5 m/s)

# 无人机缺省物理参数
DEFAULT_ALTITUDE = 4.0
DEFAULT_PITCH = -90.0
DEFAULT_ROLL = 0.0
DEFAULT_FOV = 80.0

DRONE_ID = None
is_flying = False
# ==========================================


def calculate_distance(lng1, lat1, lng2, lat2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_heading(lng1, lat1, lng2, lat2):
    angle = math.degrees(math.atan2(lat2 - lat1, lng2 - lng1))
    return (90 - angle) % 360


def generate_flight_path(waypoints, speed):
    path = []
    for i in range(len(waypoints) - 1):
        p1, p2 = waypoints[i], waypoints[i+1]
        dist = calculate_distance(p1["lng"], p1["lat"], p2["lng"], p2["lat"])
        duration = dist / speed
        steps = int(duration / TELEMETRY_INTERVAL)
        heading = calculate_heading(p1["lng"], p1["lat"], p2["lng"], p2["lat"])

        if steps == 0:
            continue

        lng_step = (p2["lng"] - p1["lng"]) / steps
        lat_step = (p2["lat"] - p1["lat"]) / steps

        for j in range(steps):
            path.append({
                "lng": round(p1["lng"] + lng_step * j, 6),
                "lat": round(p1["lat"] + lat_step * j, 6),
                "yaw": round(heading, 2)
            })
    return path


def execute_mission(task):
    global is_flying
    is_flying = True

    task_id = task['id']
    task_name = task['taskName']

    print(f"\n[无人机 #{DRONE_ID}] 开始执行任务 #{task_id} <{task_name}>")

    # ================= 图片初始化 =================
    image_folder = "photo"
    image_list = [f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    image_list.sort()

    if not image_list:
        print("⚠️ photo 文件夹没有图片！")
        is_flying = False
        return

    image_index = 0
    # ============================================

    # 每次任务开始都从第一张图片重新开始
    image_index = 0

    route_data = task.get('routePoints')

    if isinstance(route_data, str):
        try:
            waypoints = json.loads(route_data)
        except Exception as e:
            print(f"航线解析失败: {e}")
            is_flying = False
            return
    elif isinstance(route_data, list):
        waypoints = route_data
    else:
        print("航线数据格式错误")
        is_flying = False
        return

    try:
        flight_path = generate_flight_path(waypoints, FLIGHT_SPEED)

        tick = 0
        for point in flight_path:
            current_lng = point["lng"]
            current_lat = point["lat"]
            current_yaw = point["yaw"]

            # ===== 遥测 =====
            telemetry = {
                "taskId": task_id,
                "droneId": DRONE_ID,
                "lng": current_lng,
                "lat": current_lat,
                "heading": current_yaw
            }

            try:
                requests.post(f"{BACKEND_HTTP_URL}/api/v1/drones/telemetry", json=telemetry, timeout=0.5)
            except:
                pass

            # ===== 上传图片 =====
            if tick > 0 and tick % int(IMAGE_INTERVAL / TELEMETRY_INTERVAL) == 0:
                image_name = image_list[image_index]
                image_path = os.path.join(image_folder, image_name)

                print(f"📸 上传图片: {image_name}")

                upload_data = {
                    "taskId": task_id,
                    "droneId": DRONE_ID,
                    "lng": current_lng,
                    "lat": current_lat,
                    "altitude": DEFAULT_ALTITUDE,
                    "yaw": current_yaw,
                    "pitch": DEFAULT_PITCH,
                    "roll": DEFAULT_ROLL,
                    "fov": DEFAULT_FOV
                }

                try:
                    with open(image_path, 'rb') as f:
                        files = {'file': (image_name, f, 'image/jpeg')}

                        res = requests.post(
                            f"{BACKEND_HTTP_URL}/api/v1/drones/upload",
                            data=upload_data,
                            files=files,
                            timeout=5
                        )

                    print(f"   ☁️ 上传成功: {res.text}")
                except Exception as e:
                    print(f"   ⚠️ 上传失败: {e}")

                # 循环图片
                image_index = (image_index + 1) % len(image_list)

            tick += 1
            time.sleep(TELEMETRY_INTERVAL)

        print(f"🛬 任务结束 #{task_id}")
        requests.put(f"{BACKEND_HTTP_URL}/api/v1/tasks/{DRONE_ID}/finish")

    except Exception as e:
        print(f"任务异常: {e}")
    finally:
        is_flying = False


# ================= WebSocket =================

def on_message(ws, message):
    global is_flying
    try:
        msg = json.loads(message)

        if msg.get("type") == "task_start":
            task_data = msg.get("data", {})

            if task_data.get("droneId") == DRONE_ID:
                if not is_flying:
                    threading.Thread(target=execute_mission, args=(task_data,)).start()
                else:
                    print("⚠️ 正在飞行，忽略新任务")

    except:
        pass


def on_error(ws, error):
    print(f"WebSocket错误: {error}")


def on_close(ws, a, b):
    print("连接断开，重连中...")


def on_open(ws):
    print(f"无人机 {DRONE_ID} 已连接，等待任务...")


def main_loop():
    while True:
        try:
            ws = websocket.WebSocketApp(
                BACKEND_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"连接异常: {e}")

        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drone-id", type=int, required=True)
    args = parser.parse_args()

    DRONE_ID = args.drone_id
    main_loop()

