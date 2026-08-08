
> Версия: 1.1  
> Статус: Проектирование  
> Последнее обновление: 2026-07-09  
> Ответственный: TBD  

---

# Назначение

Модуль **Subjects** отвечает за управление учебными предметами платформы.

Предмет является верхним уровнем образовательной структуры системы и объединяет:

- темы;
- теоретические материалы;
- задания;
- учебные маршруты;
- прогресс пользователя.

Примеры предметов:

- Математика;
- Русский язык;
- Физика;
- Информатика;
- Химия;
- Биология.

Subjects является единым источником информации о доступных учебных направлениях платформы.

---

# Зона ответственности

Модуль отвечает за:

- создание предметов;
- хранение предметов;
- обновление информации о предметах;
- управление статусом доступности;
- хранение метаданных предметов;
- определение типа экзамена;
- предоставление информации другим образовательным модулям.

---

# Что НЕ входит в ответственность

Модуль не отвечает за:

- содержание учебных материалов;
- хранение теории;
- генерацию заданий;
- проверку ответов;
- построение индивидуального плана обучения;
- хранение прогресса пользователя;
- аналитику обучения;
- AI-рекомендации.

Эти функции реализуются:

- Theory;
- Tasks;
- Roadmap;
- Progress;
- Analytics;
- AI.

---

# Ограничения

Модуль не должен:

- хранить темы внутри собственной таблицы;
- хранить учебные материалы;
- хранить задания;
- управлять процессом обучения;
- зависеть от пользователей;
- изменять данные других модулей напрямую.

Дополнительные ограничения:

- Каждый предмет имеет уникальный идентификатор.
- Название предмета уникально.
- Каждый предмет должен иметь тип экзамена.
- Удаление предмета запрещено при наличии зависимых сущностей.
- Только администратор может изменять структуру предметов.

---

# Архитектура

Subjects является частью образовательного домена.

Структура:

```
Subjects

    │

    ▼

Topics

    │

    ├── Theory

    ├── Tasks

    ├── Roadmap

    └── Progress
```

Subjects является владельцем верхнего уровня образовательной структуры.

---

# Структура папки

```
subjects/

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

## router.py

Назначение:

HTTP API слой.

Ответственность:

- получение списка предметов;
- получение предмета;
- создание предмета;
- обновление предмета;
- удаление предмета.

Не содержит:

- бизнес-логику;
- SQL-запросы.

---

## service.py

Назначение:

Основной бизнес-слой.

Методы:

```
create_subject()

update_subject()

delete_subject()

get_subject()

get_subjects()

activate_subject()

deactivate_subject()
```

Ответственность:

- бизнес-правила;
- проверка ограничений;
- управление состоянием предметов.

---

## repository.py

Назначение:

Работа с базой данных.

Методы:

```
create()

get_by_id()

get_all()

update()

delete()

exists_by_name()
```

Repository не содержит бизнес-логики.

---

## schemas.py

Назначение:

DTO для API.

Содержит:

- SubjectCreate;
- SubjectUpdate;
- SubjectRead.

---

## models.py

Назначение:

SQLAlchemy модели.

Основная модель:

- Subject.

---

## validators.py

Проверяет:

- корректность названия;
- уникальность;
- допустимость статуса;
- корректность типа экзамена.

---

## permissions.py

Управляет доступом.

Пример:

```
Admin

Teacher

Student
```

---

## exceptions.py

Ошибки:

```
SubjectNotFound

SubjectAlreadyExists

SubjectHasDependencies

InvalidSubjectData
```

---

# Основные сущности

## Subject

Назначение:

Представляет учебный предмет платформы.

Поля:

```
id

name

code

description

exam_type

is_active

created_at

updated_at
```

---

## ExamType

Тип экзамена.

Enum:

```
EGE

OGE

BOTH
```

---

# Модель данных

## Subject

Table:

```
subjects
```

Fields:

| Field | Type | Constraints |
|-|-|-|
| id | UUID | PK |
| name | VARCHAR(255) | NOT NULL, UNIQUE |
| code | VARCHAR(50) | NOT NULL, UNIQUE |
| description | TEXT | NULL |
| exam_type | ENUM | NOT NULL |
| is_active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMP | NOT NULL |
| updated_at | TIMESTAMP | NOT NULL |

Indexes:

```
idx_subjects_name

idx_subjects_code

idx_subjects_exam_type
```

Constraints:

```
UNIQUE(name)

UNIQUE(code)
```

---

# Сервисы

## SubjectService

Назначение:

Управление жизненным циклом предмета.

Методы:

```
create_subject()

update_subject()

delete_subject()

activate_subject()

deactivate_subject()

get_subject_tree()
```

---

## SubjectValidator

Методы:

```
validate_name()

validate_exam_type()

check_dependencies()
```

---

# Схемы данных

## SubjectCreate

Input:

```
name: str

code: str

description: str | None

exam_type: ExamType
```

---

## SubjectUpdate

Input:

```
name: str | None

description: str | None

exam_type: ExamType | None

is_active: bool | None
```

---

## SubjectRead

Output:

```
id

name

code

description

exam_type

is_active

created_at

updated_at
```

---

# Permissions

| Action | Role |
|-|-|
| View Subjects | Student |
| View Subjects | Teacher |
| Create Subject | Administrator |
| Update Subject | Administrator |
| Delete Subject | Administrator |
| Activate Subject | Administrator |

---

# API / Интерфейсы

## GET /subjects

Получение списка предметов.

Response:

```
[
 SubjectRead
]
```

---

## GET /subjects/{id}

Получение предмета.

Response:

```
SubjectRead
```

---

## POST /subjects

Создание предмета.

Role:

```
Administrator
```

Request:

```
SubjectCreate
```

Response:

```
SubjectRead
```

---

## PATCH /subjects/{id}

Обновление предмета.

Role:

```
Administrator
```

Request:

```
SubjectUpdate
```

---

## DELETE /subjects/{id}

Удаление предмета.

Role:

```
Administrator
```

---

# Бизнес-правила

- Каждый предмет имеет уникальное название.
- Каждый предмет имеет уникальный код.
- Каждый предмет относится минимум к одному типу экзамена.
- Неактивные предметы не используются в новых учебных сценариях.
- Предмет нельзя удалить при наличии связанных Topics.
- Изменение структуры предметов доступно только администраторам.

---

# Инварианты

Следующие правила никогда не должны нарушаться:

- Каждый Subject имеет уникальный идентификатор.
- Каждый Subject имеет название.
- Название Subject уникально.
- Код Subject уникален.
- Каждый Subject имеет тип экзамена.
- Неактивный Subject не используется для новых учебных процессов.
- Subject не зависит от пользователя.
- Другие модули не изменяют Subject напрямую.
- Topics не могут существовать без Subject.

---

# Исключения

```
SubjectNotFound

SubjectAlreadyExists

InvalidSubjectData

SubjectHasDependencies

SubjectInactive
```

---

# Доменные события

## Публикует

### SubjectCreated

Payload:

```
{
subject_id,
name,
exam_type
}
```

---

### SubjectUpdated

Payload:

```
{
subject_id,
changed_fields
}
```

---

### SubjectActivated

Payload:

```
{
subject_id
}
```

---

### SubjectDeactivated

Payload:

```
{
subject_id
}
```

---

### SubjectDeleted

Payload:

```
{
subject_id
}
```

---

## Подписывается

### ExamStructureUpdated

Payload:

```
{
exam_type,
version
}
```

---

# Зависимости

## Использует

- Database;
- Event Bus.

---

## Используется

- Topics;
- Theory;
- Tasks;
- Roadmap;
- Progress;
- Analytics;
- AI.

---

# Безопасность

Модуль обеспечивает:

- проверку прав администратора;
- защиту образовательной структуры;
- контроль изменений;
- валидацию входных данных.

---

# Логирование

Логируются:

- создание предмета;
- изменение предмета;
- изменение статуса;
- удаление;
- ошибки операций.

Не логируются:

- персональные данные;
- внутренние секреты.

---

# Возможности расширения

В будущем:

- версии учебных программ;
- соответствие спецификациям ФИПИ;
- региональные программы;
- международные экзамены;
- граф знаний;
- AI-анализ структуры предметов.

---

# Правила разработки

- Subjects является владельцем предметов.
- Topics не создают предметы самостоятельно.
- Другие модули получают предметы через публичные интерфейсы.
- Изменения схемы БД выполняются через миграции.
- Изменение событий требует обновления Event Catalog.

---

# Definition of Done

Модуль считается завершенным, если:

- реализовано создание предметов;
- реализовано получение предметов;
- реализовано обновление;
- реализовано удаление;
- реализованы права доступа;
- описана модель БД;
- описаны схемы;
- описаны сервисы;
- определены события;
- настроено логирование;
- написаны тесты;
- документация актуальна.
- 