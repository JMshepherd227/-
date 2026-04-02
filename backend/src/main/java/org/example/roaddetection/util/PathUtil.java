package org.example.roaddetection.util;

public class PathUtil {
    /**
     * 从绝对路径中提取相对路径
     */
    public static String extractRelativePath(String path, String keyword) {
        if (path == null || path.isBlank()) {
            throw new IllegalArgumentException("路径不能为空");
        }
        int index = path.indexOf(keyword);
        if (index == -1) {
            throw new IllegalArgumentException(
                    "路径 [" + path + "] 中未找到关键字 [" + keyword + "]，请检查目录配置是否正确");
        }
        return path.substring(index);
    }
}
