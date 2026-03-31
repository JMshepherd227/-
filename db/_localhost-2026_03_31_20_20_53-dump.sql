-- MySQL dump 10.13  Distrib 8.0.40, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: drone_inspection
-- ------------------------------------------------------
-- Server version	8.0.40

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `defect_detail`
--

DROP TABLE IF EXISTS `defect_detail`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `defect_detail` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `image_id` bigint NOT NULL COMMENT '所属抓拍图片ID',
  `defect_type` varchar(50) NOT NULL COMMENT '病害类型',
  `confidence` double NOT NULL COMMENT 'AI置信度',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `entity_id` bigint DEFAULT NULL COMMENT '关联的实体ID',
  `bbox` varchar(255) DEFAULT NULL COMMENT '检测框坐标 [x1, y1, x2, y2]',
  `feature_vector` text COMMENT '特征向量(Base64或JSON存储)',
  `road_name` varchar(100) DEFAULT NULL COMMENT '所属路段/街道名称',
  `address` varchar(255) DEFAULT NULL COMMENT '完整物理地址',
  `address_detail` varchar(255) DEFAULT NULL COMMENT '病害相对路段位置',
  PRIMARY KEY (`id`),
  KEY `idx_image_id` (`image_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='病害详情表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `defect_detail`
--

LOCK TABLES `defect_detail` WRITE;
/*!40000 ALTER TABLE `defect_detail` DISABLE KEYS */;
/*!40000 ALTER TABLE `defect_detail` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `defect_entity`
--

DROP TABLE IF EXISTS `defect_entity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `defect_entity` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `defect_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '病害类型',
  `lng` double NOT NULL COMMENT '经度(聚合后的中心点)',
  `lat` double NOT NULL COMMENT '纬度(聚合后的中心点)',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'ACTIVE' COMMENT '状态: 待维修/已修复',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `defect_entity`
--

LOCK TABLES `defect_entity` WRITE;
/*!40000 ALTER TABLE `defect_entity` DISABLE KEYS */;
/*!40000 ALTER TABLE `defect_entity` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `drone_device`
--

DROP TABLE IF EXISTS `drone_device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `drone_device` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `drone_name` varchar(50) NOT NULL COMMENT '无人机编号',
  `status` tinyint NOT NULL DEFAULT '0' COMMENT '状态: 0-空闲, 1-任务中, 2-维护中',
  `last_lng` double DEFAULT NULL COMMENT '最后上报经度',
  `last_lat` double DEFAULT NULL COMMENT '最后上报纬度',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='无人机设备表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `drone_device`
--

LOCK TABLES `drone_device` WRITE;
/*!40000 ALTER TABLE `drone_device` DISABLE KEYS */;
INSERT INTO `drone_device` VALUES (1,'大疆M300-测试01',0,NULL,NULL,'2026-03-04 11:06:07','2026-03-04 11:06:07'),(2,'string',0,NULL,NULL,'2026-03-25 23:24:19','2026-03-25 23:24:19');
/*!40000 ALTER TABLE `drone_device` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inspection_image`
--

DROP TABLE IF EXISTS `inspection_image`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspection_image` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `task_id` bigint NOT NULL COMMENT '所属任务ID',
  `drone_id` bigint NOT NULL COMMENT '拍摄无人机ID',
  `original_image_url` varchar(255) NOT NULL COMMENT '原始图片URL',
  `result_image_url` varchar(255) DEFAULT NULL COMMENT '处理后图片URL',
  `raw_lng` double NOT NULL COMMENT '原始经度',
  `raw_lat` double NOT NULL COMMENT '原始纬度',
  `matched_lng` double DEFAULT NULL COMMENT '纠偏后经度',
  `matched_lat` double DEFAULT NULL COMMENT '纠偏后纬度',
  `is_defect` tinyint NOT NULL DEFAULT '0' COMMENT '是否包含病害: 0-无, 1-有',
  `defect_count` int NOT NULL DEFAULT '0' COMMENT '病害数量',
  `capture_time` datetime NOT NULL COMMENT '拍摄时间',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `status` varchar(50) DEFAULT NULL,
  `error_msg` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_location` (`matched_lng`,`matched_lat`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='无人机抓拍记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inspection_image`
--

LOCK TABLES `inspection_image` WRITE;
/*!40000 ALTER TABLE `inspection_image` DISABLE KEYS */;
/*!40000 ALTER TABLE `inspection_image` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inspection_task`
--

DROP TABLE IF EXISTS `inspection_task`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspection_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `task_name` varchar(100) NOT NULL COMMENT '任务名称',
  `drone_id` bigint DEFAULT NULL COMMENT '绑定的无人机ID',
  `route_points` json DEFAULT NULL COMMENT '前端规划的航线点位(JSON数组)',
  `status` tinyint NOT NULL DEFAULT '0' COMMENT '状态: 0-未开始, 1-执行中, 2-已完成',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `defect_count` int NOT NULL DEFAULT '0' COMMENT '病害数量',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='巡检任务表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inspection_task`
--

LOCK TABLES `inspection_task` WRITE;
/*!40000 ALTER TABLE `inspection_task` DISABLE KEYS */;
INSERT INTO `inspection_task` VALUES (10,'南校区主干道AI巡检测试',1,NULL,0,'2026-03-05 00:51:29','2026-03-31 20:14:02',27),(11,'string',1,'[{\"lag\": 114514.0, \"lng\": 114514.0}]',2,'2026-03-25 23:26:30','2026-03-25 23:26:30',0);
/*!40000 ALTER TABLE `inspection_task` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-31 20:20:53
