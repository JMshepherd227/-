package org.example.roaddetection.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/result/**")
                .addResourceLocations("file:D:/work(work only)/python/UAVRoadDetection/result/");

        registry.addResourceHandler("/origin/**")
                .addResourceLocations("file:D:/work(work only)/python/UAVRoadDetection/origin/");
    }
}
