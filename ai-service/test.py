import requests
import random
import math
import copy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

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

def latlon_to_m(lat, lon):
    dy = (lat - BASE_LAT) * M_PER_LAT
    dx = (lon - BASE_LON) * M_PER_LON
    return dx, dy

# ─────────────────────────────────────────────
# 随机路网与点位生成（修复拓扑连接与 2D 离散散布）
# ─────────────────────────────────────────────
def get_random_point_on_polyline(nodes):
    """在折线上随机挑选一个点（用于支路精确连接主路）"""
    lengths = [math.hypot(nodes[i+1][0]-nodes[i][0], nodes[i+1][1]-nodes[i][1]) for i in range(len(nodes)-1)]
    total_len = sum(lengths)
    if total_len == 0: return nodes[0]

    rand_len = random.uniform(0.1 * total_len, 0.9 * total_len) # 避免连在两端
    accum = 0
    for i, l in enumerate(lengths):
        if accum + l >= rand_len:
            t = (rand_len - accum) / l
            x = nodes[i][0] + t * (nodes[i+1][0] - nodes[i][0])
            y = nodes[i][1] + t * (nodes[i+1][1] - nodes[i][1])
            return x, y
        accum += l
    return nodes[-1]

def generate_road_network():
    roads = []

    # 主干道（带弯折）
    main_nodes = [(0, 0)]
    curr_x, curr_y = 0, 0
    for _ in range(3):
        curr_x += random.uniform(100, 150)
        curr_y += random.uniform(-25, 25)
        main_nodes.append((curr_x, curr_y))
    roads.append({"name": "主干道", "nodes": main_nodes, "role": "main"})

    # 生成 4~5 条支路
    num_branches = random.randint(4, 5)
    for i in range(num_branches):
        # 【修复】：确保支路的起点精确落在主干道的折线段上
        start_x, start_y = get_random_point_on_polyline(main_nodes)

        angle = random.uniform(math.pi / 5, math.pi * 4 / 5)
        if random.choice([True, False]):
            angle = -angle

        branch_len = random.uniform(60, 130)
        end_x = start_x + branch_len * math.cos(angle)
        end_y = start_y + branch_len * math.sin(angle)

        roads.append({"name": f"支路{i+1}", "nodes": [(start_x, start_y), (end_x, end_y)], "role": "branch"})

    branch_indices = [i for i, r in enumerate(roads) if r["role"] == "branch"]
    new_only_idx, dense_idx = random.sample(branch_indices, 2)

    roads[new_only_idx]["role"] = "new_only"
    roads[dense_idx]["role"] = "dense"

    return roads, new_only_idx, dense_idx


def road_length(nodes):
    return sum(math.hypot(nodes[i+1][0] - nodes[i][0], nodes[i+1][1] - nodes[i][1]) for i in range(len(nodes) - 1))


def sample_around_road(nodes, n, max_offset=8.0):
    """
    【修复】：在道路周围散布点位（默认路中心两侧 8 米以内），
    符合 2D 分布，使得拓扑特征对 GNN 更友好。
    """
    total = road_length(nodes)
    seg_lengths = [math.hypot(nodes[i+1][0]-nodes[i][0], nodes[i+1][1]-nodes[i][1]) for i in range(len(nodes)-1)]
    points = []

    for _ in range(n):
        if total == 0:
            base_x, base_y = nodes[0]
        else:
            seg_weights = [l / total for l in seg_lengths]
            seg_idx = random.choices(range(len(seg_lengths)), weights=seg_weights, k=1)[0]
            t = random.random()
            base_x = nodes[seg_idx][0] + t * (nodes[seg_idx+1][0] - nodes[seg_idx][0])
            base_y = nodes[seg_idx][1] + t * (nodes[seg_idx+1][1] - nodes[seg_idx][1])

        # 添加半径为 max_offset 的随机圆盘散布
        angle = random.uniform(0, 2 * math.pi)
        # 取平方根保证在圆内均匀分布
        r = max_offset * math.sqrt(random.uniform(0, 1))
        x = base_x + r * math.cos(angle)
        y = base_y + r * math.sin(angle)

        points.append((x, y, random.randint(0, 3)))
    return points


# ─────────────────────────────────────────────
# 可视化 (代码不变，渲染效果会自然变好)
# ─────────────────────────────────────────────
def visualize_results(roads, old_points, new_points, results, matched_tracking,
                      new_only_idx, dense_idx, global_off_x, global_off_y,
                      correct_match, wrong_match, false_new, new_identified,
                      matched_count, N_NEW_DISEASE):

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    fig.patch.set_facecolor('#1a1a2e')

    role_colors = {
        "main":     "#aaaacc",
        "branch":   "#667788",
        "new_only": "#ff6b6b",
        "dense":    "#ffd93d",
    }

    for ax in axes:
        ax.set_facecolor('#16213e')
        ax.tick_params(colors='#cccccc')
        ax.spines['bottom'].set_color('#444466')
        ax.spines['left'].set_color('#444466')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    # ── 左图：点位分布 ──────────────────────────────────
    ax1 = axes[0]
    ax1.set_title("点位分布概览", color='white', fontsize=14, pad=12)

    for i, road in enumerate(roads):
        nodes = road["nodes"]
        xs = [n[0] for n in nodes]
        ys = [n[1] for n in nodes]
        color = role_colors.get(road["role"], "#667788")
        lw = 6 if road["role"] == "main" else 4 # 把线画粗点，像真实马路
        ax1.plot(xs, ys, color=color, linewidth=lw, zorder=1, solid_capstyle='round', alpha=0.3)
        # 画中心细线
        ax1.plot(xs, ys, color=color, linewidth=1, zorder=1, alpha=0.8)

        mid_x = (xs[0] + xs[-1]) / 2
        mid_y = (ys[0] + ys[-1]) / 2
        label = road["name"]
        if road["role"] == "new_only":
            label += "\n(仅新病害)"
        elif road["role"] == "dense":
            label += "\n(密集病害)"
        ax1.text(mid_x, mid_y + 10, label, fontsize=7, color=color,
                 ha='center', va='bottom', zorder=5,
                 bbox=dict(boxstyle='round,pad=0.2', fc='#1a1a2e', ec='none', alpha=0.7))

    for p in old_points:
        ox, oy = latlon_to_m(p["y"], p["x"])
        ax1.scatter(ox, oy, s=30, color='#4fc3f7', marker='o', alpha=0.7, zorder=3,
                    edgecolors='#0288d1', linewidths=0.5)

    for p in new_points:
        nx, ny = latlon_to_m(p["y"], p["x"])
        is_match = p["id"] in matched_tracking
        color = '#66bb6a' if is_match else '#ef5350'
        ax1.scatter(nx, ny, s=22, color=color, marker='^', alpha=0.85, zorder=4,
                    edgecolors='white', linewidths=0.3)

    legend_handles = [
        mpatches.Patch(color=role_colors["main"], label='主干道 (带8m宽度)'),
        mpatches.Patch(color=role_colors["new_only"], label=f'仅新病害支路（支路{new_only_idx}）'),
        mpatches.Patch(color=role_colors["dense"], label=f'密集病害支路（支路{dense_idx}）'),
        mpatches.Patch(color='#4fc3f7', label='历史病害（老点）'),
        mpatches.Patch(color='#66bb6a', label='本次检测（应匹配）'),
        mpatches.Patch(color='#ef5350', label='本次检测（新病害）'),
    ]
    ax1.legend(handles=legend_handles, loc='upper left', fontsize=7,
               facecolor='#0f0f1e', edgecolor='#444466', labelcolor='#cccccc')
    ax1.set_xlabel("X 坐标 (米)", color='#aaaacc', fontsize=9)
    ax1.set_ylabel("Y 坐标 (米)", color='#aaaacc', fontsize=9)

    # ── 右图：匹配结果 ──────────────────────────────────
    ax2 = axes[1]
    ax2.set_title("匹配结果详情", color='white', fontsize=14, pad=12)

    for road in roads:
        nodes = road["nodes"]
        xs = [n[0] for n in nodes]
        ys = [n[1] for n in nodes]
        color = role_colors.get(road["role"], "#667788")
        ax2.plot(xs, ys, color=color, linewidth=4, zorder=1, alpha=0.2, solid_capstyle='round')

    old_coord = {p["id"]: latlon_to_m(p["y"], p["x"]) for p in old_points}
    new_coord = {p["id"]: latlon_to_m(p["y"], p["x"]) for p in new_points}

    if results:
        for item in results:
            nid = item['new_id']
            best = item['candidates'][0]
            nx, ny = new_coord[nid]
            is_match_point = nid in matched_tracking

            if best['is_new_disease']:
                if not is_match_point:
                    ax2.scatter(nx, ny, s=35, color='#ef5350', marker='*', zorder=5, edgecolors='#ff8a80', linewidths=0.4)
                else:
                    ax2.scatter(nx, ny, s=40, color='#ff6d00', marker='x', zorder=6, linewidths=1.5)
                    ox, oy = old_coord.get(matched_tracking[nid], (nx, ny))
                    ax2.plot([nx, ox], [ny, oy], color='#ff6d00', linewidth=0.8, linestyle='--', alpha=0.5, zorder=4)
            else:
                mid_old = best['matched_old_id']
                if mid_old in old_coord:
                    ox, oy = old_coord[mid_old]
                    if is_match_point and matched_tracking[nid] == mid_old:
                        ax2.plot([nx, ox], [ny, oy], color='#69f0ae', linewidth=0.9, alpha=0.6, zorder=3)
                        ax2.scatter(nx, ny, s=25, color='#69f0ae', marker='^', zorder=5, edgecolors='white', linewidths=0.3)
                    else:
                        ax2.plot([nx, ox], [ny, oy], color='#ff1744', linewidth=1.2, alpha=0.8, zorder=4)
                        ax2.scatter(nx, ny, s=35, color='#ff1744', marker='D', zorder=6, edgecolors='white', linewidths=0.4)

        for p in old_points:
            ox, oy = latlon_to_m(p["y"], p["x"])
            ax2.scatter(ox, oy, s=18, color='#4fc3f7', marker='o', alpha=0.5, zorder=2, edgecolors='none')

    match_prec = correct_match / (correct_match + wrong_match + 1e-9)
    new_recall = new_identified / N_NEW_DISEASE if N_NEW_DISEASE > 0 else float('nan')

    legend2 = [
        Line2D([0],[0], color='#69f0ae', linewidth=1.2, label=f'正确匹配连线 ({correct_match}个)'),
        Line2D([0],[0], color='#ff1744', linewidth=1.2, label=f'错误匹配连线 ({wrong_match}个)'),
        mpatches.Patch(color='#ef5350', label=f'正确识别新病害 ({new_identified}个)'),
        mpatches.Patch(color='#ff6d00', label=f'旧病害误判为新增 ({false_new}个)'),
        mpatches.Patch(color='#4fc3f7', label='历史病害位置'),
    ]
    ax2.legend(handles=legend2, loc='upper left', fontsize=7, facecolor='#0f0f1e', edgecolor='#444466', labelcolor='#cccccc')

    stats_text = (
        f"匹配精确率：{match_prec:.1%}\n"
        f"新增拦截率：{new_recall:.1%}\n"
        f"历史点数：{len(old_points)}\n"
        f"检测点数：{len(new_points)}\n"
        f"全局GPS偏移：X={global_off_x:.1f}m Y={global_off_y:.1f}m"
    )
    ax2.text(0.98, 0.02, stats_text, transform=ax2.transAxes, fontsize=8, color='#cccccc', va='bottom', ha='right', bbox=dict(boxstyle='round,pad=0.5', fc='#0f0f1e', ec='#444466', alpha=0.85))
    ax2.set_xlabel("X 坐标 (米)", color='#aaaacc', fontsize=9)
    plt.tight_layout(pad=2.5)

    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_result.png")
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"📊 可视化图已保存：{out_path}")
    return out_path


# ─────────────────────────────────────────────
# 主逻辑
# ─────────────────────────────────────────────
def run_stress_test():
    random.seed(42)
    roads, new_only_idx, dense_idx = generate_road_network()

    print("\n🗺️ 路网已生成：")
    for i, road in enumerate(roads):
        l = road_length(road["nodes"])
        role_tag = "  ← 【仅新病害支路】" if road["role"] == "new_only" else "  ← 【密集病害支路】" if road["role"] == "dense" else ""
        print(f"   [{i}] {road['name']}（{road['role']}）：长度 {l:.0f}m{role_tag}")

    N_MAIN_OLD    = 15
    N_BRANCH_OLD  = 8
    N_DENSE_OLD   = 25
    N_NEW_ONLY_OLD = 0

    N_MAIN_NEW    = 3
    N_BRANCH_NEW  = 3
    N_DENSE_NEW   = 8
    N_NEW_ONLY_NEW = 15

    DETECT_RATE = 0.8

    true_positions = {}
    new_disease_positions = {}

    for i, road in enumerate(roads):
        if road["role"] == "main": n_old, n_new = N_MAIN_OLD, N_MAIN_NEW
        elif road["role"] == "new_only": n_old, n_new = N_NEW_ONLY_OLD, N_NEW_ONLY_NEW
        elif road["role"] == "dense": n_old, n_new = N_DENSE_OLD, N_DENSE_NEW
        else: n_old, n_new = N_BRANCH_OLD, N_BRANCH_NEW

        # 使用散布函数，偏移 8 米以内
        true_positions[i] = sample_around_road(road["nodes"], n_old, max_offset=8.0) if n_old > 0 else []
        new_disease_positions[i] = sample_around_road(road["nodes"], n_new, max_offset=8.0) if n_new > 0 else []

    global_off_x = random.uniform(1, 2)
    global_off_y = random.uniform(-2, -1)

    old_points = []
    hist_id = 0
    for road_idx, pts in true_positions.items():
        for (x, y, t) in pts:
            px, py = x + global_off_x, y + global_off_y
            lat, lon = m_to_latlon(px, py)
            lat, lon = add_noise_latlon(lat, lon, noise_m=1.0)
            old_points.append({"id": f"HIST_{hist_id:03d}", "x": lon, "y": lat, "type": t})
            hist_id += 1

    new_points = []
    matched_tracking = {}
    uav_id = 0

    hist_id = 0
    for road_idx, pts in true_positions.items():
        for (x, y, t) in pts:
            if random.random() < DETECT_RATE:
                lat, lon = m_to_latlon(x, y)
                lat, lon = add_noise_latlon(lat, lon, noise_m=1.5)
                nid = f"UAV_MATCH_{uav_id:03d}"
                new_points.append({"id": nid, "x": lon, "y": lat, "type": t})
                matched_tracking[nid] = f"HIST_{hist_id:03d}"
                uav_id += 1
            hist_id += 1

    matched_count = len(matched_tracking)

    new_disease_total = 0
    for road_idx, pts in new_disease_positions.items():
        for (x, y, t) in pts:
            lat, lon = m_to_latlon(x, y)
            lat, lon = add_noise_latlon(lat, lon, noise_m=1.0)
            new_points.append({"id": f"UAV_NEW_{uav_id:03d}", "x": lon, "y": lat, "type": t})
            uav_id += 1
            new_disease_total += 1

    N_NEW_DISEASE = new_disease_total
    random.shuffle(new_points)

    print(f"\n📦 测试集：")
    print(f"   历史库 P = {len(old_points)} 个老病害")
    print(f"   检测集 Q = {len(new_points)} 个（真实匹配 {matched_count} 个，真新增 {N_NEW_DISEASE} 个）")
    print(f"📐 GPS偏移模拟：X={global_off_x:.1f}m, Y={global_off_y:.1f}m\n")

    results = None
    correct_match = wrong_match = false_new = new_identified = 0

    print("📡 正在发送请求...")
    try:
        response = requests.post(URL, json={"old_points": old_points, "new_points": new_points}, timeout=30)
        response.raise_for_status()
        results = response.json()['results']

        for item in results:
            nid = item['new_id']
            best = item['candidates'][0]
            is_match_point = nid in matched_tracking

            if best['is_new_disease']:
                if not is_match_point: new_identified += 1
                else: false_new += 1
            else:
                matched_old = best['matched_old_id']
                if is_match_point:
                    if matched_tracking[nid] == matched_old: correct_match += 1
                    else: wrong_match += 1
                else:
                    wrong_match += 1

        match_prec = correct_match / (correct_match + wrong_match + 1e-9)
        new_recall = new_identified / N_NEW_DISEASE if N_NEW_DISEASE > 0 else 0

        print(f"📊 【测试报告】")
        print(f"   ✔ 成功找回旧病害：{correct_match} / {matched_count}")
        print(f"   ✦ 准确识别新病害：{new_identified} / {N_NEW_DISEASE}")
        print(f"   ✘ 旧病害被误判为新增：{false_new}")
        print(f"   ✘ 错误匹配：{wrong_match}")
        print(f"   🔥 匹配精确率：{match_prec:.1%}  新增拦截率：{new_recall:.1%}")

    except Exception as e:
        print(f"⚠️  请求失败（{e}），将仅生成分布可视化图")

    visualize_results(
        roads=roads, old_points=old_points, new_points=new_points, results=results or [],
        matched_tracking=matched_tracking, new_only_idx=new_only_idx, dense_idx=dense_idx,
        global_off_x=global_off_x, global_off_y=global_off_y,
        correct_match=correct_match, wrong_match=wrong_match, false_new=false_new,
        new_identified=new_identified, matched_count=matched_count, N_NEW_DISEASE=N_NEW_DISEASE,
    )

if __name__ == "__main__":
    run_stress_test()