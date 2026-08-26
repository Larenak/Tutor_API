from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock

from fastapi import HTTPException, status

from app.modules.exam_prep.catalog import EXAM, ROADMAP_STAGES, TASKS, THEORY, TOPICS

_lock = Lock()
_attempts: dict[str, list[dict[str, object]]] = {}
_theory_completions: dict[str, set[str]] = {}
_published: dict[str, bool] = {str(task["id"]): True for task in TASKS}

# Official EGE-2026 profile mathematics scale: primary score (tuple index)
# to test/secondary score. The conversion is intentionally table-based because
# the official scale is nonlinear.
_PROFILE_MATH_TEST_SCORES = (
    0,
    6,
    11,
    17,
    22,
    27,
    34,
    40,
    46,
    52,
    58,
    64,
    70,
    72,
    74,
    76,
    78,
    80,
    82,
    84,
    86,
    88,
    90,
    92,
    94,
    95,
    96,
    97,
    98,
    99,
    100,
    100,
    100,
)
_TEST_SCORE_SCALE_SOURCE = (
    "https://obrnadzor.gov.ru/wp-content/uploads/2026/04/"
    "tabliczy-sootvetstviya-pervichnyh-i-testovyh-ballov-ege.pdf"
)


def _sdamgia_source(problem_id: str) -> dict[str, object]:
    return {
        "label": f"СдамГИА · задание №{problem_id}",
        "url": f"https://math-ege.sdamgia.ru/problem?id={problem_id}",
        "source_id": problem_id,
        "attribution": "СдамГИА («РЕШУ ЕГЭ»)",
        "adapted": True,
        "verbatim": False,
    }


_HOMEWORK_TASK_OVERRIDES: dict[str, list[dict[str, object]]] = {
    "short-geometry:vectors": [
        {
            "prompt": "Дан вектор a = (7; 24). Найдите длину вектора a.",
            "answer_aliases": ["25", "25.0", "25,0"],
            "explanation": "|a| = √(7² + 24²) = √625 = 25.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27663"),
        },
        {
            "prompt": "Дан вектор b = (−9; 12). Найдите квадрат длины вектора b.",
            "answer_aliases": ["225", "225.0", "225,0"],
            "explanation": "|b|² = (−9)² + 12² = 81 + 144 = 225.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27664"),
        },
        {
            "prompt": (
                "Вектор AB начинается в точке A(−4; −1) и заканчивается в точке "
                "B(2; 7). Найдите сумму координат вектора AB."
            ),
            "answer_aliases": ["14", "14.0", "14,0"],
            "explanation": "AB = (6; 8), поэтому сумма координат равна 14.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27723"),
        },
        {
            "prompt": (
                "Вектор AB начинается в точке A(5; −6) и имеет координаты (−8; 10). "
                "Найдите сумму координат точки B."
            ),
            "answer_aliases": ["1", "1.0", "1,0"],
            "explanation": "B = (5 − 8; −6 + 10) = (−3; 4), сумма координат равна 1.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27726"),
        },
        {
            "prompt": (
                "Вектор AB заканчивается в точке B(11; 3) и имеет координаты (7; −5). "
                "Найдите сумму координат точки A."
            ),
            "answer_aliases": ["12", "12.0", "12,0"],
            "explanation": "A = (11 − 7; 3 − (−5)) = (4; 8), сумма координат равна 12.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27729"),
        },
        {
            "prompt": (
                "Даны векторы a = (4; 7) и b = (−1; 3). Найдите сумму координат вектора a + b."
            ),
            "answer_aliases": ["13", "13.0", "13,0"],
            "explanation": "a + b = (3; 10), сумма координат равна 13.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27730"),
        },
        {
            "prompt": (
                "Даны векторы a = (9; 2) и b = (3; −4). Найдите сумму координат вектора a − b."
            ),
            "answer_aliases": ["12", "12.0", "12,0"],
            "explanation": "a − b = (6; 6), сумма координат равна 12.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27732"),
        },
        {
            "prompt": (
                "Даны векторы a = (4; −1) и b = (2; 3). Найдите сумму координат вектора 2a + b."
            ),
            "answer_aliases": ["11", "11.0", "11,0"],
            "explanation": "2a + b = (8; −2) + (2; 3) = (10; 1), сумма равна 11.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27736"),
        },
        {
            "prompt": (
                "Даны векторы a = (7; 5) и b = (3; 1). Найдите квадрат длины вектора a − 2b."
            ),
            "answer_aliases": ["10", "10.0", "10,0"],
            "explanation": "a − 2b = (1; 3), поэтому |a − 2b|² = 1 + 9 = 10.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27737"),
        },
        {
            "prompt": (
                "Даны векторы a = (−3; 6) и b = (5; 2). Найдите скалярное произведение a · b."
            ),
            "answer_aliases": ["-3", "−3", "-3.0", "-3,0"],
            "explanation": "a · b = (−3) · 5 + 6 · 2 = −15 + 12 = −3.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27734"),
        },
        {
            "prompt": (
                "Даны векторы a = (2; 7) и b = (7; −2). Найдите угол между векторами в градусах."
            ),
            "answer_aliases": ["90", "90.0", "90,0"],
            "explanation": "a · b = 14 − 14 = 0, поэтому угол между векторами равен 90°.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27741"),
        },
        {
            "prompt": (
                "Длины векторов a и b равны 6 и 8, угол между ними равен 60°. "
                "Найдите скалярное произведение a · b."
            ),
            "answer_aliases": ["24", "24.0", "24,0"],
            "explanation": "a · b = 6 · 8 · cos 60° = 48 · 1/2 = 24.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("649909"),
        },
        {
            "prompt": (
                "Длины векторов a и b равны 10 и 4, угол между ними равен 120°. "
                "Найдите скалярное произведение a · b."
            ),
            "answer_aliases": ["-20", "−20", "-20.0", "-20,0"],
            "explanation": "a · b = 10 · 4 · cos 120° = 40 · (−1/2) = −20.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("670261"),
        },
        {
            "prompt": ("Даны векторы a = (6; 8) и b = (8; 6). Найдите косинус угла между ними."),
            "answer_aliases": ["0.96", "0,96", "24/25"],
            "explanation": "a · b = 96, |a| = |b| = 10, поэтому cos α = 96 / 100 = 0,96.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("649915"),
        },
        {
            "prompt": (
                "Длина вектора a равна 8, угол между a и b равен 60°, а их "
                "скалярное произведение равно 28. Найдите длину вектора b."
            ),
            "answer_aliases": ["7", "7.0", "7,0"],
            "explanation": "28 = 8 · |b| · cos 60° = 4|b|, поэтому |b| = 7.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("649918"),
        },
    ],
    "short-geometry:geometry": [
        {
            "title": "Прямоугольный треугольник",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Катеты прямоугольного треугольника равны 8 и 15. Найдите гипотенузу.",
            "answer_aliases": ["17", "17.0", "17,0"],
            "explanation": "c = √(8² + 15²) = √289 = 17.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("53823"),
        },
        {
            "title": "Площадь треугольника",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Две стороны треугольника равны 12 и 10, угол между ними равен 30°. Найдите площадь.",
            "answer_aliases": ["30", "30.0", "30,0"],
            "explanation": "S = 1/2 · 12 · 10 · sin 30° = 60 · 1/2 = 30.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("55261"),
        },
        {
            "title": "Равнобедренный треугольник",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Боковые стороны равнобедренного треугольника равны 10, основание равно 12. Найдите площадь.",
            "answer_aliases": ["48", "48.0", "48,0"],
            "explanation": "Высота равна √(10² − 6²) = 8, поэтому S = 1/2 · 12 · 8 = 48.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("53823"),
        },
        {
            "title": "Параллелограмм",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Основание параллелограмма равно 15, высота к нему равна 6. Найдите площадь.",
            "answer_aliases": ["90", "90.0", "90,0"],
            "explanation": "S = a · h = 15 · 6 = 90.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("259873"),
        },
        {
            "title": "Трапеция",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Основания трапеции равны 10 и 18, высота равна 4. Найдите площадь.",
            "answer_aliases": ["56", "56.0", "56,0"],
            "explanation": "S = (10 + 18) / 2 · 4 = 14 · 4 = 56.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27821"),
        },
        {
            "title": "Прямоугольник",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Диагональ прямоугольника равна 10, одна сторона равна 6. Найдите площадь прямоугольника.",
            "answer_aliases": ["48", "48.0", "48,0"],
            "explanation": "Вторая сторона равна √(10² − 6²) = 8, поэтому S = 6 · 8 = 48.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("259873"),
        },
        {
            "title": "Длина окружности",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Радиус окружности равен 7. Найдите длину окружности, делённую на π.",
            "answer_aliases": ["14", "14.0", "14,0"],
            "explanation": "L / π = 2R = 14.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("55679"),
        },
        {
            "title": "Сектор круга",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Радиус круга равен 6, угол сектора равен 90°. Найдите площадь сектора, делённую на π.",
            "answer_aliases": ["9", "9.0", "9,0"],
            "explanation": "S / π = 90 / 360 · 6² = 9.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("55679"),
        },
        {
            "title": "Касательная к окружности",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Расстояние от точки P до центра окружности равно 10, радиус равен 6. Найдите длину касательной из P.",
            "answer_aliases": ["8", "8.0", "8,0"],
            "explanation": "Касательная перпендикулярна радиусу: PT = √(10² − 6²) = 8.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("52207"),
        },
        {
            "title": "Куб",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Площадь поверхности куба равна 54. Найдите ребро куба.",
            "answer_aliases": ["3", "3.0", "3,0"],
            "explanation": "6a² = 54, поэтому a² = 9 и a = 3.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27055"),
        },
        {
            "title": "Прямоугольный параллелепипед",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Объём прямоугольного параллелепипеда равен 120, площадь одной грани равна 30. Найдите перпендикулярное этой грани ребро.",
            "answer_aliases": ["4", "4.0", "4,0"],
            "explanation": "V = Sграни · h, поэтому h = 120 / 30 = 4.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("73455"),
        },
        {
            "title": "Призма",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Площадь основания прямой призмы равна 25, высота равна 6. Найдите объём.",
            "answer_aliases": ["150", "150.0", "150,0"],
            "explanation": "V = Sосн · h = 25 · 6 = 150.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27082"),
        },
        {
            "title": "Цилиндр",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус цилиндра равен 4, высота равна 5. Найдите объём цилиндра, делённый на π.",
            "answer_aliases": ["80", "80.0", "80,0"],
            "explanation": "V / π = R²h = 4² · 5 = 80.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("5037"),
        },
        {
            "title": "Конус",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус основания конуса равен 3, высота равна 12. Найдите объём конуса, делённый на π.",
            "answer_aliases": ["36", "36.0", "36,0"],
            "explanation": "V / π = 1/3 · 3² · 12 = 36.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("269293"),
        },
        {
            "title": "Шар",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус шара равен 3. Найдите объём шара, делённый на π.",
            "answer_aliases": ["36", "36.0", "36,0"],
            "explanation": "V / π = 4/3 · 3³ = 36.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("269293"),
        },
    ],
    "probability-models:probability": [
        {
            "title": "Равновероятные исходы",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Из 30 билетов 9 выигрышных. Найдите вероятность выиграть при выборе одного билета.",
            "answer_aliases": ["0.3", "0,3", "3/10"],
            "explanation": "P = 9 / 30 = 0,3.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320181"),
        },
        {
            "title": "Случайное число",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Наугад выбирают целое число от 1 до 20. Найдите вероятность, что оно делится на 5.",
            "answer_aliases": ["0.2", "0,2", "1/5"],
            "explanation": "Подходят 4 числа: 5, 10, 15 и 20. P = 4 / 20 = 0,2.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320208"),
        },
        {
            "title": "Случайное место",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "В зале 32 места, из них 8 находятся у прохода. Найдите вероятность получить место у прохода.",
            "answer_aliases": ["0.25", "0,25", "1/4"],
            "explanation": "P = 8 / 32 = 0,25.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("660787"),
        },
        {
            "title": "Противоположное событие",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Вероятность неисправности прибора равна 0,04. Найдите вероятность, что прибор исправен.",
            "answer_aliases": ["0.96", "0,96"],
            "explanation": "P(исправен) = 1 − 0,04 = 0,96.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Вложенные события",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "P(X < 30) = 0,91, а P(X < 20) = 0,63. Найдите P(20 ≤ X < 30).",
            "answer_aliases": ["0.28", "0,28"],
            "explanation": "Меньший диапазон вложен в больший: 0,91 − 0,63 = 0,28.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("685348"),
        },
        {
            "title": "Противоположное событие",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Вероятность промаха равна 0,18. Найдите вероятность попадания.",
            "answer_aliases": ["0.82", "0,82"],
            "explanation": "Попадание и промах противоположны: 1 − 0,18 = 0,82.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Произведение вероятностей",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Два независимых датчика срабатывают с вероятностями 0,7 и 0,6. Найдите вероятность срабатывания обоих.",
            "answer_aliases": ["0.42", "0,42"],
            "explanation": "P = 0,7 · 0,6 = 0,42.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Три независимых испытания",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятность правильного ответа в каждом из трёх независимых раундов равна 0,8. Найдите вероятность трёх правильных ответов.",
            "answer_aliases": ["0.512", "0,512"],
            "explanation": "P = 0,8³ = 0,512.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Две независимые неудачи",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятности отказа двух независимых устройств равны 0,1 и 0,2. Найдите вероятность отказа обоих.",
            "answer_aliases": ["0.02", "0,02"],
            "explanation": "P = 0,1 · 0,2 = 0,02.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Несовместные события",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятности двух несовместных событий равны 0,18 и 0,27. Найдите вероятность наступления одного из них.",
            "answer_aliases": ["0.45", "0,45"],
            "explanation": "Для несовместных событий вероятности складываются: 0,18 + 0,27 = 0,45.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320199"),
        },
        {
            "title": "Хотя бы один успех",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятности успеха в двух независимых испытаниях равны 0,5 и 0,6. Найдите вероятность хотя бы одного успеха.",
            "answer_aliases": ["0.8", "0,8"],
            "explanation": "P = 1 − (1 − 0,5)(1 − 0,6) = 1 − 0,2 = 0,8.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("320199"),
        },
        {
            "title": "Объединение событий",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "P(A) = 0,55, P(B) = 0,4, P(A ∩ B) = 0,25. Найдите P(A ∪ B).",
            "answer_aliases": ["0.7", "0,7"],
            "explanation": "P(A ∪ B) = 0,55 + 0,4 − 0,25 = 0,7.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("321893"),
        },
        {
            "title": "Полная вероятность",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "80% деталей выпускает линия A с браком 1%, остальные — линия B с браком 6%. Найдите вероятность брака случайной детали.",
            "answer_aliases": ["0.02", "0,02"],
            "explanation": "P = 0,8 · 0,01 + 0,2 · 0,06 = 0,008 + 0,012 = 0,02.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("320751"),
        },
        {
            "title": "Выбор без возвращения",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "В коробке 2 красных и 3 синих шара. Берут два шара без возвращения. Найдите вероятность получить шары разных цветов.",
            "answer_aliases": ["0.6", "0,6", "3/5"],
            "explanation": "P = 2/5 · 3/4 + 3/5 · 2/4 = 0,3 + 0,3 = 0,6.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("508863"),
        },
        {
            "title": "Два выбора без возвращения",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "В коробке 3 белых и 2 чёрных шара. Берут два шара без возвращения. Найдите вероятность, что оба шара чёрные.",
            "answer_aliases": ["0.1", "0,1", "1/10"],
            "explanation": "P = 2/5 · 1/4 = 1/10 = 0,1.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("508863"),
        },
    ],
}
_PRACTICE_TASK_OVERRIDES: dict[str, list[dict[str, object]]] = {
    "short-geometry:vectors": [
        {
            "prompt": "Дан вектор a = (8; 15). Найдите длину вектора a.",
            "answer_aliases": ["17", "17.0", "17,0"],
            "explanation": "|a| = √(8² + 15²) = √289 = 17.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27663"),
        },
        {
            "prompt": "Дан вектор b = (−7; 24). Найдите квадрат длины вектора b.",
            "answer_aliases": ["625", "625.0", "625,0"],
            "explanation": "|b|² = (−7)² + 24² = 49 + 576 = 625.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27664"),
        },
        {
            "prompt": (
                "Начало вектора AB находится в точке A(−1; 2), а конец — в точке "
                "B(5; 10). Найдите длину вектора AB."
            ),
            "answer_aliases": ["10", "10.0", "10,0"],
            "explanation": "AB = (5 − (−1); 10 − 2) = (6; 8), поэтому |AB| = 10.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27723"),
        },
        {
            "prompt": (
                "Начало вектора AB — точка A(4; −3), конец — точка B(−2; 5). "
                "Найдите сумму координат вектора AB."
            ),
            "answer_aliases": ["2", "2.0", "2,0"],
            "explanation": "AB = (−2 − 4; 5 − (−3)) = (−6; 8), сумма равна 2.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27724"),
        },
        {
            "prompt": (
                "Вектор AB начинается в точке A(−3; 7) и имеет координаты (11; −4). "
                "Найдите абсциссу точки B."
            ),
            "answer_aliases": ["8", "8.0", "8,0"],
            "explanation": "xB = xA + 11 = −3 + 11 = 8.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27725"),
        },
        {
            "prompt": (
                "Вектор AB начинается в точке A(6; −5) и имеет координаты (−2; 13). "
                "Найдите ординату точки B."
            ),
            "answer_aliases": ["8", "8.0", "8,0"],
            "explanation": "yB = yA + 13 = −5 + 13 = 8.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27727"),
        },
        {
            "prompt": (
                "Вектор AB заканчивается в точке B(9; −1) и имеет координаты (5; 6). "
                "Найдите абсциссу точки A."
            ),
            "answer_aliases": ["4", "4.0", "4,0"],
            "explanation": "xA = xB − 5 = 9 − 5 = 4.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27728"),
        },
        {
            "prompt": (
                "Вектор AB заканчивается в точке B(−4; 10) и имеет координаты (−7; 3). "
                "Найдите ординату точки A."
            ),
            "answer_aliases": ["7", "7.0", "7,0"],
            "explanation": "yA = yB − 3 = 10 − 3 = 7.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27729"),
        },
        {
            "prompt": (
                "Даны векторы a = (−4; 9) и b = (7; −2). Найдите сумму координат вектора a + b."
            ),
            "answer_aliases": ["10", "10.0", "10,0"],
            "explanation": "a + b = (3; 7), сумма координат равна 10.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27730"),
        },
        {
            "prompt": (
                "Даны векторы a = (5; −1) и b = (−2; 5). Найдите квадрат длины вектора a + b."
            ),
            "answer_aliases": ["25", "25.0", "25,0"],
            "explanation": "a + b = (3; 4), поэтому |a + b|² = 3² + 4² = 25.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27731"),
        },
        {
            "prompt": (
                "Даны векторы a = (8; 3) и b = (−5; 7). Найдите сумму координат вектора a − b."
            ),
            "answer_aliases": ["9", "9.0", "9,0"],
            "explanation": "a − b = (13; −4), сумма координат равна 9.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27732"),
        },
        {
            "prompt": (
                "Даны векторы a = (3; 2) и b = (1; −4). Найдите квадрат длины вектора 2a − b."
            ),
            "answer_aliases": ["89", "89.0", "89,0"],
            "explanation": "2a − b = (6; 4) − (1; −4) = (5; 8), квадрат длины равен 89.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27733"),
        },
        {
            "prompt": (
                "Даны векторы a = (−2; 5) и b = (4; 3). "
                "Найдите скалярное произведение векторов a и b."
            ),
            "answer_aliases": ["7", "7.0", "7,0"],
            "explanation": "a · b = (−2) · 4 + 5 · 3 = −8 + 15 = 7.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27734"),
        },
        {
            "prompt": (
                "Даны векторы a = (1; −2), b = (5; 1) и c = (2; 4). "
                "Найдите скалярное произведение (a + b) · c."
            ),
            "answer_aliases": ["8", "8.0", "8,0"],
            "explanation": "a + b = (6; −1), поэтому (a + b) · c = 6 · 2 − 1 · 4 = 8.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27740"),
        },
        {
            "prompt": ("Векторы a = (x; 4) и b = (2; −3) перпендикулярны. Найдите x."),
            "answer_aliases": ["6", "6.0", "6,0"],
            "explanation": "Для перпендикулярных векторов a · b = 0: 2x − 12 = 0, откуда x = 6.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27735"),
        },
        {
            "prompt": (
                "Даны векторы a = (3; 4) и b = (4; −3). "
                "Найдите угол между векторами a и b в градусах."
            ),
            "answer_aliases": ["90", "90.0", "90,0"],
            "explanation": "a · b = 12 − 12 = 0, поэтому векторы перпендикулярны и угол равен 90°.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("27741"),
        },
        {
            "prompt": ("Даны векторы a = (6; 7) и b = (1; 2). Найдите длину вектора a − 2b."),
            "answer_aliases": ["5", "5.0", "5,0"],
            "explanation": "a − 2b = (6; 7) − (2; 4) = (4; 3), поэтому длина равна 5.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("644850"),
        },
        {
            "prompt": (
                "Длины векторов a и b равны 4 и 6, угол между ними равен 60°. "
                "Найдите скалярное произведение a · b."
            ),
            "answer_aliases": ["12", "12.0", "12,0"],
            "explanation": "a · b = |a| · |b| · cos 60° = 4 · 6 · 1/2 = 12.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("649909"),
        },
        {
            "prompt": (
                "Даны векторы a = (5; 0) и b = (−3; 4). Найдите косинус угла между векторами a и b."
            ),
            "answer_aliases": ["-0.6", "−0.6", "-0,6", "-3/5", "−3/5"],
            "explanation": "a · b = −15, |a| = |b| = 5, поэтому cos α = −15 / 25 = −0,6.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("649915"),
        },
        {
            "prompt": (
                "Длина вектора a равна 5, угол между a и b равен 60°, а их "
                "скалярное произведение равно 20. Найдите длину вектора b."
            ),
            "answer_aliases": ["8", "8.0", "8,0"],
            "explanation": "20 = 5 · |b| · cos 60° = 2,5|b|, поэтому |b| = 8.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("649918"),
        },
    ],
    "short-geometry:geometry": [
        {
            "title": "Прямоугольный треугольник",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Катеты прямоугольного треугольника равны 9 и 12. Найдите гипотенузу.",
            "answer_aliases": ["15", "15.0", "15,0"],
            "explanation": "c = √(9² + 12²) = √225 = 15.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("53823"),
        },
        {
            "title": "Площадь треугольника",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Две стороны треугольника равны 10 и 14, угол между ними равен 30°. Найдите площадь.",
            "answer_aliases": ["35", "35.0", "35,0"],
            "explanation": "S = 1/2 · 10 · 14 · sin 30° = 70 · 1/2 = 35.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("55261"),
        },
        {
            "title": "Равнобедренный треугольник",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Боковые стороны равнобедренного треугольника равны 13, основание равно 10. Найдите площадь.",
            "answer_aliases": ["60", "60.0", "60,0"],
            "explanation": "Высота равна √(13² − 5²) = 12, поэтому S = 1/2 · 10 · 12 = 60.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("53823"),
        },
        {
            "title": "Описанная окружность",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Гипотенуза прямоугольного треугольника равна 26. Найдите радиус описанной окружности.",
            "answer_aliases": ["13", "13.0", "13,0"],
            "explanation": "Центр окружности — середина гипотенузы, поэтому R = 26 / 2 = 13.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("53823"),
        },
        {
            "title": "Параллелограмм",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Основание параллелограмма равно 12, высота к нему равна 7. Найдите площадь.",
            "answer_aliases": ["84", "84.0", "84,0"],
            "explanation": "S = a · h = 12 · 7 = 84.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("259873"),
        },
        {
            "title": "Трапеция",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Основания трапеции равны 8 и 14, высота равна 5. Найдите площадь.",
            "answer_aliases": ["55", "55.0", "55,0"],
            "explanation": "S = (8 + 14) / 2 · 5 = 11 · 5 = 55.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27821"),
        },
        {
            "title": "Прямоугольник",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Диагональ прямоугольника равна 13, одна сторона равна 5. Найдите площадь прямоугольника.",
            "answer_aliases": ["60", "60.0", "60,0"],
            "explanation": "Вторая сторона равна √(13² − 5²) = 12, поэтому S = 5 · 12 = 60.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("259873"),
        },
        {
            "title": "Средняя линия трапеции",
            "exam_number": 1,
            "codifier_code": "7.1",
            "prompt": "Основания трапеции равны 6 и 16. Найдите больший отрезок, на который диагональ делит среднюю линию.",
            "answer_aliases": ["8", "8.0", "8,0"],
            "explanation": "Больший отрезок равен половине большего основания: 16 / 2 = 8.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27821"),
        },
        {
            "title": "Длина окружности",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Радиус окружности равен 6. Найдите длину окружности, делённую на π.",
            "answer_aliases": ["12", "12.0", "12,0"],
            "explanation": "L / π = 2R = 12.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("55679"),
        },
        {
            "title": "Сектор круга",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Радиус круга равен 9, угол сектора равен 40°. Найдите площадь сектора, делённую на π.",
            "answer_aliases": ["9", "9.0", "9,0"],
            "explanation": "S / π = 40 / 360 · 9² = 9.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("55679"),
        },
        {
            "title": "Вписанный угол",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Вписанный угол опирается на дугу величиной 110°. Найдите этот угол.",
            "answer_aliases": ["55", "55.0", "55,0"],
            "explanation": "Вписанный угол равен половине дуги: 110° / 2 = 55°.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27878"),
        },
        {
            "title": "Касательная к окружности",
            "exam_number": 1,
            "codifier_code": "7.2",
            "prompt": "Расстояние от точки P до центра окружности равно 13, радиус равен 5. Найдите длину касательной из P.",
            "answer_aliases": ["12", "12.0", "12,0"],
            "explanation": "Касательная перпендикулярна радиусу: PT = √(13² − 5²) = 12.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("52207"),
        },
        {
            "title": "Куб",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Ребро куба равно 4. Найдите объём куба.",
            "answer_aliases": ["64", "64.0", "64,0"],
            "explanation": "V = a³ = 4³ = 64.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27056"),
        },
        {
            "title": "Диагональ параллелепипеда",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Рёбра прямоугольного параллелепипеда равны 3, 4 и 12. Найдите его диагональ.",
            "answer_aliases": ["13", "13.0", "13,0"],
            "explanation": "d = √(3² + 4² + 12²) = √169 = 13.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("73455"),
        },
        {
            "title": "Призма",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Площадь основания прямой призмы равна 18, высота равна 7. Найдите объём.",
            "answer_aliases": ["126", "126.0", "126,0"],
            "explanation": "V = Sосн · h = 18 · 7 = 126.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27082"),
        },
        {
            "title": "Пирамида",
            "exam_number": 3,
            "codifier_code": "7.3",
            "prompt": "Площадь основания пирамиды равна 48, высота равна 9. Найдите объём.",
            "answer_aliases": ["144", "144.0", "144,0"],
            "explanation": "V = 1/3 · 48 · 9 = 144.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("324459"),
        },
        {
            "title": "Цилиндр",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус цилиндра равен 3, высота равна 8. Найдите объём цилиндра, делённый на π.",
            "answer_aliases": ["72", "72.0", "72,0"],
            "explanation": "V / π = R²h = 3² · 8 = 72.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("5037"),
        },
        {
            "title": "Боковая поверхность цилиндра",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус цилиндра равен 5, высота равна 6. Найдите площадь боковой поверхности, делённую на π.",
            "answer_aliases": ["60", "60.0", "60,0"],
            "explanation": "Sбок / π = 2Rh = 2 · 5 · 6 = 60.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27173"),
        },
        {
            "title": "Конус",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус основания конуса равен 6, высота равна 4. Найдите объём конуса, делённый на π.",
            "answer_aliases": ["48", "48.0", "48,0"],
            "explanation": "V / π = 1/3 · 6² · 4 = 48.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("269293"),
        },
        {
            "title": "Поверхность шара",
            "exam_number": 3,
            "codifier_code": "7.4",
            "prompt": "Радиус шара равен 3. Найдите площадь поверхности шара, делённую на π.",
            "answer_aliases": ["36", "36.0", "36,0"],
            "explanation": "S / π = 4R² = 4 · 3² = 36.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("27174"),
        },
    ],
    "probability-models:probability": [
        {
            "title": "Доля выбранных участников",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Из 24 участников случайно выбирают 6 человек. Найдите вероятность выбора конкретного участника.",
            "answer_aliases": ["0.25", "0,25", "1/4"],
            "explanation": "P = 6 / 24 = 0,25.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320181"),
        },
        {
            "title": "Случайное число",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Наугад выбирают целое число от 1 до 10. Найдите вероятность, что оно чётное.",
            "answer_aliases": ["0.5", "0,5", "1/2"],
            "explanation": "Подходят 5 чисел из 10: P = 5 / 10 = 0,5.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320208"),
        },
        {
            "title": "Место у окна",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "В вагоне 48 мест, из них 12 у окна. Найдите вероятность получить место у окна.",
            "answer_aliases": ["0.25", "0,25", "1/4"],
            "explanation": "P = 12 / 48 = 0,25.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("660787"),
        },
        {
            "title": "Случайный выбор",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Из 25 заявок случайно выбирают 5. Найдите вероятность выбора заранее указанной заявки.",
            "answer_aliases": ["0.2", "0,2", "1/5"],
            "explanation": "Все заявки равноправны: P = 5 / 25 = 0,2.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("685348"),
        },
        {
            "title": "Противоположное событие",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Вероятность брака детали равна 0,09. Найдите вероятность, что деталь исправна.",
            "answer_aliases": ["0.91", "0,91"],
            "explanation": "P(исправна) = 1 − 0,09 = 0,91.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Разность вложенных событий",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "P(X < 40) = 0,88, а P(X < 25) = 0,57. Найдите P(25 ≤ X < 40).",
            "answer_aliases": ["0.31", "0,31"],
            "explanation": "P = 0,88 − 0,57 = 0,31.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("685348"),
        },
        {
            "title": "Вероятность отсутствия события",
            "exam_number": 4,
            "codifier_code": "6.3",
            "prompt": "Вероятность дождя равна 0,27. Найдите вероятность, что дождя не будет.",
            "answer_aliases": ["0.73", "0,73"],
            "explanation": "P(нет дождя) = 1 − 0,27 = 0,73.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Вероятность диапазона",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "P(Y ≤ 80) = 0,95, а P(Y ≤ 50) = 0,62. Найдите P(51 ≤ Y ≤ 80).",
            "answer_aliases": ["0.33", "0,33"],
            "explanation": "События вложены: P = 0,95 − 0,62 = 0,33.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("685348"),
        },
        {
            "title": "Два независимых события",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Независимые события A и B имеют вероятности 0,8 и 0,75. Найдите вероятность их одновременного наступления.",
            "answer_aliases": ["0.6", "0,6"],
            "explanation": "P(A ∩ B) = 0,8 · 0,75 = 0,6.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Два исправных изделия",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятность исправности каждого из двух независимых изделий равна 0,97. Найдите вероятность исправности обоих.",
            "answer_aliases": ["0.9409", "0,9409"],
            "explanation": "P = 0,97² = 0,9409.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Заданный порядок исходов",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Честную монету бросают трижды. Найдите вероятность последовательности орёл, решка, орёл.",
            "answer_aliases": ["0.125", "0,125", "1/8"],
            "explanation": "P = 1/2 · 1/2 · 1/2 = 1/8 = 0,125.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320210"),
        },
        {
            "title": "Три независимых события",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятности успеха в трёх независимых испытаниях равны 0,9, 0,8 и 0,7. Найдите вероятность успеха во всех трёх.",
            "answer_aliases": ["0.504", "0,504"],
            "explanation": "P = 0,9 · 0,8 · 0,7 = 0,504.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("321893"),
        },
        {
            "title": "Сумма несовместных событий",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "События A и B несовместны, P(A) = 0,24, P(B) = 0,36. Найдите P(A ∪ B).",
            "answer_aliases": ["0.6", "0,6"],
            "explanation": "P(A ∪ B) = 0,24 + 0,36 = 0,6.",
            "estimated_minutes": 4,
            "source": _sdamgia_source("320199"),
        },
        {
            "title": "Хотя бы одно событие",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятности успеха в двух независимых испытаниях равны 0,3 и 0,4. Найдите вероятность хотя бы одного успеха.",
            "answer_aliases": ["0.58", "0,58"],
            "explanation": "P = 1 − 0,7 · 0,6 = 0,58.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("320199"),
        },
        {
            "title": "Совместные события",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "P(A) = 0,65, P(B) = 0,45, P(A ∩ B) = 0,30. Найдите P(A ∪ B).",
            "answer_aliases": ["0.8", "0,8"],
            "explanation": "P(A ∪ B) = 0,65 + 0,45 − 0,30 = 0,8.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("321893"),
        },
        {
            "title": "Ровно один успех",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Вероятности успеха в двух независимых испытаниях равны 0,7 и 0,4. Найдите вероятность ровно одного успеха.",
            "answer_aliases": ["0.54", "0,54"],
            "explanation": "P = 0,7 · 0,6 + 0,3 · 0,4 = 0,42 + 0,12 = 0,54.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("320199"),
        },
        {
            "title": "Полная вероятность брака",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "60% продукции выпускает линия A с браком 2%, остальное — линия B с браком 7%. Найдите вероятность брака случайного изделия.",
            "answer_aliases": ["0.04", "0,04"],
            "explanation": "P = 0,6 · 0,02 + 0,4 · 0,07 = 0,012 + 0,028 = 0,04.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("320751"),
        },
        {
            "title": "Два пути к успеху",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "Алгоритм выбирает путь A с вероятностью 0,4 и путь B с вероятностью 0,6. Успех на них равен 0,9 и 0,5. Найдите общую вероятность успеха.",
            "answer_aliases": ["0.66", "0,66"],
            "explanation": "P = 0,4 · 0,9 + 0,6 · 0,5 = 0,36 + 0,30 = 0,66.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("320751"),
        },
        {
            "title": "Разные цвета без возвращения",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "В коробке 3 красных и 2 синих шара. Берут два шара без возвращения. Найдите вероятность получить шары разных цветов.",
            "answer_aliases": ["0.6", "0,6", "3/5"],
            "explanation": "P = 3/5 · 2/4 + 2/5 · 3/4 = 0,3 + 0,3 = 0,6.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("508863"),
        },
        {
            "title": "Два шара без возвращения",
            "exam_number": 5,
            "codifier_code": "6.3",
            "prompt": "В коробке 3 белых и 1 чёрный шар. Берут два шара без возвращения. Найдите вероятность, что оба шара белые.",
            "answer_aliases": ["0.5", "0,5", "1/2"],
            "explanation": "P = 3/4 · 2/3 = 1/2 = 0,5.",
            "estimated_minutes": 5,
            "source": _sdamgia_source("508863"),
        },
    ],
}

_PRACTICE_SUBTOPIC_IDS: dict[str, list[list[str]]] = {
    "short-geometry:vectors": [
        ["vector-length"],
        ["vector-length"],
        ["vector-coordinates", "vector-length"],
        ["vector-coordinates"],
        ["vector-coordinates"],
        ["vector-coordinates"],
        ["vector-coordinates"],
        ["vector-coordinates"],
        ["vector-operations"],
        ["vector-operations", "vector-length"],
        ["vector-operations"],
        ["vector-operations", "vector-length"],
        ["scalar-product"],
        ["vector-operations", "scalar-product"],
        ["scalar-product"],
        ["scalar-product"],
        ["vector-operations", "vector-length"],
        ["scalar-product"],
        ["scalar-product"],
        ["scalar-product"],
    ],
    "short-geometry:geometry": [
        ["geometry-triangles"],
        ["geometry-triangles"],
        ["geometry-triangles"],
        ["geometry-triangles"],
        ["geometry-quadrilaterals"],
        ["geometry-quadrilaterals"],
        ["geometry-quadrilaterals"],
        ["geometry-quadrilaterals"],
        ["geometry-circles"],
        ["geometry-circles"],
        ["geometry-circles"],
        ["geometry-circles"],
        ["geometry-polyhedra"],
        ["geometry-polyhedra"],
        ["geometry-polyhedra"],
        ["geometry-polyhedra"],
        ["geometry-round-solids"],
        ["geometry-round-solids"],
        ["geometry-round-solids"],
        ["geometry-round-solids"],
    ],
    "probability-models:probability": [
        ["probability-outcomes"],
        ["probability-outcomes"],
        ["probability-outcomes"],
        ["probability-outcomes"],
        ["probability-complement"],
        ["probability-complement"],
        ["probability-complement"],
        ["probability-complement"],
        ["probability-product"],
        ["probability-product"],
        ["probability-product"],
        ["probability-product"],
        ["probability-union"],
        ["probability-union"],
        ["probability-union"],
        ["probability-union"],
        ["probability-tree"],
        ["probability-tree"],
        ["probability-tree"],
        ["probability-tree"],
    ],
}

_HOMEWORK_SUBTOPIC_IDS: dict[str, list[list[str]]] = {
    "short-geometry:vectors": [
        ["vector-length"],
        ["vector-length"],
        ["vector-coordinates"],
        ["vector-coordinates"],
        ["vector-coordinates"],
        ["vector-operations"],
        ["vector-operations"],
        ["vector-operations"],
        ["vector-operations", "vector-length"],
        ["scalar-product"],
        ["scalar-product"],
        ["scalar-product"],
        ["scalar-product"],
        ["scalar-product"],
        ["scalar-product"],
    ],
    "short-geometry:geometry": [
        ["geometry-triangles"],
        ["geometry-triangles"],
        ["geometry-triangles"],
        ["geometry-quadrilaterals"],
        ["geometry-quadrilaterals"],
        ["geometry-quadrilaterals"],
        ["geometry-circles"],
        ["geometry-circles"],
        ["geometry-circles"],
        ["geometry-polyhedra"],
        ["geometry-polyhedra"],
        ["geometry-polyhedra"],
        ["geometry-round-solids"],
        ["geometry-round-solids"],
        ["geometry-round-solids"],
    ],
    "probability-models:probability": [
        ["probability-outcomes"],
        ["probability-outcomes"],
        ["probability-outcomes"],
        ["probability-complement"],
        ["probability-complement"],
        ["probability-complement"],
        ["probability-product"],
        ["probability-product"],
        ["probability-product"],
        ["probability-union"],
        ["probability-union"],
        ["probability-union"],
        ["probability-tree"],
        ["probability-tree"],
        ["probability-tree"],
    ],
}


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
    result["source"] = deepcopy(
        task.get("source")
        or {
            "label": "По типу открытых материалов ФИПИ ЕГЭ-2026",
            "url": EXAM["sources"][0]["url"],
            "adapted": True,
        }
    )
    if include_answer:
        result["accepted_answers"] = deepcopy(task["answer_aliases"])
    return result


def _practice_tasks(unit_id: str, tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    overrides = _PRACTICE_TASK_OVERRIDES.get(unit_id)
    if overrides:
        result = []
        for index, override in enumerate(overrides):
            practice_task = deepcopy(tasks[0])
            practice_task.update(override)
            practice_task["lesson_task_key"] = f"{unit_id}:practice:{index + 1}"
            practice_task["subtopic_ids"] = deepcopy(
                _PRACTICE_SUBTOPIC_IDS.get(unit_id, [[] for _ in overrides])[index]
            )
            result.append(practice_task)
        return result
    result = []
    for index, task in enumerate(tasks):
        practice_task = deepcopy(task)
        practice_task["lesson_task_key"] = f"{unit_id}:practice:{index + 1}"
        practice_task["subtopic_ids"] = [f"task:{task['id']}"]
        result.append(practice_task)
    return result


def _homework_tasks(unit_id: str, tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    overrides = _HOMEWORK_TASK_OVERRIDES.get(unit_id)
    if overrides:
        result = []
        subtopic_mappings = _HOMEWORK_SUBTOPIC_IDS.get(unit_id, [])
        for index, override in enumerate(overrides):
            homework_task = deepcopy(tasks[-1])
            homework_task.update(override)
            homework_task["lesson_task_key"] = f"{unit_id}:homework:{index + 1}"
            if index < len(subtopic_mappings):
                homework_task["subtopic_ids"] = deepcopy(subtopic_mappings[index])
            result.append(homework_task)
        return result
    homework_task = deepcopy(tasks[-1])
    homework_task["lesson_task_key"] = f"{unit_id}:homework:1"
    return [homework_task]


def _lesson_units() -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    for stage in ROADMAP_STAGES:
        stage_numbers = {int(number) for number in stage["task_numbers"]}
        for topic_id in stage["topic_ids"]:
            topic = next(item for item in TOPICS if item["id"] == topic_id)
            tasks = [
                task
                for task in TASKS
                if task["topic_id"] == topic_id and int(task["exam_number"]) in stage_numbers
            ]
            if not tasks:
                continue
            theory = next(item for item in THEORY if item["topic_id"] == topic_id)
            unit_id = f"{stage['id']}:{topic_id}"
            practice_tasks = _practice_tasks(unit_id, tasks)
            homework_tasks = _homework_tasks(unit_id, tasks)
            units.append(
                {
                    "id": unit_id,
                    "stage_id": stage["id"],
                    "stage_number": stage["number"],
                    "stage_title": stage["title"],
                    "topic": topic,
                    "theory": theory,
                    "tasks": tasks,
                    "practice_tasks": practice_tasks,
                    "homework_tasks": homework_tasks,
                    "homework_task": homework_tasks[0],
                }
            )
    return units


def _session_theory_completions(session_id: str) -> set[str]:
    with _lock:
        return set(_theory_completions.get(session_id, set()))


def _has_homework_attempt(
    attempts: list[dict[str, object]],
    unit_id: str,
    homework_task: dict[str, object],
) -> bool:
    lesson_task_key = str(homework_task["lesson_task_key"])
    return any(
        item.get("lesson_unit_id") == unit_id
        and item.get("mode") == "homework"
        and item["task_id"] == homework_task["id"]
        and item.get("lesson_task_key") == lesson_task_key
        for item in attempts
    )


def _has_correct_homework_task(
    attempts: list[dict[str, object]],
    unit_id: str,
    homework_task: dict[str, object],
) -> bool:
    lesson_task_key = str(homework_task["lesson_task_key"])
    return any(
        item.get("lesson_unit_id") == unit_id
        and item.get("mode") == "homework"
        and item["task_id"] == homework_task["id"]
        and item.get("lesson_task_key") == lesson_task_key
        and bool(item["is_correct"])
        for item in attempts
    )


def _has_practice_attempt(
    attempts: list[dict[str, object]],
    unit_id: str,
    practice_task: dict[str, object],
    task_index: int,
) -> bool:
    lesson_task_key = str(practice_task["lesson_task_key"])
    return any(
        item.get("lesson_unit_id") == unit_id
        and item.get("mode") == "practice"
        and item["task_id"] == practice_task["id"]
        and (
            item.get("lesson_task_key") == lesson_task_key
            or (task_index == 0 and item.get("lesson_task_key") is None)
        )
        for item in attempts
    )


def _has_correct_practice_task(
    attempts: list[dict[str, object]],
    unit_id: str,
    practice_task: dict[str, object],
    task_index: int,
) -> bool:
    lesson_task_key = str(practice_task["lesson_task_key"])
    return any(
        item.get("lesson_unit_id") == unit_id
        and item.get("mode") == "practice"
        and item["task_id"] == practice_task["id"]
        and bool(item["is_correct"])
        and (
            item.get("lesson_task_key") == lesson_task_key
            or (task_index == 0 and item.get("lesson_task_key") is None)
        )
        for item in attempts
    )


def _lesson_unit_state(
    unit: dict[str, object],
    attempts: list[dict[str, object]],
    theory_completions: set[str],
) -> dict[str, object]:
    unit_id = str(unit["id"])
    practice_tasks = unit["practice_tasks"]
    homework_tasks = unit["homework_tasks"]
    theory_done = unit_id in theory_completions
    practice_completion = [
        _has_practice_attempt(attempts, unit_id, task, index)
        for index, task in enumerate(practice_tasks)
    ]
    practice_attempted_tasks = sum(practice_completion)
    practice_correct_tasks = sum(
        _has_correct_practice_task(attempts, unit_id, task, index)
        for index, task in enumerate(practice_tasks)
    )
    current_practice_index = next(
        (index for index, is_complete in enumerate(practice_completion) if not is_complete),
        len(practice_tasks),
    )
    practice_done = practice_attempted_tasks == len(practice_tasks)
    homework_completion = [
        _has_homework_attempt(attempts, unit_id, task) for task in homework_tasks
    ]
    homework_attempted_tasks = sum(homework_completion)
    homework_correct_tasks = sum(
        _has_correct_homework_task(attempts, unit_id, task) for task in homework_tasks
    )
    current_homework_index = next(
        (index for index, is_complete in enumerate(homework_completion) if not is_complete),
        len(homework_tasks),
    )
    homework_done = homework_attempted_tasks == len(homework_tasks)
    if practice_done:
        current_step = "complete"
    elif not theory_done:
        current_step = "theory"
    else:
        current_step = "practice"
    return {
        "current_step": current_step,
        "theory_done": theory_done,
        "practice_done": practice_done,
        "practice_attempted_tasks": practice_attempted_tasks,
        "practice_correct_tasks": practice_correct_tasks,
        "practice_total_tasks": len(practice_tasks),
        "current_practice_index": current_practice_index,
        "homework_done": homework_done,
        "homework_attempted_tasks": homework_attempted_tasks,
        "homework_correct_tasks": homework_correct_tasks,
        "homework_total_tasks": len(homework_tasks),
        "current_homework_index": current_homework_index,
        "homework_assigned": practice_done,
        "complete": practice_done,
    }


def _scaled_progress(completed: int, total: int, weight: int) -> int:
    if total <= 0:
        return weight
    return min(weight, (completed * weight + total // 2) // total)


def _lesson_progress(unit_state: dict[str, object]) -> int:
    theory_progress = 50 if bool(unit_state["theory_done"]) else 0
    practice_progress = _scaled_progress(
        int(unit_state["practice_attempted_tasks"]),
        int(unit_state["practice_total_tasks"]),
        50,
    )
    return min(100, theory_progress + practice_progress)


def _unit_subtopics(
    unit: dict[str, object],
    unit_state: dict[str, object],
    attempts: list[dict[str, object]],
) -> list[dict[str, object]]:
    theory = unit["theory"]
    sections = theory.get("sections", [])
    if sections:
        definitions = [
            {
                "id": str(section["id"]),
                "title": str(section["title"]),
                "description": str(section.get("lead", "Раздел теории урока.")),
                "kind": "theory_section",
            }
            for section in sections
        ]
    else:
        definitions = [
            {
                "id": f"task:{task['id']}",
                "title": str(task["title"]),
                "description": f"Экзаменационное задание №{task['exam_number']}",
                "kind": "exam_skill",
            }
            for task in unit["tasks"]
        ]

    result = []
    for order, definition in enumerate(definitions, start=1):
        related_tasks = [
            (index, task)
            for index, task in enumerate(unit["practice_tasks"])
            if definition["id"] in task.get("subtopic_ids", [])
        ]
        attempted_tasks = sum(
            _has_practice_attempt(attempts, str(unit["id"]), task, index)
            for index, task in related_tasks
        )
        theory_progress = 50 if bool(unit_state["theory_done"]) else 0
        practice_progress = (
            _scaled_progress(attempted_tasks, len(related_tasks), 50) if related_tasks else 0
        )
        progress = min(100, theory_progress + practice_progress)
        result.append(
            {
                **definition,
                "order": order,
                "progress": progress,
                "state": (
                    "completed"
                    if progress == 100
                    else "in_progress"
                    if progress > 0
                    else "upcoming"
                ),
                "practice_attempted_tasks": attempted_tasks,
                "practice_total_tasks": len(related_tasks),
            }
        )
    return result


def _step_state(done: bool, current: bool) -> str:
    if done:
        return "completed"
    if current:
        return "current"
    return "locked"


def _unit_error_summary(
    unit: dict[str, object], attempts: list[dict[str, object]]
) -> dict[str, int | float]:
    task_ids = {str(task["id"]) for task in unit["tasks"]}
    relevant = [item for item in attempts if str(item["task_id"]) in task_ids]
    errors = sum(not bool(item["is_correct"]) for item in relevant)
    error_rate = round(errors / len(relevant) * 100) if relevant else 0
    return {"attempts": len(relevant), "errors": errors, "error_rate": error_rate}


def _ordered_lesson_units(
    session_id: str,
    attempts: list[dict[str, object]] | None = None,
    theory_completions: set[str] | None = None,
) -> list[dict[str, object]]:
    """Keep started lessons stable and move frequently missed future units forward."""
    session_attempts = attempts if attempts is not None else _session_attempts(session_id)
    completions = (
        theory_completions
        if theory_completions is not None
        else _session_theory_completions(session_id)
    )
    ranked = []
    for base_position, unit in enumerate(_lesson_units()):
        unit_state = _lesson_unit_state(unit, session_attempts, completions)
        errors = _unit_error_summary(unit, session_attempts)
        if unit_state["complete"]:
            bucket = 0
            priority = (base_position,)
        elif unit_state["theory_done"]:
            bucket = 1
            priority = (base_position,)
        elif errors["errors"]:
            bucket = 2
            priority = (
                -int(errors["errors"]),
                -float(errors["error_rate"]),
                base_position,
            )
        else:
            bucket = 3
            priority = (base_position,)
        ranked.append((bucket, priority, unit))
    return [item[2] for item in sorted(ranked, key=lambda item: (item[0], item[1]))]


def get_current_lesson(session_id: str) -> dict[str, object]:
    attempts = _session_attempts(session_id)
    theory_completions = _session_theory_completions(session_id)
    units = _ordered_lesson_units(session_id, attempts, theory_completions)
    states = [_lesson_unit_state(unit, attempts, theory_completions) for unit in units]
    current_index = next(
        (index for index, unit_state in enumerate(states) if not unit_state["complete"]),
        None,
    )
    completed = sum(bool(unit_state["complete"]) for unit_state in states)
    overall_progress = round(
        sum(_lesson_progress(unit_state) for unit_state in states) / len(states)
    )
    if current_index is None:
        return {
            "session_id": session_id,
            "status": "completed",
            "current_step": "complete",
            "completed_units": completed,
            "total_units": len(units),
            "overall_progress": overall_progress,
        }

    unit = units[current_index]
    unit_state = states[current_index]
    current_step = str(unit_state["current_step"])
    theory = deepcopy(unit["theory"])
    practice_task = _public_task(unit["practice_tasks"][int(unit_state["current_practice_index"])])
    homework_task = _public_task(unit["homework_task"])
    steps = [
        {
            "id": "theory",
            "label": "Теория",
            "state": _step_state(bool(unit_state["theory_done"]), current_step == "theory"),
        },
        {
            "id": "practice",
            "label": "Практика",
            "state": _step_state(
                bool(unit_state["practice_done"]),
                current_step == "practice",
            ),
        },
    ]
    topic = unit["topic"]
    return {
        "session_id": session_id,
        "status": "active",
        "unit_id": unit["id"],
        "position": current_index + 1,
        "completed_units": completed,
        "total_units": len(units),
        "overall_progress": overall_progress,
        "progress": _lesson_progress(unit_state),
        "subtopics": _unit_subtopics(unit, unit_state, attempts),
        "current_step": current_step,
        "steps": steps,
        "stage": {
            "id": unit["stage_id"],
            "number": unit["stage_number"],
            "title": unit["stage_title"],
        },
        "topic": {
            "id": topic["id"],
            "title": topic["title"],
            "short_title": topic["short_title"],
            "description": topic["description"],
            "accent": topic["accent"],
        },
        "theory": theory,
        "practice_task": practice_task,
        "practice": {
            "attempted_tasks": unit_state["practice_attempted_tasks"],
            "correct_tasks": unit_state["practice_correct_tasks"],
            "total_tasks": unit_state["practice_total_tasks"],
            "current_task_number": int(unit_state["current_practice_index"]) + 1,
            "topic_id": topic["id"],
        },
        "homework_task": homework_task,
    }


def get_current_homework(session_id: str) -> dict[str, object]:
    attempts = _session_attempts(session_id)
    theory_completions = _session_theory_completions(session_id)
    pending = []
    for unit in _lesson_units():
        unit_state = _lesson_unit_state(unit, attempts, theory_completions)
        if not unit_state["homework_assigned"] or unit_state["homework_done"]:
            continue
        assigned_attempt = max(
            (
                item
                for item in attempts
                if item.get("lesson_unit_id") == unit["id"] and item.get("mode") == "practice"
            ),
            key=lambda item: str(item["created_at"]),
        )
        assigned_at = datetime.fromisoformat(str(assigned_attempt["created_at"]))
        pending.append((assigned_at, unit, unit_state))

    if not pending:
        return {
            "session_id": session_id,
            "status": "empty",
            "pending_count": 0,
            "message": "Новое домашнее задание появится после учебной практики.",
        }

    assigned_at, unit, unit_state = min(pending, key=lambda item: item[0])
    topic = unit["topic"]
    current_task = unit["homework_tasks"][int(unit_state["current_homework_index"])]
    pending_count = sum(
        int(state["homework_total_tasks"]) - int(state["homework_attempted_tasks"])
        for _, _, state in pending
    )
    return {
        "session_id": session_id,
        "status": "active",
        "pending_count": pending_count,
        "unit_id": unit["id"],
        "assigned_at": assigned_at.isoformat(),
        "due_date": (assigned_at.date() + timedelta(days=1)).isoformat(),
        "attempted_tasks": unit_state["homework_attempted_tasks"],
        "correct_tasks": unit_state["homework_correct_tasks"],
        "total_tasks": unit_state["homework_total_tasks"],
        "current_task_number": int(unit_state["current_homework_index"]) + 1,
        "remaining_tasks": (
            int(unit_state["homework_total_tasks"]) - int(unit_state["homework_attempted_tasks"])
        ),
        "estimated_minutes": sum(
            int(task["estimated_minutes"])
            for task in unit["homework_tasks"][int(unit_state["current_homework_index"]) :]
        ),
        "topic": {
            "id": topic["id"],
            "title": topic["title"],
            "short_title": topic["short_title"],
            "description": topic["description"],
            "accent": topic["accent"],
        },
        "stage": {
            "id": unit["stage_id"],
            "number": unit["stage_number"],
            "title": unit["stage_title"],
        },
        "task": _public_task(current_task),
    }


def complete_lesson_theory(session_id: str, lesson_unit_id: str) -> dict[str, object]:
    lesson = get_current_lesson(session_id)
    if lesson["status"] == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Roadmap completed")
    if lesson["unit_id"] != lesson_unit_id or lesson["current_step"] != "theory":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete the current roadmap theory step first",
        )
    with _lock:
        _theory_completions.setdefault(session_id, set()).add(lesson_unit_id)
    return get_current_lesson(session_id)


def _validate_lesson_attempt(
    session_id: str,
    task_id: str,
    mode: str,
    lesson_unit_id: str | None,
    lesson_task_key: str | None,
) -> None:
    if mode == "diagnostic":
        return
    if lesson_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lesson_unit_id is required for a roadmap lesson attempt",
        )
    if mode == "homework":
        homework = get_current_homework(session_id)
        if homework["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No assigned homework is waiting for completion",
            )
        if homework["unit_id"] != lesson_unit_id or homework["task"]["id"] != task_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This task is not the current homework assignment",
            )
        if lesson_task_key is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="lesson_task_key is required for a homework attempt",
            )
        if homework["task"].get("lesson_task_key") != lesson_task_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This homework task is no longer available for answering",
            )
        if any(
            item.get("lesson_unit_id") == lesson_unit_id
            and item.get("mode") == "homework"
            and item.get("lesson_task_key") == lesson_task_key
            for item in _session_attempts(session_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This homework task has already been answered",
            )
        return
    lesson = get_current_lesson(session_id)
    if lesson["status"] == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Roadmap completed")
    if lesson["unit_id"] != lesson_unit_id or lesson["current_step"] != mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Follow the roadmap lesson order: theory, then practice",
        )
    expected_task = lesson[f"{mode}_task"]
    if expected_task["id"] != task_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task is not the current roadmap step",
        )
    if mode == "practice":
        if lesson_task_key is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="lesson_task_key is required for a practice attempt",
            )
        if expected_task.get("lesson_task_key") != lesson_task_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This practice task is no longer available for answering",
            )
        if any(
            item.get("lesson_unit_id") == lesson_unit_id
            and item.get("mode") == "practice"
            and item.get("lesson_task_key") == lesson_task_key
            for item in _session_attempts(session_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This practice task has already been answered",
            )


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
    mode: str = "diagnostic",
    lesson_unit_id: str | None = None,
    lesson_task_key: str | None = None,
) -> dict[str, object]:
    task = _task(task_id)
    if not _published[task_id]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    _validate_lesson_attempt(
        session_id,
        task_id,
        mode,
        lesson_unit_id,
        lesson_task_key,
    )
    lesson_task = None
    if mode == "practice":
        lesson_before_attempt = get_current_lesson(session_id)
        lesson_unit = next(
            unit for unit in _lesson_units() if unit["id"] == lesson_before_attempt.get("unit_id")
        )
        lesson_task = next(
            item
            for item in lesson_unit["practice_tasks"]
            if item["lesson_task_key"] == lesson_task_key
        )
    elif mode == "homework":
        homework_before_attempt = get_current_homework(session_id)
        lesson_unit = next(
            unit for unit in _lesson_units() if unit["id"] == homework_before_attempt.get("unit_id")
        )
        lesson_task = next(
            item
            for item in lesson_unit["homework_tasks"]
            if item["lesson_task_key"] == lesson_task_key
        )
    accepted_answers = list(
        lesson_task["answer_aliases"] if isinstance(lesson_task, dict) else task["answer_aliases"]
    )
    is_correct = _matches(answer, accepted_answers)
    attempt = {
        "id": f"attempt-{datetime.now(UTC).timestamp()}",
        "task_id": task_id,
        "answer": answer,
        "is_correct": is_correct,
        "duration_seconds": duration_seconds,
        "mode": mode,
        "lesson_unit_id": lesson_unit_id,
        "lesson_task_key": (
            lesson_task.get("lesson_task_key") if isinstance(lesson_task, dict) else None
        ),
        "created_at": datetime.now(UTC).isoformat(),
    }
    with _lock:
        _attempts.setdefault(session_id, []).append(attempt)
    topic = next(item for item in TOPICS if item["id"] == task["topic_id"])
    lesson_after_attempt = get_current_lesson(session_id) if mode != "diagnostic" else None
    homework_after_attempt = get_current_homework(session_id) if mode != "diagnostic" else None
    practice_unit_complete = bool(
        mode == "practice"
        and isinstance(lesson_after_attempt, dict)
        and lesson_after_attempt.get("unit_id") != lesson_unit_id
    )
    homework_unit_complete = bool(
        mode == "homework"
        and isinstance(homework_after_attempt, dict)
        and (
            homework_after_attempt.get("status") != "active"
            or homework_after_attempt.get("unit_id") != lesson_unit_id
        )
    )
    return {
        "attempt": deepcopy(attempt),
        "is_correct": is_correct,
        "earned_primary_score": int(task["max_primary_score"]) if is_correct else 0,
        "max_primary_score": task["max_primary_score"],
        "explanation": (
            lesson_task["explanation"] if isinstance(lesson_task, dict) else task["explanation"]
        ),
        "correct_answer": accepted_answers[0],
        "theory_id": task["theory_id"],
        "topic": {"id": topic["id"], "title": topic["title"]},
        "recommendation": (
            "Отлично. Домашняя работа завершена."
            if homework_unit_complete and is_correct
            else "Домашняя работа завершена. Ошибки добавлены в план повторения."
            if homework_unit_complete
            else "Верно. Переходите к следующей самостоятельной задаче."
            if is_correct and mode == "homework"
            else "Задание отмечено неверным. Повторный ответ недоступен; переходите к следующему."
            if mode == "homework"
            else "Тематический блок завершён. Домашнее задание добавлено отдельно."
            if practice_unit_complete
            else "Верно. Продолжайте следующей задачей по этой же теории."
            if is_correct and mode == "practice"
            else "Отлично. Переходите к следующему шагу занятия."
            if is_correct
            else "Задание отмечено неверным. Повторный ответ недоступен; тема добавлена в повторение."
        ),
        "lesson": lesson_after_attempt,
        "homework": homework_after_attempt,
        "lesson_unit_complete": practice_unit_complete,
        "homework_unit_complete": homework_unit_complete,
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


def _to_test_score(primary_score: int) -> int:
    return _PROFILE_MATH_TEST_SCORES[primary_score]


def _prediction(attempts: list[dict[str, object]]) -> dict[str, object]:
    latest_by_task: dict[str, dict[str, object]] = {}
    for attempt in attempts:
        latest_by_task[str(attempt["task_id"])] = attempt

    missing = [int(task["exam_number"]) for task in TASKS if str(task["id"]) not in latest_by_task]
    available = not missing
    primary = None
    if available:
        primary = sum(
            int(task["max_primary_score"])
            for task in TASKS
            if bool(latest_by_task[str(task["id"])]["is_correct"])
        )
    test_score = _to_test_score(primary) if primary is not None else None
    return {
        "available": available,
        "predicted_primary_score": primary,
        "predicted_test_score": test_score,
        "max_primary_score": int(EXAM["max_primary_score"]),
        "max_test_score": 100,
        "covered_task_types": len(TASKS) - len(missing),
        "required_task_types": len(TASKS),
        "missing_task_numbers": missing,
        "basis": (
            "Ожидаемый балл по полной диагностике: последняя реальная попытка по каждому из 19 типов."
            if available
            else "Прогноз появится после реальных попыток по всем 19 типам заданий."
        ),
        "test_score_note": (
            f"{primary} из 32 первичных переведены по шкале ЕГЭ-2026."
            if available
            else "До полной диагностики тестовый балл не подставляется."
        ),
        "test_score_scale": "ЕГЭ-2026",
        "test_score_scale_source": _TEST_SCORE_SCALE_SOURCE,
    }


def _prediction_history(attempts: list[dict[str, object]]) -> list[dict[str, object]]:
    latest_by_task: dict[str, dict[str, object]] = {}
    history = []
    for attempt_number, attempt in enumerate(attempts, start=1):
        task_id = str(attempt["task_id"])
        latest_by_task[task_id] = attempt
        if len(latest_by_task) < len(TASKS):
            continue
        primary_score = sum(
            int(task["max_primary_score"])
            for task in TASKS
            if bool(latest_by_task[str(task["id"])]["is_correct"])
        )
        task = _task(task_id)
        history.append(
            {
                "attempt_number": attempt_number,
                "label": f"№{task['exam_number']}",
                "score": _to_test_score(primary_score),
                "max_score": 100,
                "primary_score": primary_score,
                "max_primary_score": int(EXAM["max_primary_score"]),
                "created_at": attempt["created_at"],
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


def _study_streak(attempts: list[dict[str, object]]) -> int:
    active_dates = {datetime.fromisoformat(str(item["created_at"])).date() for item in attempts}
    if not active_dates:
        return 0
    today = datetime.now(UTC).date()
    cursor = today if today in active_dates else today - timedelta(days=1)
    if cursor not in active_dates:
        return 0
    streak = 0
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


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
            "streak_days": _study_streak(attempts),
        },
        "prediction": _prediction(attempts),
        "topics": metrics,
        "weak_topics": weak,
        "strong_topics": strong,
        "individual_plan": plan,
        "prediction_history": _prediction_history(attempts),
        "week_activity": _week_activity(attempts),
    }


def get_roadmap(session_id: str) -> dict[str, object]:
    attempts = _session_attempts(session_id)
    metrics = {str(item["topic_id"]): item for item in _topic_metrics(attempts)}
    attempted_task_ids = {str(item["task_id"]) for item in attempts}
    theory_completions = _session_theory_completions(session_id)
    base_units = _lesson_units()
    base_positions = {str(unit["id"]): index for index, unit in enumerate(base_units)}
    lesson_units = _ordered_lesson_units(session_id, attempts, theory_completions)
    lesson_states = {
        str(unit["id"]): _lesson_unit_state(unit, attempts, theory_completions)
        for unit in lesson_units
    }
    current_lesson = get_current_lesson(session_id)
    current_unit_id = (
        str(current_lesson["unit_id"]) if current_lesson["status"] == "active" else None
    )
    stages = []

    for stage in ROADMAP_STAGES:
        task_numbers = [int(number) for number in stage["task_numbers"]]
        stage_tasks = [task for task in TASKS if int(task["exam_number"]) in task_numbers]
        stage_units = [unit for unit in lesson_units if unit["stage_id"] == stage["id"]]
        completed_lessons = sum(
            bool(lesson_states[str(unit["id"])]["complete"]) for unit in stage_units
        )
        stage_task_ids = {str(task["id"]) for task in stage_tasks}
        stage_attempts = [item for item in attempts if str(item["task_id"]) in stage_task_ids]
        covered = len(stage_task_ids & attempted_task_ids)
        mastery = (
            round(
                sum(bool(item["is_correct"]) for item in stage_attempts) / len(stage_attempts) * 100
            )
            if stage_attempts
            else None
        )
        stages.append(
            {
                **deepcopy(stage),
                "mastery": mastery,
                "state": (
                    "completed"
                    if completed_lessons == len(stage_units)
                    else "current"
                    if any(str(unit["id"]) == current_unit_id for unit in stage_units)
                    else "upcoming"
                ),
                "completed_lessons": completed_lessons,
                "lesson_units": len(stage_units),
                "progress": (
                    round(
                        sum(
                            _lesson_progress(lesson_states[str(unit["id"])]) for unit in stage_units
                        )
                        / len(stage_units)
                    )
                    if stage_units
                    else 0
                ),
                "covered_task_types": covered,
                "task_types": len(stage_tasks),
                "tasks": [
                    {
                        "id": task["id"],
                        "exam_number": task["exam_number"],
                        "title": task["title"],
                        "difficulty": task["difficulty"],
                        "href": "#lessons",
                    }
                    for task in stage_tasks
                ],
                "topics": [
                    {
                        "unit_id": unit["id"],
                        "id": str(unit["topic"]["id"]),
                        "title": metrics[str(unit["topic"]["id"])]["short_title"],
                        "mastery": metrics[str(unit["topic"]["id"])]["mastery"],
                        "attempts": metrics[str(unit["topic"]["id"])]["attempts"],
                        "task_numbers": [int(task["exam_number"]) for task in unit["tasks"]],
                        "theory_id": metrics[str(unit["topic"]["id"])]["theory_id"],
                        "current_step": lesson_states[str(unit["id"])]["current_step"],
                        "progress": _lesson_progress(lesson_states[str(unit["id"])]),
                        "subtopics": _unit_subtopics(
                            unit,
                            lesson_states[str(unit["id"])],
                            attempts,
                        ),
                        "lesson_state": (
                            "completed"
                            if lesson_states[str(unit["id"])]["complete"]
                            else "current"
                            if str(unit["id"]) == current_unit_id
                            else "locked"
                        ),
                        "lesson_href": "#lessons",
                    }
                    for unit in stage_units
                ],
            }
        )

    lesson_order = []
    for position, unit in enumerate(lesson_units, start=1):
        unit_id = str(unit["id"])
        topic_id = str(unit["topic"]["id"])
        unit_state = lesson_states[unit_id]
        errors = _unit_error_summary(unit, attempts)
        movement = base_positions[unit_id] + 1 - position
        is_current = unit_id == current_unit_id
        if unit_state["complete"]:
            reason = "Урок пройден; домашняя работа хранится отдельно."
        elif errors["errors"] and movement > 0:
            reason = (
                f"Поднята на {movement} поз. из-за ошибок: "
                f"{errors['errors']} из {errors['attempts']} попыток."
            )
        elif errors["errors"]:
            reason = f"Приоритет подтверждён ошибками: {errors['errors']} попыток."
        elif is_current:
            reason = "Текущий урок по базовой логике курса."
        else:
            reason = "Базовый порядок: от опорных тем к более сложным."
        lesson_order.append(
            {
                "position": position,
                "unit_id": unit_id,
                "topic": {
                    "id": topic_id,
                    "title": unit["topic"]["title"],
                    "short_title": unit["topic"]["short_title"],
                    "description": unit["topic"]["description"],
                },
                "stage": {
                    "id": unit["stage_id"],
                    "number": unit["stage_number"],
                    "title": unit["stage_title"],
                },
                "task_numbers": [int(task["exam_number"]) for task in unit["tasks"]],
                "mastery": metrics[topic_id]["mastery"],
                "current_step": unit_state["current_step"],
                "progress": _lesson_progress(unit_state),
                "subtopics": _unit_subtopics(unit, unit_state, attempts),
                "lesson_state": (
                    "completed"
                    if unit_state["complete"]
                    else "current"
                    if is_current
                    else "upcoming"
                ),
                "homework_status": (
                    "completed"
                    if unit_state["homework_done"]
                    else "assigned"
                    if unit_state["homework_assigned"]
                    else "not_assigned"
                ),
                "is_adapted": bool(errors["errors"] and movement > 0),
                "reason": reason,
            }
        )

    current_stage_id = (
        str(current_lesson["stage"]["id"])
        if current_lesson["status"] == "active"
        else str(stages[-1]["id"])
    )
    return {
        "session_id": session_id,
        "principle": (
            "Roadmap задаёт порядок уроков и поднимает темы, где ученик чаще ошибается. "
            "Домашние задания и интервальные повторения планируются отдельно."
        ),
        "adaptation": {
            "active": any(item["is_adapted"] for item in lesson_order),
            "adapted_units": sum(bool(item["is_adapted"]) for item in lesson_order),
            "message": (
                "Порядок пересчитан по реальным ошибкам ученика."
                if any(item["is_adapted"] for item in lesson_order)
                else "Пока используется базовый порядок курса; он изменится после ошибок."
            ),
        },
        "current_stage_id": current_stage_id,
        "current_unit_id": current_unit_id,
        "overall_progress": current_lesson["overall_progress"],
        "completed_lesson_units": current_lesson["completed_units"],
        "total_lesson_units": current_lesson["total_units"],
        "covered_task_types": len(attempted_task_ids),
        "total_task_types": len(TASKS),
        "current_lesson": current_lesson,
        "lesson_order": lesson_order,
        "stages": stages,
    }


def get_student_dashboard(session_id: str) -> dict[str, object]:
    analytics = get_analytics(session_id)
    roadmap = get_roadmap(session_id)
    lesson = roadmap["current_lesson"]
    homework = get_current_homework(session_id)
    today = datetime.now(UTC).date()

    lesson_today = None
    if lesson["status"] == "active":
        current_step = str(lesson["current_step"])
        lesson_today = {
            "unit_id": lesson["unit_id"],
            "title": lesson["topic"]["short_title"],
            "description": lesson["topic"]["description"],
            "step": current_step,
            "step_label": "Теория" if current_step == "theory" else "Практика",
            "progress": lesson["progress"],
            "subtopics": lesson["subtopics"],
            "estimated_minutes": (
                lesson["theory"]["read_minutes"]
                if current_step == "theory"
                else lesson["practice_task"]["estimated_minutes"]
            ),
            "href": "#lessons",
        }

    homework_today = None
    if homework["status"] == "active":
        homework_today = {
            "unit_id": homework["unit_id"],
            "title": homework["topic"]["short_title"],
            "description": (
                f"Самостоятельная работа: осталось {homework['remaining_tasks']} "
                "заданий без подсказок из практики."
            ),
            "due_date": homework["due_date"],
            "estimated_minutes": homework["estimated_minutes"],
            "progress": _scaled_progress(
                int(homework["attempted_tasks"]),
                int(homework["total_tasks"]),
                100,
            ),
            "href": "#homework",
        }

    roadmap_preview = [
        item for item in roadmap["lesson_order"] if item["lesson_state"] != "completed"
    ][:4]
    schedule = []
    for index, item in enumerate(roadmap_preview[:3]):
        schedule.append(
            {
                "kind": "lesson",
                "date": (today + timedelta(days=index * 2)).isoformat(),
                "title": item["topic"]["short_title"],
                "detail": (
                    "Текущий урок"
                    if item["lesson_state"] == "current"
                    else f"Этап {item['stage']['number']} · по roadmap"
                ),
                "progress": item["progress"],
                "subtopics": item["subtopics"],
                "href": "#lessons",
            }
        )
    if homework_today:
        schedule.append(
            {
                "kind": "homework",
                "date": homework_today["due_date"],
                "title": homework_today["title"],
                "detail": "Срок домашней работы",
                "progress": homework_today["progress"],
                "href": "#homework",
            }
        )
    for item in analytics["individual_plan"]:
        schedule.append(
            {
                "kind": "review",
                "date": item["due_date"],
                "title": item["title"],
                "detail": item["action"],
                "href": "#lessons",
            }
        )
    kind_order = {"homework": 0, "review": 1, "lesson": 2}
    schedule.sort(key=lambda item: (str(item["date"]), kind_order[str(item["kind"])]))

    prediction = analytics["prediction"]
    return {
        "session_id": session_id,
        "date": today.isoformat(),
        "metrics": {
            "expected_test_score": prediction["predicted_test_score"],
            "max_test_score": prediction["max_test_score"],
            "prediction_available": prediction["available"],
            "prediction_basis": prediction["basis"],
            "streak_days": analytics["summary"]["streak_days"],
        },
        "today": {
            "lesson": lesson_today,
            "homework": homework_today,
            "reviews": [
                item
                for item in analytics["individual_plan"]
                if str(item["due_date"]) <= today.isoformat()
            ],
        },
        "schedule": schedule,
        "schedule_note": (
            "Даты следующих уроков ориентировочные: после каждой попытки roadmap "
            "пересчитывает порядок и добавляет повторения."
        ),
        "roadmap": {
            "progress": roadmap["overall_progress"],
            "completed_units": roadmap["completed_lesson_units"],
            "total_units": roadmap["total_lesson_units"],
            "adaptation": roadmap["adaptation"],
            "next_lessons": roadmap_preview,
            "href": "#roadmap",
            "lessons_href": "#lessons",
        },
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
                "risk": "stable"
                if accuracy >= 70
                else "attention"
                if accuracy >= 50
                else "critical",
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
        _theory_completions.clear()
        _published.clear()
        _published.update({str(task["id"]): True for task in TASKS})
