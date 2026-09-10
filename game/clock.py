from dataclasses import dataclass
import random


@dataclass(frozen=True)
class GameDate:
    year: int = 1
    month: int = 1
    day: int = 1
    hour: int = 6

    def advance(self, hours: int) -> "GameDate":
        total = ((self.year - 1) * 360 + (self.month - 1) * 30 + (self.day - 1)) * 24 + self.hour + max(0, hours)
        days, hour = divmod(total, 24)
        year, day_of_year = divmod(days, 360)
        month, day = divmod(day_of_year, 30)
        return GameDate(year + 1, month + 1, day + 1, hour)

    def text(self) -> str:
        return f"Year {self.year}, Month {self.month}, Day {self.day}, {self.hour:02d}:00"

    @property
    def season(self) -> str:
        return ("Spring", "Summer", "Autumn", "Winter")[(self.month - 1) // 3]

    @property
    def day_of_year(self) -> int:
        return (self.month - 1) * 30 + self.day

    def weather(self, seed: int) -> str:
        options = {"Spring": ("Clear", "Cloudy", "Rain", "Fog"), "Summer": ("Clear", "Heat", "Storm", "Cloudy"), "Autumn": ("Clear", "Cloudy", "Rain", "Wind"), "Winter": ("Cold", "Snow", "Cloudy", "Clear")}
        return random.Random(seed + self.year * 1000 + self.day_of_year).choice(options[self.season])