-- База данных: `supply_service`
-- Сметы: смета -> разделы -> работы -> ресурсы; графики работ (несколько периодов у одной работы)
CREATE TABLE `estimates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `status` enum('draft','planning','in_progress','completed') NOT NULL DEFAULT 'draft',
  `object_id` char(36) DEFAULT NULL,
  `object_type` enum('object','object_levels_id') DEFAULT NULL,
  `comment` text,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `status` (`status`),
  KEY `object_id` (`object_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `estimate_sections` (
  `id` int NOT NULL AUTO_INCREMENT,
  `estimate_id` int NOT NULL,
  `position` int NOT NULL,
  `name` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `estimate_id` (`estimate_id`,`position`),
  CONSTRAINT `estimate_sections_fk` FOREIGN KEY (`estimate_id`) REFERENCES `estimates` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `estimate_works` (
  `id` int NOT NULL AUTO_INCREMENT,
  `section_id` int NOT NULL,
  `position` int NOT NULL,
  `name` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `section_id` (`section_id`,`position`),
  CONSTRAINT `estimate_works_fk` FOREIGN KEY (`section_id`) REFERENCES `estimate_sections` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `estimate_work_periods` (
  `id` int NOT NULL AUTO_INCREMENT,
  `work_id` int NOT NULL,
  `date_from` date NOT NULL,
  `date_to` date NOT NULL,
  PRIMARY KEY (`id`),
  KEY `work_id` (`work_id`,`date_from`),
  CONSTRAINT `estimate_work_periods_fk` FOREIGN KEY (`work_id`) REFERENCES `estimate_works` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `estimate_resources` (
  `id` int NOT NULL AUTO_INCREMENT,
  `work_id` int NOT NULL,
  `position` int NOT NULL,
  `type` enum('material','machine','overhead','labor','profit') NOT NULL,
  `name` varchar(255) NOT NULL,
  `contractor_id` char(36) DEFAULT NULL,
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit_name` varchar(50) DEFAULT NULL,
  `unit_price` decimal(18,2) NOT NULL DEFAULT 0,
  `markup_percent` decimal(9,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `work_id` (`work_id`,`position`),
  KEY `contractor_id` (`contractor_id`),
  CONSTRAINT `estimate_resources_fk` FOREIGN KEY (`work_id`) REFERENCES `estimate_works` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
