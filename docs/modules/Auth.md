
> Версия: 1.1  
> Статус: Проектирование  
> Последнее обновление: 2026-07-09  
> Ответственный: TBD  

---

# Назначение

Модуль **Auth** отвечает за аутентификацию и авторизацию пользователей платформы.

Основная задача модуля — безопасно идентифицировать пользователя, управлять доступом к системе, выдавать токены доступа и обеспечивать защиту API.

Auth является единственным модулем, который отвечает за:

- проверку личности пользователя;
- управление учетными данными;
- управление пользовательскими сессиями;
- создание и проверку токенов доступа.

Модуль **не хранит профиль пользователя**.

Работа с профилем, настройками и персональными данными пользователя осуществляется модулем **Users**.

---

# Зона ответственности

Модуль отвечает за:

- регистрацию пользователей;
- вход пользователя в систему;
- выход пользователя из системы;
- создание Access Token;
- создание Refresh Token;
- обновление Access Token;
- хранение активных сессий;
- подтверждение электронной почты;
- восстановление пароля;
- смену пароля;
- проверку JWT;
- управление сессиями пользователя;
- контроль доступа к защищенным API.

---

# Что НЕ входит в ответственность

Модуль не отвечает за:

- пользовательский профиль;
- имя пользователя;
- аватар;
- настройки пользователя;
- учебный прогресс;
- статистику обучения;
- подписки;
- платежи;
- рекомендации AI;
- образовательные данные.

Этими функциями занимаются:

- Users;
- Progress;
- Analytics;
- Payments;
- AI.

---

# Ограничения

Модуль Auth не должен:

- хранить профиль пользователя;
- хранить образовательные данные;
- управлять пользовательскими настройками;
- изменять данные Users напрямую;
- создавать роли пользователей;
- содержать бизнес-логику обучения.

Дополнительные ограничения:

- Пароли никогда не хранятся в открытом виде.
- JWT не должен содержать чувствительные данные.
- Refresh Token должен иметь возможность отзыва.
- Один email соответствует одному аккаунту.
- Все операции аутентификации должны проходить через Auth.
- Другие модули не должны самостоятельно проверять пароли или создавать JWT.

---

# Архитектура

```
Client

    │

    ▼

Auth Router

    │

    ▼

Auth Service

    │

    ├───────────────┐

    ▼               ▼

Repository     Token Service

    │

    ▼

Database
```

---

# Структура папки

```
auth/

├── router.py
├── service.py
├── repository.py
├── schemas.py
├── models.py
├── security.py
├── jwt.py
├── dependencies.py
├── validators.py
├── exceptions.py
└── events.py
```

---

# Компоненты

## router.py

Назначение:

HTTP API слой.

Ответственность:

- обработка HTTP запросов;
- валидация входных данных;
- возврат HTTP ответов.

Не содержит:

- бизнес-логику;
- SQL-запросы.

---

## service.py

Назначение:

Основной слой бизнес-логики.

Ответственность:

- регистрация пользователя;
- вход пользователя;
- проверка учетных данных;
- создание сессий;
- управление токенами;
- запуск событий.

Не выполняет:

- прямые SQL-запросы.

---

## repository.py

Назначение:

Работа с базой данных.

Методы:

```
create_credentials()

get_by_email()

get_by_user_id()

create_session()

get_session()

delete_session()

delete_user_sessions()

update_password()

verify_email()
```

Repository не содержит:

- JWT-логику;
- бизнес-правила.

---

## security.py

Назначение:

Работа с безопасностью паролей.

Содержит:

- bcrypt;
- Argon2;
- hashing;
- password verification.

Методы:

```
hash_password()

verify_password()

validate_password_strength()
```

---

## jwt.py

Назначение:

Работа с JWT.

Методы:

```
create_access_token()

create_refresh_token()

decode_token()

verify_token()

```

---

## dependencies.py

Назначение:

FastAPI зависимости.

Содержит:

```
CurrentUser

CurrentAdmin

CurrentTeacher
```

---

## validators.py

Проверки:

- email;
- пароль;
- токены.

---

## exceptions.py

Ошибки модуля.

---

# Основные сущности

## UserCredentials

Данные необходимые для входа пользователя.

Поля:

```
id

user_id

email

password_hash

email_verified

created_at

updated_at
```

---

## RefreshSession

Активная сессия пользователя.

Поля:

```
id

user_id

token_hash

device

ip_address

expires_at

created_at
```

---

# Модель данных

## UserCredentials

Table:

```
user_credentials
```

Fields:

| Field | Type | Constraints |
|-|-|-|
| id | UUID | PK |
| user_id | UUID | FK users.id, UNIQUE |
| email | VARCHAR(255) | NOT NULL, UNIQUE |
| password_hash | VARCHAR(255) | NOT NULL |
| email_verified | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMP | NOT NULL |
| updated_at | TIMESTAMP | NOT NULL |

Indexes:

```
idx_user_credentials_email

idx_user_credentials_user_id
```

Constraints:

```
UNIQUE(email)

UNIQUE(user_id)
```

---

## RefreshSession

Table:

```
refresh_sessions
```

Fields:

| Field | Type | Constraints |
|-|-|-|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| token_hash | VARCHAR(255) | NOT NULL |
| device | VARCHAR(255) | NULL |
| ip_address | VARCHAR(45) | NULL |
| expires_at | TIMESTAMP | NOT NULL |
| created_at | TIMESTAMP | NOT NULL |

Indexes:

```
idx_refresh_sessions_user_id

idx_refresh_sessions_token_hash
```

---

# Сервисы

## AuthService

Методы:

```
register_user()

login_user()

logout_user()

refresh_token()

change_password()

reset_password()

verify_email()
```

---

## TokenService

Методы:

```
create_access_token()

create_refresh_token()

validate_token()

revoke_token()
```

---

## PasswordService

Методы:

```
hash_password()

verify_password()

validate_password_strength()
```

---

# JWT

Используются два типа токенов.

## Access Token

Срок жизни:

```
15 минут
```

Назначение:

```
Авторизация API запросов
```

Хранение:

```
Не хранится в базе данных
```

---

## Refresh Token

Срок жизни:

```
30 дней
```

Назначение:

```
Получение нового Access Token
```

Хранение:

```
В БД или Redis
```

---

# Схемы данных

## RegisterRequest

Input:

```
email: EmailStr

password: str
```

---

## LoginRequest

Input:

```
email: EmailStr

password: str
```

---

## TokenResponse

Output:

```
access_token: str

refresh_token: str

token_type: str
```

---

## PasswordResetRequest

Input:

```
email: EmailStr
```

---

## ChangePasswordRequest

Input:

```
old_password: str

new_password: str
```

---

# Permissions

| Action | Role |
|-|-|
| Register | Anonymous |
| Login | Anonymous |
| Logout | Authenticated User |
| Refresh Token | Authenticated User |
| Change Password | Authenticated User |
| Reset Password | Anonymous |
| Verify Email | Anonymous |
| Manage Sessions | User |

---

# API / Интерфейсы

## POST /auth/register

Создание нового аккаунта.

Request:

```
email

password
```

Response:

```
user_id

access_token

refresh_token
```

---

## POST /auth/login

Вход пользователя.

Request:

```
email

password
```

Response:

```
access_token

refresh_token
```

---

## POST /auth/logout

Удаляет активную сессию.

---

## POST /auth/refresh

Создает новый Access Token.

---

## POST /auth/change-password

Изменение пароля.

---

## POST /auth/forgot-password

Запрос восстановления пароля.

---

## POST /auth/reset-password

Установка нового пароля.

---

## GET /auth/me

Получение информации текущей аутентификации.

---

# Бизнес-правила

## Регистрация

При регистрации:

- email должен быть уникальным;
- пароль проходит проверку сложности;
- пароль хешируется;
- создается учетная запись;
- создается пользовательская сессия;
- отправляется событие UserRegistered.

---

## Пароль

Минимальные требования:

- минимум 8 символов;
- минимум одна цифра;
- минимум одна буква.

---

## Email

После регистрации:

- email имеет статус неподтвержденного;
- отправляется письмо подтверждения;
- подтверждение меняет статус email.

---

# Инварианты

Следующие правила никогда не должны нарушаться:

- Пароль пользователя никогда не хранится в открытом виде.
- В базе данных хранится только hash пароля.
- Email уникален.
- Refresh Token принадлежит только одной сессии.
- Истекший Refresh Token недействителен.
- Access Token имеет ограниченное время жизни.
- Access Token не хранится в БД.
- JWT всегда подписан секретным ключом.
- Недействительный JWT не проходит проверку.
- Активная сессия всегда принадлежит существующему пользователю.
- Logout делает Refresh Token недействительным.
- Auth не изменяет профиль пользователя.
- Auth не хранит данные обучения.
- Только Auth управляет токенами.

---

# Исключения

```
EmailAlreadyExists

InvalidCredentials

EmailNotVerified

TokenExpired

InvalidToken

PasswordTooWeak

RefreshTokenExpired

SessionNotFound
```

---

# Доменные события

## Публикует

### UserRegistered

Payload:

```
{
user_id,
email,
created_at
}
```

---

### UserLoggedIn

Payload:

```
{
user_id,
session_id,
created_at
}
```

---

### UserLoggedOut

Payload:

```
{
user_id,
session_id
}
```

---

### PasswordChanged

Payload:

```
{
user_id,
created_at
}
```

---

### EmailVerified

Payload:

```
{
user_id
}
```

---

## Подписывается

### UserDeleted

Payload:

```
{
user_id
}
```

Действия:

- удалить активные сессии;
- отозвать Refresh Token.

---

# Зависимости

## Использует

- Users;
- Notifications;
- Database;
- Redis;
- Event Bus.

---

## Используется

- API Gateway;
- все защищенные модули платформы.

---

# Безопасность

Используется:

- JWT;
- HTTPS;
- bcrypt или Argon2;
- Rate Limiting;
- CORS;
- CSRF при Cookie-based авторизации.

Дополнительно:

- защита от перебора паролей;
- ограничение попыток входа;
- аудит критических операций.

---

# Логирование

Логируются:

- успешные входы;
- неудачные входы;
- создание аккаунта;
- изменение пароля;
- выход;
- восстановление пароля;
- подозрительная активность.

Не логируются:

- пароли;
- JWT;
- Refresh Token;
- секретные ключи.

---

# Возможности расширения

В будущем:

- OAuth;
- Google;
- VK;
- Яндекс;
- 2FA;
- вход по одноразовой ссылке;
- управление устройствами;
- история авторизаций.

---

# Правила разработки

- Router не содержит бизнес-логики.
- Service содержит бизнес-логику.
- Repository работает только с данными.
- JWT изолирован.
- Пароли никогда не хранятся открыто.
- Изменения схем БД выполняются через миграции.
- Новые события добавляются в Event Catalog.

---

# Definition of Done

Модуль считается завершенным, если:

- реализована регистрация;
- реализован вход;
- реализован logout;
- реализован JWT;
- реализован Refresh Token;
- реализовано подтверждение Email;
- реализовано восстановление пароля;
- определены модели БД;
- определены схемы API;
- определены события;
- реализована безопасность;
- настроено логирование;
- написаны тесты;
- документация актуальна.