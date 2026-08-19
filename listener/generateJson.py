import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))


import json
from typing import List, Dict
import asyncio
import random

from libs.renovation_api import RenovatioClient

class GenerationJsonDataSet:
    def __init__(self):
        self.client = RenovatioClient(
            "https://192.168.19.2:3010/api/public",
            "b56d520a62c1e2861b93141f74895878",
            verify_ssl=False
        )

    def _generate_category_requests(self, name: str) -> List[str]:
        """Генерирует разнообразные запросы пользователя для категории (специальности)."""
        templates = [
            f"Хочу записаться к {name}",
            f"Мне нужно попасть на приём к {name}",
            f"Запишите меня к {name}",
            f"Нужен приём у {name}",
            f"Ищу {name}",
            f"Хочу попасть к {name}",
            f"Мне нужен {name}",
            f"Подскажите, есть ли {name}?",
            f"Можно ли записаться к {name}?",
            f"Хочу на приём к {name}",
            # ... остальные шаблоны (оставляем как в оригинале)
        ]
        return templates

    def _generate_doctor_requests(self, doctor_name: str) -> List[str]:
        """Генерирует запросы для конкретного врача."""
        templates = [
            f"Хочу записаться к {doctor_name}",
            f"Есть ли {doctor_name}?",
            f"Когда принимает {doctor_name}?",
            f"Можно ли к {doctor_name}?",
            f"Запишите меня к {doctor_name}",
            f"Ищу врача {doctor_name}",
            f"Нужен {doctor_name}",
            f"Как попасть к {doctor_name}?",
            # ... остальные шаблоны (оставляем как в оригинале)
        ]
        return templates

    async def get_categories_and_doctors(self) -> None:
        """
        Получает категории и врачей, генерирует датасет и сохраняет в JSONL.
        """
        categories = await self.client.get_professions()
        doctors = await self.client.get_users(role="doctor")

        training_data = []

        # 1. Генерация данных по категориям (специальностям)
        for item in categories:
            name = item['name'].lower()
            cat_id = str(item['id'])

            user_requests = self._generate_category_requests(name)

            for user_text in user_requests:
                response_obj = {
                    "text": f"Да, в нашей клинике принимает {name}.",
                    "method": "get_specialty",
                    "specialty_id": cat_id,
                    "title": name
                }
                training_data.append({
                    "request": [{"role": "user", "text": user_text}],
                    "response": json.dumps(response_obj, ensure_ascii=False)  # строка, а не массив
                })

        # 2. Генерация данных по конкретным врачам
        for doc in doctors:
            doctor_name = doc['name']
            doc_id = str(doc['id'])

            user_requests = self._generate_doctor_requests(doctor_name)

            for user_text in user_requests:
                response_obj = {
                    "text": f"Да, {doctor_name} принимает в нашей клинике.",
                    "method": "get_doctor",
                    "doctor_id": doc_id,
                    "title": doctor_name
                }
                training_data.append({
                    "request": [{"role": "user", "text": user_text}],
                    "response": json.dumps(response_obj, ensure_ascii=False)  # строка, а не массив
                })

        # Добавляем примеры с ошибками (не существующие специалисты/врачи)
        error_queries = [
            "Хочу записаться к косметологу",
            "Нужен остеопат",
            "Ищу фитотерапевта",
            "Есть ли мануальный терапевт?",
            "Могу ли я попасть к гомеопату?"
        ]

        for query in error_queries:
            response_obj = {
                "text": "К сожалению, данный специалист не представлен в нашей клинике",
                "method": "not_found",
                "id": None,
                "title": query.split()[-1]
            }
            training_data.append({
                "request": [{"role": "user", "text": query}],
                "response": json.dumps(response_obj, ensure_ascii=False)  # строка, а не массив
            })

        # Перемешиваем данные для лучшего обучения
        random.shuffle(training_data)

        # Сохраняем в формате JSON Lines
        with open('training_data.jsonl', 'w', encoding='utf-8') as f:
            for record in training_data:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"✅ Сохранено {len(training_data)} записей для обучения в training_data.jsonl")

async def main():
    gen = GenerationJsonDataSet()
    await gen.get_categories_and_doctors()

if __name__ == "__main__":
    asyncio.run(main())
