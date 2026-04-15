import os
import requests
import random
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

API_URL = "http://127.0.0.1:8000/match_points/"
SAVE_DIR = "test_scenarios"
os.makedirs(SAVE_DIR, exist_ok=True)

# ==========================================
# 坐标转换工具
# ==========================================
BASE_LAT = 39.901100
BASE_LON = 116.391100
M_PER_LAT = 111000.0
M_PER_LON = 111000.0 * math.cos(math.radians(BASE_LAT))

def m_to_latlon(x_m, y_m):
    return BASE_LAT + y_m / M_PER_LAT, BASE_LON + x_m / M_PER_LON

def latlon_to_m(lat, lon):
    dy = (lat - BASE_LAT) * M_PER_LAT
    dx = (lon - BASE_LON) * M_PER_LON
    return dx, dy

# ==========================================
# 场景生成器
# ==========================================
def generate_scenario(scenario_name):
    # 使用随机种子但根据场景微调，保证测试的可重复性
    random.seed(42)
    np.random.seed(42)

    n_old = 40
    n_matched = 35
    n_new = 5
    map_size = 200.0
    rel_offset = np.array([0.0, 0.0])
    noise_std = 0.5
    title = ""

    if scenario_name == "01_NORMAL":
        title = "常规场景 (2m 漂移, 少量新增)"
        rel_offset = np.array([1.5, -1.5])

    elif scenario_name == "02_DRIFT_15M":
        title = "极限漂移 (15m 漂移)"
        rel_offset = np.array([12.0, -9.0])

    elif scenario_name == "03_DENSE_05M":
        # 【核心修改】：超级密集场景
        title = "密集场景"
        map_size = 5.0     # 限制在 5 米范围内
        n_old = 40         # 30个老点
        n_matched = 40     # 匹配30个
        n_new = 10          # 新增8个
        rel_offset = np.array([0.5, 0.5]) # 即使偏移小，密度也极大
        noise_std = 0.05   # 密集场景下噪声必须小，否则物理上点会重叠

    elif scenario_name == "04_MASSIVE_ISOLATED":
        title = "海量孤立新增 (全方位随机干扰)"
        n_old = 30
        n_matched = 25
        n_new = 80
        rel_offset = np.array([2.0, 2.0])
        # 这里的新增点生成逻辑在下方会进行【随机方位】处理

    elif scenario_name == "05_MASSIVE_MIXED":
        title = "海量混淆新增 (新旧交织)"
        n_old = 20
        n_matched = 18
        n_new = 80
        rel_offset = np.array([1.5, 1.5])
        noise_std = 0.5

    # 1. 生成旧点坐标
    P_m = np.random.rand(n_old, 2) * map_size
    P_types = np.random.randint(0, 4, n_old)

    # 2. 生成匹配的新点
    matched_indices = np.random.choice(n_old, n_matched, replace=False)
    Q_matched_m = P_m[matched_indices] + rel_offset + np.random.normal(0, noise_std, (n_matched, 2))
    Q_matched_types = P_types[matched_indices]

    # 3. 生成新增点 (针对 04 场景做方位随机化)
    if scenario_name == "04_MASSIVE_ISOLATED":
        # 【核心修改】：随机方位平移，消除右上角偏置
        angle = random.uniform(0, 2 * math.pi)
        dist = map_size * 1.5
        shift_vector = np.array([math.cos(angle) * dist, math.sin(angle) * dist])
        Q_new_m = np.random.rand(n_new, 2) * (map_size * 0.5) + shift_vector
    elif scenario_name == "05_MASSIVE_MIXED":
        base_idx = np.random.randint(0, n_matched, n_new)
        Q_new_m = Q_matched_m[base_idx] + np.random.normal(0, 1.5, (n_new, 2))
    else:
        Q_new_m = np.random.rand(n_new, 2) * map_size

    Q_new_types = np.random.randint(0, 4, n_new)

    # 组合 Q
    Q_m = np.vstack([Q_matched_m, Q_new_m]) if n_new > 0 else Q_matched_m
    Q_types = np.concatenate([Q_matched_types, Q_new_types]) if n_new > 0 else Q_matched_types

    # --- 构造 ID 映射和接口数据格式 (剩余代码保持不变) ---
    old_points = []
    P_id_map = {}
    for i in range(n_old):
        lat, lon = m_to_latlon(P_m[i, 0], P_m[i, 1])
        pid = f"P_{i}"
        old_points.append({"id": pid, "x": lon, "y": lat, "type": int(P_types[i])})
        P_id_map[pid] = P_m[i]

    new_points = []
    Q_id_map = {}
    ground_truth = {}
    for i in range(len(Q_m)):
        lat, lon = m_to_latlon(Q_m[i, 0], Q_m[i, 1])
        qid = f"Q_{i}"
        new_points.append({"id": qid, "x": lon, "y": lat, "type": int(Q_types[i])})
        Q_id_map[qid] = Q_m[i]
        if i < n_matched:
            ground_truth[qid] = f"P_{matched_indices[i]}"
        else:
            ground_truth[qid] = None

    return title, old_points, new_points, ground_truth, P_id_map, Q_id_map

# ==========================================
# 可视化与评估核心
# ==========================================
def evaluate_and_plot(scenario_name):
    title, old_points, new_points, gt_map, P_coords_dict, Q_coords_dict = generate_scenario(scenario_name)

    print(f"\n🚀 开始测试: {title}")
    print(f"   - 旧点数量: {len(old_points)}")
    print(f"   - 新点数量: {len(new_points)}")

    try:
        response = requests.post(API_URL, json={"old_points": old_points, "new_points": new_points}, timeout=10)
        response.raise_for_status()
        results = response.json().get('results', [])
    except Exception as e:
        print(f"   ❌ API 请求失败: {e}")
        return

    # 解析预测结果
    pred_map = {}
    for item in results:
        best_cand = item['candidates'][0]
        if best_cand['is_new_disease']:
            pred_map[item['new_id']] = None
        else:
            pred_map[item['new_id']] = best_cand['matched_old_id']

    # 统计指标
    stats = {'tp': 0, 'wm': 0, 'fp': 0, 'fn': 0, 'tn': 0}
    plot_actions = [] # 用于绘图

    for qid, q_pt in Q_coords_dict.items():
        true_p = gt_map[qid]
        pred_p = pred_map.get(qid)

        is_new_gt = (true_p is None)
        is_new_pred = (pred_p is None)

        if is_new_gt and is_new_pred:
            stats['tn'] += 1
            plot_actions.append(('circle_green', q_pt))
        elif is_new_gt and not is_new_pred:
            stats['fp'] += 1
            plot_actions.append(('line_purple', q_pt, P_coords_dict[pred_p]))
        elif not is_new_gt and is_new_pred:
            stats['fn'] += 1
            plot_actions.append(('circle_orange', q_pt))
        elif not is_new_gt and not is_new_pred:
            if true_p == pred_p:
                stats['tp'] += 1
                plot_actions.append(('line_green', q_pt, P_coords_dict[pred_p]))
            else:
                stats['wm'] += 1
                plot_actions.append(('line_red', q_pt, P_coords_dict[pred_p]))

    # 计算精确率
    precision = stats['tp'] / (stats['tp'] + stats['fp'] + stats['wm'] + 1e-9)
    recall = stats['tp'] / (stats['tp'] + stats['fn'] + stats['wm'] + 1e-9)
    print(f"   📊 成绩: TP={stats['tp']} | TN={stats['tn']} | WM={stats['wm']} | FP={stats['fp']} | FN={stats['fn']}")
    print(f"   🔥 匹配精确率: {precision:.1%} | 匹配召回率: {recall:.1%}")

    # ================= 绘图 =================
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_title(title, fontsize=16, pad=15)

    # 提取坐标转换为 numpy
    P_arr = np.array(list(P_coords_dict.values()))
    Q_arr = np.array(list(Q_coords_dict.values()))

    # 动态半径计算
    x_range = P_arr[:, 0].max() - P_arr[:, 0].min() if len(P_arr) > 0 else 1.0
    dynamic_radius = max(x_range * 0.03, 0.5)

    # 散点
    ax.scatter(P_arr[:, 0], P_arr[:, 1], c='dodgerblue', marker='X', s=120, label='Old (P)', zorder=3, edgecolors='white', linewidths=0.5)
    ax.scatter(Q_arr[:, 0], Q_arr[:, 1], c='tomato', marker='o', s=80, label='New (Q)', zorder=3, edgecolors='white', linewidths=0.5)

    # 绘制动作
    for action in plot_actions:
        cmd = action[0]
        q_pt = action[1]
        if cmd == 'circle_green':
            ax.add_patch(plt.Circle(q_pt, dynamic_radius, color='forestgreen', fill=False, linewidth=2, linestyle='--', zorder=4))
        elif cmd == 'circle_orange':
            ax.add_patch(plt.Circle(q_pt, dynamic_radius, color='darkorange', fill=False, linewidth=2, linestyle='-.', zorder=4))
        elif cmd == 'line_green':
            ax.plot([q_pt[0], action[2][0]], [q_pt[1], action[2][1]], c='forestgreen', linewidth=2.5, alpha=0.8, zorder=1)
        elif cmd == 'line_red':
            ax.plot([q_pt[0], action[2][0]], [q_pt[1], action[2][1]], c='crimson', linewidth=2.5, alpha=0.8, zorder=2)
        elif cmd == 'line_purple':
            ax.plot([q_pt[0], action[2][0]], [q_pt[1], action[2][1]], c='purple', linestyle=':', linewidth=2, alpha=0.8, zorder=2)

    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle='--', alpha=0.3)

    # 统计面板
    legend_elements = [
        Line2D([0], [0], marker='X', color='w', markerfacecolor='dodgerblue', markersize=11, label=f'Old Points Total: {len(P_arr)}'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='tomato', markersize=9, label=f'New Points Total: {len(Q_arr)}'),
        Line2D([0], [0], color='w', label=''),
        Line2D([0], [0], color='forestgreen', lw=3, label=f'Correct Match (TP): {stats["tp"]}'),
        Line2D([0], [0], color='crimson', lw=3, label=f'Wrong Match (WM): {stats["wm"]}'),
        Line2D([0], [0], color='purple', lw=2, linestyle=':', label=f'False Match (FP): {stats["fp"]}'),
        Line2D([0], [0], marker='o', color='w', markeredgecolor='forestgreen', markerfacecolor='none', markersize=12, markeredgewidth=2, linestyle='--', label=f'Correct New (TN): {stats["tn"]}'),
        Line2D([0], [0], marker='o', color='w', markeredgecolor='darkorange', markerfacecolor='none', markersize=12, markeredgewidth=2, linestyle='-.', label=f'Missed Match (FN): {stats["fn"]}')
    ]
    ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.02, 0.5),
              fontsize=11, framealpha=0.9, edgecolor='#cccccc', title="Scenario Statistics", title_fontsize=13)

    plt.tight_layout()
    save_path = os.path.join(SAVE_DIR, f"{scenario_name}.png")
    plt.savefig(save_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"   🖼️ 可视化已保存至: {save_path}")

if __name__ == "__main__":
    print("==================================================")
    print(" 🛠️ GNN 模型 API 端全场景压力测试工具启动")
    print(" 确保后端服务 app.py 正在运行 (http://127.0.0.1:8000)")
    print("==================================================")

    scenarios = [
        "01_NORMAL",
        "02_DRIFT_15M",
        "03_DENSE_05M",
        "04_MASSIVE_ISOLATED",
        "05_MASSIVE_MIXED"
    ]

    for sc in scenarios:
        evaluate_and_plot(sc)

    print("\n✅ 所有场景测试完毕，请在 test_scenarios 文件夹中查看结果！")