import pytest
from fastapi.testclient import TestClient

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
    assert all(topic["mastery"] is None for topic in before["topics"])
    assert correct.status_code == 200
    assert correct.json()["data"]["is_correct"] is True
    assert incorrect.json()["data"]["is_correct"] is False
    assert after["summary"]["attempts"] == 2
    assert after["summary"]["accuracy"] == 50
    assert len(after["individual_plan"]) == 1
    assert after["individual_plan"][0]["task_id"] == "math-06"
    assert "№6" in after["individual_plan"][0]["action"]
    assert after["prediction"]["available"] is False
    assert after["history"][-1]["score"] == 50


def test_roadmap_is_ordered_from_basic_to_expert(client: TestClient) -> None:
    response = client.get("/api/v1/exam/math-profile/roadmap")

    assert response.status_code == 200
    stages = response.json()["data"]["stages"]
    assert [stage["number"] for stage in stages] == [1, 2, 3, 4, 5]
    assert stages[0]["difficulty"] == "basic"
    assert stages[-1]["difficulty"] == "expert"
    assert stages[0]["topics"][0]["id"] == "vectors"
    assert stages[0]["topics"][0]["lesson_state"] == "current"
    assert stages[0]["topics"][1]["lesson_state"] == "locked"
    task_numbers = [number for stage in stages for number in stage["task_numbers"]]
    assert sorted(task_numbers) == list(range(1, 20))
    assert all(topic["lesson_href"] == "#lessons" for stage in stages for topic in stage["topics"])
    assert all(task["href"] == "#lessons" for stage in stages for task in stage["tasks"])


def test_lesson_follows_roadmap_theory_practice_homework_order(client: TestClient) -> None:
    lesson = client.get(
        "/api/v1/exam/math-profile/lesson/current",
        params={"session_id": "lesson-student"},
    ).json()["data"]

    assert lesson["topic"]["id"] == "vectors"
    assert lesson["current_step"] == "theory"
    assert [step["state"] for step in lesson["steps"]] == ["current", "locked", "locked"]
    assert lesson["practice_task"]["id"] == "math-02"
    assert lesson["homework_task"]["id"] == "math-02"
    assert lesson["practice_task"]["prompt"] != lesson["homework_task"]["prompt"]

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

    practice = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "-5",
            "mode": "practice",
            "lesson_unit_id": lesson["unit_id"],
        },
    ).json()["data"]
    assert practice["is_correct"] is True
    assert practice["lesson"]["current_step"] == "homework"

    homework = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": "lesson-student",
            "task_id": "math-02",
            "answer": "-5",
            "mode": "homework",
            "lesson_unit_id": lesson["unit_id"],
        },
    ).json()["data"]
    assert homework["is_correct"] is True
    assert homework["lesson"]["topic"]["id"] == "geometry"
    assert homework["lesson"]["current_step"] == "theory"

    roadmap = client.get(
        "/api/v1/exam/math-profile/roadmap",
        params={"session_id": "lesson-student"},
    ).json()["data"]
    assert roadmap["stages"][0]["topics"][0]["lesson_state"] == "completed"
    assert roadmap["stages"][0]["topics"][1]["lesson_state"] == "current"


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
    assert "Занятия" in response.text
