-- База данных: `supply_service`
-- Справочники расценок: отдельно работы и отдельно ресурсы (материалы/механизмы/накладные/люди).
-- Папки вложенные (parent_id), позиции лежат в папке или в корне (folder_id NULL).
CREATE TABLE `price_work_folders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `parent_id` int DEFAULT NULL,
  `name` varchar(255) NOT NULL,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `parent_id` (`parent_id`),
  CONSTRAINT `price_work_folders_fk` FOREIGN KEY (`parent_id`) REFERENCES `price_work_folders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `price_work_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `folder_id` int DEFAULT NULL,
  `code` varchar(100) DEFAULT NULL,
  `name` varchar(500) NOT NULL,
  `unit_name` varchar(50) DEFAULT NULL,
  `price` decimal(18,2) NOT NULL DEFAULT 0,
  `comment` text,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `folder_id` (`folder_id`),
  KEY `name` (`name`(100)),
  CONSTRAINT `price_work_items_fk` FOREIGN KEY (`folder_id`) REFERENCES `price_work_folders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `price_resource_folders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `parent_id` int DEFAULT NULL,
  `name` varchar(255) NOT NULL,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `parent_id` (`parent_id`),
  CONSTRAINT `price_resource_folders_fk` FOREIGN KEY (`parent_id`) REFERENCES `price_resource_folders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `price_resource_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `folder_id` int DEFAULT NULL,
  `type` enum('material','machine','overhead','labor','profit') NOT NULL,
  `code` varchar(100) DEFAULT NULL,
  `name` varchar(500) NOT NULL,
  `unit_name` varchar(50) DEFAULT NULL,
  `price` decimal(18,2) NOT NULL DEFAULT 0,
  `contractor_id` char(36) DEFAULT NULL,
  `comment` text,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `folder_id` (`folder_id`),
  KEY `type` (`type`),
  KEY `contractor_id` (`contractor_id`),
  KEY `name` (`name`(100)),
  CONSTRAINT `price_resource_items_fk` FOREIGN KEY (`folder_id`) REFERENCES `price_resource_folders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
