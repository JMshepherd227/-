import requests
import random
import math
import copy

URL = "http://127.0.0.1:8000/match_points/"

# ─────────────────────────────────────────────
# 坐标工具
# ─────────────────────────────────────────────
BASE_LAT = 39.901100
BASE_LON = 116.391100
M_PER_LAT = 111000.0
M_PER_LON = 111000.0 * math.cos(math.radians(BASE_LAT))

def m_to_latlon(dx_m, dy_m):
    return BASE_LAT + dy_m / M_PER_LAT, BASE_LON + dx_m / M_PER_LON

def add_noise_latlon(lat, lon, noise_m):
    nx = random.uniform(-noise_m, noise_m)
    ny = random.uniform(-noise_m, noise_m)
    return lat + ny / M_PER_LAT, lon + nx / M_PER_LON

# ─────────────────────────────────────────────
# 随机路网与点位生成器
# ─────────────────────────────────────────────
def generate_random_road_network():
    """生成随机的拓扑路网"""
    roads = []

    # 1. 随机主干道 (长 300~500m，带几次随机弯折)
    main_len = random.uniform(300, 500)
    main_nodes = [(0, 0)]
    curr_x, curr_y = 0, 0
    for _ in range(random.randint(2, 4)):
        curr_x += random.uniform(80, 150)
        curr_y += random.uniform(-20, 20)
        main_nodes.append((curr_x, curr_y))
    roads.append(("主干道", main_nodes))

    # 2. 随机支路 (3~6条，随机角度和长度)
    num_branches = random.randint(3, 6)
    for i in range(num_branches):
        # 在主干道上随机选一个起点
        t = random.random()
        start_x = t * curr_x
        start_y = t * curr_y

        angle = random.uniform(math.pi/6, math.pi*5/6) # 30度到150度
        if random.choice([True, False]): angle = -angle # 随机向上下分叉

        branch_len = random.uniform(40, 150)
        end_x = start_x + branch_len * math.cos(angle)
        end_y = start_y + branch_len * math.sin(angle)

        roads.append((f"支路{i+1}", [(start_x, start_y), (end_x, end_y)]))

    return roads

def sample_points_on_roads(roads, n_points):
    """在路网上随机插值生成点"""
    road_lengths = []
    for _, nodes in roads:
        length = sum(math.hypot(nodes[i+1][0] - nodes[i][0], nodes[i+1][1] - nodes[i][1]) for i in range(len(nodes) - 1))
        road_lengths.append(length)

    total_length = sum(road_lengths)
    weights = [l / total_length for l in road_lengths]

    points = []
    for _ in range(n_points):
        road_idx = random.choices(range(len(roads)), weights=weights, k=1)[0]
        _, nodes = roads[road_idx]

        seg_lengths = [math.hypot(nodes[i+1][0] - nodes[i][0], nodes[i+1][1] - nodes[i][1]) for i in range(len(nodes) - 1)]
        seg_weights = [l / road_lengths[road_idx] for l in seg_lengths]
        seg_idx = random.choices(range(len(seg_lengths)), weights=seg_weights, k=1)[0]

        t = random.random()
        x = nodes[seg_idx][0] + t * (nodes[seg_idx+1][0] - nodes[seg_idx][0])
        y = nodes[seg_idx][1] + t * (nodes[seg_idx+1][1] - nodes[seg_idx][1])
        points.append((x, y, random.randint(0, 3))) # 返回 x, y, type

    return points

# ─────────────────────────────────────────────
# 极限压测主逻辑
# ─────────────────────────────────────────────
def run_extreme_stress_test():
    roads = generate_random_road_network()

    print("\n🗺️ 随机路网已生成：")
    for name, nodes in roads:
        length = sum(math.hypot(nodes[i+1][0]-nodes[i][0], nodes[i+1][1]-nodes[i][1]) for i in range(len(nodes)-1))
        print(f"   - {name}：长度约 {length:.0f}m")

    # ── 超高密度参数设定 ──
    N_OLD = 100            # 历史库里有 100 个老病害 (极度密集)
    DETECT_RATE = 0.8      # 本次无人机只扫到了 80% 的老病害 (漏检干扰)
    N_NEW_DISEASE = 60     # 突然爆发了 60 个全新的病害 (数量极其庞大)

    true_positions = sample_points_on_roads(roads, N_OLD)
    new_disease_positions = sample_points_on_roads(roads, N_NEW_DISEASE)

    # 模拟全局 GPS 漂移 (6~9m)
    global_off_x = random.uniform(6, 9)
    global_off_y = random.uniform(-9, -6)

    # ── 构造历史库 P ──
    old_points = []
    for i, (x, y, t) in enumerate(true_positions):
        px, py = x + global_off_x, y + global_off_y
        lat, lon = m_to_latlon(px, py)
        lat, lon = add_noise_latlon(lat, lon, noise_m=1.0)
        old_points.append({"id": f"HIST_{i:03d}", "x": lon, "y": lat, "type": t})

    # ── 构造本次检测 Q ──
    new_points = []
    matched_tracking = {} # 用于校验结果 { "UAV_ID": "HIST_ID" }

    # 1. 抽样生成被成功识别的老病害 (模拟漏检)
    for i, (x, y, t) in enumerate(true_positions):
        if random.random() < DETECT_RATE:
            lat, lon = m_to_latlon(x, y)
            lat, lon = add_noise_latlon(lat, lon, noise_m=1.5) # 新次抖动
            new_id = f"UAV_MATCH_{i:03d}"
            new_points.append({"id": new_id, "x": lon, "y": lat, "type": t})
            matched_tracking[new_id] = f"HIST_{i:03d}"

    matched_count = len(matched_tracking)

    # 2. 混入海量新增病害
    for i, (x, y, t) in enumerate(new_disease_positions):
        lat, lon = m_to_latlon(x, y)
        lat, lon = add_noise_latlon(lat, lon, noise_m=1.0)
        new_points.append({"id": f"UAV_NEW_{i:03d}", "x": lon, "y": lat, "type": t})

    # 随机打乱 Q 的顺序，防止模型猜出规律
    random.shuffle(new_points)

    print(f"\n📦 极限点集压测：")
    print(f"   旧点集 P = {len(old_points)} 个")
    print(f"   新点集 Q = {len(new_points)} 个 (其中真实匹配 {matched_count} 个，真正新增 {N_NEW_DISEASE} 个)")
    print(f"📐 模拟全局偏移：X={global_off_x:.1f}m, Y={global_off_y:.1f}m\n")

    print("📡 正在发送极限压测请求...")
    try:
        response = requests.post(URL, json={"old_points": old_points, "new_points": new_points})
        response.raise_for_status()
        results = response.json()['results']

        correct_match = 0
        new_identified = 0
        false_new = 0
        wrong_match = 0

        for item in results:
            new_id = item['new_id']
            best = item['candidates'][0]
            conf = best['confidence']
            is_match_point = new_id in matched_tracking

            if best['is_new_disease']:
                if not is_match_point:
                    new_identified += 1
                else:
                    false_new += 1      # 本该匹配却扔进了垃圾桶
            else:
                matched_old = best['matched_old_id']
                if is_match_point:
                    if matched_tracking[new_id] == matched_old:
                        correct_match += 1
                    else:
                        wrong_match += 1 # 连错线了
                else:
                    wrong_match += 1   # 新增点强行连了老点

        print(f"📊 【终极测试报告】")
        print(f"   ✔ 成功找回旧病害：{correct_match} / {matched_count}")
        print(f"   ✦ 准确识别新病害：{new_identified} / {N_NEW_DISEASE}")
        print(f"   ✘ 旧病害被当成新增 (保守误判)：{false_new}")
        print(f"   ✘ 乱牵红线 (灾难误配)：{wrong_match}")

        match_precision = correct_match / (correct_match + wrong_match + 1e-9)
        new_recall = new_identified / N_NEW_DISEASE if N_NEW_DISEASE else 0

        print(f"\n   🔥 综合匹配精确率 (Precision)：{match_precision:.1%}")
        print(f"   🔥 新增病害拦截率 (Recall)：   {new_recall:.1%}")

        if wrong_match > 5:
            print("\n⚠️ 警告：灾难误配较高！说明模型在极高密度下产生了'特征坍塌'，需要加高频位置编码并重训！")
        else:
            print("\n🎉 太强了！模型扛住了超高密度、漏检和海量干扰的轮番轰炸！")

    except Exception as e:
        print(f"❌ 请求失败：{e}")

if __name__ == "__main__":
    run_extreme_stress_test()