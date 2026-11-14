-- База данных: `supply_service`
-- Пользовательские реестры документов: реестр -> блоки -> поля (тип, обязательность) -> записи -> значения.

CREATE TABLE `custom_registries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_custom_registries_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `custom_registry_blocks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `registry_id` int NOT NULL,
  `name` varchar(200) NOT NULL,
  `sort_order` int NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `registry_id` (`registry_id`),
  CONSTRAINT `custom_registry_blocks_fk` FOREIGN KEY (`registry_id`) REFERENCES `custom_registries` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `custom_registry_fields` (
  `id` int NOT NULL AUTO_INCREMENT,
  `registry_id` int NOT NULL,
  `block_id` int DEFAULT NULL,
  `field_key` varchar(64) NOT NULL,
  `label` varchar(200) NOT NULL,
  `field_type` enum('text','textarea','number','money','date','boolean','select','multiselect','counterparty','user','object') NOT NULL,
  `required` tinyint(1) NOT NULL DEFAULT 0,
  `multiple` tinyint(1) NOT NULL DEFAULT 0,          -- для counterparty / user / object: можно выбрать несколько
  `options` json DEFAULT NULL,                        -- для select / multiselect: список вариантов
  `show_in_list` tinyint(1) NOT NULL DEFAULT 0,       -- показывать колонкой в списке записей
  `sort_order` int NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_custom_registry_fields_key` (`registry_id`,`field_key`),
  KEY `block_id` (`block_id`),
  CONSTRAINT `custom_registry_fields_reg_fk` FOREIGN KEY (`registry_id`) REFERENCES `custom_registries` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `custom_registry_fields_block_fk` FOREIGN KEY (`block_id`) REFERENCES `custom_registry_blocks` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `custom_registry_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `registry_id` int NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `registry_id` (`registry_id`,`created_at`),
  CONSTRAINT `custom_registry_records_fk` FOREIGN KEY (`registry_id`) REFERENCES `custom_registries` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `custom_registry_values` (
  `id` int NOT NULL AUTO_INCREMENT,
  `record_id` int NOT NULL,
  `field_id` int NOT NULL,
  `value` json DEFAULT NULL,
  `search_text` text DEFAULT NULL,                    -- человекочитаемое значение для поиска
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_custom_registry_values` (`record_id`,`field_id`),
  KEY `field_id` (`field_id`),
  CONSTRAINT `custom_registry_values_rec_fk` FOREIGN KEY (`record_id`) REFERENCES `custom_registry_records` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `custom_registry_values_field_fk` FOREIGN KEY (`field_id`) REFERENCES `custom_registry_fields` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
