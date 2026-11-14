-- Выполнить в базе снабжения каждого сайта.
-- user_id: users.id в базе авторизации; company_id: counterparties.id в базе справочников.
CREATE TABLE IF NOT EXISTS `user_company_positions` (
  `user_id` VARCHAR(36) NOT NULL,
  `company_id` VARCHAR(36) NOT NULL,
  `position` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  KEY `ix_user_company_positions_company_id` (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
