package org.example.roaddetection.util;

import java.util.List;

public class GpsOffsetUtil {

    // 地球半径 (米)
    private static final double EARTH_RADIUS = 6378137.0;

    /**
     * 根据 BBox 二次定位病害的真实 GPS 坐标
     *
     * @param droneLng      无人机当前经度
     * @param droneLat      无人机当前纬度
     * @param droneYaw      无人机航向角 (0=北, 90=东, 180=南, 270=西)
     * @param altitude      飞行高度 (米) - 用于估算 1 像素代表几米
     * @param fov           无人机水平视角场
     * @param imgWidth      图片宽度 (像素)
     * @param imgHeight     图片高度 (像素)
     * @param bbox          病害的框 [x1, y1, x2, y2]
     * @return double[]     包含修正后的 [真实经度, 真实纬度]
     */
    public static double[] calculateRealGps(
            Double droneLng, Double droneLat, Double droneYaw, Double altitude, Double fov,
            int imgWidth, int imgHeight, List<Float> bbox) {

        // 1. GSD 计算
        double viewWidthMeters = 2.0 * altitude * Math.tan(Math.toRadians(fov / 2.0));
        double gsd = viewWidthMeters / (double) imgWidth;

        // 2. 计算 BBox 中心点坐标
        double bboxCenterX = (bbox.get(0) + bbox.get(2)) / 2.0;
        double bboxCenterY = (bbox.get(1) + bbox.get(3)) / 2.0;

        // 3. 计算相对于图片中心点的像素偏移量
        double deltaXPx = bboxCenterX - (imgWidth / 2.0);
        double deltaYPx = bboxCenterY - (imgHeight / 2.0);

        // 4. 将像素偏移转换为物理偏移
        double deltaEastMeters = deltaXPx * gsd;
        double deltaNorthMeters = -deltaYPx * gsd;

        // 5. 结合航向角 Yaw 进行二维旋转矩阵计算
        double yawRad = Math.toRadians(droneYaw);
        double realEastOffset = deltaEastMeters * Math.cos(yawRad) + deltaNorthMeters * Math.sin(yawRad);
        double realNorthOffset = -deltaEastMeters * Math.sin(yawRad) + deltaNorthMeters * Math.cos(yawRad);

        // 6. 将物理偏移(米)转换为经纬度偏移
        double deltaLat = (realNorthOffset / EARTH_RADIUS) * (180.0 / Math.PI);
        double deltaLng = (realEastOffset / (EARTH_RADIUS * Math.cos(Math.toRadians(droneLat)))) * (180.0 / Math.PI);

        return new double[]{droneLng + deltaLng, droneLat + deltaLat};
    }
}
