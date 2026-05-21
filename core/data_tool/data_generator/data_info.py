from dataclasses import dataclass


@dataclass
class WeightRange:
    min_weight: float = 50.0
    max_weight: float = 200.0
    unit: str = "kgs"


@dataclass
class HeightRange:
    min_height: float = 150.0
    max_height: float = 300.0
    unit: str = "cms"


@dataclass
class PhoneConfig:
    area_code_min: int = 100
    area_code_max: int = 999
    exchange_code_min: int = 100
    exchange_code_max: int = 999
    subscriber_min: int = 1000
    subscriber_max: int = 9999
    format_with_dashes: bool = False
