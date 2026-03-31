package org.example.roaddetection.Listener;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.roaddetection.entity.DefectDetail;
import org.example.roaddetection.events.RoadInfoUpdateEvent;
import org.example.roaddetection.mapper.DefectDetailMapper;
import org.example.roaddetection.service.RoadService;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class RoadInfoListener {
    private final RoadService roadService;
    private final DefectDetailMapper detailMapper;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleRoadInfoUpdate(RoadInfoUpdateEvent event) {
        log.info("开始后台异步解析路段: ImageId={}", event.imageId());

        Map<String, String> roadInfo = roadService.getRoadInfoFromAmap(event.lng(), event.lat());

        LambdaUpdateWrapper<DefectDetail> updateWrapper = new LambdaUpdateWrapper<>();
        updateWrapper.eq(DefectDetail::getImageId, event.imageId())
                .set(DefectDetail::getRoadName, roadInfo.get("roadName"))
                .set(DefectDetail::getAddress, roadInfo.get("address"))
                .set(DefectDetail::getAddressDetail, roadInfo.get("detail"));

        detailMapper.update(null, updateWrapper);
        log.info("路段信息补全成功: ImageId={}", event.imageId());
    }
}
