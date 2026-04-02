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

                // 1. 获取主路名
                String roadName = "未知路段";
                cn.hutool.json.JSONArray roads = regeocode.getJSONArray("roads");
                if (roads != null && !roads.isEmpty()) {
                    roadName = roads.getJSONObject(0).getStr("name");
                }
                roadInfo.put("roadName", roadName);

                String detailLocation = "";

                // 第一优先级：交叉路口
                cn.hutool.json.JSONArray roadinters = regeocode.getJSONArray("roadinters");
                if (roadinters != null && !roadinters.isEmpty()) {
                    cn.hutool.json.JSONObject inter = roadinters.getJSONObject(0);
                    detailLocation = String.format("%s (距【与%s交叉口】向%s %s米)",
                            inter.getStr("first_name"), inter.getStr("second_name"),
                            inter.getStr("direction"), inter.getStr("distance"));
                }
                // 第二优先级：AOI 区域
                else if (regeocode.getJSONArray("aois") != null && !regeocode.getJSONArray("aois").isEmpty()) {
                    cn.hutool.json.JSONObject aoi = regeocode.getJSONArray("aois").getJSONObject(0);
                    detailLocation = String.format("%s (位于【%s】附近约 %s米)",
                            roadName, aoi.getStr("name"), aoi.getStr("distance"));
                }
                // 第三优先级：POI 点
                else if (regeocode.getJSONArray("pois") != null && !regeocode.getJSONArray("pois").isEmpty()) {
                    cn.hutool.json.JSONObject poi = regeocode.getJSONArray("pois").getJSONObject(0);
                    detailLocation = String.format("%s (距【%s】约 %s米)",
                            roadName, poi.getStr("name"), poi.getStr("distance"));
                }
                // 第四优先级
                else {
                    detailLocation = regeocode.getStr("formatted_address");
                }

                roadInfo.put("detail", detailLocation);
                roadInfo.put("address", regeocode.getStr("formatted_address"));
            } else {
                log.error("高德 API 报错，状态码: {}, 错误信息: {}", jsonObj.getStr("infocode"), jsonObj.getStr("info"));
            }
        } catch (Exception e) {
            log.error("调用高德逆地理编码网络异常: {}", e.getMessage());
        }
        return roadInfo;
    }
}