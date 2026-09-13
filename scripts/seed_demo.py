"""Пересобирает демонстрационные данные: справочники, работников, дейлики за 30 дней."""

import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    DailyEntry,
    Department,
    EmployeeProfile,
    EmployeeSettings,
    EntryItem,
    InternalChatMessage,
    Job,
    Reviewer,
    Statistic,
    Task,
    User,
)
from app.models.enums import (
    DailyEntryStatus,
    DayType,
    EntryItemStatus,
    ScheduleType,
    UserRole,
    UserStatus,
)

WINDOW_DAYS = 30
DEMO_PASSWORD = "Demo12345"
SEED = 20260913

IN_PROGRESS = EntryItemStatus.IN_PROGRESS.value
BLOCKED = EntryItemStatus.BLOCKED.value
DONE = EntryItemStatus.DONE.value
DROPPED = EntryItemStatus.DROPPED.value

REVIEWERS = [
    {
        "name": "Тимлид разработки",
        "description": "Оценивает продуктивность и инженерную культуру разработчиков",
        "metrics": [
            {
                "json_name": "code_quality",
                "display_name": "Качество кода",
                "description": "Соответствие кода стандартам команды, читаемость, покрытие тестами",
                "value": 9,
            },
            {
                "json_name": "timeline_awareness",
                "display_name": "Соблюдение сроков",
                "description": "Насколько точно разработчик попадает в оценки и дедлайны",
                "value": 8,
            },
            {
                "json_name": "blockers_handling",
                "display_name": "Работа с блокерами",
                "description": "Скорость эскалации и снятия блокирующих задач",
                "value": 7,
            },
        ],
    },
    {
        "name": "Руководитель поддержки",
        "description": "Оценивает работу линии поддержки с клиентскими обращениями",
        "metrics": [
            {
                "json_name": "response_time",
                "display_name": "Скорость ответа",
                "description": "Среднее время первого ответа на обращение клиента",
                "value": 9,
            },
            {
                "json_name": "resolution_rate",
                "display_name": "Доля решённых обращений",
                "description": "Процент обращений, закрытых без повторного открытия",
                "value": 8,
            },
            {
                "json_name": "client_satisfaction",
                "display_name": "Удовлетворённость клиентов",
                "description": "Оценки, которые клиенты ставят после закрытия обращения",
                "value": 7,
            },
        ],
    },
    {
        "name": "Директор по маркетингу",
        "description": "Оценивает эффективность маркетинговых активностей",
        "metrics": [
            {
                "json_name": "campaign_effectiveness",
                "display_name": "Эффективность кампаний",
                "description": "Достижение KPI по охвату, конверсии и стоимости привлечения",
                "value": 9,
            },
            {
                "json_name": "content_quality",
                "display_name": "Качество материалов",
                "description": "Соответствие брендбуку, точность и убедительность текстов",
                "value": 7,
            },
            {
                "json_name": "budget_management",
                "display_name": "Управление бюджетом",
                "description": "Соблюдение рекламного бюджета и распределение расходов",
                "value": 6,
            },
        ],
    },
]

DEPARTMENTS = ["Разработка", "Поддержка", "Маркетинг"]

JOBS = [
    {
        "name": "Фронтенд-разработчик",
        "description": "Интерфейсы веб-приложения, интеграция с API",
        "department": "Разработка",
        "reviewer": "Тимлид разработки",
        "schedule_type": ScheduleType.WEEKLY.value,
        "work_days": [1, 2, 3, 4, 5],
    },
    {
        "name": "Бэкенд-разработчик",
        "description": "Серверная логика, API, интеграции со смежными сервисами",
        "department": "Разработка",
        "reviewer": "Тимлид разработки",
        "schedule_type": ScheduleType.WEEKLY.value,
        "work_days": [1, 2, 3, 4, 5],
    },
    {
        "name": "Специалист поддержки",
        "description": "Первая линия: разбор обращений, эскалация в разработку",
        "department": "Поддержка",
        "reviewer": "Руководитель поддержки",
        "schedule_type": ScheduleType.WEEKLY.value,
        "work_days": [1, 3, 5],
    },
    {
        "name": "Маркетолог",
        "description": "Рекламные кампании, контент, аналитика каналов",
        "department": "Маркетинг",
        "reviewer": "Директор по маркетингу",
        "schedule_type": ScheduleType.NONE.value,
        "work_days": None,
    },
    {
        "name": "Контент-менеджер",
        "description": "Наполнение сайта и рассылок, работа с подрядчиками",
        "department": "Маркетинг",
        "reviewer": "Директор по маркетингу",
        "schedule_type": ScheduleType.WEEKLY.value,
        "work_days": [1, 2, 3, 4, 5],
    },
]

WORKERS = [
    {
        "name": "Анна Соколова",
        "email": "anna.sokolova@example.com",
        "job": "Фронтенд-разработчик",
        "status": UserStatus.ACTIVE.value,
        "profile": {"timezone": "Europe/Moscow", "preferred_language": "ru"},
        "settings": {
            "notification_time": time(18, 30),
            "reminder_enabled": True,
            "preferred_daily_format": "list",
        },
        "skip_days": [],
        "off_days": [],
        "writes_today": True,
        "today_status": DailyEntryStatus.SUBMITTED.value,
    },
    {
        "name": "Дмитрий Орлов",
        "email": "dmitry.orlov@example.com",
        "job": "Бэкенд-разработчик",
        "status": UserStatus.ACTIVE.value,
        "profile": {"timezone": "Europe/Samara", "preferred_language": "ru"},
        "settings": {
            "notification_time": time(19, 0),
            "reminder_enabled": True,
            "preferred_daily_format": "text",
        },
        "skip_days": [4, 11],
        "off_days": [7, 8],
        "writes_today": True,
        "today_status": DailyEntryStatus.DRAFT.value,
    },
    {
        "name": "Мария Ильина",
        "email": "maria.ilina@example.com",
        "job": "Специалист поддержки",
        "status": UserStatus.ACTIVE.value,
        "profile": {"timezone": "Asia/Yekaterinburg", "preferred_language": "ru"},
        "settings": {
            "notification_time": time(17, 0),
            "reminder_enabled": False,
            "preferred_daily_format": "list",
        },
        "skip_days": [9],
        "off_days": [],
        "writes_today": False,
        "today_status": DailyEntryStatus.SUBMITTED.value,
    },
    {
        "name": "Павел Гущин",
        "email": "pavel.gushchin@example.com",
        "job": "Маркетолог",
        "status": UserStatus.ACTIVE.value,
        "profile": {"timezone": "Europe/Moscow", "preferred_language": "ru"},
        "settings": {
            "notification_time": None,
            "reminder_enabled": False,
            "preferred_daily_format": "text",
        },
        "skip_days": [2, 6, 13],
        "off_days": [],
        "writes_today": True,
        "today_status": DailyEntryStatus.SUBMITTED.value,
    },
    {
        "name": "Ольга Титова",
        "email": "olga.titova@example.com",
        "job": "Контент-менеджер",
        "status": UserStatus.INVITED.value,
        "profile": {"timezone": "Europe/Moscow", "preferred_language": "ru"},
        "settings": {
            "notification_time": time(18, 0),
            "reminder_enabled": True,
            "preferred_daily_format": "list",
        },
        "skip_days": [],
        "off_days": [],
        "writes_today": False,
        "today_status": DailyEntryStatus.SUBMITTED.value,
    },
]

CHAINS = {
    "Анна Соколова": [
        {
            "text": "Переезд формы логина на новый дизайн",
            "link": "https://git.example.com/web/pull/412",
            "steps": [IN_PROGRESS, IN_PROGRESS, BLOCKED, IN_PROGRESS, DONE],
        },
        {
            "text": "Таблица дейликов: виртуальный скролл вместо пагинации",
            "link": "https://git.example.com/web/pull/430",
            "steps": [IN_PROGRESS, IN_PROGRESS, DONE],
        },
        {
            "text": "Тёмная тема для админки",
            "link": None,
            "steps": [IN_PROGRESS, BLOCKED, DROPPED],
        },
        {
            "text": "Экран аналитики по департаментам",
            "link": "https://git.example.com/web/pull/451",
            "steps": [IN_PROGRESS, IN_PROGRESS, IN_PROGRESS],
        },
    ],
    "Дмитрий Орлов": [
        {
            "text": "Ручка массовой простановки типа дня",
            "link": "https://git.example.com/api/pull/288",
            "steps": [IN_PROGRESS, IN_PROGRESS, DONE],
        },
        {
            "text": "История линий по chain_id",
            "link": "https://git.example.com/api/pull/295",
            "steps": [IN_PROGRESS, BLOCKED, BLOCKED, IN_PROGRESS, DONE],
        },
        {
            "text": "Миграция на пул соединений PgBouncer",
            "link": None,
            "steps": [IN_PROGRESS, BLOCKED, BLOCKED],
        },
        {
            "text": "Выгрузка OpenAPI в CI",
            "link": "https://git.example.com/api/pull/301",
            "steps": [IN_PROGRESS, DONE],
        },
        {
            "text": "Перевод отчётов на материализованные представления",
            "link": None,
            "steps": [IN_PROGRESS, IN_PROGRESS, DROPPED],
        },
    ],
    "Мария Ильина": [
        {
            "text": "Разбор очереди обращений по оплате",
            "link": "https://help.example.com/tickets/5512",
            "steps": [IN_PROGRESS, IN_PROGRESS, DONE],
        },
        {
            "text": "Инструкция по восстановлению доступа для клиентов",
            "link": None,
            "steps": [IN_PROGRESS, DONE],
        },
        {
            "text": "Эскалация бага с дублями уведомлений",
            "link": "https://help.example.com/tickets/5570",
            "steps": [BLOCKED, BLOCKED, IN_PROGRESS],
        },
    ],
    "Павел Гущин": [
        {
            "text": "Запуск осенней кампании в РСЯ",
            "link": "https://ads.example.com/campaigns/771",
            "steps": [IN_PROGRESS, IN_PROGRESS, IN_PROGRESS, DONE],
        },
        {
            "text": "A/B тест лендинга тарифов",
            "link": None,
            "steps": [IN_PROGRESS, BLOCKED, DONE],
        },
        {
            "text": "Согласование бюджета на Q4",
            "link": None,
            "steps": [IN_PROGRESS, BLOCKED],
        },
    ],
}

ONE_DAY_ITEMS = {
    "Анна Соколова": [
        "Ревью PR коллег по компонентам формы",
        "Правка вёрстки карточки работника на мобильных",
        "Разбор замечаний дизайнера по отступам",
        "Обновление зависимостей фронтенда",
        "Починил падающий снапшот-тест",
        "Синк с бэкендом по контракту дейликов",
        "Разбор ошибок из Sentry по проду",
        "Вынесла общие стили в токены",
        "Настроила прелоадеры на списках",
        "Поправила фокус-стили для доступности",
        "Ускорила сборку, убрала лишние чанки",
        "Дневной созвон команды",
    ],
    "Дмитрий Орлов": [
        "Разбор алертов по медленным запросам",
        "Ревью миграций от коллеги",
        "Дописал тесты на границу редактирования дейлика",
        "Ответил на вопросы фронта по контракту",
        "Почистил логи от шумных предупреждений",
        "Поднял индекс на выборку дейликов по дате",
        "Разобрал падение ночного прогона тестов",
        "Обновил зависимости бэкенда",
        "Описал схему ответа для карточки работника",
        "Дневной созвон команды",
        "Разбор инцидента с таймаутами на проде",
        "Актуализировал README по запуску",
    ],
    "Мария Ильина": [
        "Обработала обращения из ночной очереди",
        "Созвон с клиентом по интеграции",
        "Обновила шаблоны ответов",
        "Разобрала спорные тикеты с руководителем",
        "Закрыла обращения по возвратам",
        "Передала в разработку баг с выгрузкой",
        "Проверила отчёт по времени ответа",
        "Разобрала жалобы из отзывов",
    ],
    "Павел Гущин": [
        "Свёл отчёт по каналам за неделю",
        "Правки текстов для рассылки",
        "Встреча с подрядчиком по видео",
        "Собрал сегменты для ретаргетинга",
        "Проверил креативы перед запуском",
        "Обновил дашборд по конверсии",
        "Планёрка с отделом продаж",
        "Разобрал заявки с прошлой кампании",
    ],
}

MIN_ITEMS_PER_DAY = 2
MAX_ITEMS_PER_DAY = 4

CHAT_MESSAGES = {
    "Анна Соколова": [
        "Закончила форму логина, осталось дождаться правок от дизайна.",
        "Тёмную тему пока откладываю — нет утверждённой палитры.",
        "Взяла экран аналитики, там много состояний, займёт несколько дней.",
    ],
    "Дмитрий Орлов": [
        "История линий готова, но упёрся в блокировку на стороне базы.",
        "PgBouncer не поднимается на стенде, жду доступы от админов.",
        "Выгрузку схемы в CI докрутил, теперь контракт сверяется тестом.",
    ],
    "Мария Ильина": [
        "Очередь по оплатам разобрала, повторных обращений нет.",
        "По дублям уведомлений жду фикс от разработки, клиентам отвечаю вручную.",
    ],
    "Павел Гущин": [
        "Осеннюю кампанию запустили, первые цифры по конверсии в отчёте.",
        "Бюджет на Q4 пока не согласован, это тормозит планирование.",
    ],
}

TASKS = {
    "Анна Соколова": [
        (2, "Подготовить демо нового экрана аналитики"),
        (5, "Составить список компонентов под тёмную тему"),
    ],
    "Дмитрий Орлов": [
        (1, "Описать схему индексов для отчётов"),
        (4, "Запросить доступы к стенду PgBouncer"),
    ],
    "Мария Ильина": [
        (3, "Обновить регламент эскалации"),
    ],
    "Павел Гущин": [
        (2, "Свести медиаплан на октябрь"),
    ],
}


def wipe(db: Session) -> None:
    db.query(EntryItem).delete(synchronize_session=False)
    db.query(DailyEntry).delete(synchronize_session=False)
    db.query(Statistic).delete(synchronize_session=False)
    db.query(Task).delete(synchronize_session=False)
    db.query(InternalChatMessage).delete(synchronize_session=False)
    db.query(EmployeeProfile).delete(synchronize_session=False)
    db.query(EmployeeSettings).delete(synchronize_session=False)
    db.query(User).filter(User.role != UserRole.ADMIN.value).delete(synchronize_session=False)
    db.query(User).filter(User.role == UserRole.ADMIN.value).update(
        {User.department_id: None, User.job_id: None}, synchronize_session=False
    )
    db.query(Job).delete(synchronize_session=False)
    db.query(Department).delete(synchronize_session=False)
    db.query(Reviewer).delete(synchronize_session=False)
    db.flush()


def create_catalog(db: Session) -> tuple[dict[str, Department], dict[str, Job]]:
    reviewers = {}
    for payload in REVIEWERS:
        reviewer = Reviewer(**payload)
        db.add(reviewer)
        reviewers[payload["name"]] = reviewer

    departments = {}
    for name in DEPARTMENTS:
        department = Department(name=name)
        db.add(department)
        departments[name] = department

    db.flush()

    jobs = {}
    for payload in JOBS:
        job = Job(
            name=payload["name"],
            description=payload["description"],
            department_id=departments[payload["department"]].id,
            reviewer_id=reviewers[payload["reviewer"]].id,
            schedule_type=payload["schedule_type"],
            work_days=payload["work_days"],
        )
        db.add(job)
        jobs[payload["name"]] = job

    db.flush()
    return departments, jobs


def create_workers(db: Session, jobs: dict[str, Job]) -> dict[str, User]:
    password_hash = hash_password(DEMO_PASSWORD)
    workers = {}
    for payload in WORKERS:
        job = jobs[payload["job"]]
        user = User(
            name=payload["name"],
            email=payload["email"],
            password_hash=password_hash,
            role=UserRole.EMPLOYEE.value,
            department_id=job.department_id,
            job_id=job.id,
            status=payload["status"],
            schedule_type=job.schedule_type,
            work_days=list(job.work_days) if job.work_days else None,
        )
        db.add(user)
        db.flush()

        db.add(
            EmployeeProfile(
                user_id=user.id,
                position=job.name,
                avatar=None,
                **payload["profile"],
            )
        )
        db.add(EmployeeSettings(user_id=user.id, daily_template_id=None, **payload["settings"]))
        workers[payload["name"]] = user

    db.flush()
    return workers


def entry_days(user: User, payload: dict, today: date) -> list[date]:
    window_start = today - timedelta(days=WINDOW_DAYS - 1)
    skip = {today - timedelta(days=offset) for offset in payload["skip_days"]}

    days = []
    current = window_start
    while current <= today:
        if current == today:
            if payload["writes_today"]:
                days.append(current)
            current += timedelta(days=1)
            continue
        if current in skip:
            current += timedelta(days=1)
            continue
        if user.schedule_type == ScheduleType.WEEKLY.value:
            if current.isoweekday() in (user.work_days or []):
                days.append(current)
        elif current.isoweekday() <= 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def create_entries(
    db: Session,
    user: User,
    payload: dict,
    days: list[date],
    today: date,
    rng: random.Random,
) -> dict[date, DailyEntry]:
    off_days = {today - timedelta(days=offset) for offset in payload["off_days"]}
    entries = {}

    for day in days:
        is_off = day in off_days
        status = payload["today_status"] if day == today else DailyEntryStatus.SUBMITTED.value
        entry = DailyEntry(
            user_id=user.id,
            department_id=user.department_id,
            date=day,
            day_type=DayType.OFF.value if is_off else DayType.WORK.value,
            status=status,
            submitted_at=(
                datetime.combine(day, time(rng.randint(17, 20), rng.randint(0, 59)))
                if status == DailyEntryStatus.SUBMITTED.value and not is_off
                else None
            ),
            created_at=datetime.combine(day, time(9, 30)),
            updated_at=datetime.combine(day, time(19, 0)),
        )
        db.add(entry)
        entries[day] = entry

    db.flush()
    return entries


def fill_items(
    db: Session,
    user_name: str,
    entries: dict[date, DailyEntry],
    rng: random.Random,
) -> None:
    work_days = sorted(
        day for day, entry in entries.items() if entry.day_type == DayType.WORK.value
    )
    if not work_days:
        return

    positions = {day: 0 for day in work_days}

    def add_item(day: date, chain_id: str, text: str, status: str, link: str | None) -> None:
        entry = entries[day]
        db.add(
            EntryItem(
                entry_id=entry.id,
                chain_id=chain_id,
                text=text,
                status=status,
                link=link,
                position=positions[day],
                created_at=datetime.combine(day, time(10, 0)),
                updated_at=datetime.combine(day, time(18, 30)),
            )
        )
        positions[day] += 1

    chains = CHAINS.get(user_name, [])
    for index, chain in enumerate(chains):
        steps = chain["steps"]
        if len(steps) > len(work_days):
            steps = steps[-len(work_days) :]

        last_status = steps[-1]
        if last_status in (IN_PROGRESS, BLOCKED):
            start_index = len(work_days) - len(steps)
        else:
            latest_start = len(work_days) - len(steps)
            start_index = rng.randint(0, latest_start) if latest_start > 0 else 0
            if index == 0:
                start_index = 0

        chain_id = str(uuid4())
        for offset, status in enumerate(steps):
            add_item(
                work_days[start_index + offset],
                chain_id,
                chain["text"],
                status,
                chain["link"],
            )

    routine = ONE_DAY_ITEMS.get(user_name, [])
    if routine:
        for day in work_days:
            target = rng.randint(MIN_ITEMS_PER_DAY, MAX_ITEMS_PER_DAY)
            while positions[day] < target:
                status = DONE if rng.random() < 0.96 else DROPPED
                add_item(day, str(uuid4()), rng.choice(routine), status, None)

    db.flush()


def create_side_data(db: Session, user: User, user_name: str, today: date, rng: random.Random) -> None:
    for offset, description in TASKS.get(user_name, []):
        db.add(Task(user_id=user.id, date=today - timedelta(days=offset), description=description))

    for index, message in enumerate(CHAT_MESSAGES.get(user_name, [])):
        created = datetime.combine(today - timedelta(days=index * 3 + 1), time(11, rng.randint(0, 59)))
        db.add(InternalChatMessage(user_id=user.id, message_text=message, created_at=created))

    for offset in range(14):
        day = today - timedelta(days=offset)
        if day.isoweekday() > 5:
            continue
        db.add(Statistic(user_id=user.id, date=day, value=rng.randint(3, 12)))

    db.flush()


def main() -> None:
    rng = random.Random(SEED)
    today = date.today()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
        if admin is None:
            raise SystemExit("В базе нет администратора — сначала создайте его через /api/auth/bootstrap-admin")

        wipe(db)
        _, jobs = create_catalog(db)
        workers = create_workers(db, jobs)

        for payload in WORKERS:
            user = workers[payload["name"]]
            if payload["status"] != UserStatus.ACTIVE.value:
                continue
            days = entry_days(user, payload, today)
            entries = create_entries(db, user, payload, days, today, rng)
            fill_items(db, payload["name"], entries, rng)
            create_side_data(db, user, payload["name"], today, rng)

        db.commit()

        print(f"админ сохранён: {admin.name} <{admin.email}>")
        print(f"работников: {db.query(User).filter(User.role == UserRole.EMPLOYEE.value).count()}")
        print(f"дейликов: {db.query(DailyEntry).count()}, строк в них: {db.query(EntryItem).count()}")
        print(f"пароль всех работников: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
