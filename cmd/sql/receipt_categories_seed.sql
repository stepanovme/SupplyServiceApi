-- База данных: `supply_service`
-- Запускать с --default-character-set=utf8mb4, иначе кириллица запишется в двойной кодировке:
--   mysql --default-character-set=utf8mb4 ... < receipt_categories_seed.sql
-- Стандартные категории чеков (owner_user_id IS NULL - доступны всем). Скрипт можно запускать повторно:
-- уникальность (scope_key, name) не даёт создать дубли, существующие категории (и их цвета) не меняются.
-- created_by - первый пользователь с ролью администратора.
INSERT IGNORE INTO `receipt_categories` (`id`, `name`, `color`, `owner_user_id`, `created_by`)
SELECT UUID(), v.name, v.color, NULL,
       (SELECT `user_id` FROM `{{DB_NAME}}`.`user_roles` WHERE `role_id` = '697afdbf-4f2e-47fb-8277-7127b9b85317' ORDER BY `user_id` LIMIT 1)
FROM (
  SELECT 'Строительные материалы'   AS name, '#D97706' AS color UNION ALL  -- янтарный
  SELECT 'Инструмент и оснастка',            '#64748B' UNION ALL           -- сланцево-серый
  SELECT 'Крепёж и метизы',                  '#78716C' UNION ALL           -- «металл»
  SELECT 'Электрика и освещение',            '#EAB308' UNION ALL           -- жёлтый
  SELECT 'Сантехника и отопление',           '#0EA5E9' UNION ALL           -- голубой (вода)
  SELECT 'Лакокрасочные материалы',          '#A855F7' UNION ALL           -- фиолетовый (краска)
  SELECT 'Спецодежда и СИЗ',                 '#F97316' UNION ALL           -- сигнальный оранжевый
  SELECT 'Топливо и ГСМ',                    '#EF4444' UNION ALL           -- красный
  SELECT 'Транспорт, такси и парковка',      '#3B82F6' UNION ALL           -- синий
  SELECT 'Командировочные расходы',          '#14B8A6' UNION ALL           -- бирюзовый
  SELECT 'Продукты и питание',               '#22C55E' UNION ALL           -- зелёный
  SELECT 'Хозяйственные товары',             '#06B6D4' UNION ALL           -- циан
  SELECT 'Канцелярия и оргтехника',          '#8B5CF6' UNION ALL           -- сиреневый
  SELECT 'Связь и интернет',                 '#6366F1' UNION ALL           -- индиго
  SELECT 'Аптека и медицина',                '#EC4899' UNION ALL           -- розовый
  SELECT 'Аренда техники и услуги',          '#10B981' UNION ALL           -- изумрудный
  SELECT 'Прочее',                           '#9CA3AF'                     -- нейтральный серый
) AS v;
