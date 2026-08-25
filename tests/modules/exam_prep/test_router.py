import pytest
from fastapi.testclient import TestClient

from app.modules.exam_prep.catalog import TASKS
from app.modules.exam_prep.service import reset_demo_state


@pytest.fixture(autouse=True)
def reset_state() -> None:
    reset_demo_state()


def test_overview_matches_fipi_2026_structure(client: TestClient) -> None:
    response = client.get("/api/v1/exam/math-profile/overview")

    assert response.status_code == 200
    exam = response.json()["data"]["exam"]
    assert exam["tasks_count"] == 19
    assert exam["short_answer_count"] == 12
    assert exam["extended_answer_count"] == 7
    assert exam["duration_minutes"] == 235
    assert exam["max_primary_score"] == 32
    assert sum(exam["scoring"].values()) == 32


def test_task_bank_exposes_sources_without_answers(client: TestClient) -> None:
    response = client.get("/api/v1/exam/math-profile/tasks")

    assert response.status_code == 200
    tasks = response.json()["data"]
    assert len(tasks) == 19
    assert all(task["source"]["adapted"] for task in tasks)
    assert all("answer_aliases" not in task for task in tasks)
    assert all("accepted_answers" not in task for task in tasks)


def test_vector_theory_covers_only_current_exam_methods(client: TestClient) -> None:
    response = client.get(
        "/api/v1/exam/math-profile/theory",
        params={"topic_id": "vectors"},
    )

    assert response.status_code == 200
    chapters = response.json()["data"]
    assert len(chapters) == 1
    chapter = chapters[0]
    assert chapter["title"] == "Векторы: полный минимум для ЕГЭ"
    assert chapter["read_minutes"] == 18
    assert chapter["exam_scope"]["label"] == "ЕГЭ-2026 · задание №2"
    assert [section["id"] for section in chapter["sections"]] == [
        "vector-coordinates",
        "vector-operations",
        "vector-length",
        "scalar-product",
    ]
    assert len(chapter["exam_patterns"]) == 5
    assert "a · b = aₓbₓ + aᵧbᵧ" in chapter["sections"][-1]["formulas"]
    assert "|a|·|b|·cos α" in chapter["sections"][-1]["formulas"][1]
    assert "Атанасян" in chapter["reference"]["title"]
    assert chapter["reference"]["sections"] == "§§ 84–91, 94, 109–111"

    lesson = client.get(
        "/api/v1/exam/math-profile/lesson/current",
        params={"session_id": "vector-theory-student"},
    ).json()["data"]
    assert lesson["topic"]["id"] == "vectors"
    assert lesson["theory"]["sections"] == chapter["sections"]


def test_attempt_updates_personal_analytics(client: TestClient) -> None:
    before = client.get(
        "/api/v1/exam/math-profile/analytics", params={"session_id": "test-student"}
    ).json()["data"]

    correct = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={"session_id": "test-student", "task_id": "math-04", "answer": "0,1"},
    )
    incorrect = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={"session_id": "test-student", "task_id": "math-06", "answer": "6"},
    )
    after = client.get(
        "/api/v1/exam/math-profile/analytics", params={"session_id": "test-student"}
    ).json()["data"]

    assert before["summary"]["attempts"] == 0
    assert before["summary"]["accuracy"] is None
    assert before["prediction"]["available"] is False
    assert before["prediction"]["predicted_primary_score"] is None
    assert before["prediction"]["predicted_test_score"] is None
    assert all(topic["mastery"] is None for topic in before["topics"])
    assert correct.status_code == 200
    assert correct.json()["data"]["is_correct"] is True
    assert incorrect.json()["data"]["is_correct"] is False
    assert after["summary"]["attempts"] == 2
    assert after["summary"]["accuracy"] == 50
    assert after["summary"]["streak_days"] == 1
    assert len(after["individual_plan"]) == 1
    assert after["individual_plan"][0]["task_id"] == "math-06"
    assert "№6" in after["individual_plan"][0]["action"]
    assert after["prediction"]["available"] is False
    assert after["prediction_history"] == []
    assert "task_accuracy" not in after


def test_expected_score_history_starts_after_full_diagnostic(client: TestClient) -> None:
    for task in TASKS:
        response = client.post(
            "/api/v1/exam/math-profile/attempts",
            json={
                "session_id": "score-history-student",
                "task_id": task["id"],
                "answer": task["answer_aliases"][0],
            },
        )
        assert response.status_code == 200

    after_diagnostic = client.get(
        "/api/v1/exam/math-profile/analytics",
        params={"session_id": "score-history-student"},
    ).json()["data"]
    assert after_diagnostic["prediction"]["available"] is True
    assert after_diagnostic["prediction"]["predicted_primary_score"] == 32
    assert after_diagnostic["prediction"]["predicted_test_score"] == 100
    assert after_diagnostic["prediction"]["max_test_score"] == 100
    assert after_diagnostic["prediction_history"] == [
        {
            "attempt_number": 19,
            "label": "№19",
            "score": 100,
            "max_score": 100,
            "primary_score": 32,
            "max_primary_score": 32,
            "created_at": after_diagnostic["prediction_history"][0]["created_at"],
        }
    ]

    changed = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "score-history-student",
            "task_id": "math-19",
            "answer": "заведомо неверный ответ",
        },
    )
    assert changed.status_code == 200
    after_change = client.get(
        "/api/v1/exam/math-profile/analytics",
        params={"session_id": "score-history-student"},
    ).json()["data"]
    assert after_change["prediction"]["predicted_primary_score"] == 28
    assert after_change["prediction"]["predicted_test_score"] == 98
    assert [point["score"] for point in after_change["prediction_history"]] == [100, 98]
    assert [point["primary_score"] for point in after_change["prediction_history"]] == [32, 28]
    assert after_change["prediction_history"][-1]["attempt_number"] == 20
    assert after_change["prediction_history"][-1]["label"] == "№19"


def test_roadmap_is_ordered_from_basic_to_expert(client: TestClient) -> None:
    response = client.get("/api/v1/exam/math-profile/roadmap")

    assert response.status_code == 200
    stages = response.json()["data"]["stages"]
    assert [stage["number"] for stage in stages] == [1, 2, 3, 4, 5]
    assert stages[0]["difficulty"] == "basic"
    assert stages[-1]["difficulty"] == "expert"
    assert stages[0]["topics"][0]["id"] == "vectors"
    assert stages[0]["topics"][0]["lesson_state"] == "current"
    assert stages[0]["topics"][0]["progress"] == 0
    assert [item["id"] for item in stages[0]["topics"][0]["subtopics"]] == [
        "vector-coordinates",
        "vector-operations",
        "vector-length",
        "scalar-product",
    ]
    assert all(item["progress"] == 0 for item in stages[0]["topics"][0]["subtopics"])
    assert stages[0]["topics"][1]["lesson_state"] == "locked"
    task_numbers = [number for stage in stages for number in stage["task_numbers"]]
    assert sorted(task_numbers) == list(range(1, 20))
    assert all(topic["lesson_href"] == "#lessons" for stage in stages for topic in stage["topics"])
    assert all(task["href"] == "#lessons" for stage in stages for task in stage["tasks"])


def test_roadmap_moves_frequently_missed_future_lesson_forward(client: TestClient) -> None:
    for _ in range(2):
        response = client.post(
            "/api/v1/exam/math-profile/attempts",
            json={"session_id": "adaptive-student", "task_id": "math-06", "answer": "0"},
        )
        assert response.status_code == 200

    roadmap = client.get(
        "/api/v1/exam/math-profile/roadmap",
        params={"session_id": "adaptive-student"},
    ).json()["data"]
    lesson = client.get(
        "/api/v1/exam/math-profile/lesson/current",
        params={"session_id": "adaptive-student"},
    ).json()["data"]

    assert roadmap["adaptation"]["active"] is True
    assert roadmap["lesson_order"][0]["topic"]["id"] == "equations"
    assert roadmap["lesson_order"][0]["is_adapted"] is True
    assert "ошиб" in roadmap["lesson_order"][0]["reason"]
    assert lesson["topic"]["id"] == "equations"


def test_homework_is_assigned_and_solved_outside_the_lesson(client: TestClient) -> None:
    lesson = client.get(
        "/api/v1/exam/math-profile/lesson/current",
        params={"session_id": "lesson-student"},
    ).json()["data"]

    assert lesson["topic"]["id"] == "vectors"
    assert lesson["current_step"] == "theory"
    assert lesson["progress"] == 0
    assert len(lesson["subtopics"]) == 4
    assert [step["state"] for step in lesson["steps"]] == ["current", "locked"]
    assert lesson["practice_task"]["id"] == "math-02"
    assert lesson["homework_task"]["id"] == "math-02"
    assert lesson["practice_task"]["prompt"] != lesson["homework_task"]["prompt"]
    homework_before = client.get(
        "/api/v1/exam/math-profile/homework/current",
        params={"session_id": "lesson-student"},
    ).json()["data"]
    assert homework_before["status"] == "empty"

    blocked = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "-5",
            "mode": "practice",
            "lesson_unit_id": lesson["unit_id"],
        },
    )
    assert blocked.status_code == 409

    after_theory = client.post(
        "/api/v1/exam/math-profile/lesson/theory/complete",
        json={"session_id": "lesson-student", "lesson_unit_id": lesson["unit_id"]},
    ).json()["data"]
    assert after_theory["current_step"] == "practice"
    assert after_theory["progress"] == 50
    assert all(item["progress"] == 50 for item in after_theory["subtopics"])
    assert after_theory["practice"] == {
        "attempted_tasks": 0,
        "correct_tasks": 0,
        "total_tasks": 20,
        "current_task_number": 1,
        "topic_id": "vectors",
    }

    first_task = after_theory["practice_task"]
    first_attempt = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "0",
            "mode": "practice",
            "lesson_unit_id": lesson["unit_id"],
            "lesson_task_key": first_task["lesson_task_key"],
        },
    )
    assert first_attempt.status_code == 200
    first_result = first_attempt.json()["data"]
    assert first_result["is_correct"] is False
    assert "отмечено неверным" in first_result["recommendation"]
    assert first_result["lesson"]["practice"]["attempted_tasks"] == 1
    assert first_result["lesson"]["practice"]["correct_tasks"] == 0
    assert first_result["lesson"]["practice"]["current_task_number"] == 2
    assert first_result["lesson"]["progress"] == 53
    subtopics_after_first = {
        item["id"]: item for item in first_result["lesson"]["subtopics"]
    }
    assert subtopics_after_first["vector-length"]["progress"] == 58
    assert subtopics_after_first["vector-coordinates"]["progress"] == 50

    repeated = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "17",
            "mode": "practice",
            "lesson_unit_id": lesson["unit_id"],
            "lesson_task_key": first_task["lesson_task_key"],
        },
    )
    assert repeated.status_code == 409

    vector_prompts = [first_task["prompt"]]
    vector_sources = [first_task["source"]]
    answers = [
        "625",
        "10",
        "2",
        "8",
        "8",
        "4",
        "7",
        "10",
        "25",
        "9",
        "89",
        "7",
        "8",
        "6",
        "90",
        "5",
        "12",
        "-0.6",
        "8",
    ]
    for task_number, answer in enumerate(answers, start=2):
        current_lesson = client.get(
            "/api/v1/exam/math-profile/lesson/current",
            params={"session_id": "lesson-student"},
        ).json()["data"]
        current_task = current_lesson["practice_task"]
        vector_prompts.append(current_task["prompt"])
        vector_sources.append(current_task["source"])
        practice = client.post(
            "/api/v1/exam/math-profile/attempts",
            json={
                "session_id": "lesson-student",
                "task_id": "math-02",
                "answer": answer,
                "mode": "practice",
                "lesson_unit_id": lesson["unit_id"],
                "lesson_task_key": current_task["lesson_task_key"],
            },
        ).json()["data"]
        assert practice["is_correct"] is True
        if task_number < 20:
            assert practice["lesson_unit_complete"] is False
            assert practice["lesson"]["topic"]["id"] == "vectors"
            assert practice["lesson"]["practice"]["current_task_number"] == task_number + 1
            assert practice["homework"]["status"] == "empty"

    assert all("вектор" in prompt.lower() for prompt in vector_prompts)
    assert len(vector_prompts) == len(set(vector_prompts)) == 20
    assert len({source["source_id"] for source in vector_sources}) == 20
    assert all(source["url"].startswith("https://math-ege.sdamgia.ru/problem?id=") for source in vector_sources)
    assert all(source["adapted"] is True and source["verbatim"] is False for source in vector_sources)
    theory_examples = {
        example["prompt"]
        for section in lesson["theory"]["sections"]
        for example in (section.get("example"), section.get("secondary_example"))
        if example
    }
    assert theory_examples.isdisjoint(vector_prompts)
    assert practice["lesson_unit_complete"] is True
    assert practice["lesson"]["topic"]["id"] == "geometry"
    assert practice["lesson"]["current_step"] == "theory"
    assert practice["homework"]["status"] == "active"
    assert practice["homework"]["topic"]["id"] == "vectors"
    assert practice["homework"]["total_tasks"] == 15
    assert practice["homework"]["current_task_number"] == 1
    assert practice["homework"]["pending_count"] == 15

    first_homework = practice["homework"]
    first_homework_task = first_homework["task"]
    first_homework_result = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "0",
            "mode": "homework",
            "lesson_unit_id": lesson["unit_id"],
            "lesson_task_key": first_homework_task["lesson_task_key"],
        },
    ).json()["data"]
    assert first_homework_result["is_correct"] is False
    assert first_homework_result["homework_unit_complete"] is False
    assert first_homework_result["homework"]["current_task_number"] == 2
    assert first_homework_result["homework"]["attempted_tasks"] == 1
    assert first_homework_result["homework"]["correct_tasks"] == 0

    repeated_homework = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "25",
            "mode": "homework",
            "lesson_unit_id": lesson["unit_id"],
            "lesson_task_key": first_homework_task["lesson_task_key"],
        },
    )
    assert repeated_homework.status_code == 409

    homework_prompts = [first_homework_task["prompt"]]
    homework_sources = [first_homework_task["source"]]
    homework_answers = [
        "225",
        "14",
        "1",
        "12",
        "13",
        "12",
        "11",
        "10",
        "-3",
        "90",
        "24",
        "-20",
        "0.96",
        "7",
    ]
    for task_number, answer in enumerate(homework_answers, start=2):
        current_homework = client.get(
            "/api/v1/exam/math-profile/homework/current",
            params={"session_id": "lesson-student"},
        ).json()["data"]
        current_task = current_homework["task"]
        homework_prompts.append(current_task["prompt"])
        homework_sources.append(current_task["source"])
        homework = client.post(
            "/api/v1/exam/math-profile/attempts",
            json={
                "session_id": "lesson-student",
                "task_id": "math-02",
                "answer": answer,
                "mode": "homework",
                "lesson_unit_id": lesson["unit_id"],
                "lesson_task_key": current_task["lesson_task_key"],
            },
        ).json()["data"]
        assert homework["is_correct"] is True
        if task_number < 15:
            assert homework["homework_unit_complete"] is False
            assert homework["homework"]["current_task_number"] == task_number + 1

    assert len(homework_prompts) == len(set(homework_prompts)) == 15
    assert set(homework_prompts).isdisjoint(vector_prompts)
    assert len({source["source_id"] for source in homework_sources}) == 15
    assert all(source["adapted"] is True for source in homework_sources)
    assert homework["homework_unit_complete"] is True
    assert homework["lesson"]["topic"]["id"] == "geometry"
    assert homework["lesson"]["current_step"] == "theory"
    assert homework["homework"]["status"] == "empty"

    roadmap = client.get(
        "/api/v1/exam/math-profile/roadmap",
        params={"session_id": "lesson-student"},
    ).json()["data"]
    assert roadmap["stages"][0]["topics"][0]["lesson_state"] == "completed"
    assert roadmap["stages"][0]["topics"][0]["progress"] == 100
    assert all(
        item["progress"] == 100
        for item in roadmap["stages"][0]["topics"][0]["subtopics"]
    )
    assert roadmap["stages"][0]["topics"][1]["lesson_state"] == "current"


def test_dashboard_contains_today_schedule_roadmap_score_and_streak(client: TestClient) -> None:
    response = client.get(
        "/api/v1/exam/math-profile/dashboard",
        params={"session_id": "dashboard-student"},
    )

    assert response.status_code == 200
    dashboard = response.json()["data"]
    assert dashboard["metrics"] == {
        "expected_test_score": None,
        "max_test_score": 100,
        "prediction_available": False,
        "prediction_basis": "Прогноз появится после реальных попыток по всем 19 типам заданий.",
        "streak_days": 0,
    }
    assert dashboard["today"]["lesson"]["title"] == "Векторы"
    assert dashboard["today"]["lesson"]["progress"] == 0
    assert len(dashboard["today"]["lesson"]["subtopics"]) == 4
    assert dashboard["today"]["homework"] is None
    assert dashboard["schedule"][0]["kind"] == "lesson"
    assert dashboard["schedule"][0]["progress"] == 0
    assert dashboard["roadmap"]["next_lessons"][0]["topic"]["id"] == "vectors"


def test_complex_tasks_and_admin_metrics_are_not_fabricated(client: TestClient) -> None:
    tasks = client.get("/api/v1/exam/math-profile/tasks").json()["data"]
    by_number = {task["exam_number"]: task for task in tasks}
    admin = client.get("/api/v1/exam/math-profile/admin/dashboard").json()["data"]
    users = client.get("/api/v1/exam/math-profile/admin/users").json()["data"]

    assert by_number[14]["difficulty"] == "expert"
    assert by_number[17]["difficulty"] == "expert"
    assert admin["metrics"] == {
        "students": 0,
        "active_today": 0,
        "attempts_today": 0,
        "average_primary_result": None,
    }
    assert users == []


def test_admin_can_unpublish_task_without_deleting_it(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/exam/math-profile/admin/tasks/math-01/status",
        json={"published": False},
    )

    assert response.status_code == 200
    assert response.json()["data"]["published"] is False
    public_tasks = client.get("/api/v1/exam/math-profile/tasks").json()["data"]
    admin_tasks = client.get("/api/v1/exam/math-profile/admin/tasks").json()["data"]
    assert len(public_tasks) == 18
    assert len(admin_tasks) == 19


def test_website_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Вектор — подготовка к ЕГЭ" in response.text
    assert "Домашние задания" in response.text
    assert "Уроки" in response.text
