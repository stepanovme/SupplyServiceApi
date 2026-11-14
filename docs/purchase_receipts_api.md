# Чеки (`/api/supply/purchase-receipts`) — примеры запросов и ответов

Все примеры получены реальными вызовами сервиса на тестовых данных (транзакция откатывалась). Пользователь **A** — владелец чеков, **B** — тот, кому открывают доступ. Все запросы требуют обычный заголовок авторизации (`Authorization`/сессия, как и остальные эндпоинты).

Категории чеков: стандартные «Продукты» и «Стройматериалы» (доступны всем) и личная «Командировка» пользователя A.

Идентификаторы в примерах: объект `00081ac4-67de-4ae2-bf00-384c4d5c9bea`, бизнес-карта `e173fa88-5054-42f9-b9a1-a8da139d6e84`, категории `3517f173-8b5d-4ade-a93b-470a9730dcd7`, `43b34198-42be-4b39-9dc8-dc855de99714`, `87704e9c-b59d-405a-a39d-7a2dfb09363c`, пользователь A `06968a8b-e24c-4099-998d-3d4c16ebc63a`, пользователь B `122d844d-b3be-42d9-8b5b-8a0058edb2d8`.

## 1. Добавление чека

### 1.1 Вручную

`total_sum` не передан — считается как сумма позиций. У первой позиции нет `sum` — берётся `price × quantity`. `fn/fd/fp` необязательны (но только все три вместе).

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-10-01T12:00:00",
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "category_ids": [
    "3517f173-8b5d-4ade-a93b-470a9730dcd7",
    "43b34198-42be-4b39-9dc8-dc855de99714"
  ],
  "comment": "Для объекта на Валявкина",
  "items": [
    {
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3
    },
    {
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ]
}
```

**Ответ** — `201`

```json
{
  "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
  "source": "manual",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": null,
  "purchased_at": "2026-10-01T12:00:00",
  "receipt_type": 1,
  "total_sum": 631.3,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "fn": null,
  "fd": null,
  "fp": null,
  "comment": "Для объекта на Валявкина",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "business_card": {
    "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
    "card_number_mask": "220015******0537",
    "card_last4": "0537",
    "holder_name": "OOO STORI TEHNOLOG",
    "bank_type": "alfabank"
  },
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    }
  ],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3.0,
      "sum": 451.5,
      "nds_code": null,
      "nds_sum": null
    },
    {
      "position": 2,
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2.0,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ],
  "shared_with": []
}
```

### 1.2 Вручную, с фискальными реквизитами (защита от дублей)

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-09-15T09:30:00",
  "total_sum": 1250.0,
  "seller_name": "ООО Ромашка",
  "fn": "9960440300123456",
  "fd": "1042",
  "fp": "2288776655",
  "items": [
    {
      "name": "Краска фасадная 10л",
      "price": 1250,
      "quantity": 1
    }
  ]
}
```

**Ответ** — `201`

```json
{
  "id": "257de45d-89d5-49dc-9971-bc72b71d0aaa",
  "source": "manual",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": null,
  "purchased_at": "2026-09-15T09:30:00",
  "receipt_type": 1,
  "total_sum": 1250.0,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ООО Ромашка",
  "seller_inn": null,
  "retail_place": null,
  "retail_place_address": null,
  "fn": "9960440300123456",
  "fd": "1042",
  "fp": "2288776655",
  "comment": null,
  "object_id": null,
  "object": null,
  "business_card_id": null,
  "business_card": null,
  "categories": [],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Краска фасадная 10л",
      "price": 1250.0,
      "quantity": 1.0,
      "sum": 1250.0,
      "nds_code": null,
      "nds_sum": null
    }
  ],
  "shared_with": []
}
```

### 1.3 По QR-коду (строка `qrraw`)

Данные берутся с proverkacheka.com (в этом примере ответ сервиса подставлен из вашего образца). Суммы там в копейках — в ответе они уже в рублях.

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь A)

```json
{
  "qrraw": "t=20260923T2230&s=1719.45&fn=7380440903639999&i=26770&fp=505260300&n=1",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "category_ids": [
    "3517f173-8b5d-4ade-a93b-470a9730dcd7",
    "43b34198-42be-4b39-9dc8-dc855de99714"
  ],
  "comment": "Продукты в бытовку"
}
```

**Ответ** — `201`

```json
{
  "id": "b27907e0-4e85-44b2-89f7-dd2c9cf9deda",
  "source": "qr",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:13",
  "updated_at": null,
  "purchased_at": "2026-09-23T22:30:00",
  "receipt_type": 1,
  "total_sum": 1719.45,
  "cash_sum": 0.0,
  "ecash_sum": 1719.45,
  "seller_name": "ООО \"Лента\"",
  "seller_inn": "7814148471",
  "retail_place": "ТК Лента-204",
  "retail_place_address": "Россия, Архангельская обл., г. Архангельск, Московский пр-кт, д. 12",
  "fn": "7380440903639999",
  "fd": "26770",
  "fp": "505260300",
  "comment": "Продукты в бытовку",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "business_card": {
    "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
    "card_number_mask": "220015******0537",
    "card_last4": "0537",
    "holder_name": "OOO STORI TEHNOLOG",
    "bank_type": "alfabank"
  },
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    }
  ],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Шоколад KINDER Chocolate мол/мол нач 50г",
      "price": 94.99,
      "quantity": 1.0,
      "sum": 94.99,
      "nds_code": 11,
      "nds_sum": 17.13
    },
    {
      "position": 2,
      "name": "Гренки BEERKA Бород с Чесн смет соус 85г",
      "price": 44.99,
      "quantity": 1.0,
      "sum": 44.99,
      "nds_code": 2,
      "nds_sum": 4.09
    },
    {
      "position": 3,
      "name": "Капуста СВОЙ УРОЖАЙ брокколи зам 400г",
      "price": 139.99,
      "quantity": 1.0,
      "sum": 139.99,
      "nds_code": 11,
      "nds_sum": 25.24
    },
    {
      "position": 4,
      "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
      "price": 78.99,
      "quantity": 1.0,
      "sum": 78.99,
      "nds_code": 2,
      "nds_sum": 7.18
    },
    {
      "position": 5,
      "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
      "price": 78.99,
      "quantity": 1.0,
      "sum": 78.99,
      "nds_code": 2,
      "nds_sum": 7.18
    },
    {
      "position": 6,
      "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 7,
      "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 8,
      "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 9,
      "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 10,
      "name": "Морковь мытая вес 1кг",
      "price": 89.99,
      "quantity": 0.184,
      "sum": 16.56,
      "nds_code": 2,
      "nds_sum": 1.51
    },
    {
      "position": 11,
      "name": "Подг-трус PAMPERS PantJumoJun 12-17кг42",
      "price": 1099.99,
      "quantity": 1.0,
      "sum": 1099.99,
      "nds_code": 2,
      "nds_sum": 100.0
    },
    {
      "position": 12,
      "name": "Пакет ЛЕНТА 12кг",
      "price": 12.99,
      "quantity": 1.0,
      "sum": 12.99,
      "nds_code": 11,
      "nds_sum": 2.34
    }
  ],
  "shared_with": []
}
```

### 1.4 По QR-коду (отдельные реквизиты)

Для случая, когда QR не читается, а цифры видны на чеке. (Здесь внешний сервис подменён тестовым ответом.)

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь A)

```json
{
  "t": "20260930T1805",
  "s": "450.90",
  "fn": "7380440911112222",
  "fd": "48213",
  "fp": "3127745518",
  "n": 1
}
```

**Ответ** — `201`

```json
{
  "id": "6f11e9fd-f852-47b6-acbf-8da6fe47d61b",
  "source": "qr",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:13",
  "updated_at": null,
  "purchased_at": "2026-09-30T18:05:00",
  "receipt_type": 1,
  "total_sum": 450.9,
  "cash_sum": 0.0,
  "ecash_sum": 450.9,
  "seller_name": "ИП Петров А.В.",
  "seller_inn": "290123456789",
  "retail_place": "Магазин «Стройдвор»",
  "retail_place_address": "г. Архангельск, ул. Выучейского, д. 5",
  "fn": "7380440911112222",
  "fd": "48213",
  "fp": "3127745518",
  "comment": null,
  "object_id": null,
  "object": null,
  "business_card_id": null,
  "business_card": null,
  "categories": [],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Саморез кровельный 4.8x35 (уп.200шт)",
      "price": 225.0,
      "quantity": 1.0,
      "sum": 225.0,
      "nds_code": 2,
      "nds_sum": 20.45
    },
    {
      "position": 2,
      "name": "Перчатки рабочие х/б",
      "price": 112.95,
      "quantity": 2.0,
      "sum": 225.9,
      "nds_code": 2,
      "nds_sum": 20.53
    }
  ],
  "shared_with": []
}
```

### 1.5 По фото

multipart/form-data; поле `category_ids` можно повторять. QR на снимке распознаёт сам proverkacheka.com.

**Запрос** — `POST /api/supply/purchase-receipts/from-photo` (пользователь A)

```bash
curl -X POST "$HOST/api/supply/purchase-receipts/from-photo" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@check.jpg;type=image/jpeg" \
  -F "object_id=00081ac4-67de-4ae2-bf00-384c4d5c9bea" \
  -F "category_ids=87704e9c-b59d-405a-a39d-7a2dfb09363c" \
  -F "comment=Фото чека"
```

**Ответ** — `201`

```json
{
  "id": "73178ac9-67b9-4581-91ae-ea830c2361fb",
  "source": "photo",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:13",
  "updated_at": null,
  "purchased_at": "2026-10-03T11:40:00",
  "receipt_type": 1,
  "total_sum": 1299.0,
  "cash_sum": 0.0,
  "ecash_sum": 1299.0,
  "seller_name": "ООО \"Леруа Мерлен Восток\"",
  "seller_inn": "5029069967",
  "retail_place": "ТЦ Леруа Мерлен Архангельск",
  "retail_place_address": "г. Архангельск, Талажское ш., д. 30",
  "fn": "7380440955556666",
  "fd": "51007",
  "fp": "1894402271",
  "comment": "Фото чека",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": null,
  "business_card": null,
  "categories": [
    {
      "id": "87704e9c-b59d-405a-a39d-7a2dfb09363c",
      "name": "Командировка",
      "color": "#3B82F6",
      "is_system": false
    }
  ],
  "files": [
    {
      "id": "29643ec6-4cbb-4344-871d-1988fc14016a",
      "original_name": "check.jpg",
      "mime_type": "image/jpeg",
      "file_size": 9,
      "source": "receipt_photo",
      "uploaded_by": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "created_at": "2026-10-08T18:49:13",
      "url": "https://supply.st29.ru/storage/receipts/73178ac9-67b9-4581-91ae-ea830c2361fb/134e9d3c75a74614ad20313d929d5007.jpg",
      "download_url": "/api/supply/purchase-receipts/73178ac9-67b9-4581-91ae-ea830c2361fb/files/29643ec6-4cbb-4344-871d-1988fc14016a"
    }
  ],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Грунтовка глубокого проникновения 10л",
      "price": 1299.0,
      "quantity": 1.0,
      "sum": 1299.0,
      "nds_code": 11,
      "nds_sum": 234.22
    }
  ],
  "shared_with": []
}
```

## 2. Ошибки при добавлении

### 2.1 Этот чек уже добавлен мной

Внешний сервис при этом не вызывается.

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь A)

```json
{
  "qrraw": "t=20260923T2230&s=1719.45&fn=7380440903639999&i=26770&fp=505260300&n=1"
}
```

**Ответ** — `409`

```json
{
  "detail": {
    "message": "Этот чек уже добавлен",
    "receipt_id": "b27907e0-4e85-44b2-89f7-dd2c9cf9deda",
    "has_access": true
  }
}
```

### 2.2 Этот чек уже добавил другой пользователь

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь B)

```json
{
  "qrraw": "t=20260923T2230&s=1719.45&fn=7380440903639999&i=26770&fp=505260300&n=1"
}
```

**Ответ** — `409`

```json
{
  "detail": {
    "message": "Этот чек уже добавлен другим пользователем — попросите владельца открыть вам доступ",
    "receipt_id": null,
    "has_access": false
  }
}
```

### 2.3 В QR не хватает полей

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь A)

```json
{
  "qrraw": "t=20260923T2230&s=1719.45"
}
```

**Ответ** — `422`

```json
{
  "detail": "В строке QR-кода не хватает полей: fn, i, fp"
}
```

### 2.4 Не передан ни qrraw, ни реквизиты

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь A)

```json
{
  "t": "20260923T2230"
}
```

**Ответ** — `422` (валидация тела запроса)

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "body"
      ],
      "msg": "Value error, Передайте qrraw либо все поля t, s, fn, fd, fp",
      "input": {
        "t": "20260923T2230"
      }
    }
  ]
}
```

### 2.5 Не изображение

**Запрос** — `POST /api/supply/purchase-receipts/from-photo` (пользователь A)

```bash
curl -X POST "$HOST/api/supply/purchase-receipts/from-photo" -H "Authorization: Bearer $TOKEN" -F "file=@notes.txt;type=text/plain"
```

**Ответ** — `400`

```json
{
  "detail": "Нужен файл-изображение с QR-кодом чека"
}
```

### 2.6 Фискальные реквизиты не все

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-10-01T12:00:00",
  "total_sum": 100,
  "fn": "9960440300123456"
}
```

**Ответ** — `422` (валидация тела запроса)

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "body"
      ],
      "msg": "Value error, Фискальные реквизиты fn, fd, fp указываются только все вместе",
      "input": {
        "purchased_at": "2026-10-01T12:00:00",
        "total_sum": 100,
        "fn": "9960440300123456"
      }
    }
  ]
}
```

### 2.7 Нет ни суммы, ни позиций

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-10-01T12:00:00"
}
```

**Ответ** — `422` (валидация тела запроса)

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "body"
      ],
      "msg": "Value error, Укажите total_sum или хотя бы одну позицию в items",
      "input": {
        "purchased_at": "2026-10-01T12:00:00"
      }
    }
  ]
}
```

### 2.8 Несуществующий объект

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-10-01T12:00:00",
  "total_sum": 100,
  "object_id": "nope"
}
```

**Ответ** — `404`

```json
{
  "detail": "Объект не найден"
}
```

### 2.9 Несуществующая бизнес-карта

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-10-01T12:00:00",
  "total_sum": 100,
  "business_card_id": "nope"
}
```

**Ответ** — `404`

```json
{
  "detail": "Бизнес-карта не найдена"
}
```

### 2.10 Несуществующая категория

**Запрос** — `POST /api/supply/purchase-receipts` (пользователь A)

```json
{
  "purchased_at": "2026-10-01T12:00:00",
  "total_sum": 100,
  "category_ids": [
    "nope"
  ]
}
```

**Ответ** — `404`

```json
{
  "detail": "Категории чеков не найдены: nope"
}
```

### 2.11 Сервис проверки чеков не вернул данные

Если чек не найден/некорректен — `422` с текстом от сервиса; токен не настроен — `503`; сеть недоступна — `502`.

**Запрос** — `POST /api/supply/purchase-receipts/from-qr` (пользователь A)

```json
{
  "qrraw": "t=20260101T1000&s=10.00&fn=1111111111111111&i=1&fp=1&n=1"
}
```

**Ответ** — `503`

```json
{
  "detail": "Сервис проверки чеков не вернул данные (code=2). Данные чека ещё не получены от ФНС, повторите запрос позже."
}
```

## 3. Чтение

### 3.1 Список (мои и расшаренные)

Фильтры: `scope` (all|mine|shared), `object_id`, `business_card_id`, `category_id`, `date_from`, `date_to`, `limit` (1–500), `offset`.

**Запрос** — `GET /api/supply/purchase-receipts?scope=all&object_id=00081ac4-67de-4ae2-bf00-384c4d5c9bea&category_id=3517f173-8b5d-4ade-a93b-470a9730dcd7&date_from=2026-09-01T00:00:00&limit=2` (пользователь A)

**Ответ** — `200`

```json
[
  {
    "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
    "source": "manual",
    "my_access": "owner",
    "created_by": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "created_at": "2026-10-08T18:49:12",
    "updated_at": null,
    "purchased_at": "2026-10-01T12:00:00",
    "receipt_type": 1,
    "total_sum": 631.3,
    "cash_sum": null,
    "ecash_sum": null,
    "seller_name": "ИП Иванов",
    "seller_inn": "290100000000",
    "retail_place": "Магазин «Электрика»",
    "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
    "fn": null,
    "fd": null,
    "fp": null,
    "comment": "Для объекта на Валявкина",
    "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "object": {
      "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
      "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
    },
    "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
    "business_card": {
      "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
      "card_number_mask": "220015******0537",
      "card_last4": "0537",
      "holder_name": "OOO STORI TEHNOLOG",
      "bank_type": "alfabank"
    },
    "categories": [
      {
        "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
        "name": "Продукты",
        "color": "#2E9E4F",
        "is_system": true
      },
      {
        "id": "43b34198-42be-4b39-9dc8-dc855de99714",
        "name": "Стройматериалы",
        "color": "#E8A317",
        "is_system": true
      }
    ],
    "files": [],
    "shared_with_count": 0,
    "items": [
      {
        "position": 1,
        "name": "Кабель ВВГ 3x2.5",
        "price": 150.5,
        "quantity": 3.0,
        "sum": 451.5,
        "nds_code": null,
        "nds_sum": null
      },
      {
        "position": 2,
        "name": "Розетка",
        "price": 89.9,
        "quantity": 2.0,
        "sum": 179.8,
        "nds_code": 1,
        "nds_sum": 29.97
      }
    ],
    "shared_with": []
  },
  {
    "id": "b27907e0-4e85-44b2-89f7-dd2c9cf9deda",
    "source": "qr",
    "my_access": "owner",
    "created_by": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "created_at": "2026-10-08T18:49:13",
    "updated_at": null,
    "purchased_at": "2026-09-23T22:30:00",
    "receipt_type": 1,
    "total_sum": 1719.45,
    "cash_sum": 0.0,
    "ecash_sum": 1719.45,
    "seller_name": "ООО \"Лента\"",
    "seller_inn": "7814148471",
    "retail_place": "ТК Лента-204",
    "retail_place_address": "Россия, Архангельская обл., г. Архангельск, Московский пр-кт, д. 12",
    "fn": "7380440903639999",
    "fd": "26770",
    "fp": "505260300",
    "comment": "Продукты в бытовку",
    "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "object": {
      "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
      "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
    },
    "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
    "business_card": {
      "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
      "card_number_mask": "220015******0537",
      "card_last4": "0537",
      "holder_name": "OOO STORI TEHNOLOG",
      "bank_type": "alfabank"
    },
    "categories": [
      {
        "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
        "name": "Продукты",
        "color": "#2E9E4F",
        "is_system": true
      },
      {
        "id": "43b34198-42be-4b39-9dc8-dc855de99714",
        "name": "Стройматериалы",
        "color": "#E8A317",
        "is_system": true
      }
    ],
    "files": [],
    "shared_with_count": 0,
    "items": [
      {
        "position": 1,
        "name": "Шоколад KINDER Chocolate мол/мол нач 50г",
        "price": 94.99,
        "quantity": 1.0,
        "sum": 94.99,
        "nds_code": 11,
        "nds_sum": 17.13
      },
      {
        "position": 2,
        "name": "Гренки BEERKA Бород с Чесн смет соус 85г",
        "price": 44.99,
        "quantity": 1.0,
        "sum": 44.99,
        "nds_code": 2,
        "nds_sum": 4.09
      },
      {
        "position": 3,
        "name": "Капуста СВОЙ УРОЖАЙ брокколи зам 400г",
        "price": 139.99,
        "quantity": 1.0,
        "sum": 139.99,
        "nds_code": 11,
        "nds_sum": 25.24
      },
      {
        "position": 4,
        "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
        "price": 78.99,
        "quantity": 1.0,
        "sum": 78.99,
        "nds_code": 2,
        "nds_sum": 7.18
      },
      {
        "position": 5,
        "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
        "price": 78.99,
        "quantity": 1.0,
        "sum": 78.99,
        "nds_code": 2,
        "nds_sum": 7.18
      },
      {
        "position": 6,
        "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
        "price": 37.99,
        "quantity": 1.0,
        "sum": 37.99,
        "nds_code": 2,
        "nds_sum": 3.45
      },
      {
        "position": 7,
        "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
        "price": 37.99,
        "quantity": 1.0,
        "sum": 37.99,
        "nds_code": 2,
        "nds_sum": 3.45
      },
      {
        "position": 8,
        "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
        "price": 37.99,
        "quantity": 1.0,
        "sum": 37.99,
        "nds_code": 2,
        "nds_sum": 3.45
      },
      {
        "position": 9,
        "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
        "price": 37.99,
        "quantity": 1.0,
        "sum": 37.99,
        "nds_code": 2,
        "nds_sum": 3.45
      },
      {
        "position": 10,
        "name": "Морковь мытая вес 1кг",
        "price": 89.99,
        "quantity": 0.184,
        "sum": 16.56,
        "nds_code": 2,
        "nds_sum": 1.51
      },
      {
        "position": 11,
        "name": "Подг-трус PAMPERS PantJumoJun 12-17кг42",
        "price": 1099.99,
        "quantity": 1.0,
        "sum": 1099.99,
        "nds_code": 2,
        "nds_sum": 100.0
      },
      {
        "position": 12,
        "name": "Пакет ЛЕНТА 12кг",
        "price": 12.99,
        "quantity": 1.0,
        "sum": 12.99,
        "nds_code": 11,
        "nds_sum": 2.34
      }
    ],
    "shared_with": []
  }
]
```

### 3.2 Один чек

**Запрос** — `GET /api/supply/purchase-receipts/b27907e0-4e85-44b2-89f7-dd2c9cf9deda` (пользователь A)

**Ответ** — `200`

```json
{
  "id": "b27907e0-4e85-44b2-89f7-dd2c9cf9deda",
  "source": "qr",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:13",
  "updated_at": null,
  "purchased_at": "2026-09-23T22:30:00",
  "receipt_type": 1,
  "total_sum": 1719.45,
  "cash_sum": 0.0,
  "ecash_sum": 1719.45,
  "seller_name": "ООО \"Лента\"",
  "seller_inn": "7814148471",
  "retail_place": "ТК Лента-204",
  "retail_place_address": "Россия, Архангельская обл., г. Архангельск, Московский пр-кт, д. 12",
  "fn": "7380440903639999",
  "fd": "26770",
  "fp": "505260300",
  "comment": "Продукты в бытовку",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
  "business_card": {
    "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
    "card_number_mask": "220015******0537",
    "card_last4": "0537",
    "holder_name": "OOO STORI TEHNOLOG",
    "bank_type": "alfabank"
  },
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    }
  ],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Шоколад KINDER Chocolate мол/мол нач 50г",
      "price": 94.99,
      "quantity": 1.0,
      "sum": 94.99,
      "nds_code": 11,
      "nds_sum": 17.13
    },
    {
      "position": 2,
      "name": "Гренки BEERKA Бород с Чесн смет соус 85г",
      "price": 44.99,
      "quantity": 1.0,
      "sum": 44.99,
      "nds_code": 2,
      "nds_sum": 4.09
    },
    {
      "position": 3,
      "name": "Капуста СВОЙ УРОЖАЙ брокколи зам 400г",
      "price": 139.99,
      "quantity": 1.0,
      "sum": 139.99,
      "nds_code": 11,
      "nds_sum": 25.24
    },
    {
      "position": 4,
      "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
      "price": 78.99,
      "quantity": 1.0,
      "sum": 78.99,
      "nds_code": 2,
      "nds_sum": 7.18
    },
    {
      "position": 5,
      "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
      "price": 78.99,
      "quantity": 1.0,
      "sum": 78.99,
      "nds_code": 2,
      "nds_sum": 7.18
    },
    {
      "position": 6,
      "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 7,
      "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 8,
      "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 9,
      "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
      "price": 37.99,
      "quantity": 1.0,
      "sum": 37.99,
      "nds_code": 2,
      "nds_sum": 3.45
    },
    {
      "position": 10,
      "name": "Морковь мытая вес 1кг",
      "price": 89.99,
      "quantity": 0.184,
      "sum": 16.56,
      "nds_code": 2,
      "nds_sum": 1.51
    },
    {
      "position": 11,
      "name": "Подг-трус PAMPERS PantJumoJun 12-17кг42",
      "price": 1099.99,
      "quantity": 1.0,
      "sum": 1099.99,
      "nds_code": 2,
      "nds_sum": 100.0
    },
    {
      "position": 12,
      "name": "Пакет ЛЕНТА 12кг",
      "price": 12.99,
      "quantity": 1.0,
      "sum": 12.99,
      "nds_code": 11,
      "nds_sum": 2.34
    }
  ],
  "shared_with": []
}
```

### 3.3 Чеки по объекту со сводкой

`net_spent` = покупки − возвраты; `paid_by_business_card` — часть, оплаченная бизнес-картами. В выдачу входят только чеки, доступные пользователю.

**Запрос** — `GET /api/supply/purchase-receipts/by-object/00081ac4-67de-4ae2-bf00-384c4d5c9bea` (пользователь A)

**Ответ** — `200`

```json
{
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object_short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске",
  "period": {
    "date_from": null,
    "date_to": null
  },
  "summary": {
    "total_purchases": 3649.75,
    "total_returns": 0,
    "net_spent": 3649.75,
    "paid_by_business_card": 2350.75,
    "receipts_count": 3
  },
  "receipts": [
    {
      "id": "73178ac9-67b9-4581-91ae-ea830c2361fb",
      "source": "photo",
      "my_access": "owner",
      "created_by": {
        "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
        "short_fio": "Бартинов А. М."
      },
      "created_at": "2026-10-08T18:49:13",
      "updated_at": null,
      "purchased_at": "2026-10-03T11:40:00",
      "receipt_type": 1,
      "total_sum": 1299.0,
      "cash_sum": 0.0,
      "ecash_sum": 1299.0,
      "seller_name": "ООО \"Леруа Мерлен Восток\"",
      "seller_inn": "5029069967",
      "retail_place": "ТЦ Леруа Мерлен Архангельск",
      "retail_place_address": "г. Архангельск, Талажское ш., д. 30",
      "fn": "7380440955556666",
      "fd": "51007",
      "fp": "1894402271",
      "comment": "Фото чека",
      "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
      "object": {
        "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
        "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
      },
      "business_card_id": null,
      "business_card": null,
      "categories": [
        {
          "id": "87704e9c-b59d-405a-a39d-7a2dfb09363c",
          "name": "Командировка",
          "color": "#3B82F6",
          "is_system": false
        }
      ],
      "files": [
        {
          "id": "29643ec6-4cbb-4344-871d-1988fc14016a",
          "original_name": "check.jpg",
          "mime_type": "image/jpeg",
          "file_size": 9,
          "source": "receipt_photo",
          "uploaded_by": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
          "created_at": "2026-10-08T18:49:13",
          "url": "https://supply.st29.ru/storage/receipts/73178ac9-67b9-4581-91ae-ea830c2361fb/134e9d3c75a74614ad20313d929d5007.jpg",
          "download_url": "/api/supply/purchase-receipts/73178ac9-67b9-4581-91ae-ea830c2361fb/files/29643ec6-4cbb-4344-871d-1988fc14016a"
        }
      ],
      "shared_with_count": 0,
      "items": [
        {
          "position": 1,
          "name": "Грунтовка глубокого проникновения 10л",
          "price": 1299.0,
          "quantity": 1.0,
          "sum": 1299.0,
          "nds_code": 11,
          "nds_sum": 234.22
        }
      ],
      "shared_with": []
    },
    {
      "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
      "source": "manual",
      "my_access": "owner",
      "created_by": {
        "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
        "short_fio": "Бартинов А. М."
      },
      "created_at": "2026-10-08T18:49:12",
      "updated_at": null,
      "purchased_at": "2026-10-01T12:00:00",
      "receipt_type": 1,
      "total_sum": 631.3,
      "cash_sum": null,
      "ecash_sum": null,
      "seller_name": "ИП Иванов",
      "seller_inn": "290100000000",
      "retail_place": "Магазин «Электрика»",
      "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
      "fn": null,
      "fd": null,
      "fp": null,
      "comment": "Для объекта на Валявкина",
      "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
      "object": {
        "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
        "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
      },
      "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
      "business_card": {
        "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
        "card_number_mask": "220015******0537",
        "card_last4": "0537",
        "holder_name": "OOO STORI TEHNOLOG",
        "bank_type": "alfabank"
      },
      "categories": [
        {
          "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
          "name": "Продукты",
          "color": "#2E9E4F",
          "is_system": true
        },
        {
          "id": "43b34198-42be-4b39-9dc8-dc855de99714",
          "name": "Стройматериалы",
          "color": "#E8A317",
          "is_system": true
        }
      ],
      "files": [],
      "shared_with_count": 0,
      "items": [
        {
          "position": 1,
          "name": "Кабель ВВГ 3x2.5",
          "price": 150.5,
          "quantity": 3.0,
          "sum": 451.5,
          "nds_code": null,
          "nds_sum": null
        },
        {
          "position": 2,
          "name": "Розетка",
          "price": 89.9,
          "quantity": 2.0,
          "sum": 179.8,
          "nds_code": 1,
          "nds_sum": 29.97
        }
      ],
      "shared_with": []
    },
    {
      "id": "b27907e0-4e85-44b2-89f7-dd2c9cf9deda",
      "source": "qr",
      "my_access": "owner",
      "created_by": {
        "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
        "short_fio": "Бартинов А. М."
      },
      "created_at": "2026-10-08T18:49:13",
      "updated_at": null,
      "purchased_at": "2026-09-23T22:30:00",
      "receipt_type": 1,
      "total_sum": 1719.45,
      "cash_sum": 0.0,
      "ecash_sum": 1719.45,
      "seller_name": "ООО \"Лента\"",
      "seller_inn": "7814148471",
      "retail_place": "ТК Лента-204",
      "retail_place_address": "Россия, Архангельская обл., г. Архангельск, Московский пр-кт, д. 12",
      "fn": "7380440903639999",
      "fd": "26770",
      "fp": "505260300",
      "comment": "Продукты в бытовку",
      "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
      "object": {
        "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
        "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
      },
      "business_card_id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
      "business_card": {
        "id": "e173fa88-5054-42f9-b9a1-a8da139d6e84",
        "card_number_mask": "220015******0537",
        "card_last4": "0537",
        "holder_name": "OOO STORI TEHNOLOG",
        "bank_type": "alfabank"
      },
      "categories": [
        {
          "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
          "name": "Продукты",
          "color": "#2E9E4F",
          "is_system": true
        },
        {
          "id": "43b34198-42be-4b39-9dc8-dc855de99714",
          "name": "Стройматериалы",
          "color": "#E8A317",
          "is_system": true
        }
      ],
      "files": [],
      "shared_with_count": 0,
      "items": [
        {
          "position": 1,
          "name": "Шоколад KINDER Chocolate мол/мол нач 50г",
          "price": 94.99,
          "quantity": 1.0,
          "sum": 94.99,
          "nds_code": 11,
          "nds_sum": 17.13
        },
        {
          "position": 2,
          "name": "Гренки BEERKA Бород с Чесн смет соус 85г",
          "price": 44.99,
          "quantity": 1.0,
          "sum": 44.99,
          "nds_code": 2,
          "nds_sum": 4.09
        },
        {
          "position": 3,
          "name": "Капуста СВОЙ УРОЖАЙ брокколи зам 400г",
          "price": 139.99,
          "quantity": 1.0,
          "sum": 139.99,
          "nds_code": 11,
          "nds_sum": 25.24
        },
        {
          "position": 4,
          "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
          "price": 78.99,
          "quantity": 1.0,
          "sum": 78.99,
          "nds_code": 2,
          "nds_sum": 7.18
        },
        {
          "position": 5,
          "name": "Молоко ТЕМА у/п пит 3,2% сombiblock 500м",
          "price": 78.99,
          "quantity": 1.0,
          "sum": 78.99,
          "nds_code": 2,
          "nds_sum": 7.18
        },
        {
          "position": 6,
          "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
          "price": 37.99,
          "quantity": 1.0,
          "sum": 37.99,
          "nds_code": 2,
          "nds_sum": 3.45
        },
        {
          "position": 7,
          "name": "Д/п нектар ФРУТОНЯНЯ банан с мяк 200мл",
          "price": 37.99,
          "quantity": 1.0,
          "sum": 37.99,
          "nds_code": 2,
          "nds_sum": 3.45
        },
        {
          "position": 8,
          "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
          "price": 37.99,
          "quantity": 1.0,
          "sum": 37.99,
          "nds_code": 2,
          "nds_sum": 3.45
        },
        {
          "position": 9,
          "name": "Д/п сок ФРУТОНЯНЯ груш осв. с 4мес 200мл",
          "price": 37.99,
          "quantity": 1.0,
          "sum": 37.99,
          "nds_code": 2,
          "nds_sum": 3.45
        },
        {
          "position": 10,
          "name": "Морковь мытая вес 1кг",
          "price": 89.99,
          "quantity": 0.184,
          "sum": 16.56,
          "nds_code": 2,
          "nds_sum": 1.51
        },
        {
          "position": 11,
          "name": "Подг-трус PAMPERS PantJumoJun 12-17кг42",
          "price": 1099.99,
          "quantity": 1.0,
          "sum": 1099.99,
          "nds_code": 2,
          "nds_sum": 100.0
        },
        {
          "position": 12,
          "name": "Пакет ЛЕНТА 12кг",
          "price": 12.99,
          "quantity": 1.0,
          "sum": 12.99,
          "nds_code": 11,
          "nds_sum": 2.34
        }
      ],
      "shared_with": []
    }
  ]
}
```

### 3.4 Чужой чек без доступа

**Запрос** — `GET /api/supply/purchase-receipts/b27907e0-4e85-44b2-89f7-dd2c9cf9deda` (пользователь B)

**Ответ** — `404`

```json
{
  "detail": "Чек не найден"
}
```

## 4. Изменение привязок

### 4.1 Сменить объект/карту/категории/комментарий

Передаются только изменяемые поля. `null` снимает привязку к объекту/карте, `category_ids` заменяет весь набор.

**Запрос** — `PATCH /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь A)

```json
{
  "business_card_id": null,
  "category_ids": [
    "87704e9c-b59d-405a-a39d-7a2dfb09363c"
  ],
  "comment": "Оплатили наличными"
}
```

**Ответ** — `200`

```json
{
  "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
  "source": "manual",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": "2026-10-08T18:49:13",
  "purchased_at": "2026-10-01T12:00:00",
  "receipt_type": 1,
  "total_sum": 631.3,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "fn": null,
  "fd": null,
  "fp": null,
  "comment": "Оплатили наличными",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": null,
  "business_card": null,
  "categories": [
    {
      "id": "87704e9c-b59d-405a-a39d-7a2dfb09363c",
      "name": "Командировка",
      "color": "#3B82F6",
      "is_system": false
    }
  ],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3.0,
      "sum": 451.5,
      "nds_code": null,
      "nds_sum": null
    },
    {
      "position": 2,
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2.0,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ],
  "shared_with": []
}
```

### 4.2 Добавить категории

**Запрос** — `POST /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/categories` (пользователь A)

```json
{
  "category_ids": [
    "3517f173-8b5d-4ade-a93b-470a9730dcd7",
    "43b34198-42be-4b39-9dc8-dc855de99714"
  ]
}
```

**Ответ** — `200`

```json
{
  "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
  "source": "manual",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": "2026-10-08T18:49:13",
  "purchased_at": "2026-10-01T12:00:00",
  "receipt_type": 1,
  "total_sum": 631.3,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "fn": null,
  "fd": null,
  "fp": null,
  "comment": "Оплатили наличными",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": null,
  "business_card": null,
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    },
    {
      "id": "87704e9c-b59d-405a-a39d-7a2dfb09363c",
      "name": "Командировка",
      "color": "#3B82F6",
      "is_system": false
    }
  ],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3.0,
      "sum": 451.5,
      "nds_code": null,
      "nds_sum": null
    },
    {
      "position": 2,
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2.0,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ],
  "shared_with": []
}
```

### 4.3 Убрать категорию

**Запрос** — `DELETE /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/categories/87704e9c-b59d-405a-a39d-7a2dfb09363c` (пользователь A)

**Ответ** — `200`

```json
{
  "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
  "source": "manual",
  "my_access": "owner",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": "2026-10-08T18:49:13",
  "purchased_at": "2026-10-01T12:00:00",
  "receipt_type": 1,
  "total_sum": 631.3,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "fn": null,
  "fd": null,
  "fp": null,
  "comment": "Оплатили наличными",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": null,
  "business_card": null,
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    }
  ],
  "files": [],
  "shared_with_count": 0,
  "items": [
    {
      "position": 1,
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3.0,
      "sum": 451.5,
      "nds_code": null,
      "nds_sum": null
    },
    {
      "position": 2,
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2.0,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ],
  "shared_with": []
}
```

### 4.4 Убрать категорию, которой нет

**Запрос** — `DELETE /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/categories/87704e9c-b59d-405a-a39d-7a2dfb09363c` (пользователь A)

**Ответ** — `404`

```json
{
  "detail": "У чека нет такой категории"
}
```

## 5. Доступ другим пользователям

### 5.1 Дать доступ на просмотр

Только владелец. Повторный вызов для того же пользователя меняет уровень.

**Запрос** — `POST /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access` (пользователь A)

```json
{
  "user_id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
  "access_level": "view"
}
```

**Ответ** — `200`

```json
[
  {
    "user": {
      "id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
      "short_fio": "Степанов С. А."
    },
    "access_level": "view",
    "created_at": "2026-10-08T18:49:13"
  }
]
```

### 5.2 Пользователь B видит чек

`my_access: "view"`; список `shared_with` виден только владельцу.

**Запрос** — `GET /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь B)

**Ответ** — `200`

```json
{
  "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
  "source": "manual",
  "my_access": "view",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": "2026-10-08T18:49:13",
  "purchased_at": "2026-10-01T12:00:00",
  "receipt_type": 1,
  "total_sum": 631.3,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "fn": null,
  "fd": null,
  "fp": null,
  "comment": "Оплатили наличными",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": null,
  "business_card": null,
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    }
  ],
  "files": [],
  "shared_with_count": 1,
  "items": [
    {
      "position": 1,
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3.0,
      "sum": 451.5,
      "nds_code": null,
      "nds_sum": null
    },
    {
      "position": 2,
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2.0,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ]
}
```

### 5.3 B (view) пытается изменить

**Запрос** — `PATCH /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь B)

```json
{
  "comment": "правка"
}
```

**Ответ** — `403`

```json
{
  "detail": "Недостаточно прав для этого действия с чеком"
}
```

### 5.4 Расшаренные мне чеки

**Запрос** — `GET /api/supply/purchase-receipts?scope=shared` (пользователь B)

**Ответ** — `200`

```json
[
  {
    "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
    "source": "manual",
    "my_access": "view",
    "created_by": {
      "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
      "short_fio": "Бартинов А. М."
    },
    "created_at": "2026-10-08T18:49:12",
    "updated_at": "2026-10-08T18:49:13",
    "purchased_at": "2026-10-01T12:00:00",
    "receipt_type": 1,
    "total_sum": 631.3,
    "cash_sum": null,
    "ecash_sum": null,
    "seller_name": "ИП Иванов",
    "seller_inn": "290100000000",
    "retail_place": "Магазин «Электрика»",
    "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
    "fn": null,
    "fd": null,
    "fp": null,
    "comment": "Оплатили наличными",
    "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "object": {
      "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
      "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
    },
    "business_card_id": null,
    "business_card": null,
    "categories": [
      {
        "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
        "name": "Продукты",
        "color": "#2E9E4F",
        "is_system": true
      },
      {
        "id": "43b34198-42be-4b39-9dc8-dc855de99714",
        "name": "Стройматериалы",
        "color": "#E8A317",
        "is_system": true
      }
    ],
    "files": [],
    "shared_with_count": 1,
    "items": [
      {
        "position": 1,
        "name": "Кабель ВВГ 3x2.5",
        "price": 150.5,
        "quantity": 3.0,
        "sum": 451.5,
        "nds_code": null,
        "nds_sum": null
      },
      {
        "position": 2,
        "name": "Розетка",
        "price": 89.9,
        "quantity": 2.0,
        "sum": 179.8,
        "nds_code": 1,
        "nds_sum": 29.97
      }
    ]
  }
]
```

### 5.5 Повысить до edit

**Запрос** — `POST /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access` (пользователь A)

```json
{
  "user_id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
  "access_level": "edit"
}
```

**Ответ** — `200`

```json
[
  {
    "user": {
      "id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
      "short_fio": "Степанов С. А."
    },
    "access_level": "edit",
    "created_at": "2026-10-08T18:49:13"
  }
]
```

### 5.6 B (edit) меняет привязки

**Запрос** — `PATCH /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь B)

```json
{
  "comment": "Перепривязал к другому объекту"
}
```

**Ответ** — `200`

```json
{
  "id": "334e4e66-1d5b-44b2-b68f-59c3a2921ff7",
  "source": "manual",
  "my_access": "edit",
  "created_by": {
    "id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "short_fio": "Бартинов А. М."
  },
  "created_at": "2026-10-08T18:49:12",
  "updated_at": "2026-10-08T18:49:14",
  "purchased_at": "2026-10-01T12:00:00",
  "receipt_type": 1,
  "total_sum": 631.3,
  "cash_sum": null,
  "ecash_sum": null,
  "seller_name": "ИП Иванов",
  "seller_inn": "290100000000",
  "retail_place": "Магазин «Электрика»",
  "retail_place_address": "г. Архангельск, пр. Ломоносова, 10",
  "fn": null,
  "fd": null,
  "fp": null,
  "comment": "Перепривязал к другому объекту",
  "object_id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
  "object": {
    "id": "00081ac4-67de-4ae2-bf00-384c4d5c9bea",
    "short_name": "Жилой комплекс по ул.Валявкина в г. Архангельске"
  },
  "business_card_id": null,
  "business_card": null,
  "categories": [
    {
      "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
      "name": "Продукты",
      "color": "#2E9E4F",
      "is_system": true
    },
    {
      "id": "43b34198-42be-4b39-9dc8-dc855de99714",
      "name": "Стройматериалы",
      "color": "#E8A317",
      "is_system": true
    }
  ],
  "files": [],
  "shared_with_count": 1,
  "items": [
    {
      "position": 1,
      "name": "Кабель ВВГ 3x2.5",
      "price": 150.5,
      "quantity": 3.0,
      "sum": 451.5,
      "nds_code": null,
      "nds_sum": null
    },
    {
      "position": 2,
      "name": "Розетка",
      "price": 89.9,
      "quantity": 2.0,
      "sum": 179.8,
      "nds_code": 1,
      "nds_sum": 29.97
    }
  ]
}
```

### 5.7 Список доступов (владелец)

**Запрос** — `GET /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access` (пользователь A)

**Ответ** — `200`

```json
[
  {
    "user": {
      "id": "122d844d-b3be-42d9-8b5b-8a0058edb2d8",
      "short_fio": "Степанов С. А."
    },
    "access_level": "edit",
    "created_at": "2026-10-08T18:49:13"
  }
]
```

### 5.8 B смотрит список доступов

**Запрос** — `GET /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access` (пользователь B)

**Ответ** — `403`

```json
{
  "detail": "Недостаточно прав для этого действия с чеком"
}
```

### 5.9 B пытается удалить чек

**Запрос** — `DELETE /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь B)

**Ответ** — `403`

```json
{
  "detail": "Недостаточно прав для этого действия с чеком"
}
```

### 5.10 Дать доступ владельцу

**Запрос** — `POST /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access` (пользователь A)

```json
{
  "user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a"
}
```

**Ответ** — `400`

```json
{
  "detail": "Владелец чека и так имеет полный доступ"
}
```

### 5.11 Дать доступ несуществующему пользователю

**Запрос** — `POST /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access` (пользователь A)

```json
{
  "user_id": "nope"
}
```

**Ответ** — `404`

```json
{
  "detail": "Пользователь не найден"
}
```

### 5.12 B отказывается от доступа

Владелец так же может забрать доступ у любого, подставив его `user_id`.

**Запрос** — `DELETE /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7/access/122d844d-b3be-42d9-8b5b-8a0058edb2d8` (пользователь B)

**Ответ** — `204`

### 5.13 После этого B чек не видит

**Запрос** — `GET /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь B)

**Ответ** — `404`

```json
{
  "detail": "Чек не найден"
}
```

## 6. Категории чеков (`/api/supply/receipt-categories`)

### 6.1 Список доступных мне категорий

Стандартные (is_system=true) и мои личные. `can_edit` — могу ли я их менять. scope: all | system | mine.

**Запрос** — `GET /api/supply/receipt-categories?scope=all` (пользователь A)

**Ответ** — `200`

```json
[
  {
    "id": "3517f173-8b5d-4ade-a93b-470a9730dcd7",
    "name": "Продукты",
    "color": "#2E9E4F",
    "is_system": true,
    "owner_user_id": null,
    "can_edit": false,
    "created_at": "2026-10-08T18:49:12",
    "updated_at": null
  },
  {
    "id": "43b34198-42be-4b39-9dc8-dc855de99714",
    "name": "Стройматериалы",
    "color": "#E8A317",
    "is_system": true,
    "owner_user_id": null,
    "can_edit": false,
    "created_at": "2026-10-08T18:49:12",
    "updated_at": null
  },
  {
    "id": "87704e9c-b59d-405a-a39d-7a2dfb09363c",
    "name": "Командировка",
    "color": "#3B82F6",
    "is_system": false,
    "owner_user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
    "can_edit": true,
    "created_at": "2026-10-08T18:49:12",
    "updated_at": null
  }
]
```

### 6.2 Создать личную категорию

Личная категория видна только её владельцу.

**Запрос** — `POST /api/supply/receipt-categories` (пользователь A)

```json
{
  "name": "Хоз. нужды",
  "color": "#9333ea"
}
```

**Ответ** — `201`

```json
{
  "id": "7b99b12d-ba83-4298-b4b7-d9a0f1a7d60f",
  "name": "Хоз. нужды",
  "color": "#9333EA",
  "is_system": false,
  "owner_user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
  "can_edit": true,
  "created_at": "2026-10-08T18:49:14",
  "updated_at": null
}
```

### 6.3 Создать стандартную категорию (администратор)

**Запрос** — `POST /api/supply/receipt-categories` (пользователь администратор)

```json
{
  "name": "Топливо",
  "color": "#EF4444",
  "is_system": true
}
```

**Ответ** — `201`

```json
{
  "id": "5d7c3910-75bd-4998-b1ee-d54b3d6bc308",
  "name": "Топливо",
  "color": "#EF4444",
  "is_system": true,
  "owner_user_id": null,
  "can_edit": true,
  "created_at": "2026-10-08T18:49:14",
  "updated_at": null
}
```

### 6.4 Обычный пользователь создаёт стандартную

**Запрос** — `POST /api/supply/receipt-categories` (пользователь A)

```json
{
  "name": "Топливо2",
  "is_system": true
}
```

**Ответ** — `403`

```json
{
  "detail": "Стандартные категории может создавать только администратор"
}
```

### 6.5 Повторное название

Название уникально внутри своей области (регистр не важен): личное может совпадать со стандартным, но не с другим вашим.

**Запрос** — `POST /api/supply/receipt-categories` (пользователь A)

```json
{
  "name": "командировка"
}
```

**Ответ** — `409`

```json
{
  "detail": "Категория «командировка» уже есть среди ваших категорий"
}
```

### 6.6 Неверный цвет

**Запрос** — `POST /api/supply/receipt-categories` (пользователь A)

```json
{
  "name": "Тест",
  "color": "red"
}
```

**Ответ** — `422` (валидация тела запроса)

```json
{
  "detail": [
    {
      "type": "string_pattern_mismatch",
      "loc": [
        "body",
        "color"
      ],
      "msg": "String should match pattern '^#[0-9A-Fa-f]{6}$'",
      "input": "red",
      "ctx": {
        "pattern": "^#[0-9A-Fa-f]{6}$"
      }
    }
  ]
}
```

### 6.7 Изменить название и цвет

`color: null` убирает цвет.

**Запрос** — `PATCH /api/supply/receipt-categories/87704e9c-b59d-405a-a39d-7a2dfb09363c` (пользователь A)

```json
{
  "name": "Командировки",
  "color": "#0EA5E9"
}
```

**Ответ** — `200`

```json
{
  "id": "87704e9c-b59d-405a-a39d-7a2dfb09363c",
  "name": "Командировки",
  "color": "#0EA5E9",
  "is_system": false,
  "owner_user_id": "06968a8b-e24c-4099-998d-3d4c16ebc63a",
  "can_edit": true,
  "created_at": "2026-10-08T18:49:12",
  "updated_at": "2026-10-08T18:49:14"
}
```

### 6.8 Изменить стандартную обычным пользователем

**Запрос** — `PATCH /api/supply/receipt-categories/3517f173-8b5d-4ade-a93b-470a9730dcd7` (пользователь A)

```json
{
  "color": "#000000"
}
```

**Ответ** — `403`

```json
{
  "detail": "Стандартные категории может менять только администратор"
}
```

### 6.9 Чужая личная категория

Личные категории других пользователей недоступны и выглядят как несуществующие.

**Запрос** — `GET /api/supply/receipt-categories/87704e9c-b59d-405a-a39d-7a2dfb09363c` (пользователь B)

**Ответ** — `404`

```json
{
  "detail": "Категория чеков не найдена"
}
```

### 6.10 Удалить категорию, привязанную к чекам

Пока категория есть на чеках, она не удаляется.

**Запрос** — `DELETE /api/supply/receipt-categories/43b34198-42be-4b39-9dc8-dc855de99714` (пользователь администратор)

**Ответ** — `409`

```json
{
  "detail": {
    "message": "Категория привязана к чекам; при удалении она будет снята с них. Повторите с force=true",
    "usage": {
      "receipts": 2
    }
  }
}
```

### 6.11 Удалить с force=true

Категория удаляется и снимается со всех чеков.

**Запрос** — `DELETE /api/supply/receipt-categories/43b34198-42be-4b39-9dc8-dc855de99714?force=true` (пользователь администратор)

**Ответ** — `204`

## 7. Удаление чека

### 7.1 Владелец удаляет чек

Позиции, категории и доступы удаляются вместе с чеком.

**Запрос** — `DELETE /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь A)

**Ответ** — `204`

### 7.2 Повторное обращение

**Запрос** — `GET /api/supply/purchase-receipts/334e4e66-1d5b-44b2-b68f-59c3a2921ff7` (пользователь A)

**Ответ** — `404`

```json
{
  "detail": "Чек не найден"
}
```
