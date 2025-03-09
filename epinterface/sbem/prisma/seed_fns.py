"""Seed functions for the prisma database to get dummy data into the db."""

from prisma import Prisma
from prisma.models import Day
from prisma.types import DayCreateInput, WeekCreateInput

typologies = ["office", "residential"]
ages = ["new", "old"]
locations = ["cold", "warm"]
dhw_systems = ["bad", "medium", "good"]


def create_schedule(db: Prisma, name_prefix: str):
    """Create a schedule for the given name prefix."""
    with db.tx() as tx:
        day_create_input: DayCreateInput = {
            "Name": f"{name_prefix} Monday",
            "Type": "Fraction",
            "Hour_00": 0,
            "Hour_01": 0,
            "Hour_02": 0,
            "Hour_03": 0,
            "Hour_04": 0,
            "Hour_05": 0,
            "Hour_06": 0,
            "Hour_07": 0,
            "Hour_08": 0,
            "Hour_09": 0,
            "Hour_10": 0,
            "Hour_11": 0,
            "Hour_12": 0,
            "Hour_13": 0,
            "Hour_14": 0,
            "Hour_15": 0,
            "Hour_16": 0,
            "Hour_17": 0,
            "Hour_18": 0,
            "Hour_19": 0,
            "Hour_20": 0,
            "Hour_21": 0,
            "Hour_22": 0,
            "Hour_23": 0,
        }
        day_creations_for_whole_week = {
            "Monday": day_create_input,
            "Tuesday": day_create_input,
            "Wednesday": day_create_input,
            "Thursday": day_create_input,
            "Friday": day_create_input,
            "Saturday": day_create_input,
            "Sunday": day_create_input,
        }
        created_days: dict[str, Day] = {}
        for day_name, day_create_input in day_creations_for_whole_week.items():
            day_create_input["Name"] = f"{name_prefix}_{day_name}"
            day = tx.day.create(data=day_create_input)
            created_days[day_name] = day

        week_a_create_input: WeekCreateInput = {
            "Name": f"{name_prefix}_RegularWeek",
            "Monday": {"connect": {"id": created_days["Monday"].id}},
            "Tuesday": {"connect": {"id": created_days["Tuesday"].id}},
            "Wednesday": {"connect": {"id": created_days["Wednesday"].id}},
            "Thursday": {"connect": {"id": created_days["Thursday"].id}},
            "Friday": {"connect": {"id": created_days["Friday"].id}},
            "Saturday": {"connect": {"id": created_days["Saturday"].id}},
            "Sunday": {"connect": {"id": created_days["Sunday"].id}},
        }
        week_a = tx.week.create(data=week_a_create_input)
        week_b_create_input: WeekCreateInput = {
            "Name": f"{name_prefix}_All_Monday",
            "Monday": {"connect": {"id": created_days["Monday"].id}},
            "Tuesday": {"connect": {"id": created_days["Monday"].id}},
            "Wednesday": {"connect": {"id": created_days["Monday"].id}},
            "Thursday": {"connect": {"id": created_days["Monday"].id}},
            "Friday": {"connect": {"id": created_days["Monday"].id}},
            "Saturday": {"connect": {"id": created_days["Monday"].id}},
            "Sunday": {"connect": {"id": created_days["Monday"].id}},
        }
        week_b = tx.week.create(data=week_b_create_input)
        tx.year.create(
            data={
                "Name": f"{name_prefix}_Year",
                "Type": "Fraction",
                "Weeks": {
                    "create": [
                        {
                            "Week": {"connect": {"id": week_a.id}},  # pyright: ignore [reportArgumentType]
                            "StartDay": 1,
                            "StartMonth": 1,
                            "EndDay": 30,
                            "EndMonth": 6,
                        },
                        {
                            "Week": {"connect": {"id": week_b.id}},
                            "StartDay": 1,
                            "StartMonth": 7,
                            "EndDay": 31,
                            "EndMonth": 12,
                        },
                    ]
                },
            }
        )


def create_schedules(db: Prisma):
    """Create schedules for the given database for the typical uses."""
    create_schedule(db, "Lights")
    create_schedule(db, "Equipment")
    create_schedule(db, "Occupancy")
    create_schedule(db, "WaterUse")
    create_schedule(db, "Heating")
    create_schedule(db, "Cooling")
    create_schedule(db, "Ventilation")


def create_space_use_children(db: Prisma):
    """Create space use children objects for the given database for the typical uses."""
    last_equipment_name = ""
    for typology in typologies:
        epd = 10 if typology == "office" else 20
        for age in ages:
            epd = epd * 0.83 if age == "new" else epd
            last_equipment_name = f"{age}_{typology}"
            db.equipment.create(
                data={
                    "Name": last_equipment_name,
                    "Schedule": {"connect": {"Name": "Equipment_Year"}},
                    "PowerDensity": epd,
                    "IsOn": True,
                }
            )

    last_lighting_name = ""
    for typology in typologies:
        lpd = 10 if typology == "office" else 20
        for age in ages:
            lpd = lpd * 0.8 if age == "old" else lpd
            for loc in locations:
                lpd = lpd * 1.23 if loc == "cold" else lpd
                last_lighting_name = f"{age}_{loc}_{typology}"
                db.lighting.create(
                    data={
                        "Name": last_lighting_name,
                        "Schedule": {"connect": {"Name": "Lights_Year"}},
                        "PowerDensity": lpd,
                        "DimmingType": "Stepped" if typology == "office" else "Off",
                        "IsOn": True,
                    }
                )

    last_thermostat_name = ""
    for typology in typologies:
        for loc in locations:
            last_thermostat_name = f"{loc}_{typology}"
            db.thermostat.create(
                data={
                    "Name": last_thermostat_name,
                    "HeatingSchedule": {"connect": {"Name": "Heating_Year"}},
                    "CoolingSchedule": {"connect": {"Name": "Cooling_Year"}},
                    "IsOn": True,
                    "HeatingSetpoint": 20 if loc == "cold" else 23,
                    "CoolingSetpoint": 24 if typology == "office" else 23,
                }
            )

    last_occupancy_name = ""
    for typology in typologies:
        last_occupancy_name = typology
        db.occupancy.create(
            data={
                "Name": last_occupancy_name,
                "Schedule": {"connect": {"Name": "Occupancy_Year"}},
                "PeopleDensity": 0.05 if typology == "office" else 0.01,
                "IsOn": True,
                "MetabolicRate": 1.2,
            }
        )

    last_water_use_name = ""
    for typology in typologies:
        last_water_use_name = typology
        db.wateruse.create(
            data={
                "Name": last_water_use_name,
                "Schedule": {"connect": {"Name": "WaterUse_Year"}},
                "FlowRatePerPerson": 0.05 if typology == "office" else 0.01,
            }
        )

    space_use_name = "default"
    db.spaceuse.create(
        data={
            "Name": space_use_name,
            "Equipment": {"connect": {"Name": last_equipment_name}},
            "Lighting": {"connect": {"Name": last_lighting_name}},
            "Thermostat": {"connect": {"Name": last_thermostat_name}},
            "Occupancy": {"connect": {"Name": last_occupancy_name}},
            "WaterUse": {"connect": {"Name": last_water_use_name}},
        }
    )
    return space_use_name


def create_hvac_systems(db: Prisma):
    """Create HVAC systems for the given database for the typical uses."""
    last_heating_name = ""
    last_cooling_name = ""
    last_con_systems_name = ""
    last_ventilation_name = ""
    last_hvac_name = ""
    for typology in typologies:
        for location in locations:
            last_heating_name = f"Heating_{location}_{typology}"
            last_cooling_name = f"Cooling_{location}_{typology}"
            last_con_systems_name = f"{location}_{typology}"
            last_ventilation_name = f"{location}_{typology}"
            last_hvac_name = f"{location}_{typology}"
            db.thermalsystem.create(
                data={
                    "Name": last_heating_name,
                    "ConditioningType": "Heating",
                    "Fuel": "Electricity" if typology == "office" else "NaturalGas",
                    "SystemCOP": 3.5
                    if location == "cold" and typology == "office"
                    else 0.95,
                    "DistributionCOP": 0.9 if typology == "office" else 0.8,
                }
            )
            db.thermalsystem.create(
                data={
                    "Name": last_cooling_name,
                    "ConditioningType": "Cooling",
                    "Fuel": "Electricity",
                    "SystemCOP": 3.5 if location == "cold" else 4.5,
                    "DistributionCOP": 0.9 if typology == "office" else 0.8,
                }
            )
            db.conditioningsystems.create(
                data={
                    "Name": last_con_systems_name,
                    "Heating": {"connect": {"Name": last_heating_name}},
                    "Cooling": {"connect": {"Name": last_cooling_name}},
                }
            )
            db.ventilation.create(
                data={
                    "Name": last_ventilation_name,
                    "Schedule": {"connect": {"Name": "Ventilation_Year"}},
                    "Rate": 0.5 if location == "cold" else 0.1,
                    "MinFreshAir": 0.4 if typology == "office" else 0.1,
                    "Type": "Natural",
                    "TechType": "HRV",
                }
            )
            db.hvac.create(
                data={
                    "Name": last_hvac_name,
                    "ConditioningSystems": {"connect": {"Name": last_con_systems_name}},
                    "Ventilation": {"connect": {"Name": last_ventilation_name}},
                }
            )
    return last_hvac_name


def create_dhw_systems(db: Prisma):
    """Create DHW systems for the given database for the typical uses."""
    last_dhw_name = ""
    for dhw_system in dhw_systems:
        last_dhw_name = dhw_system
        db.dhw.create(
            data={
                "Name": last_dhw_name,
                "SystemCOP": 3.5 if dhw_system == "good" else 0.95,
                "DistributionCOP": 0.9 if dhw_system == "good" else 0.8,
                "WaterTemperatureInlet": 10,
                "WaterSupplyTemperature": 55,
                "IsOn": True,
                "FuelType": "Electricity" if dhw_system == "medium" else "NaturalGas",
            }
        )
    return last_dhw_name


def create_operations(db: Prisma, space_use_name: str, hvac_name: str, dhw_name: str):
    """Create operations for the given database for the typical uses."""
    db.operations.create(
        data={
            "Name": "default_ops",
            "SpaceUse": {"connect": {"Name": space_use_name}},
            "HVAC": {"connect": {"Name": hvac_name}},
            "DHW": {"connect": {"Name": dhw_name}},
        }
    )
    return "default_ops"
