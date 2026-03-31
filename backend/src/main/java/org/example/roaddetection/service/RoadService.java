package org.example.roaddetection.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class RoadService {

    @Value("${amap.key}")
    private String AMAP_WEB_KEY;

    public Map<String, String> getRoadInfoFromAmap(Double lng, Double lat) {
        Map<String, String> roadInfo = new java.util.HashMap<>();
        roadInfo.put("roadName", "未知路段");
        roadInfo.put("address", "未知地址");
        roadInfo.put("detail", "未知位置");

        try {
            String url = "https://restapi.amap.com/v3/geocode/regeo?location="
                         + lng + "," + lat
                         + "&key=" + AMAP_WEB_KEY
                         + "&radius=200&extensions=all";

            String response = cn.hutool.http.HttpUtil.get(url, 3000);

            log.info("坐标[{},{}] 请求高德，返回结果: {}", lng, lat, response);

            cn.hutool.json.JSONObject jsonObj = cn.hutool.json.JSONUtil.parseObj(response);

            if ("1".equals(jsonObj.getStr("status"))) {
                cn.hutool.json.JSONObject regeocode = jsonObj.getJSONObject("regeocode");

                String formattedAddress = regeocode.getStr("formatted_address");
                roadInfo.put("address", formattedAddress);

                cn.hutool.json.JSONArray roads = regeocode.getJSONArray("roads");
                String bestRoadName = "未知路段";
                if (roads != null && !roads.isEmpty()) {
                    cn.hutool.json.JSONObject nearestRoad = roads.getJSONObject(0);
                    bestRoadName = nearestRoad.getStr("name");
                } else {
                    cn.hutool.json.JSONObject addressComponent = regeocode.getJSONObject("addressComponent");
                    cn.hutool.json.JSONObject streetNumber = addressComponent.getJSONObject("streetNumber");
                    if (streetNumber != null && cn.hutool.core.util.StrUtil.isNotBlank(streetNumber.getStr("street"))) {
                        bestRoadName = streetNumber.getStr("street");
                    }
                }
                roadInfo.put("roadName", bestRoadName);

                cn.hutool.json.JSONArray crosses = regeocode.getJSONArray("roadinters");
                if (crosses != null && !crosses.isEmpty()) {
                    cn.hutool.json.JSONObject nearestCross = crosses.getJSONObject(0);
                    String firstName = nearestCross.getStr("first_name");
                    String secondName = nearestCross.getStr("second_name");
                    String distance = nearestCross.getStr("distance");
                    String direction = nearestCross.getStr("direction");

                    String exactLocation = String.format("%s (距【与%s交叉口】向%s %s米)",
                            firstName, secondName, direction, distance);
                    roadInfo.put("detail", exactLocation);
                } else {
                    roadInfo.put("detail", bestRoadName);
                }
            } else {
                log.error("高德 API 报错，状态码: {}, 错误信息: {}", jsonObj.getStr("infocode"), jsonObj.getStr("info"));
            }
        } catch (Exception e) {
            log.error("调用高德逆地理编码网络异常: {}", e.getMessage());
        }
        return roadInfo;
    }
}