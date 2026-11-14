-- База данных: `supply_service`
-- Дата письма (дата на самом письме; не путать с created_at - когда письмо добавлено в программу).
ALTER TABLE `letter`
  ADD COLUMN `date` date DEFAULT NULL AFTER `name`,
  ADD KEY `date` (`date`);
