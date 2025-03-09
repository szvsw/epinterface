-- CreateTable
CREATE TABLE "Metadata" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "description" TEXT,
    "source" TEXT,
    "reference" TEXT,
    "comments" TEXT,
    "tags" TEXT
);

-- CreateTable
CREATE TABLE "EnvironmentalData" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Cost" REAL,
    "RateUnit" TEXT,
    "Life" REAL,
    "EmbodiedCarbon" REAL
);

-- CreateTable
CREATE TABLE "Occupancy" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "PeopleDensity" REAL NOT NULL,
    "IsOn" BOOLEAN NOT NULL,
    "MetabolicRate" REAL NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "Occupancy_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Occupancy_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Lighting" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "PowerDensity" REAL NOT NULL,
    "DimmingType" TEXT NOT NULL,
    "IsOn" BOOLEAN NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "Lighting_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Lighting_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Equipment" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "PowerDensity" REAL NOT NULL,
    "IsOn" BOOLEAN NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "Equipment_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Equipment_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Thermostat" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "IsOn" BOOLEAN NOT NULL,
    "HeatingSetpoint" REAL NOT NULL,
    "CoolingSetpoint" REAL NOT NULL,
    "MetadataId" TEXT,
    "HeatingScheduleId" TEXT NOT NULL,
    "CoolingScheduleId" TEXT NOT NULL,
    CONSTRAINT "Thermostat_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Thermostat_HeatingScheduleId_fkey" FOREIGN KEY ("HeatingScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Thermostat_CoolingScheduleId_fkey" FOREIGN KEY ("CoolingScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "WaterUse" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "FlowRatePerPerson" REAL NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "WaterUse_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "WaterUse_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "SpaceUse" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "OccupancyId" TEXT NOT NULL,
    "LightingId" TEXT NOT NULL,
    "EquipmentId" TEXT NOT NULL,
    "ThermostatId" TEXT NOT NULL,
    "WaterUseId" TEXT NOT NULL,
    CONSTRAINT "SpaceUse_OccupancyId_fkey" FOREIGN KEY ("OccupancyId") REFERENCES "Occupancy" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "SpaceUse_LightingId_fkey" FOREIGN KEY ("LightingId") REFERENCES "Lighting" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "SpaceUse_EquipmentId_fkey" FOREIGN KEY ("EquipmentId") REFERENCES "Equipment" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "SpaceUse_ThermostatId_fkey" FOREIGN KEY ("ThermostatId") REFERENCES "Thermostat" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "SpaceUse_WaterUseId_fkey" FOREIGN KEY ("WaterUseId") REFERENCES "WaterUse" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ThermalSystem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "ConditioningType" TEXT NOT NULL,
    "Fuel" TEXT NOT NULL,
    "SystemCOP" REAL NOT NULL,
    "DistributionCOP" REAL NOT NULL,
    "MetadataId" TEXT,
    CONSTRAINT "ThermalSystem_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConditioningSystems" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "HeatingId" TEXT,
    "CoolingId" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "ConditioningSystems_HeatingId_fkey" FOREIGN KEY ("HeatingId") REFERENCES "ThermalSystem" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "ConditioningSystems_CoolingId_fkey" FOREIGN KEY ("CoolingId") REFERENCES "ThermalSystem" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "ConditioningSystems_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Ventilation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Rate" REAL NOT NULL,
    "MinFreshAir" REAL NOT NULL,
    "Type" TEXT NOT NULL,
    "TechType" TEXT NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "Ventilation_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Ventilation_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "HVAC" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "ConditioningSystemsId" TEXT NOT NULL,
    "VentilationId" TEXT NOT NULL,
    "MetadataId" TEXT,
    CONSTRAINT "HVAC_ConditioningSystemsId_fkey" FOREIGN KEY ("ConditioningSystemsId") REFERENCES "ConditioningSystems" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "HVAC_VentilationId_fkey" FOREIGN KEY ("VentilationId") REFERENCES "Ventilation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "HVAC_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DHW" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "SystemCOP" REAL NOT NULL,
    "WaterTemperatureInlet" REAL NOT NULL,
    "DistributionCOP" REAL NOT NULL,
    "WaterSupplyTemperature" REAL NOT NULL,
    "IsOn" BOOLEAN NOT NULL,
    "FuelType" TEXT NOT NULL,
    "MetadataId" TEXT,
    CONSTRAINT "DHW_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Operations" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "SpaceUseId" TEXT NOT NULL,
    "HVACId" TEXT NOT NULL,
    "DHWId" TEXT NOT NULL,
    "MetadataId" TEXT,
    CONSTRAINT "Operations_SpaceUseId_fkey" FOREIGN KEY ("SpaceUseId") REFERENCES "SpaceUse" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Operations_HVACId_fkey" FOREIGN KEY ("HVACId") REFERENCES "HVAC" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Operations_DHWId_fkey" FOREIGN KEY ("DHWId") REFERENCES "DHW" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Operations_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConstructionMaterial" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Conductivity" REAL NOT NULL,
    "Density" REAL NOT NULL,
    "Roughness" TEXT NOT NULL,
    "SpecificHeat" REAL NOT NULL,
    "ThermalAbsorptance" REAL NOT NULL,
    "SolarAbsorptance" REAL NOT NULL,
    "TemperatureCoefficientThermalConductivity" REAL NOT NULL,
    "VisibleAbsorptance" REAL NOT NULL,
    "Type" TEXT NOT NULL,
    "MetadataId" TEXT,
    "EnvironmentalDataId" TEXT,
    CONSTRAINT "ConstructionMaterial_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "ConstructionMaterial_EnvironmentalDataId_fkey" FOREIGN KEY ("EnvironmentalDataId") REFERENCES "EnvironmentalData" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConstructionAssemblyLayer" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "LayerOrder" INTEGER NOT NULL,
    "Thickness" REAL NOT NULL,
    "ConstructionAssemblyId" TEXT NOT NULL,
    "ConstructionMaterialId" TEXT NOT NULL,
    CONSTRAINT "ConstructionAssemblyLayer_ConstructionAssemblyId_fkey" FOREIGN KEY ("ConstructionAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "ConstructionAssemblyLayer_ConstructionMaterialId_fkey" FOREIGN KEY ("ConstructionMaterialId") REFERENCES "ConstructionMaterial" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConstructionAssembly" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Type" TEXT NOT NULL,
    "VegetationLayer" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "ConstructionAssembly_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "EnvelopeAssembly" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "InternalMassExposedAreaPerArea" REAL,
    "GroundIsAdiabatic" BOOLEAN NOT NULL,
    "RoofIsAdiabatic" BOOLEAN NOT NULL,
    "FacadeIsAdiabatic" BOOLEAN NOT NULL,
    "SlabIsAdiabatic" BOOLEAN NOT NULL,
    "PartitionIsAdiabatic" BOOLEAN NOT NULL,
    "RoofAssemblyId" TEXT NOT NULL,
    "FacadeAssemblyId" TEXT NOT NULL,
    "SlabAssemblyId" TEXT NOT NULL,
    "PartitionAssemblyId" TEXT NOT NULL,
    "ExternalFloorAssemblyId" TEXT NOT NULL,
    "GroundSlabAssemblyId" TEXT NOT NULL,
    "GroundWallAssemblyId" TEXT NOT NULL,
    "InternalMassAssemblyId" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "EnvelopeAssembly_RoofAssemblyId_fkey" FOREIGN KEY ("RoofAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_FacadeAssemblyId_fkey" FOREIGN KEY ("FacadeAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_SlabAssemblyId_fkey" FOREIGN KEY ("SlabAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_PartitionAssemblyId_fkey" FOREIGN KEY ("PartitionAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_ExternalFloorAssemblyId_fkey" FOREIGN KEY ("ExternalFloorAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_GroundSlabAssemblyId_fkey" FOREIGN KEY ("GroundSlabAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_GroundWallAssemblyId_fkey" FOREIGN KEY ("GroundWallAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_InternalMassAssemblyId_fkey" FOREIGN KEY ("InternalMassAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "GlazingConstructionSimple" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "SHGF" REAL NOT NULL,
    "UValue" REAL NOT NULL,
    "TVis" REAL NOT NULL,
    "Type" TEXT NOT NULL,
    "MetadataId" TEXT,
    "EnvironmentalDataId" TEXT,
    CONSTRAINT "GlazingConstructionSimple_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "GlazingConstructionSimple_EnvironmentalDataId_fkey" FOREIGN KEY ("EnvironmentalDataId") REFERENCES "EnvironmentalData" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Infiltration" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "IsOn" BOOLEAN NOT NULL,
    "ConstantCoefficient" REAL NOT NULL,
    "TemperatureCoefficient" REAL NOT NULL,
    "WindVelocityCoefficient" REAL NOT NULL,
    "WindVelocitySquaredCoefficient" REAL NOT NULL,
    "AFNAirMassFlowCoefficientCrack" REAL NOT NULL,
    "AirChangesPerHour" REAL NOT NULL,
    "FlowPerExteriorSurfaceArea" REAL NOT NULL,
    "CalculationMethod" TEXT NOT NULL,
    "MetadataId" TEXT,
    CONSTRAINT "Infiltration_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Envelope" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "AssembliesId" TEXT NOT NULL,
    "InfiltrationId" TEXT NOT NULL,
    "WindowId" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "Envelope_AssembliesId_fkey" FOREIGN KEY ("AssembliesId") REFERENCES "EnvelopeAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_InfiltrationId_fkey" FOREIGN KEY ("InfiltrationId") REFERENCES "Infiltration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_WindowId_fkey" FOREIGN KEY ("WindowId") REFERENCES "GlazingConstructionSimple" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Envelope_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Day" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Type" TEXT NOT NULL,
    "Hour_00" REAL NOT NULL,
    "Hour_01" REAL NOT NULL,
    "Hour_02" REAL NOT NULL,
    "Hour_03" REAL NOT NULL,
    "Hour_04" REAL NOT NULL,
    "Hour_05" REAL NOT NULL,
    "Hour_06" REAL NOT NULL,
    "Hour_07" REAL NOT NULL,
    "Hour_08" REAL NOT NULL,
    "Hour_09" REAL NOT NULL,
    "Hour_10" REAL NOT NULL,
    "Hour_11" REAL NOT NULL,
    "Hour_12" REAL NOT NULL,
    "Hour_13" REAL NOT NULL,
    "Hour_14" REAL NOT NULL,
    "Hour_15" REAL NOT NULL,
    "Hour_16" REAL NOT NULL,
    "Hour_17" REAL NOT NULL,
    "Hour_18" REAL NOT NULL,
    "Hour_19" REAL NOT NULL,
    "Hour_20" REAL NOT NULL,
    "Hour_21" REAL NOT NULL,
    "Hour_22" REAL NOT NULL,
    "Hour_23" REAL NOT NULL
);

-- CreateTable
CREATE TABLE "Week" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "MondayId" TEXT NOT NULL,
    "TuesdayId" TEXT NOT NULL,
    "WednesdayId" TEXT NOT NULL,
    "ThursdayId" TEXT NOT NULL,
    "FridayId" TEXT NOT NULL,
    "SaturdayId" TEXT NOT NULL,
    "SundayId" TEXT NOT NULL,
    CONSTRAINT "Week_MondayId_fkey" FOREIGN KEY ("MondayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Week_TuesdayId_fkey" FOREIGN KEY ("TuesdayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Week_WednesdayId_fkey" FOREIGN KEY ("WednesdayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Week_ThursdayId_fkey" FOREIGN KEY ("ThursdayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Week_FridayId_fkey" FOREIGN KEY ("FridayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Week_SaturdayId_fkey" FOREIGN KEY ("SaturdayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Week_SundayId_fkey" FOREIGN KEY ("SundayId") REFERENCES "Day" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RepeatedWeek" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "StartDay" INTEGER NOT NULL,
    "StartMonth" INTEGER NOT NULL,
    "EndDay" INTEGER NOT NULL,
    "EndMonth" INTEGER NOT NULL,
    "WeekId" TEXT NOT NULL,
    "YearId" TEXT NOT NULL,
    CONSTRAINT "RepeatedWeek_WeekId_fkey" FOREIGN KEY ("WeekId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "RepeatedWeek_YearId_fkey" FOREIGN KEY ("YearId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Year" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Type" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "Zone" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "MetadataId" TEXT,
    "EnvelopeId" TEXT NOT NULL,
    "OperationsId" TEXT NOT NULL,
    CONSTRAINT "Zone_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Zone_EnvelopeId_fkey" FOREIGN KEY ("EnvelopeId") REFERENCES "Envelope" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Zone_OperationsId_fkey" FOREIGN KEY ("OperationsId") REFERENCES "Operations" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Occupancy_Name_key" ON "Occupancy"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Lighting_Name_key" ON "Lighting"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Equipment_Name_key" ON "Equipment"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Thermostat_Name_key" ON "Thermostat"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "WaterUse_Name_key" ON "WaterUse"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "SpaceUse_Name_key" ON "SpaceUse"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "ThermalSystem_Name_key" ON "ThermalSystem"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "ConditioningSystems_Name_key" ON "ConditioningSystems"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Ventilation_Name_key" ON "Ventilation"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "HVAC_Name_key" ON "HVAC"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "DHW_Name_key" ON "DHW"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Operations_Name_key" ON "Operations"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "ConstructionMaterial_Name_key" ON "ConstructionMaterial"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "ConstructionAssemblyLayer_ConstructionAssemblyId_LayerOrder_key" ON "ConstructionAssemblyLayer"("ConstructionAssemblyId", "LayerOrder");

-- CreateIndex
CREATE UNIQUE INDEX "ConstructionAssembly_Name_key" ON "ConstructionAssembly"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "EnvelopeAssembly_Name_key" ON "EnvelopeAssembly"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "GlazingConstructionSimple_Name_key" ON "GlazingConstructionSimple"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Infiltration_Name_key" ON "Infiltration"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Envelope_Name_key" ON "Envelope"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Day_Name_key" ON "Day"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Week_Name_key" ON "Week"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Year_Name_key" ON "Year"("Name");

-- CreateIndex
CREATE UNIQUE INDEX "Zone_Name_key" ON "Zone"("Name");
