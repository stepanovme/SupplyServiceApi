-- База данных: `reference_service`

CREATE TABLE `object_groups` (
  `id` char(36) NOT NULL,
  `name` varchar(255) NOT NULL,
  `main_object_id` char(36) NOT NULL,
  `comment` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_object_groups_main_object` (`main_object_id`),
  KEY `created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Объект входит максимум в одну группу (uq на object_id)
CREATE TABLE `object_group_members` (
  `id` int NOT NULL AUTO_INCREMENT,
  `group_id` char(36) NOT NULL,
  `object_id` char(36) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_object_group_members_object` (`object_id`),
  KEY `group_id` (`group_id`),
  CONSTRAINT `fk_object_group_members_group` FOREIGN KEY (`group_id`) REFERENCES `object_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
