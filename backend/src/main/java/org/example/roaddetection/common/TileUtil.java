package org.example.roaddetection.common;

public class TileUtil {

    public static TileBBox tileToBBox(int z, int x, int y) {

        double n = Math.pow(2, z);

        double minLng = x / n * 360.0 - 180.0;
        double maxLng = (x + 1) / n * 360.0 - 180.0;

        double maxLat = tile2lat(y, z);
        double minLat = tile2lat(y + 1, z);

        return new TileBBox(minLat, maxLat, minLng, maxLng);
    }

    private static double tile2lat(int y, int z) {
        double n = Math.PI - (2.0 * Math.PI * y) / Math.pow(2, z);

        return Math.toDegrees(Math.atan(Math.sinh(n)));
    }
}
