-- База данных: `supply_service`
-- Выполнение работы: какой подрядчик выполнил
ALTER TABLE `estimate_work_progress`
  ADD COLUMN `contractor_id` char(36) DEFAULT NULL AFTER `quantity`,
  ADD KEY `contractor_id` (`contractor_id`);
