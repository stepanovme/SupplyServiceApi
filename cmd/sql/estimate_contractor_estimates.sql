-- База данных: `supply_service`
-- Сметы подрядчиков: отдельные сметы (kind = 'contractor') со своим исполнителем, договором и статусом утверждения.
-- Заменяют расценки подрядчика по основной смете; акты с подрядчиком строятся по такой смете.
ALTER TABLE `estimates`
  ADD COLUMN `kind` enum('main','contractor') NOT NULL DEFAULT 'main',
  ADD COLUMN `executor_id` char(36) DEFAULT NULL,
  ADD COLUMN `contract_id` int DEFAULT NULL,
  ADD COLUMN `approval_status` enum('pending','approved') NOT NULL DEFAULT 'pending',
  ADD COLUMN `approved_at` datetime DEFAULT NULL,
  ADD COLUMN `approved_by` char(36) DEFAULT NULL,
  ADD KEY `kind_executor` (`kind`,`executor_id`);
-- Старые таблицы estimate_contractor_rates / estimate_contractor_rate_items больше не используются кодом; данные в них сохранены.
