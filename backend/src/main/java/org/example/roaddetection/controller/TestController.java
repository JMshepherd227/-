package org.example.roaddetection.controller;

import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.multipart.MultipartFile;
import reactor.core.publisher.Mono;

import java.io.IOException;

@RestController
@RequestMapping("/test")
public class TestController {

    private final WebClient webClient = WebClient.builder()
            .baseUrl("http://127.0.0.1:8000")
            .build();

    @GetMapping("/hello")
    public String hello() {
        return "Spring Boot OK";
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<String> upload(
            @RequestPart("file") MultipartFile file,
            @RequestParam("longitude") double longitude,
            @RequestParam("latitude") double latitude
    ) throws IOException {

        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("file", file.getResource());
        builder.part("longitude", String.valueOf(longitude));
        builder.part("latitude", String.valueOf(latitude));

        return webClient.post()
                .uri("/predict/")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(builder.build())
                .retrieve()
                .bodyToMono(String.class);
    }
}