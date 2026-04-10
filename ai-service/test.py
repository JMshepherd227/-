import requests
import json
import random
import math

URL = "http://127.0.0.1:8000/match_points/"

def run_large_test():
    # 基准坐标：北京故宫附近
    base_lat, base_lon = 39.901100, 116.391100

    # 模拟 35 个真实病害的原始位置 (分布在 500m x 50m 的长条形区域内)
    true_points = []
    for i in range(50):
        # 沿 X 方向拉长 (经度)，沿 Y 方向窄 (纬度)
        dx_m = random.uniform(0, 500)
        dy_m = random.uniform(-25, 25)

        # 米转经纬度近似
        lat = base_lat + (dy_m / 111000.0)
        lon = base_lon + (dx_m / (111000.0 * math.cos(math.radians(base_lat))))

        true_points.append({
            "lat": lat,
            "lon": lon,
            "type": random.randint(0, 3)
        })

    # --- 1. 构造旧点集 P (取前 30 个点，模拟 GPS 整体偏航) ---
    # 模拟 GPS 整体往东北方向偏移了约 7 米
    off_y, off_x = 5.0 / 111000.0, 5.0 / 85000.0

    old_points = []
    for i in range(50):
        old_points.append({
            "id": f"HIST_DB_{i:03d}",
            "x": true_points[i]["lon"] + off_x,
            "y": true_points[i]["lat"] + off_y,
            "type": true_points[i]["type"]
        })

    # --- 2. 构造新点集 Q (本次巡检发现 30 个点) ---
    new_points = []

    # A. 20 个是匹配的 (取前 20 个，模拟本次巡检又看到了它们)
    # 模拟局部抖动 1.5 米
    for i in range(50):
        noise_y = random.uniform(-1.5, 1.5) / 111000.0
        noise_x = random.uniform(-1.5, 1.5) / 85000.0
        new_points.append({
            "id": f"UAV_DETECT_{i:03d}",
            "x": true_points[i]["lon"] + noise_x,
            "y": true_points[i]["lat"] + noise_y,
            "type": true_points[i]["type"]
        })

    # B. 10 个是真正的新增病害 (随机撒在区域内)
    for i in range(10):
        new_points.append({
            "id": f"UAV_NEW_PRO_{i:03d}",
            "x": base_lon + random.uniform(0, 500)/85000.0,
            "y": base_lat + random.uniform(-25, 25)/111000.0,
            "type": random.randint(0, 3)
        })

    payload = {"old_points": old_points, "new_points": new_points}

    print(f"📡 正在发送大规模匹配请求 (P=30, Q=30)...")
    try:
        response = requests.post(URL, json=payload)
        res_data = response.json()

        results = res_data['results']

        # 统计结果
        correct_match = 0
        new_identified = 0

        print(f"\n{'新点ID':<15} | {'判定状态':<15} | {'置信度':<10} | {'匹配详情'}")
        print("-" * 70)

        for item in results:
            new_id = item['new_id']
            best = item['candidates'][0]
            conf = best['confidence']

            if best['is_new_disease']:
                status = "NEW (新增)"
                detail = "--"
                if "UAV_NEW" in new_id: new_identified += 1
            else:
                status = "MATCH (匹配)"
                match_old = best['matched_old_id']
                detail = f"-> {match_old}"
                # 检查索引是否对应 (UAV_001 应该对应 HIST_001)
                num_part = new_id.split('_')[-1]
                if f"HIST_DB_{num_part}" == match_old:
                    correct_match += 1

            print(f"{new_id:<15} | {status:<15} | {conf:<10.4f} | {detail}")

        print("-" * 70)
        print(f"📊 测试总结:")
        print(f"   - 成功关联旧病害: {correct_match}/50")
        print(f"   - 准确识别新病害: {new_identified}/10")

    except Exception as e:
        print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    run_large_test()