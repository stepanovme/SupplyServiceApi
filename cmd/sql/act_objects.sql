-- База данных: `supply_service`
-- Несколько объектов у акта (как contract_object у договоров и letter_objects у писем).
-- Колонки acts.object_id / acts.object_type остаются: в них хранится «основной» (первый) объект.
CREATE TABLE `act_objects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `act_id` int NOT NULL,
  `object_id` char(36) NOT NULL,
  `object_type` enum('object','object_levels_id') NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_act_objects` (`act_id`,`object_id`,`object_type`),
  KEY `object_id` (`object_id`),
  CONSTRAINT `act_objects_act_fk` FOREIGN KEY (`act_id`) REFERENCES `acts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Перенос существующих одиночных объектов актов в новую таблицу
INSERT IGNORE INTO `act_objects` (`act_id`, `object_id`, `object_type`, `created_at`, `created_by`)
SELECT `id`, `object_id`, `object_type`, `created_at`, `created_by`
FROM `acts`
WHERE `object_id` IS NOT NULL AND `object_id` <> '' AND `object_type` IS NOT NULL;
