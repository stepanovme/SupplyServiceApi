-- База данных: `supply_service`
-- Права на пользовательские реестры: кому (пользователь или отдел), на какие реестры (все или выбранные), что можно.
-- Права суммируются: у пользователя действует всё, что дают его правила и правила его отделов. Администратор может всё.
CREATE TABLE `custom_registry_access` (
  `id` char(36) NOT NULL,
  `user_id` char(36) DEFAULT NULL,
  `department_id` int DEFAULT NULL,
  `all_registries` tinyint(1) NOT NULL DEFAULT 0,
  `registry_ids` json DEFAULT NULL,
  `can_create_registries` tinyint(1) NOT NULL DEFAULT 0,   -- создавать новые реестры (не зависит от выбранных реестров)
  `can_view` tinyint(1) NOT NULL DEFAULT 0,                -- видеть реестр и его записи, файлы, историю
  `can_add_records` tinyint(1) NOT NULL DEFAULT 0,
  `can_edit_records` tinyint(1) NOT NULL DEFAULT 0,
  `can_delete_records` tinyint(1) NOT NULL DEFAULT 0,
  `can_manage_files` tinyint(1) NOT NULL DEFAULT 0,        -- загружать и удалять файлы записей
  `can_edit_structure` tinyint(1) NOT NULL DEFAULT 0,      -- менять название, блоки и поля реестра
  `can_delete_registry` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `department_id` (`department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
