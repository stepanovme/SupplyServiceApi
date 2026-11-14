-- База данных: `supply_service`
-- Категории чеков (отдельно от складского справочника warehouse_category).
--   owner_user_id IS NULL     - стандартная категория, доступна всем (создаёт/меняет администратор)
--   owner_user_id = <user id> - личная категория, видна и доступна только её владельцу
CREATE TABLE `receipt_categories` (
  `id` char(36) NOT NULL,
  `name` varchar(100) NOT NULL,
  `color` varchar(7) DEFAULT NULL,
  `owner_user_id` varchar(36) DEFAULT NULL,
  -- для уникальности имени внутри своей области (NULL в UNIQUE-индексе не сравнивается)
  `scope_key` varchar(36) GENERATED ALWAYS AS (ifnull(`owner_user_id`,'')) STORED,
  `created_by` varchar(36) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_receipt_categories_scope_name` (`scope_key`,`name`),
  KEY `owner_user_id` (`owner_user_id`)
  -- внешнего ключа на users нет: MySQL не допускает CASCADE на колонке, от которой зависит scope_key
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Чеки теперь ссылаются на receipt_categories, а не на warehouse_category (привязок на момент смены не было)
ALTER TABLE `purchase_receipt_categories` DROP FOREIGN KEY `purchase_receipt_categories_category_fk`;
ALTER TABLE `purchase_receipt_categories`
  ADD CONSTRAINT `purchase_receipt_categories_rc_fk` FOREIGN KEY (`category_id`) REFERENCES `receipt_categories` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
