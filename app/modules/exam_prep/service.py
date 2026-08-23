from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock

from fastapi import HTTPException, status

from app.modules.exam_prep.catalog import EXAM, ROADMAP_STAGES, TASKS, THEORY, TOPICS

_lock = Lock()
_attempts: dict[str, list[dict[str, object]]] = {}
_published: dict[str, bool] = {str(task["id"]): True for task in TASKS}


def _task(task_id: str) -> dict[str, object]:
    found = next((item for item in TASKS if item["id"] == task_id), None)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return found


def _session_attempts(session_id: str) -> list[dict[str, object]]:
    with _lock:
        return deepcopy(_attempts.setdefault(session_id, []))


def _normalise(value: str) -> str:
    return value.strip().lower().replace("−", "-").replace(",", ".").replace(" ", "")


def _matches(answer: str, aliases: list[str]) -> bool:
    normalised = _normalise(answer)
    if normalised in {_normalise(alias) for alias in aliases}:
        return True
    try:
        submitted = Decimal(normalised.rstrip("%"))
    except InvalidOperation:
        return False
    for alias in aliases:
        try:
            expected = Decimal(_normalise(alias).rstrip("%"))
        except InvalidOperation:
            continue
        if abs(submitted - expected) <= Decimal("0.0001"):
            return True
    return False


def _public_task(task: dict[str, object], include_answer: bool = False) -> dict[str, object]:
    result = {key: deepcopy(value) for key, value in task.items() if key != "answer_aliases"}
    result["published"] = _published[str(task["id"])]
    result["source"] = {
        "label": "По типу открытых материалов ФИПИ ЕГЭ-2026",
        "url": EXAM["sources"][0]["url"],
        "adapted": True,
    }
    if include_answer:
        result["accepted_answers"] = deepcopy(task["answer_aliases"])
    return result


def get_overview() -> dict[str, object]:
    return {
        "exam": deepcopy(EXAM),
        "topics": deepcopy(TOPICS),
        "content": {
            "tasks": len(TASKS),
            "theory_chapters": len(THEORY),
            "roadmap_stages": len(ROADMAP_STAGES),
        },
    }


def list_tasks(
    topic_id: str | None = None,
    difficulty: str | None = None,
    include_unpublished: bool = False,
) -> list[dict[str, object]]:
    tasks = list(TASKS)
    if topic_id:
        tasks = [item for item in tasks if item["topic_id"] == topic_id]
    if difficulty:
        tasks = [item for item in tasks if item["difficulty"] == difficulty]
    if not include_unpublished:
        tasks = [item for item in tasks if _published[str(item["id"])]]
    return [_public_task(item, include_answer=include_unpublished) for item in tasks]


def list_theory(topic_id: str | None = None) -> list[dict[str, object]]:
    chapters = (
        THEORY if topic_id is None else [item for item in THEORY if item["topic_id"] == topic_id]
    )
    return deepcopy(chapters)


def submit_attempt(
    session_id: str,
    task_id: str,
    answer: str,
    duration_seconds: int,
) -> dict[str, object]:
    task = _task(task_id)
    if not _published[task_id]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    is_correct = _matches(answer, list(task["answer_aliases"]))
    attempt = {
        "id": f"attempt-{datetime.now(UTC).timestamp()}",
        "task_id": task_id,
        "answer": answer,
        "is_correct": is_correct,
        "duration_seconds": duration_seconds,
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _lock:
        _attempts.setdefault(session_id, []).append(attempt)
    topic = next(item for item in TOPICS if item["id"] == task["topic_id"])
    return {
        "attempt": deepcopy(attempt),
        "is_correct": is_correct,
        "earned_primary_score": int(task["max_primary_score"]) if is_correct else 0,
        "max_primary_score": task["max_primary_score"],
        "explanation": task["explanation"],
        "correct_answer": task["answer_aliases"][0],
        "theory_id": task["theory_id"],
        "topic": {"id": topic["id"], "title": topic["title"]},
        "recommendation": (
            "Отлично. Закрепите навык ещё одним заданием этого типа."
            if is_correct
            else "Вернитесь к короткой теории и повторите этот тип через 24 часа."
        ),
    }


def _topic_metrics(attempts: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for attempt in attempts:
        task = _task(str(attempt["task_id"]))
        grouped[str(task["topic_id"])].append(bool(attempt["is_correct"]))

    result = []
    for topic in sorted(TOPICS, key=lambda item: int(item["order"])):
        topic_id = str(topic["id"])
        values = grouped.get(topic_id, [])
        accuracy = round(sum(values) / len(values) * 100) if values else None
        topic_tasks = [task for task in TASKS if task["topic_id"] == topic_id]
        theory_id = str(topic_tasks[0]["theory_id"])
        result.append(
            {
                "topic_id": topic_id,
                "title": topic["title"],
                "short_title": topic["short_title"],
                "accent": topic["accent"],
                "attempts": len(values),
                "correct": sum(values),
                "accuracy": accuracy,
                "mastery": accuracy,
                "task_numbers": [int(task["exam_number"]) for task in topic_tasks],
                "theory_id": theory_id,
                "theory_href": f"#theory-{theory_id}",
                "practice_href": f"#practice-{topic_tasks[0]['id']}",
            }
        )
    return result


def _prediction(attempts: list[dict[str, object]]) -> dict[str, object]:
    latest_by_task: dict[str, dict[str, object]] = {}
    for attempt in attempts:
        latest_by_task[str(attempt["task_id"])] = attempt

    missing = [
        int(task["exam_number"]) for task in TASKS if str(task["id"]) not in latest_by_task
    ]
    available = not missing
    primary = None
    if available:
        primary = sum(
            int(task["max_primary_score"])
            for task in TASKS
            if bool(latest_by_task[str(task["id"])]["is_correct"])
        )
    return {
        "available": available,
        "predicted_primary_score": primary,
        "predicted_test_score": None,
        "max_primary_score": int(EXAM["max_primary_score"]),
        "covered_task_types": len(TASKS) - len(missing),
        "required_task_types": len(TASKS),
        "missing_task_numbers": missing,
        "basis": (
            "Результат полной диагностики: последняя реальная попытка по каждому из 19 типов."
            if available
            else "Прогноз появится после реальных попыток по всем 19 типам заданий."
        ),
        "test_score_note": (
            "Тестовый балл не рассчитывается: официальной шкалы перевода ЕГЭ-2026 ещё нет."
        ),
    }


def _accuracy_history(attempts: list[dict[str, object]]) -> list[dict[str, object]]:
    history = []
    correct = 0
    for index, attempt in enumerate(attempts, start=1):
        correct += int(bool(attempt["is_correct"]))
        task = _task(str(attempt["task_id"]))
        history.append(
            {
                "label": f"№{task['exam_number']}",
                "score": round(correct / index * 100),
                "attempt_number": index,
            }
        )
    return history[-10:]


def _week_activity(attempts: list[dict[str, object]]) -> list[dict[str, object]]:
    today = datetime.now(UTC).date()
    counts = defaultdict(int)
    for attempt in attempts:
        created_at = datetime.fromisoformat(str(attempt["created_at"])).date()
        counts[created_at] += 1
    return [
        {
            "date": (today - timedelta(days=offset)).isoformat(),
            "attempts": counts[today - timedelta(days=offset)],
        }
        for offset in range(6, -1, -1)
    ]


def get_analytics(session_id: str) -> dict[str, object]:
    attempts = _session_attempts(session_id)
    metrics = _topic_metrics(attempts)
    correct = sum(bool(item["is_correct"]) for item in attempts)
    attempted_metrics = [item for item in metrics if int(item["attempts"]) > 0]
    weak = sorted(
        (item for item in attempted_metrics if int(item["accuracy"]) < 100),
        key=lambda item: (int(item["accuracy"]), -int(item["attempts"]), str(item["title"])),
    )[:3]
    strong = sorted(
        attempted_metrics,
        key=lambda item: (int(item["accuracy"]), int(item["attempts"])),
        reverse=True,
    )[:3]
    today = datetime.now(UTC).date()
    plan = []
    for index, metric in enumerate(weak):
        failed_attempt = next(
            item
            for item in reversed(attempts)
            if not bool(item["is_correct"])
            and _task(str(item["task_id"]))["topic_id"] == metric["topic_id"]
        )
        task = _task(str(failed_attempt["task_id"]))
        plan.append(
            {
                "topic_id": metric["topic_id"],
                "title": metric["title"],
                "mastery": metric["mastery"],
                "due_date": (today + timedelta(days=[1, 3, 7][index])).isoformat(),
                "action": f"Повторить теорию и решить задание №{task['exam_number']}",
                "reason": f"Фактическая точность: {metric['accuracy']}% на {metric['attempts']} попытках.",
                "theory_id": metric["theory_id"],
                "task_id": task["id"],
                "theory_href": metric["theory_href"],
                "practice_href": metric["practice_href"],
            }
        )
    return {
        "session_id": session_id,
        "summary": {
            "attempts": len(attempts),
            "correct": correct,
            "accuracy": round(correct / len(attempts) * 100) if attempts else None,
            "study_minutes": round(sum(int(item["duration_seconds"]) for item in attempts) / 60),
        },
        "prediction": _prediction(attempts),
        "topics": metrics,
        "weak_topics": weak,
        "strong_topics": strong,
        "individual_plan": plan,
        "history": _accuracy_history(attempts),
        "week_activity": _week_activity(attempts),
    }


def get_roadmap(session_id: str) -> dict[str, object]:
    attempts = _session_attempts(session_id)
    metrics = {str(item["topic_id"]): item for item in _topic_metrics(attempts)}
    attempted_task_ids = {str(item["task_id"]) for item in attempts}
    stages = []

    for stage in ROADMAP_STAGES:
        task_numbers = [int(number) for number in stage["task_numbers"]]
        stage_tasks = [task for task in TASKS if int(task["exam_number"]) in task_numbers]
        stage_task_ids = {str(task["id"]) for task in stage_tasks}
        stage_attempts = [item for item in attempts if str(item["task_id"]) in stage_task_ids]
        covered = len(stage_task_ids & attempted_task_ids)
        mastery = (
            round(sum(bool(item["is_correct"]) for item in stage_attempts) / len(stage_attempts) * 100)
            if stage_attempts
            else None
        )
        stages.append(
            {
                **deepcopy(stage),
                "mastery": mastery,
                "state": "completed"
                if covered == len(stage_tasks) and mastery is not None and mastery >= 75
                else "upcoming",
                "covered_task_types": covered,
                "task_types": len(stage_tasks),
                "tasks": [
                    {
                        "id": task["id"],
                        "exam_number": task["exam_number"],
                        "title": task["title"],
                        "difficulty": task["difficulty"],
                        "href": f"#practice-{task['id']}",
                    }
                    for task in stage_tasks
                ],
                "topics": [
                    {
                        "id": topic_id,
                        "title": metrics[topic_id]["short_title"],
                        "mastery": metrics[topic_id]["mastery"],
                        "attempts": metrics[topic_id]["attempts"],
                        "task_numbers": [
                            int(task["exam_number"])
                            for task in stage_tasks
                            if task["topic_id"] == topic_id
                        ],
                        "theory_id": metrics[topic_id]["theory_id"],
                        "theory_href": metrics[topic_id]["theory_href"],
                        "practice_href": next(
                            f"#practice-{task['id']}"
                            for task in stage_tasks
                            if task["topic_id"] == topic_id
                        ),
                    }
                    for topic_id in stage["topic_ids"]
                ],
            }
        )

    current_index = next(
        (index for index, stage in enumerate(stages) if stage["state"] != "completed"),
        len(stages) - 1,
    )
    if stages[current_index]["state"] != "completed":
        stages[current_index]["state"] = "current"
    return {
        "session_id": session_id,
        "principle": "Все темы и номера ЕГЭ распределены от коротких задач к сложным №14, 17–19.",
        "current_stage_id": stages[current_index]["id"],
        "overall_progress": round(len(attempted_task_ids) / len(TASKS) * 100),
        "covered_task_types": len(attempted_task_ids),
        "total_task_types": len(TASKS),
        "stages": stages,
    }


def _attempt_snapshot() -> dict[str, list[dict[str, object]]]:
    with _lock:
        return deepcopy(_attempts)


def get_admin_dashboard() -> dict[str, object]:
    published = sum(_published.values())
    snapshot = {session_id: items for session_id, items in _attempt_snapshot().items() if items}
    today = datetime.now(UTC).date()
    all_attempts = [attempt for attempts in snapshot.values() for attempt in attempts]
    active_today = {
        session_id
        for session_id, attempts in snapshot.items()
        if any(datetime.fromisoformat(str(item["created_at"])).date() == today for item in attempts)
    }
    full_results = [
        prediction["predicted_primary_score"]
        for attempts in snapshot.values()
        if (prediction := _prediction(attempts))["available"]
    ]
    return {
        "metrics": {
            "students": len(snapshot),
            "active_today": len(active_today),
            "attempts_today": sum(
                datetime.fromisoformat(str(item["created_at"])).date() == today
                for item in all_attempts
            ),
            "average_primary_result": (
                round(sum(int(value) for value in full_results) / len(full_results))
                if full_results
                else None
            ),
        },
        "content": {
            "tasks_total": len(TASKS),
            "tasks_published": published,
            "theory_chapters": len(THEORY),
            "coverage_percent": round(published / len(TASKS) * 100),
        },
        "system": {"api": "healthy", "content_version": "ФИПИ-2026", "queue": 0},
    }


def get_admin_users() -> list[dict[str, object]]:
    users = []
    for session_id, attempts in _attempt_snapshot().items():
        if not attempts:
            continue
        correct = sum(bool(item["is_correct"]) for item in attempts)
        accuracy = round(correct / len(attempts) * 100)
        prediction = _prediction(attempts)
        users.append(
            {
                "id": session_id,
                "name": session_id,
                "attempts": len(attempts),
                "accuracy": accuracy,
                "primary_result": prediction["predicted_primary_score"],
                "activity": max(str(item["created_at"]) for item in attempts),
                "risk": "stable" if accuracy >= 70 else "attention" if accuracy >= 50 else "critical",
            }
        )
    return sorted(users, key=lambda item: str(item["activity"]), reverse=True)


def set_task_status(task_id: str, published: bool) -> dict[str, object]:
    task = _task(task_id)
    with _lock:
        _published[task_id] = published
    return _public_task(task, include_answer=True)


def reset_demo_state() -> None:
    """Reset mutable prototype state for deterministic tests."""
    with _lock:
        _attempts.clear()
        _published.clear()
        _published.update({str(task["id"]): True for task in TASKS})
