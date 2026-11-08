"""Pydantic model = the rules every row must follow.

If a row breaks a rule (e.g. humidity = 140), Pydantic raises an error and the
row is rejected (saved to processed/rejected_rows.csv with the reason).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AirWeatherRecord(BaseModel):
    time: datetime

    # Pollutants in ug/m3 (CO is also ug/m3 in Open-Meteo). PM values are required.
    pm2_5: float = Field(ge=0, le=1000)
    pm10: float = Field(ge=0, le=2000)
    nitrogen_dioxide: Optional[float] = Field(default=None, ge=0, le=1000)
    ozone: Optional[float] = Field(default=None, ge=0, le=1000)
    carbon_monoxide: Optional[float] = Field(default=None, ge=0, le=50000)
    sulphur_dioxide: Optional[float] = Field(default=None, ge=0, le=2000)

    # Weather, all required
    temperature_2m: float = Field(ge=-10, le=55)        # degrees C
    relative_humidity_2m: float = Field(ge=0, le=100)   # percent
    wind_speed_10m: float = Field(ge=0, le=150)         # km/h
    surface_pressure: float = Field(ge=850, le=1100)    # hPa
    precipitation: float = Field(ge=0, le=200)          # mm per hour
