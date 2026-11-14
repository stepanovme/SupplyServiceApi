# Чеки — новые и изменившиеся запросы и ответы

Пример собран реальными вызовами API (внешние сервисы подменены, данные откатывались). Префикс `/api/supply`. Пользователи: A — «Степанов С. А.» (владелец), B и C — другие.

Идентификаторы: пользователь A `122d844d-b3be-42d9-8b5b-8a0058edb2d8`, B `06968a8b-e24c-4099-998d-3d4c16ebc63a`, C `145c7704-bf54-47b3-82e9-41954a5ac74c`, бизнес-карта `e173fa88-5054-42f9-b9a1-a8da139d6e84`.

## 1. Создание: новые поля

### 1.1 Вручную: способ оплаты, от кого, для кого, хештеги

Хештеги нормализуются: без `#`, нижний регистр, пробелы → `_`, дубли и пустые убираются. Все новые поля необязательны.

**Запрос** — `POST /api/supply/purchase-receipts`

```json
{
  "purchased_at": "2026-10-20T12:00:00",
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "items": [
    {
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3
    }
  ],
  "payment_method": "cash",
  "from_user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
  "for_user_id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
  "hashtags": [
    "#Командировка",
    "ремонт  кровли",
    "ремонт кровли",
    ""
  ],
  "comment": "Заметка владельца"
}
```

**Ответ** — `201` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 451.5,
  "payment_method": "cash",
  "business_card_id": null,
  "from_user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "for_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "hashtags": [
    "командировка",
    "ремонт_кровли"
  ],
  "comment": "Заметка владельца",
  "comments_count": 0
}
```

### 1.2 Бизнес-карта: способ оплаты ставится сам

**Запрос** — `POST /api/supply/purchase-receipts`

```json
{
  "purchased_at": "2026-10-20T12:00:00",
  "total_sum": 640,
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84"
}
```

**Ответ** — `201` (показаны основные поля)

```json
{
  "id": "cf22577e-5dd6-44e1-b169-e62cedcba37e",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 640.0,
  "payment_method": "business_card",
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "from_user": null,
  "for_user": null,
  "hashtags": [],
  "comment": null,
  "comments_count": 0
}
```

### 1.3 Кредитная карта

**Запрос** — `POST /api/supply/purchase-receipts`

```json
{
  "purchased_at": "2026-10-20T12:00:00",
  "total_sum": 640,
  "payment_method": "credit_card"
}
```

**Ответ** — `201` (показаны основные поля)

```json
{
  "id": "87d664ee-4cb9-41b7-a08e-1ebc4e29f844",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 640.0,
  "payment_method": "credit_card",
  "business_card_id": null,
  "from_user": null,
  "for_user": null,
  "hashtags": [],
  "comment": null,
  "comments_count": 0
}
```

### 1.4 По QR-коду с новыми полями

**Запрос** — `POST /api/supply/purchase-receipts/from-qr`

```json
{
  "qrraw": "t=20261020T1000&s=300.00&fn=9999111122223333&i=55&fp=1&n=1",
  "payment_method": "cash",
  "for_user_id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
  "hashtags": [
    "Продукты"
  ],
  "auto_categorize": false
}
```

**Ответ** — `201` (показаны основные поля)

```json
{
  "id": "1d556ae8-3ebc-4ef2-bd66-32892fcda5a5",
  "source": "qr",
  "purchased_at": "2026-10-20T10:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 300.0,
  "payment_method": "cash",
  "business_card_id": null,
  "from_user": null,
  "for_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "hashtags": [
    "продукты"
  ],
  "comment": null,
  "comments_count": 0
}
```

### 1.5 По фото с новыми полями (multipart)

**Запрос** — `POST /api/supply/purchase-receipts/from-photo`

```bash
curl -X POST "$HOST/api/supply/purchase-receipts/from-photo" -H "Authorization: Bearer $TOKEN" \
  -F "file=@check.jpg" -F "payment_method=credit_card" -F "from_user_id=06968a8b-e24c-4099-998d-3d4c16ebc63a" -F "for_user_id=145c7704-bf54-47b3-82e9-41954a5ac74c" \
  -F "hashtags=#офис" -F "hashtags=канцелярия"
```

**Ответ** — `201` (показаны основные поля)

```json
{
  "id": "dd2807b4-8c6e-4f56-b802-ead818f49e46",
  "source": "photo",
  "purchased_at": "2026-10-20T10:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 300.0,
  "payment_method": "credit_card",
  "business_card_id": null,
  "from_user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "for_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "hashtags": [
    "канцелярия",
    "офис"
  ],
  "comment": null,
  "comments_count": 0
}
```

## 2. Ошибки при создании

### 2.1 Бизнес-карта вместе с наличными

**Запрос** — `POST /api/supply/purchase-receipts`

```json
{
  "purchased_at": "2026-10-20T12:00:00",
  "total_sum": 100,
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "payment_method": "cash"
}
```

**Ответ** — `400`

```json
{
  "detail": "Бизнес-карту можно указать только при способе оплаты business_card"
}
```

### 2.2 Неверный способ оплаты

**Запрос** — `POST /api/supply/purchase-receipts`

```json
{
  "purchased_at": "2026-10-20T12:00:00",
  "total_sum": 100,
  "payment_method": "bitcoin"
}
```

**Ответ** — `422`

```json
{
  "detail": [
    {
      "type": "literal_error",
      "loc": [
        "body",
        "payment_method"
      ],
      "msg": "Input should be 'business_card', 'cash' or 'credit_card'",
      "input": "bitcoin",
      "ctx": {
        "expected": "'business_card', 'cash' or 'credit_card'"
      }
    }
  ]
}
```

### 2.3 Несуществующий пользователь

**Запрос** — `POST /api/supply/purchase-receipts`

```json
{
  "purchased_at": "2026-10-20T12:00:00",
  "total_sum": 100,
  "from_user_id": "no-such-user"
}
```

**Ответ** — `404`

```json
{
  "detail": "Пользователи не найдены: no-such-user"
}
```

## 3. Изменение (PATCH)

### 3.1 Привязать бизнес-карту

Способ оплаты автоматически становится `business_card`.

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

```json
{
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84"
}
```

**Ответ** — `200` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 451.5,
  "payment_method": "business_card",
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "from_user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "for_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "hashtags": [
    "командировка",
    "ремонт_кровли"
  ],
  "comment": "Заметка владельца",
  "comments_count": 0
}
```

### 3.2 Перейти на наличные

Привязка к бизнес-карте снимается.

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

```json
{
  "payment_method": "cash"
}
```

**Ответ** — `200` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 451.5,
  "payment_method": "cash",
  "business_card_id": null,
  "from_user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "for_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "hashtags": [
    "командировка",
    "ремонт_кровли"
  ],
  "comment": "Заметка владельца",
  "comments_count": 0
}
```

### 3.3 Убрать способ оплаты при привязанной карте

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

```json
{
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84"
}
```

**Ответ** — `200` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660"
}
```

### 3.3б Попытка очистить только способ оплаты

Сначала нужно снять карту (`business_card_id: null`).

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

```json
{
  "payment_method": null
}
```

**Ответ** — `400`

```json
{
  "detail": "Чтобы убрать способ оплаты «бизнес-карта», снимите business_card_id"
}
```

### 3.4 Снять карту и способ оплаты

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

```json
{
  "business_card_id": null,
  "payment_method": null
}
```

**Ответ** — `200` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 451.5,
  "payment_method": null,
  "business_card_id": null,
  "from_user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "for_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "hashtags": [
    "командировка",
    "ремонт_кровли"
  ],
  "comment": "Заметка владельца",
  "comments_count": 0
}
```

### 3.5 Сменить «от кого», убрать «для кого», заменить хештеги

`hashtags` заменяет весь набор; `[]` убирает все хештеги; `null` у пользователя — убрать поле.

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

```json
{
  "from_user_id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
  "for_user_id": null,
  "hashtags": [
    "Итог",
    "#итог",
    "новый тег"
  ]
}
```

**Ответ** — `200` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "source": "manual",
  "purchased_at": "2026-10-20T12:00:00",
  "created_at": "2026-10-20T22:25:38",
  "total_sum": 451.5,
  "payment_method": null,
  "business_card_id": null,
  "from_user": {
    "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
    "short_fio": "Ханзин А."
  },
  "for_user": null,
  "hashtags": [
    "итог",
    "новый_тег"
  ],
  "comment": "Заметка владельца",
  "comments_count": 0
}
```

## 4. Список: порядок, фильтры, хештеги

### 4.1 По умолчанию — по дате добавления, сверху новые

Последним добавлен чек с самой старой датой покупки (2025-01-01) — он первый.

**Запрос** — `GET /api/supply/purchase-receipts?scope=mine&limit=3`

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "id": "2e0af890-06e0-4944-b2c4-33057262ec26",
    "created_at": "2026-10-20T22:25:43",
    "purchased_at": "2025-01-01T10:00:00",
    "payment_method": null,
    "hashtags": [],
    "from_user": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "comments_count": 0
  },
  {
    "id": "d2311eeb-a4f3-4bf3-93b5-65348934673e",
    "created_at": "2026-10-20T22:25:41",
    "purchased_at": "2026-10-15T10:00:00",
    "payment_method": "cash",
    "hashtags": [
      "old",
      "x"
    ],
    "from_user": null,
    "comments_count": 0
  },
  {
    "id": "564430f1-3c31-4d7f-9ab8-10e57981d492",
    "created_at": "2026-10-20T22:25:40",
    "purchased_at": "2026-09-01T10:00:00",
    "payment_method": null,
    "hashtags": [
      "old"
    ],
    "from_user": null,
    "comments_count": 0
  }
]
```

### 4.2 По дате чека

**Запрос** — `GET /api/supply/purchase-receipts?scope=mine&limit=3&sort_by=purchased_at`

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "id": "cf22577e-5dd6-44e1-b169-e62cedcba37e",
    "created_at": "2026-10-20T22:25:38",
    "purchased_at": "2026-10-20T12:00:00",
    "payment_method": "business_card",
    "hashtags": [],
    "from_user": null,
    "comments_count": 0
  },
  {
    "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
    "created_at": "2026-10-20T22:25:38",
    "purchased_at": "2026-10-20T12:00:00",
    "payment_method": null,
    "hashtags": [
      "итог",
      "новый_тег"
    ],
    "from_user": {
      "id": "145c7704-bf54-47b3-82e9-41954a5ac74c",
      "short_fio": "Ханзин А."
    },
    "comments_count": 0
  },
  {
    "id": "87d664ee-4cb9-41b7-a08e-1ebc4e29f844",
    "created_at": "2026-10-20T22:25:38",
    "purchased_at": "2026-10-20T12:00:00",
    "payment_method": "credit_card",
    "hashtags": [],
    "from_user": null,
    "comments_count": 0
  }
]
```

### 4.3 Сначала старые

**Запрос** — `GET /api/supply/purchase-receipts?scope=mine&limit=3&order=asc`

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "id": "7958433b-6f69-4bbc-b028-e78d70378ef2",
    "created_at": "2026-10-09T00:00:10",
    "purchased_at": "2026-10-08T23:57:00",
    "payment_method": "business_card",
    "hashtags": [],
    "from_user": null,
    "comments_count": 0
  },
  {
    "id": "bf4d8323-25a4-499c-beae-378890d25418",
    "created_at": "2026-10-09T11:42:52",
    "purchased_at": "2026-10-07T13:35:00",
    "payment_method": null,
    "hashtags": [],
    "from_user": null,
    "comments_count": 0
  },
  {
    "id": "d6a560d7-b1f9-4688-920f-fba2cc7e056a",
    "created_at": "2026-10-09T11:43:19",
    "purchased_at": "2026-10-03T11:22:00",
    "payment_method": null,
    "hashtags": [],
    "from_user": null,
    "comments_count": 0
  }
]
```

### 4.4 Фильтр по хештегу (с # или без)

**Запрос** — `GET /api/supply/purchase-receipts?scope=mine&hashtag=%23old`

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "id": "d2311eeb-a4f3-4bf3-93b5-65348934673e",
    "created_at": "2026-10-20T22:25:41",
    "purchased_at": "2026-10-15T10:00:00",
    "payment_method": "cash",
    "hashtags": [
      "old",
      "x"
    ],
    "from_user": null,
    "comments_count": 0
  },
  {
    "id": "564430f1-3c31-4d7f-9ab8-10e57981d492",
    "created_at": "2026-10-20T22:25:40",
    "purchased_at": "2026-09-01T10:00:00",
    "payment_method": null,
    "hashtags": [
      "old"
    ],
    "from_user": null,
    "comments_count": 0
  }
]
```

### 4.5 Фильтр по способу оплаты

**Запрос** — `GET /api/supply/purchase-receipts?scope=mine&payment_method=cash&limit=2`

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "id": "d2311eeb-a4f3-4bf3-93b5-65348934673e",
    "created_at": "2026-10-20T22:25:41",
    "purchased_at": "2026-10-15T10:00:00",
    "payment_method": "cash",
    "hashtags": [
      "old",
      "x"
    ],
    "from_user": null,
    "comments_count": 0
  },
  {
    "id": "1d556ae8-3ebc-4ef2-bd66-32892fcda5a5",
    "created_at": "2026-10-20T22:25:38",
    "purchased_at": "2026-10-20T10:00:00",
    "payment_method": "cash",
    "hashtags": [
      "продукты"
    ],
    "from_user": null,
    "comments_count": 0
  }
]
```

### 4.6 Фильтр «от кого»

**Запрос** — `GET /api/supply/purchase-receipts?scope=mine&from_user_id=06968a8b-e24c-4099-998d-3d4c16ebc63a&limit=2`

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "id": "2e0af890-06e0-4944-b2c4-33057262ec26",
    "created_at": "2026-10-20T22:25:43",
    "purchased_at": "2025-01-01T10:00:00",
    "payment_method": null,
    "hashtags": [],
    "from_user": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "comments_count": 0
  },
  {
    "id": "dd2807b4-8c6e-4f56-b802-ead818f49e46",
    "created_at": "2026-10-20T22:25:38",
    "purchased_at": "2026-10-20T10:00:00",
    "payment_method": "credit_card",
    "hashtags": [
      "канцелярия",
      "офис"
    ],
    "from_user": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "comments_count": 0
  }
]
```

### 4.7 Хештеги пользователя (подсказки, фильтр)

Самые частые сверху; `scope`: all | mine | shared.

**Запрос** — `GET /api/supply/purchase-receipts/hashtags?scope=mine`

**Ответ** — `200`

```json
[
  {
    "tag": "old",
    "receipts_count": 2
  },
  {
    "tag": "x",
    "receipts_count": 1
  },
  {
    "tag": "итог",
    "receipts_count": 1
  },
  {
    "tag": "канцелярия",
    "receipts_count": 1
  },
  {
    "tag": "новый_тег",
    "receipts_count": 1
  },
  {
    "tag": "офис",
    "receipts_count": 1
  },
  {
    "tag": "продукты",
    "receipts_count": 1
  }
]
```

### 4.8 Неверная сортировка

**Запрос** — `GET /api/supply/purchase-receipts?sort_by=zzz`

**Ответ** — `422`

```json
{
  "detail": [
    {
      "type": "literal_error",
      "loc": [
        "query",
        "sort_by"
      ],
      "msg": "Input should be 'created_at' or 'purchased_at'",
      "input": "zzz",
      "ctx": {
        "expected": "'created_at' or 'purchased_at'"
      }
    }
  ]
}
```

## 5. Комментарии

### 5.1 Владелец оставляет комментарий

**Запрос** — `POST /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments`

```json
{
  "text": "  Чек передали бухгалтеру  "
}
```

**Ответ** — `201`

```json
{
  "id": "3d4c3e7c-a074-468a-ba43-30377e9eca98",
  "receipt_id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "text": "Чек передали бухгалтеру",
  "user": {
    "id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
    "short_fio": "Степанов С. А."
  },
  "created_at": "2026-10-20T22:25:43",
  "updated_at": null,
  "can_edit": true,
  "can_delete": true
}
```

### 5.2 Дать доступ только на просмотр

**Запрос** — `POST /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/access`

```json
{
  "user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
  "access_level": "view"
}
```

**Ответ** — `200` (показаны основные поля)

```json
[
  {
    "user": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "access_level": "view"
  }
]
```

### 5.3 Комментарий от пользователя с доступом «просмотр»

**Запрос** — `POST /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments`

```json
{
  "text": "Сумма совпадает с выпиской"
}
```

**Ответ** — `201`

```json
{
  "id": "5ad97d13-e3a7-43c6-88c6-774be84c4d40",
  "receipt_id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "text": "Сумма совпадает с выпиской",
  "user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-20T22:25:43",
  "updated_at": null,
  "can_edit": true,
  "can_delete": true
}
```

### 5.4 Список комментариев

От старых к новым. `can_edit` — можно менять (только автору), `can_delete` — можно удалить (автор или владелец чека).

**Запрос** — `GET /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments`

**Ответ** — `200`

```json
[
  {
    "id": "3d4c3e7c-a074-468a-ba43-30377e9eca98",
    "receipt_id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
    "text": "Чек передали бухгалтеру",
    "user": {
      "id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
      "short_fio": "Степанов С. А."
    },
    "created_at": "2026-10-20T22:25:43",
    "updated_at": null,
    "can_edit": false,
    "can_delete": false
  },
  {
    "id": "5ad97d13-e3a7-43c6-88c6-774be84c4d40",
    "receipt_id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
    "text": "Сумма совпадает с выпиской",
    "user": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "created_at": "2026-10-20T22:25:43",
    "updated_at": null,
    "can_edit": true,
    "can_delete": true
  }
]
```

### 5.5 Изменить свой комментарий

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments/5ad97d13-e3a7-43c6-88c6-774be84c4d40`

```json
{
  "text": "Сумма совпадает с выпиской от 20.10"
}
```

**Ответ** — `200`

```json
{
  "id": "5ad97d13-e3a7-43c6-88c6-774be84c4d40",
  "receipt_id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "text": "Сумма совпадает с выпиской от 20.10",
  "user": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-20T22:25:43",
  "updated_at": "2026-10-20T22:25:44",
  "can_edit": true,
  "can_delete": true
}
```

### 5.6 Чужой комментарий изменить нельзя

**Запрос** — `PATCH /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments/3d4c3e7c-a074-468a-ba43-30377e9eca98`

```json
{
  "text": "правка"
}
```

**Ответ** — `403`

```json
{
  "detail": "Изменять можно только свои комментарии"
}
```

### 5.7 Чужой комментарий удалить нельзя (не владелец)

**Запрос** — `DELETE /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments/3d4c3e7c-a074-468a-ba43-30377e9eca98`

**Ответ** — `403`

```json
{
  "detail": "Удалить чужой комментарий может только владелец чека"
}
```

### 5.8 Владелец удаляет любой комментарий

**Запрос** — `DELETE /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments/5ad97d13-e3a7-43c6-88c6-774be84c4d40`

**Ответ** — `204`

### 5.9 Карточка чека содержит комментарии

В списке чеков только `comments_count`, сам массив `comments` приходит в карточке.

**Запрос** — `GET /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660`

**Ответ** — `200` (показаны основные поля)

```json
{
  "id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
  "comment": "Заметка владельца",
  "comments_count": 1,
  "comments": [
    {
      "id": "3d4c3e7c-a074-468a-ba43-30377e9eca98",
      "receipt_id": "8a786cb2-9903-4dc9-b139-95920a4e8660",
      "text": "Чек передали бухгалтеру",
      "user": {
        "id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
        "short_fio": "Степанов С. А."
      },
      "created_at": "2026-10-20T22:25:43",
      "updated_at": null,
      "can_edit": true,
      "can_delete": true
    }
  ]
}
```

### 5.10 Пользователь без доступа

**Запрос** — `GET /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments`

**Ответ** — `404`

```json
{
  "detail": "Чек не найден"
}
```

### 5.11 Пустой текст

**Запрос** — `POST /api/supply/purchase-receipts/8a786cb2-9903-4dc9-b139-95920a4e8660/comments`

```json
{
  "text": ""
}
```

**Ответ** — `422`

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "text"
      ],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {
        "min_length": 1
      }
    }
  ]
}
```

## 6. Массовое изменение (`bulk-update`)

### 6.1 Способ оплаты, для кого и хештеги нескольким чекам

**Запрос** — `POST /api/supply/purchase-receipts/bulk-update`

```json
{
  "receipt_ids": [
    "564430f1-3c31-4d7f-9ab8-10e57981d492",
    "2e0af890-06e0-4944-b2c4-33057262ec26"
  ],
  "payment_method": "credit_card",
  "for_user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
  "hashtags": [
    "Кварталка",
    "отчёт"
  ],
  "hashtag_mode": "add"
}
```

**Ответ** — `200`

```json
{
  "requested": 2,
  "updated": 2,
  "skipped": 0,
  "results": [
    {
      "receipt_id": "564430f1-3c31-4d7f-9ab8-10e57981d492",
      "status": "updated"
    },
    {
      "receipt_id": "2e0af890-06e0-4944-b2c4-33057262ec26",
      "status": "updated"
    }
  ]
}
```

### 6.2 Заменить хештеги

**Запрос** — `POST /api/supply/purchase-receipts/bulk-update`

```json
{
  "receipt_ids": [
    "564430f1-3c31-4d7f-9ab8-10e57981d492"
  ],
  "hashtags": [
    "a",
    "b"
  ],
  "hashtag_mode": "replace"
}
```

**Ответ** — `200`

```json
{
  "requested": 1,
  "updated": 1,
  "skipped": 0,
  "results": [
    {
      "receipt_id": "564430f1-3c31-4d7f-9ab8-10e57981d492",
      "status": "updated"
    }
  ]
}
```

### 6.3 Убрать хештег

**Запрос** — `POST /api/supply/purchase-receipts/bulk-update`

```json
{
  "receipt_ids": [
    "564430f1-3c31-4d7f-9ab8-10e57981d492"
  ],
  "hashtags": [
    "a"
  ],
  "hashtag_mode": "remove"
}
```

**Ответ** — `200`

```json
{
  "requested": 1,
  "updated": 1,
  "skipped": 0,
  "results": [
    {
      "receipt_id": "564430f1-3c31-4d7f-9ab8-10e57981d492",
      "status": "updated"
    }
  ]
}
```

### 6.4 Убрать способ оплаты: чек с картой — конфликт, остальные обновляются

Статус `conflict` — у чека остаётся бизнес-карта, сначала её нужно снять.

**Запрос** — `POST /api/supply/purchase-receipts/bulk-update`

```json
{
  "receipt_ids": [
    "564430f1-3c31-4d7f-9ab8-10e57981d492",
    "d2311eeb-a4f3-4bf3-93b5-65348934673e"
  ],
  "payment_method": null
}
```

**Ответ** — `200`

```json
{
  "requested": 2,
  "updated": 1,
  "skipped": 1,
  "results": [
    {
      "receipt_id": "564430f1-3c31-4d7f-9ab8-10e57981d492",
      "status": "conflict",
      "detail": "Чтобы убрать способ оплаты «бизнес-карта», снимите business_card_id"
    },
    {
      "receipt_id": "d2311eeb-a4f3-4bf3-93b5-65348934673e",
      "status": "updated"
    }
  ]
}
```

### 6.5 Пустой запрос

**Запрос** — `POST /api/supply/purchase-receipts/bulk-update`

```json
{
  "receipt_ids": [
    "564430f1-3c31-4d7f-9ab8-10e57981d492"
  ]
}
```

**Ответ** — `422`

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "body"
      ],
      "msg": "Value error, Укажите, что применить: object_id, business_card_id, category_ids, comment, payment_method, from_user_id, for_user_id или hashtags",
      "input": {
        "receipt_ids": [
          "564430f1-3c31-4d7f-9ab8-10e57981d492"
        ]
      },
      "ctx": {
        "error": {}
      }
    }
  ]
}
```

## 7. Чеки по объекту: разбивка по способам оплаты

### 7.1 `GET /purchase-receipts/by-object/{object_id}` (фрагмент)

В `summary` добавилась `by_payment_method` — чистая сумма (покупки минус возвраты) по способам оплаты.

**Запрос** — `GET /api/supply/purchase-receipts/by-object/00081ac4-67de-4ae2-bf00-384c4d5c9bea?limit=1`

**Ответ** — `200` (показаны основные поля)

```json
{
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "summary": {
    "total_purchases": 60.0,
    "total_returns": 0,
    "net_spent": 60.0,
    "paid_by_business_card": 10.0,
    "receipts_count": 3,
    "by_payment_method": {
      "business_card": 10.0,
      "cash": 0,
      "credit_card": 30.0,
      "unspecified": 20.0
    }
  }
}
```
