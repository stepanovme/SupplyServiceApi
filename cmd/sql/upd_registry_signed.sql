-- База данных: `supply_service`
-- УПД: признак «подписан / не подписан»
ALTER TABLE `upd_registry`
  ADD COLUMN `is_signed` tinyint(1) NOT NULL DEFAULT 0 AFTER `comment`,
  ADD COLUMN `signed_at` datetime DEFAULT NULL AFTER `is_signed`,
  ADD COLUMN `signed_by` char(36) DEFAULT NULL AFTER `signed_at`,
  ADD KEY `is_signed` (`is_signed`);
