-- База данных: `supply_service`
-- Тайный Санта: участники и результаты розыгрыша (каждый дарит одному и получает от одного)
CREATE TABLE `secret_santa_participants` (
  `user_id` char(36) NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `secret_santa_draws` (
  `id` int NOT NULL AUTO_INCREMENT,
  `giver_id` char(36) NOT NULL,
  `receiver_id` char(36) NOT NULL,
  `drawn_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `giver_id` (`giver_id`),
  UNIQUE KEY `receiver_id` (`receiver_id`),
  CONSTRAINT `secret_santa_draws_giver_fk` FOREIGN KEY (`giver_id`) REFERENCES `secret_santa_participants` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `secret_santa_draws_receiver_fk` FOREIGN KEY (`receiver_id`) REFERENCES `secret_santa_participants` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `secret_santa_no_self` CHECK (`giver_id` <> `receiver_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
