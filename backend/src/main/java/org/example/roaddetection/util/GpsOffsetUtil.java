package org.example.roaddetection.util;

import java.util.List;

public class GpsOffsetUtil {

    // 地球半径 (米)
    private static final double EARTH_RADIUS = 6378137.0;

    /**
     * 根据 BBox 及无人机姿态（Yaw / Pitch / Roll）精确定位病害的真实 GPS 坐标
     *
     * 坐标系约定：
     *   相机坐标系：x=右, y=下, z=前（标准光学坐标系）
     *   世界坐标系：NED（North-East-Down）
     *
     * @param droneLng  无人机当前经度
     * @param droneLat  无人机当前纬度
     * @param droneYaw  无人机航向角 (0=北, 90=东, 180=南, 270=西)，单位：度
     * @param pitch     相机俯仰角 (0=水平向前, -90=垂直朝下)，单位：度
     * @param roll      相机横滚角 (0=水平, 正值=右倾)，单位：度
     * @param altitude  飞行高度（相对地面，单位：米）
     * @param fov       相机水平视角（单位：度）
     * @param imgWidth  图片宽度（像素）
     * @param imgHeight 图片高度（像素）
     * @param bbox      病害检测框 [x1, y1, x2, y2]，像素坐标
     * @return double[] {经度, 纬度}
     */
    public static double[] calculateRealGps(
            double droneLng, double droneLat,
            double droneYaw, double pitch, double roll,
            double altitude, double fov,
            int imgWidth, int imgHeight,
            List<Double> bbox) {

        // Step 1. 计算焦距（像素单位）
        double focalLength = (imgWidth / 2.0) / Math.tan(Math.toRadians(fov / 2.0));

        // Step 2. 求 BBox 中心的像素坐标，转换到以图像中心为原点的相机坐标系
        //   相机坐标系：x=右, y=下, z=前
        double bboxCenterX = (bbox.get(0) + bbox.get(2)) / 2.0;
        double bboxCenterY = (bbox.get(1) + bbox.get(3)) / 2.0;

        // 归一化射线向量（相机坐标系，未旋转）
        double rcx = bboxCenterX - imgWidth  / 2.0;   // x: 向右为正
        double rcy = bboxCenterY - imgHeight / 2.0;   // y: 向下为正
        double rcz = focalLength;                      // z: 朝前为正

        // Step 3. 构建旋转矩阵 R = R_yaw * R_pitch * R_roll
        //
        //   施转顺序（内旋，ZYX）：先 Roll（绕相机Z轴），再 Pitch（绕X轴），再 Yaw（绕世界Z轴）
        //   目标：将相机坐标系下的射线旋转到世界 NED 坐标系
        //
        //   角度符号约定：
        //     Pitch: 相机朝下为负（-90° = 垂直向下）
        //     Roll:  右倾为正
        //     Yaw:   顺时针为正（0=北, 90=东）
        double yawRad   = Math.toRadians(droneYaw);
        double pitchRad = Math.toRadians(pitch);
        double rollRad  = Math.toRadians(roll);

        double cosY = Math.cos(yawRad),   sinY = Math.sin(yawRad);
        double cosP = Math.cos(pitchRad), sinP = Math.sin(pitchRad);
        double cosR = Math.cos(rollRad),  sinR = Math.sin(rollRad);

        // R_roll（绕 Z 轴旋转，相机自身横滚）
        //   [cosR  -sinR  0]
        //   [sinR   cosR  0]
        //   [0      0     1]
        double r1x = rcx * cosR - rcy * sinR;
        double r1y = rcx * sinR + rcy * cosR;
        double r1z = rcz;

        // R_pitch（相机朝下 pitch 为负）
        //   [1   0      0  ]
        //   [0   cosP  -sinP]
        //   [0   sinP   cosP]
        double r2x = r1x;
        double r2y = r1y * cosP - r1z * sinP;
        double r2z = r1y * sinP + r1z * cosP;

        // R_yaw（绕 NED 的 Down 轴 / 世界 Z 轴旋转，顺时针为正）
        //   NED 下顺时针 Yaw：
        //   North =  r2z * cosY + r2x * sinY   （相机前方 z 投影到北）
        //   East  =  r2z * sinY - r2x * cosY
        //   Down  =  r2y                        （y 朝下保持不变）
        double worldNorth = r2z * cosY - r2x * sinY;  // NED: North 分量
        double worldEast  = r2z * sinY + r2x * cosY;  // NED: East  分量
        double worldDown  = r2y;                      // NED: Down  分量（向下为正）

        // Step 4. 射线与地面求交
        //   参数方程：P = dronePos + t * rayWorld
        //   地面条件：dronePos.down + t * worldDown = altitude  =>  t = altitude / worldDown
        if (worldDown <= 0) {
            throw new IllegalArgumentException(
                    "当前姿态下射线未朝向地面（worldDown=" + worldDown + "），无法与地面相交。" +
                    "请检查 Pitch/Roll 角度是否合理。"
            );
        }

        double t = altitude / worldDown;

        double realNorthOffset = t * worldNorth;  // 单位：米，向北为正
        double realEastOffset  = t * worldEast;   // 单位：米，向东为正

        // Step 5. 米偏移转换为经纬度偏移
        double deltaLat = (realNorthOffset / EARTH_RADIUS) * (180.0 / Math.PI);
        double deltaLng = (realEastOffset  / (EARTH_RADIUS * Math.cos(Math.toRadians(droneLat))))
                          * (180.0 / Math.PI);

        return new double[]{ droneLng + deltaLng, droneLat + deltaLat };
    }
}
