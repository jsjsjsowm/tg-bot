# -*- coding: utf-8 -*-
"""
Schedule data for E-24 group, 2nd year, 1st semester
"""

SCHEDULE = {
    "monday": [
        {"time": "8:30-9:50", "subject": "Физическая культура", "pair_number": 1},
        {"time": "10:00-11:20", "subject": "География/Зарубежная литература", "pair_number": 2},
        {"time": "12:00-13:20", "subject": "Гражданское образование", "pair_number": 3},
        {"time": "13:30-14:50", "subject": "История Украины/Всемирная История", "pair_number": 4}
    ],
    "tuesday": [
        {"time": "8:30-9:50", "subject": "Защита Украины", "pair_number": 1},
        {"time": "10:00-11:20", "subject": "Химия/Биология и экология", "pair_number": 2},
        {"time": "12:00-13:20", "subject": "Математика", "pair_number": 3},
        {"time": "13:30-14:50", "subject": "Основы программирования", "pair_number": 4}
    ],
    "wednesday": [
        {"time": "8:30-9:50", "subject": "Украинский язык", "pair_number": 1},
        {"time": "10:00-11:20", "subject": "Теория электрических и магнитных цепей", "pair_number": 2},
        {"time": "12:00-13:20", "subject": "Украинская литература", "pair_number": 3}
    ],
    "thursday": [
        {"time": "8:30-9:50", "subject": "Технологии/Компьютерная графика", "pair_number": 1},
        {"time": "10:00-11:20", "subject": "Информатика", "pair_number": 2},
        {"time": "12:00-13:20", "subject": "Основы программирования/ТЭ и МК", "pair_number": 3}
    ],
    "friday": [
        {"time": "8:30-9:50", "subject": "Иностранный язык/Физика и астрономия", "pair_number": 1},
        {"time": "10:00-11:20", "subject": "Физика и астрономия", "pair_number": 2},
        {"time": "12:00-13:20", "subject": "Математика/Физическая культура", "pair_number": 3}
    ]
}


# Break schedule
BREAK_SCHEDULE = [
    {"time": "8:30-9:50", "break_after": "9:50-10:00"},
    {"time": "10:00-11:20", "break_after": "11:20-12:00"},
    {"time": "12:00-13:20", "break_after": "13:20-13:30"},
    {"time": "13:30-14:50", "break_after": "после занятий"}
]

WEEKDAYS = {
    0: "monday",
    1: "tuesday", 
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday"
}

WEEKDAYS_UA = {
    "monday": "Понедельник",
    "tuesday": "Вторник",
    "wednesday": "Среда", 
    "thursday": "Четверг",
    "friday": "Пятница",
    "saturday": "Суббота",
    "sunday": "Воскресенье"
}
