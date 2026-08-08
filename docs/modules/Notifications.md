
> Версия: 1.0  
> Статус: Проектирование  
> Последнее обновление: 2026-07-09  
> Ответственный: TBD  

---

# Назначение

Модуль **Notifications** отвечает за доставку уведомлений пользователям платформы.

Модуль обеспечивает коммуникацию между системой и пользователем, информируя о важных событиях обучения, прогресса и работы платформы.

Модуль покрывает:

- персональные уведомления;
- системные сообщения;
- напоминания о подготовке;
- уведомления об изменениях состояния обучения.

Notifications существует для повышения вовлечённости пользователя и поддержки регулярной подготовки к экзаменам.

---

# Зона ответственности

Модуль отвечает за:

- создание уведомлений;
- хранение истории уведомлений;
- управление статусами уведомлений;
- отправку уведомлений пользователям;
- настройку предпочтений пользователя;
- обработку каналов доставки;
- интеграцию с внешними сервисами уведомлений.

---

# Что НЕ входит в ответственность

Модуль не отвечает за:

- генерацию учебного контента;
- создание учебного плана;
- анализ прогресса пользователя;
- определение необходимости уведомления;
- бизнес-логику обучения;
- управление пользователями.

Модуль получает события от других модулей и только отвечает за доставку.

---

# Ограничения

Модуль не должен:

- самостоятельно принимать образовательные решения;
- изменять данные других модулей;
- хранить профиль пользователя;
- хранить прогресс подготовки;
- отправлять уведомления без бизнес-события или явной команды;
- создавать циклические зависимости.

---

# Архитектура

Notifications является событийным модулем.

Основной принцип:

Другие модули публикуют события → Notifications анализирует событие → создаёт уведомление → доставляет пользователю.

Поток:

```

Progress Module  
|  
v  
Domain Event  
|  
v  
Notifications  
|  
+--> Email Provider  
|  
+--> Push Provider  
|  
+--> In-App Notifications  
|  
v  
User

```

Пример:

```

ProgressUpdated  
|  
v  
Notifications  
|  
v  
"Сегодня завершите повторение темы"

```

---

# Структура папки

```

notifications/

├── router.py  
├── service.py  
├── repository.py  
├── schemas.py  
├── models.py  
├── validators.py  
├── permissions.py  
├── exceptions.py  
└── events.py

```

---

# Компоненты

## Router

Назначение:

Предоставляет API для работы пользователя с уведомлениями.

Ответственность:

- получение списка уведомлений;
- отметка уведомления как прочитанного;
- управление настройками уведомлений.

Не содержит:

- логику генерации уведомлений;
- правила отправки.

---

## Service

Назначение:

Содержит бизнес-логику уведомлений.

Ответственность:

- создание уведомлений;
- выбор канала доставки;
- обработка шаблонов;
- отправка уведомлений;
- изменение статусов.

Основные методы:

```

create_notification()

send_notification()

mark_as_read()

update_preferences()

```

---

## Repository

Назначение:

Работа с данными уведомлений.

Ответственность:

- сохранение уведомлений;
- получение истории;
- обновление статусов;
- работа с настройками пользователя.

---

## Schemas

Назначение:

Описание DTO для API.

Содержит:

- создание уведомления;
- чтение уведомления;
- настройки пользователя;
- статусы.

---

## Models

Назначение:

Описание ORM моделей.

Содержит:

- Notification;
- NotificationPreference;
- NotificationTemplate.

---

## Validators

Назначение:

Проверка входных данных.

Ответственность:

- проверка типа уведомления;
- проверка доступных каналов;
- проверка корректности шаблонов.

---

## Permissions

Назначение:

Контроль доступа.

Ответственность:

- пользователь видит только свои уведомления;
- пользователь изменяет только свои настройки.

---

## Exceptions

Назначение:

Ошибки Notifications.

Примеры:

```

NotificationNotFound

DeliveryFailed

InvalidNotificationType

ChannelUnavailable

```

---

## Events

Назначение:

Описание событий взаимодействия.

Модуль получает события от других доменных модулей и создаёт уведомления.

---

# Основные сущности

## Notification

Конкретное уведомление пользователя.

Пример:

```

"Вы завершили тему Алгоритмы"

```

---

## NotificationPreference

Настройки пользователя.

Определяет:

- какие уведомления получать;
- через какие каналы;
- время отправки.

---

## NotificationTemplate

Шаблон сообщения.

Пример:

```

Название:  
Progress Reminder

Шаблон:  
"У вас осталось {tasks} заданий"

```

---

# Модель данных

## Notification

Table:

```

notifications

```

Fields:

| Field | Type | Constraints |
|-|-|-|
| id | UUID | PK |
| user_id | UUID | FK |
| type | Enum | NOT NULL |
| title | String | NOT NULL |
| message | Text | NOT NULL |
| status | Enum | NOT NULL |
| read_at | Timestamp | NULL |
| created_at | Timestamp | NOT NULL |

Indexes:

```

idx_notifications_user_id

idx_notifications_status

```

Constraints:

```

status IN (  
UNREAD,  
READ,  
SENT,  
FAILED  
)

```

Relationships:

```

User → Notification

```

---

## NotificationPreference

Table:

```

notification_preferences

```

Fields:

| Field | Type | Constraints |
|-|-|-|
| id | UUID | PK |
| user_id | UUID | UNIQUE |
| email_enabled | Boolean | DEFAULT TRUE |
| push_enabled | Boolean | DEFAULT TRUE |
| reminders_enabled | Boolean | DEFAULT TRUE |

Indexes:

```

idx_notification_preferences_user_id

```

Relationships:

```

User → NotificationPreference

```

---

# Сервисы

## NotificationService

Назначение:

Управление жизненным циклом уведомлений.

Методы:

```

create_notification()

send()

mark_read()

get_user_notifications()

update_preferences()

```

---

## ReminderService

Назначение:

Создание автоматических напоминаний.

Методы:

```

generate_learning_reminders()

check_inactive_users()

```

Описание:

Вход:

```

user_progress  
learning_plan

```

Логика:

- анализирует события;
- создаёт уведомление;
- передаёт его NotificationService.

---

# Схемы данных

## NotificationCreate

Input:

```

user_id

type

title

message

```

---

## NotificationUpdate

Input:

```

status

read_at

```

---

## NotificationRead

Output:

```

id

title

message

type

status

created_at

```

---

# Permissions

| Action | Role |
|-|-|
| View own notifications | User |
| Mark own notification as read | User |
| Change notification settings | User |
| Manage templates | Admin |
| View all notifications | Admin |

---

# API / Интерфейсы

## GET /notifications

Назначение:

Получить уведомления пользователя.

Request:

```

limit

offset

```

Response:

```

notifications[]

```

---

## PATCH /notifications/{id}/read

Назначение:

Отметить уведомление прочитанным.

Request:

```

notification_id

```

Response:

```

status

```

---

## GET /notifications/preferences

Назначение:

Получить настройки уведомлений.

Response:

```

email_enabled

push_enabled

reminders_enabled

```

---

## PATCH /notifications/preferences

Назначение:

Изменить настройки уведомлений.

Request:

```

settings

```

Response:

```

updated_preferences

```

---

# Бизнес-правила

- Пользователь получает только собственные уведомления.
- Пользователь может отключить необязательные уведомления.
- Критические системные уведомления могут игнорировать пользовательские настройки.
- Каждое уведомление имеет статус.
- Ошибки доставки должны сохраняться.
- Повторная отправка возможна после ошибки.

---

# Инварианты

- Notification всегда принадлежит пользователю.
- Notification всегда имеет тип.
- Notification всегда имеет статус.
- Удалённый пользователь не должен получать новые уведомления.
- Настройки уведомлений не могут принадлежать нескольким пользователям.

---

# Исключения

```

NotificationNotFound

DeliveryFailed

ChannelUnavailable

InvalidTemplate

AccessDenied

```

---

# Доменные события

## Публикует

```

NotificationCreated

NotificationSent

NotificationFailed

```

---

## Подписывается

```

UserRegistered

UserLoggedIn

ProgressUpdated

RoadmapGenerated

TaskCompleted

AchievementUnlocked

SubscriptionChanged

```

---

# Зависимости

## Использует

- Users;
- Progress;
- Roadmap;
- Tasks;
- Payments;
- Leaderboards.

---

## Используется

- Frontend;
- Mobile Client;
- Admin Panel.

---

# Безопасность

Описание:

- проверка владельца уведомления;
- защита персональных сообщений;
- ограничение массовой отправки;
- аудит отправок.

Не хранить:

- пароли;
- токены;
- секретные данные.

---

# Логирование

Логируются:

- создание уведомлений;
- отправка;
- ошибки доставки;
- изменение настроек.

Не логируются:

- персональные данные;
- содержимое приватных сообщений;
- токены;
- пароли.

---

# Возможности расширения

Будущие возможности:

- Telegram уведомления;
- WhatsApp уведомления;
- умные AI-напоминания;
- адаптивные уведомления по поведению пользователя;
- оптимальное время отправки;
- персональные мотивационные сообщения от AI.

---

# Правила разработки

- Router не содержит бизнес-логики.
- Service содержит бизнес-логику.
- Repository работает только с данными.
- Уведомления создаются только через события или сервис.
- Новые типы уведомлений должны быть задокументированы.
- Изменение событий требует обновления Event Catalog.

---

# Definition of Done

Модуль считается завершенным, если:

- определена ответственность;
- описаны ограничения;
- описана архитектура;
- описаны компоненты;
- описана модель данных;
- описаны сервисы;
- описаны схемы;
- описаны API;
- описаны права доступа;
- описаны события;
- добавлены тесты;
- настроена доставка уведомлений;
- документация актуальна.