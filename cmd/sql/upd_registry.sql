-- База данных: `supply_service`
-- Реестр УПД (по аналогии с договорами и актами). Не путать с upd_documents - это складские УПД с позициями.

CREATE TABLE `upd_registry` (
  `id` int NOT NULL AUTO_INCREMENT,
  `num` varchar(100) DEFAULT NULL,
  `date` date DEFAULT NULL,
  `sum` double(17,2) DEFAULT NULL,
  `buyer_id` char(36) DEFAULT NULL,       -- Покупатель
  `seller_id` char(36) DEFAULT NULL,      -- Продавец
  `shipper_id` char(36) DEFAULT NULL,     -- Грузоотправитель
  `consignee_id` char(36) DEFAULT NULL,   -- Грузополучатель
  `comment` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `date` (`date`),
  KEY `buyer_id` (`buyer_id`),
  KEY `seller_id` (`seller_id`),
  KEY `shipper_id` (`shipper_id`),
  KEY `consignee_id` (`consignee_id`),
  KEY `created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `upd_registry_objects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `upd_id` int NOT NULL,
  `object_id` char(36) NOT NULL,
  `object_type` enum('object','object_levels_id') NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_upd_registry_objects` (`upd_id`,`object_id`,`object_type`),
  KEY `object_id` (`object_id`),
  CONSTRAINT `upd_registry_objects_fk` FOREIGN KEY (`upd_id`) REFERENCES `upd_registry` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `upd_registry_user_roles` (
  `id` char(36) NOT NULL,
  `upd_id` int NOT NULL,
  `user_id` char(36) NOT NULL,
  `role` enum('creator','executor','co-executor','observer') NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `upd_id` (`upd_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `upd_registry_user_roles_fk` FOREIGN KEY (`upd_id`) REFERENCES `upd_registry` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `upd_registry_statuses` (
  `id` char(36) NOT NULL,
  `upd_id` int NOT NULL,
  `status_id` char(36) NOT NULL,
  `created_by` char(36) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `upd_id` (`upd_id`),
  CONSTRAINT `upd_registry_statuses_fk` FOREIGN KEY (`upd_id`) REFERENCES `upd_registry` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `upd_registry_folders` (
  `id` char(36) NOT NULL,
  `upd_id` int NOT NULL,
  `name` text NOT NULL,
  `parent_id` char(36) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `upd_id` (`upd_id`),
  KEY `parent_id` (`parent_id`),
  CONSTRAINT `upd_registry_folders_fk` FOREIGN KEY (`upd_id`) REFERENCES `upd_registry` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `upd_registry_files` (
  `id` char(36) NOT NULL,
  `upd_id` int NOT NULL,
  `original_name` text NOT NULL,
  `storage_name` text NOT NULL,
  `extension` varchar(100) NOT NULL,
  `file_path` text NOT NULL,
  `type` enum('original','version') NOT NULL DEFAULT 'original',
  `uploaded_by` char(36) NOT NULL,
  `uploaded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `folder_id` char(36) DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `upd_id` (`upd_id`),
  KEY `folder_id` (`folder_id`),
  CONSTRAINT `upd_registry_files_fk` FOREIGN KEY (`upd_id`) REFERENCES `upd_registry` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `upd_registry_logs` (
  `id` char(36) NOT NULL,
  `upd_id` int NOT NULL,
  `user_id` char(36) NOT NULL,
  `message` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `upd_id` (`upd_id`,`created_at`),
  CONSTRAINT `upd_registry_logs_fk` FOREIGN KEY (`upd_id`) REFERENCES `upd_registry` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- права доступа к документам (document_access_settings) знают и про УПД
ALTER TABLE `document_access_settings`
  MODIFY COLUMN `document_type` enum('contract','act','letter_outgoing','letter_incoming','document','upd') NOT NULL;
