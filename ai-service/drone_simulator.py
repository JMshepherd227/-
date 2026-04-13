import requests
import time
import math
import json
import argparse
import websocket
import threading

# ================= 配置区 =================
BACKEND_HTTP_URL = "http://localhost:8080"
BACKEND_WS_URL = "ws://localhost:8080/ws/telemetry"

TELEMETRY_INTERVAL = 0.1  # 遥测发送间隔 (100ms)
IMAGE_INTERVAL = 2.0      # 拍照上传间隔 (2秒)
FLIGHT_SPEED = 5.0        # 飞行速度 (5 m/s)

# 无人机缺省物理参数 (用于视觉投影反算)
DEFAULT_ALTITUDE = 4.0   # 飞行高度 50米
DEFAULT_PITCH = -90.0     # 云台俯仰角 (-90度代表垂直朝下)
DEFAULT_ROLL = 0.0        # 云台横滚角
DEFAULT_FOV = 80.0        # 相机视场角 90度

DRONE_ID = None           # 运行时通过命令行传入
is_flying = False         # 飞行状态锁
# ==========================================

def calculate_distance(lng1, lat1, lng2, lat2):
    """Haversine 计算地球两点物理距离(米)"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calculate_heading(lng1, lat1, lng2, lat2):
    """计算机头朝向角 (正北0度，顺时针增加)"""
    angle = math.degrees(math.atan2(lat2 - lat1, lng2 - lng1))
    return (90 - angle) % 360

def generate_flight_path(waypoints, speed):
    """插值生成平滑的 100ms 连续飞行轨迹"""
    path =[]
    for i in range(len(waypoints) - 1):
        p1, p2 = waypoints[i], waypoints[i+1]
        dist = calculate_distance(p1["lng"], p1["lat"], p2["lng"], p2["lat"])
        duration = dist / speed
        steps = int(duration / TELEMETRY_INTERVAL)
        heading = calculate_heading(p1["lng"], p1["lat"], p2["lng"], p2["lat"])

        if steps == 0: continue
        lng_step = (p2["lng"] - p1["lng"]) / steps
        lat_step = (p2["lat"] - p1["lat"]) / steps

        for j in range(steps):
            path.append({
                "lng": round(p1["lng"] + lng_step * j, 6),
                "lat": round(p1["lat"] + lat_step * j, 6),
                "yaw": round(heading, 2) # 机头朝向即为偏航角(yaw)
            })
    return path

def execute_mission(task):
    """子线程：执行自动化巡检任务"""
    global is_flying
    is_flying = True

    task_id = task['id']
    task_name = task['taskName']

    print(f"\n[无人机 #{DRONE_ID}] 收到云端起飞指令！任务 #{task_id} <{task_name}> 开始执行！")

    route_data = task.get('routePoints')

    if isinstance(route_data, str):
        # 如果是字符串，说明是原始 JSON，需要解析
        try:
            waypoints = json.loads(route_data)
            print(111)
        except Exception as e:
            print(f"航线字符串解析失败: {e}")
            is_flying = False
            return
    elif isinstance(route_data, list):
        # 如果已经是列表，说明后端已经帮我们解析好了，直接用
        waypoints = route_data
        print(222)
    else:
        print(f"航线数据格式异常: {type(route_data)}")
        is_flying = False
        return

    try:
        flight_path = generate_flight_path(waypoints, FLIGHT_SPEED)
        print(f"航线规划完毕，预计飞行 {len(flight_path) * TELEMETRY_INTERVAL:.1f} 秒")

        tick = 0
        for point in flight_path:
            current_lng = point["lng"]
            current_lat = point["lat"]
            current_yaw = point["yaw"]

            # ----------------------------------------------------
            # 1. 动作 A: 发送高频遥测 (推给 WebSocket)
            # ----------------------------------------------------
            telemetry = {
                "taskId": task_id,
                "droneId": DRONE_ID,
                "lng": current_lng,
                "lat": current_lat,
                "heading": current_yaw # 前端可能还是用 heading 字段画偏转角
            }
            try:
                requests.post(f"{BACKEND_HTTP_URL}/api/v1/drones/telemetry", json=telemetry, timeout=0.5)
            except:
                pass # 忽略高频请求的偶发超时

            # ----------------------------------------------------
            # 2. 动作 B: 按时间间隔拍照并上传 (携带完整姿态参数)
            # ----------------------------------------------------
            if tick > 0 and tick % int(IMAGE_INTERVAL / TELEMETRY_INTERVAL) == 0:
                print(f"📸 咔嚓！坐标: ({current_lng}, {current_lat}), 航向: {current_yaw}°")
                try:
                    # 读取本地占位图片
                    files = {'file': ('photo/d4dc1dcbae580a4b0d9a324d826c92c4.jpeg', open('photo/d4dc1dcbae580a4b0d9a324d826c92c4.jpeg', 'rb'), 'image/jpeg')}

                    # 严格按照 SpringBoot 的 @RequestParam 构建表单数据
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

                    res = requests.post(
                        f"{BACKEND_HTTP_URL}/api/v1/drones/upload",
                        data=upload_data,
                        files=files,
                        timeout=5
                    )
                    print(f"   ☁️ 图片上传成功: {res.text}")
                except Exception as upload_err:
                    print(f"   ⚠️ 图片上传失败: {upload_err}")

            tick += 1
            time.sleep(TELEMETRY_INTERVAL)

        # ----------------------------------------------------
        # 3. 呼叫后端结束任务
        # ----------------------------------------------------
        print(f"🛬 任务 #{task_id} 飞行结束，正在向指挥中心申请结项...")
        finish_res = requests.put(f"{BACKEND_HTTP_URL}/api/v1/tasks/{DRONE_ID}/finish")
        print(f"结项结果: {finish_res.text}")
        print("无人机已归位，恢复待机状态。\n")

    except Exception as e:
        print(f"任务执行出错: {e}")
    finally:
        is_flying = False


# ================= WebSocket 实时监听流 =================

def on_message(ws, message):
    """处理云端推流的实时控制指令"""
    global is_flying
    try:
        msg = json.loads(message)

        # 识别云端的“开始任务”指令
        if msg.get("type") == "task_start":
            task_data = msg.get("data", {})

            # 判断指令是不是发给本机的
            if task_data.get("droneId") == DRONE_ID:
                if is_flying:
                    print("⚠️ 收到起飞指令，但我正在飞行中，忽略！")
                else:
                    # 开启独立线程执行飞行任务，不阻塞 WebSocket 监听
                    threading.Thread(target=execute_mission, args=(task_data,)).start()

    except Exception as e:
        pass

def on_error(ws, error):
    print(f"通讯链路异常: {error}")

def on_close(ws, close_status_code, close_msg):
    print("与指挥中心的链路断开，尝试重新建立连接...")

def on_open(ws):
    print(f"[大疆 M300 - 编号 {DRONE_ID}] 机载终端启动！")
    print(f"WebSocket 链路连接成功！正在待机等待指挥中心下发任务...")

def main_loop():
    while True:
        print(f"🤖 [无人机 {DRONE_ID}] 正在尝试连接指挥中心...")
        try:
            ws = websocket.WebSocketApp(
                BACKEND_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            # run_forever 会阻塞在这里，直到连接断开
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            print(f"📡 WebSocket 运行异常: {e}")

        # 👈 如果后端挂了，run_forever 会退出，这里等待 5 秒后尝试重连
        print("⏳ 5秒后尝试重新建立指挥链路...")
        time.sleep(5)

if __name__ == "__main__":
    # 解析启动参数
    parser = argparse.ArgumentParser(description="边缘侧无人机机载端模拟程序")
    parser.add_argument("--drone-id", type=int, required=True, help="本机绑定的设备 ID")
    args = parser.parse_args()

    DRONE_ID = args.drone_id
    main_loop()