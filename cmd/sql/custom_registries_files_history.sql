-- База данных: `supply_service`
-- Пользовательские реестры: файлы записей и история изменений.

CREATE TABLE `custom_registry_files` (
  `id` char(36) NOT NULL,
  `record_id` int NOT NULL,
  `original_name` text NOT NULL,
  `storage_name` text NOT NULL,
  `extension` varchar(100) NOT NULL,
  `file_path` text NOT NULL,
  `size` bigint DEFAULT NULL,
  `uploaded_by` char(36) NOT NULL,
  `uploaded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `record_id` (`record_id`),
  CONSTRAINT `custom_registry_files_fk` FOREIGN KEY (`record_id`) REFERENCES `custom_registry_records` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- record_id без FK: история остаётся после удаления записи; record_id NULL - изменение структуры реестра
CREATE TABLE `custom_registry_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `registry_id` int NOT NULL,
  `record_id` int DEFAULT NULL,
  `user_id` char(36) NOT NULL,
  `action` varchar(50) NOT NULL,
  `message` text NOT NULL,
  `changes` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `registry_id` (`registry_id`,`id`),
  KEY `record_id` (`record_id`,`id`),
  CONSTRAINT `custom_registry_history_fk` FOREIGN KEY (`registry_id`) REFERENCES `custom_registries` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
