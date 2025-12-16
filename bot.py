import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import random
from abc import ABC, abstractmethod

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResourceType(Enum):
    WHEAT = "пшеница"
    WOOD = "дерево"
    STONE = "камень"

class BuildingType(Enum):
    WHEAT_FARM = "ферма пшеницы"
    TREE_FARM = "ферма деревьев"
    MINE = "шахта"
    HOUSE = "дом"

class Building:
    def __init__(self, building_type: BuildingType, level: int = 1):
        self.type = building_type
        self.level = level
        self.last_production_time = datetime.now()
        
    def get_production_rate(self) -> Dict[ResourceType, float]:
        """Возвращает количество ресурсов в час для этого здания"""
        rates = {
            BuildingType.WHEAT_FARM: {ResourceType.WHEAT: 20 * self.level},
            BuildingType.TREE_FARM: {ResourceType.WOOD: 15 * self.level},
            BuildingType.MINE: {ResourceType.STONE: 10 * self.level},
            BuildingType.HOUSE: {}  # Дома не производят ресурсы
        }
        return rates.get(self.type, {})

class Town:
    def __init__(self, name: str):
        self.name = name
        self.resources = {
            ResourceType.WHEAT: 500,  # Начальные ресурсы
            ResourceType.WOOD: 300,
            ResourceType.STONE: 200
        }
        self.buildings: List[Building] = []
        self.population = 5  # Начальное население
        self.max_population = 5
        self.last_update = datetime.now()
        self.day = 1
        
        # Начальные постройки
        self.buildings.append(Building(BuildingType.WHEAT_FARM))
        self.buildings.append(Building(BuildingType.TREE_FARM))
        self.buildings.append(Building(BuildingType.HOUSE))
        
    def update(self):
        """Обновление состояния города (вызывается периодически)"""
        now = datetime.now()
        time_passed = now - self.last_update
        
        # Производство ресурсов
        for building in self.buildings:
            production = building.get_production_rate()
            for resource, rate in production.items():
                # Преобразуем скорость в ресурсы за прошедшее время
                hours_passed = time_passed.total_seconds() / 3600
                produced = rate * hours_passed
                self.resources[resource] += produced
        
        # Потребление пшеницы жителями
        wheat_needed = self.population * 10 * (time_passed.total_seconds() / 86400)  # 10 в день
        self.resources[ResourceType.WHEAT] -= wheat_needed
        
        # Проверка на голод
        if self.resources[ResourceType.WHEAT] < 0:
            starvation = int(abs(self.resources[ResourceType.WHEAT]) / 10)
            self.population = max(0, self.population - starvation)
            self.resources[ResourceType.WHEAT] = 0
        
        # Случайное прибытие новых жителей
        if random.random() < 0.1:  # 10% шанс каждое обновление
            new_residents = random.randint(0, 2)
            if self.population + new_residents <= self.max_population:
                self.population += new_residents
        
        self.last_update = now
        
    def build_house(self) -> Tuple[bool, str]:
        """Попытка построить новый дом"""
        required_resources = {
            ResourceType.STONE: 230,
            ResourceType.WOOD: 400,
            ResourceType.WHEAT: 100
        }
        
        # Проверка ресурсов
        for resource, amount in required_resources.items():
            if self.resources.get(resource, 0) < amount:
                return False, f"Недостаточно {resource.value}. Нужно: {amount}"
        
        # Списание ресурсов
        for resource, amount in required_resources.items():
            self.resources[resource] -= amount
        
        # Строительство дома
        new_house = Building(BuildingType.HOUSE)
        self.buildings.append(new_house)
        self.max_population += 5
        
        return True, "Дом успешно построен!"
    
    def build_building(self, building_type: BuildingType) -> Tuple[bool, str]:
        """Постройка производственного здания"""
        costs = {
            BuildingType.WHEAT_FARM: {
                ResourceType.WOOD: 100,
                ResourceType.STONE: 50
            },
            BuildingType.TREE_FARM: {
                ResourceType.WOOD: 50,
                ResourceType.STONE: 100
            },
            BuildingType.MINE: {
                ResourceType.WOOD: 150,
                ResourceType.STONE: 50
            }
        }
        
        if building_type not in costs:
            return False, "Неизвестный тип здания"
        
        cost = costs[building_type]
        for resource, amount in cost.items():
            if self.resources.get(resource, 0) < amount:
                return False, f"Недостаточно {resource.value}"
        
        for resource, amount in cost.items():
            self.resources[resource] -= amount
        
        new_building = Building(building_type)
        self.buildings.append(new_building)
        return True, f"{building_type.value} построена!"

class Game:
    def __init__(self):
        self.towns: Dict[int, Town] = {}  # chat_id -> Town
        self.user_states: Dict[int, str] = {}  # Текущее состояние пользователя
        
    def get_or_create_town(self, chat_id: int, town_name: str = "Мой Городок") -> Town:
        if chat_id not in self.towns:
            self.towns[chat_id] = Town(town_name)
        return self.towns[chat_id]
    
    def get_town_status(self, chat_id: int) -> str:
        town = self.get_or_create_town(chat_id)
        town.update()
        
        status = f"🏙️ *{town.name}*\n\n"
        status += f"📊 *День:* {town.day}\n"
        status += f"👥 *Население:* {town.population}/{town.max_population}\n\n"
        status += "📦 *Ресурсы:*\n"
        status += f"  🌾 Пшеница: {int(town.resources[ResourceType.WHEAT])}\n"
        status += f"  🪵 Дерево: {int(town.resources[ResourceType.WOOD])}\n"
        status += f"  ⛰️ Камень: {int(town.resources[ResourceType.STONE])}\n\n"
        status += "🏗️ *Постройки:*\n"
        
        building_counts = {}
        for building in town.buildings:
            building_counts[building.type] = building_counts.get(building.type, 0) + 1
        
        for btype, count in building_counts.items():
            status += f"  {btype.value}: {count}\n"
        
        return status
