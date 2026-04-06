package org.example.roaddetection.util;
import java.util.Arrays;
import java.util.List;

public class HomographyUtil {
    /**
     * 使用 3x3 单应性矩阵，将图 A 的 BBox 投影到图 B 中
     *
     * @param bbox 图A的病害框 [xmin, ymin, xmax, ymax]
     * @param H    Python端返回的 3x3 单应性矩阵
     * @return 投影后在图B的新病害框 [new_xmin, new_ymin, new_xmax, new_ymax]
     */
    public static List<Double> projectBbox(List<Double> bbox, double[][] H) {
        double x1 = bbox.get(0);
        double y1 = bbox.get(1);
        double x2 = bbox.get(2);
        double y2 = bbox.get(3);

        // BBox 的四个顶点 (x, y)
        double[][] corners = {
                {x1, y1},
                {x2, y1},
                {x2, y2},
                {x1, y2}
        };

        double minX = Double.MAX_VALUE;
        double minY = Double.MAX_VALUE;
        double maxX = -Double.MAX_VALUE;
        double maxY = -Double.MAX_VALUE;

        // 对四个顶点分别执行矩阵乘法 (透视变换)
        for (double[] pt : corners) {
            double x = pt[0];
            double y = pt[1];

            // 矩阵相乘： [x', y', w']^T = H * [x, y, 1]^T
            double newX = H[0][0] * x + H[0][1] * y + H[0][2];
            double newY = H[1][0] * x + H[1][1] * y + H[1][2];
            double w    = H[2][0] * x + H[2][1] * y + H[2][2];

            // 归一化 (除以 w)
            newX = newX / w;
            newY = newY / w;

            minX = Math.min(minX, newX);
            minY = Math.min(minY, newY);
            maxX = Math.max(maxX, newX);
            maxY = Math.max(maxY, newY);
        }

        return Arrays.asList(minX, minY, maxX, maxY);
    }

    /**
     * 计算两个 BBox 的交并比 (IoU)
     *
     * @param boxA BBox A, 格式: [xmin, ymin, xmax, ymax]
     * @param boxB BBox B, 格式: [xmin, ymin, xmax, ymax]
     * @return 交并比值，范围 [0.0, 1.0]
     */
    public static double calculateIou(List<Double> boxA, List<Double> boxB) {
        if (boxA == null || boxA.size() < 4 || boxB == null || boxB.size() < 4) {
            return 0.0;
        }

        // 1. 获取两个框的坐标
        double x1A = boxA.get(0);
        double y1A = boxA.get(1);
        double x2A = boxA.get(2);
        double y2A = boxA.get(3);

        double x1B = boxB.get(0);
        double y1B = boxB.get(1);
        double x2B = boxB.get(2);
        double y2B = boxB.get(3);

        // 2. 计算交集区域 (Intersection) 的左上角和右下角坐标
        double interX1 = Math.max(x1A, x1B);
        double interY1 = Math.max(y1A, y1B);
        double interX2 = Math.min(x2A, x2B);
        double interY2 = Math.min(y2A, y2B);

        // 3. 计算交集面积 (如果两个框不相交，宽或高会小于0，所以要和0取最大值)
        double interWidth = Math.max(0.0, interX2 - interX1);
        double interHeight = Math.max(0.0, interY2 - interY1);
        double interArea = interWidth * interHeight;

        // 如果没有交集，直接返回 0
        if (interArea == 0) {
            return 0.0;
        }

        // 4. 计算两个框各自的面积
        double areaA = (x2A - x1A) * (y2A - y1A);
        double areaB = (x2B - x1B) * (y2B - y1B);

        // 5. 计算并集面积 (Union)
        double unionArea = areaA + areaB - interArea;

        // 6. 计算 IoU (加上 1e-6 防止除以 0 的极端异常)
        return interArea / (unionArea + 1e-6);
    }
}
