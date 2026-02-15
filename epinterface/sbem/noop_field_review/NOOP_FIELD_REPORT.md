# SBEM Component No-Op Field Review Report

**Date:** 2025-02-15
**Scope:** `epinterface/sbem/` component fields affecting energy model construction (IDF generation, simulation, post-processing)

---

## Executive Summary

This report identifies component fields that are **no-ops** for energy model construction: they are defined and may be stored/validated, but are never referenced in any computation that affects the resulting IDF or simulation outputs.

**Total no-op fields identified:** 25
**Unused assembly:** 1 (ExternalFloorAssembly)

---

## Field Classification Table

| Component                              | Field                                         | Classification      | Notes                                                                                   |
| -------------------------------------- | --------------------------------------------- | ------------------- | --------------------------------------------------------------------------------------- |
| **GlazingConstructionSimpleComponent** | SHGF                                          | Used                | Passed to SimpleGlazingMaterial                                                         |
|                                        | UValue                                        | Used                | Passed to SimpleGlazingMaterial                                                         |
|                                        | TVis                                          | Used                | Passed to SimpleGlazingMaterial                                                         |
|                                        | **Type**                                      | **No-op**           | WindowType (Single/Double/Triple) not used in add_to_idf                                |
| **InfiltrationComponent**              | IsOn                                          | Used                | Guards add_infiltration_to_idf_zone                                                     |
|                                        | **ConstantCoefficient**                       | **No-op**           | Commented out in ZoneInfiltrationDesignFlowRate                                         |
|                                        | **TemperatureCoefficient**                    | **No-op**           | Commented out                                                                           |
|                                        | **WindVelocityCoefficient**                   | **No-op**           | Commented out                                                                           |
|                                        | **WindVelocitySquaredCoefficient**            | **No-op**           | Commented out                                                                           |
|                                        | **AFNAirMassFlowCoefficientCrack**            | **No-op**           | Commented out                                                                           |
|                                        | AirChangesPerHour                             | Used                | Passed to ZoneInfiltrationDesignFlowRate                                                |
|                                        | FlowPerExteriorSurfaceArea                    | Used                | Passed to ZoneInfiltrationDesignFlowRate                                                |
|                                        | CalculationMethod                             | Used                | Passed to ZoneInfiltrationDesignFlowRate                                                |
| **ConstructionAssemblyComponent**      | Layers                                        | Used                | add_to_idf, ep_material                                                                 |
|                                        | **VegetationLayer**                           | **No-op**           | Not referenced in add_to_idf or surface assignment                                      |
|                                        | **Type**                                      | **No-op**           | ConstructionComponentSurfaceType; assignment uses EnvelopeAssemblyComponent field names |
| **EnvelopeAssemblyComponent**          | FlatRoofAssembly                              | Used                | handle_envelope                                                                         |
|                                        | FacadeAssembly                                | Used                | handle_envelope                                                                         |
|                                        | FloorCeilingAssembly                          | Used                | handle_envelope                                                                         |
|                                        | AtticRoofAssembly                             | Used                | handle_envelope                                                                         |
|                                        | AtticFloorAssembly                            | Used                | handle_envelope                                                                         |
|                                        | PartitionAssembly                             | Used                | handle_envelope                                                                         |
|                                        | **ExternalFloorAssembly**                     | **Unused assembly** | No SurfaceHandler; never assigned to surfaces                                           |
|                                        | GroundSlabAssembly                            | Used                | handle_envelope                                                                         |
|                                        | GroundWallAssembly                            | Used                | handle_envelope                                                                         |
|                                        | BasementCeilingAssembly                       | Used                | handle_envelope                                                                         |
|                                        | InternalMassAssembly                          | Used                | handle_envelope                                                                         |
|                                        | InternalMassExposedAreaPerArea                | Used                | handle_envelope                                                                         |
| **ConstructionMaterialComponent**      | Conductivity                                  | Used                | ep_material → Material                                                                  |
|                                        | Density                                       | Used                | ep_material                                                                             |
|                                        | SpecificHeat                                  | Used                | ep_material                                                                             |
|                                        | ThermalAbsorptance                            | Used                | ep_material                                                                             |
|                                        | SolarAbsorptance                              | Used                | ep_material                                                                             |
|                                        | VisibleAbsorptance                            | Used                | ep_material                                                                             |
|                                        | Roughness                                     | Used                | ep_material                                                                             |
|                                        | **TemperatureCoefficientThermalConductivity** | **No-op**           | Not passed to Material; EP MATERIAL does not support in interface                       |
|                                        | **Type**                                      | **No-op**           | ConstructionMaterialType not used in ep_material                                        |
|                                        | **Cost**                                      | **No-op**           | LCA/costing metadata                                                                    |
|                                        | **RateUnit**                                  | **No-op**           | LCA/costing metadata                                                                    |
|                                        | **Life**                                      | **No-op**           | LCA/costing metadata                                                                    |
|                                        | **EmbodiedCarbon**                            | **No-op**           | LCA/costing metadata                                                                    |
|                                        | **Category**                                  | **No-op**           | MetadataMixin; not in construction path                                                 |
|                                        | **Comment**                                   | **No-op**           | MetadataMixin                                                                           |
|                                        | **DataSource**                                | **No-op**           | MetadataMixin                                                                           |
|                                        | **Version**                                   | **No-op**           | MetadataMixin                                                                           |
| **ThermalSystemComponent**             | ConditioningType                              | Used                | Validation, effective_system_cop context                                                |
|                                        | Fuel                                          | Used                | standard_results_postprocess                                                            |
|                                        | SystemCOP                                     | Used                | effective_system_cop                                                                    |
|                                        | DistributionCOP                               | Used                | effective_system_cop                                                                    |
|                                        | **HeatingSystemType**                         | **No-op**           | Property raises NotImplementedError; never called                                       |
|                                        | **CoolingSystemType**                         | **No-op**           | Property raises NotImplementedError; never called                                       |
|                                        | **DistributionType**                          | **No-op**           | Property raises NotImplementedError; never called                                       |
| **ThermostatComponent**                | **IsOn**                                      | **No-op**           | Never checked; thermostat always added regardless                                       |
|                                        | HeatingSetpoint                               | Used                | add_thermostat_to_idf_zone                                                              |
|                                        | HeatingSchedule                               | Used                | add_thermostat_to_idf_zone                                                              |
|                                        | CoolingSetpoint                               | Used                | add_thermostat_to_idf_zone                                                              |
|                                        | CoolingSchedule                               | Used                | add_thermostat_to_idf_zone                                                              |

_All other component fields (ZoneComponent, ZoneOperationsComponent, space use, ventilation, DHW, schedules, etc.) are **Used** in the construction path._

---

## Detailed Findings

### 1. InfiltrationComponent – AFN/Crack Coefficients

**Location:** `epinterface/sbem/components/envelope.py` lines 77–97, 148–152

**Fields:** `ConstantCoefficient`, `TemperatureCoefficient`, `WindVelocityCoefficient`, `WindVelocitySquaredCoefficient`, `AFNAirMassFlowCoefficientCrack`

**Evidence:** In `add_infiltration_to_idf_zone`, these are commented out when constructing `ZoneInfiltrationDesignFlowRate`. Only `CalculationMethod`, `FlowPerExteriorSurfaceArea`, and `AirChangesPerHour` are passed.

**Recommendation:** (b) Deprecate with TODO – document that AFN/crack model is not implemented; or (a) Remove if no near-term plan to implement.

---

### 2. GlazingConstructionSimpleComponent.Type

**Location:** `epinterface/sbem/components/envelope.py` line 41

**Evidence:** `add_to_idf` uses only `Name`, `UValue` (→ UFactor), `SHGF` (→ Solar_Heat_Gain_Coefficient), `TVis` (→ Visible_Transmittance). `Type` (Single/Double/Triple) is never used.

**Recommendation:** (c) Implement – use Type to select/configure glazing layers; or (a) Remove if redundant with U-value/SHGF.

---

### 3. ConstructionAssemblyComponent.VegetationLayer

**Location:** `epinterface/sbem/components/envelope.py` lines 215–217

**Evidence:** Not referenced in `add_to_idf` or in `handle_envelope`. Only `Layers` and `Name` affect the construction.

**Recommendation:** (c) Implement – add vegetation layer support to IDF; or (b) Deprecate with TODO.

---

### 4. ConstructionAssemblyComponent.Type

**Location:** `epinterface/sbem/components/envelope.py` lines 218–220

**Evidence:** Surface assignment in `handle_envelope` is driven by `EnvelopeAssemblyComponent` field names (e.g. `FacadeAssembly`, `FlatRoofAssembly`), not by `ConstructionAssemblyComponent.Type`.

**Recommendation:** (d) Document as intentional – Type may be for validation/UI; or (a) Remove if redundant.

---

### 5. EnvelopeAssemblyComponent.ExternalFloorAssembly

**Location:** `epinterface/sbem/components/envelope.py` lines 312–314

**Evidence:** `SurfaceHandlers` in `builder.py` has no handler for external floor. `handle_envelope` never assigns `ExternalFloorAssembly` to any surfaces. Shoebox geometry may not create external-floor surfaces.

**Recommendation:** (c) Implement – add SurfaceHandler and wiring for external floor; or (b) Deprecate until geometry supports it.

---

### 6. ConstructionMaterialComponent – Material Properties

**Fields:** `TemperatureCoefficientThermalConductivity`, `Type` (ConstructionMaterialType)

**Location:** `epinterface/sbem/components/materials.py`; `ep_material` in `envelope.py` lines 181–192

**Evidence:** `ConstructionLayerComponent.ep_material` passes only: `Thickness`, `Conductivity`, `Density`, `SpecificHeat`, `ThermalAbsorptance`, `SolarAbsorptance`, `Roughness`, `VisibleAbsorptance`. `TemperatureCoefficientThermalConductivity` and `Type` are not passed to `Material`.

**Recommendation:** (c) Implement – add support if EP/archetypal supports these; or (a) Remove if not needed.

---

### 7. EnvironmentalMixin (ConstructionMaterialComponent)

**Fields:** `Cost`, `RateUnit`, `Life`, `EmbodiedCarbon`

**Location:** `epinterface/sbem/components/materials.py` lines 11–28

**Evidence:** LCA/costing metadata. Not used in `ep_material` or IDF construction.

**Recommendation:** (d) Document as intentional – reserved for future LCA/costing; keep for schema compatibility.

---

### 8. MetadataMixin

**Fields:** `Category`, `Comment`, `DataSource`, `Version`

**Location:** `epinterface/sbem/common.py` lines 34–37

**Evidence:** No references in builder, operations, envelope, or analysis construction path.

**Recommendation:** (d) Document as intentional – metadata for library management, not energy simulation.

---

### 9. ThermalSystemComponent – Unimplemented Properties

**Fields:** `HeatingSystemType`, `CoolingSystemType`, `DistributionType` (as properties)

**Location:** `epinterface/sbem/components/systems.py` lines 53–97

**Evidence:** These properties raise `NotImplementedError`. Only `effective_system_cop`, `Fuel`, and `ConditioningType` are used in the construction/postprocess path.

**Recommendation:** (c) Implement – derive from COP and wire into HVAC templates; or (b) Deprecate/remove if not needed.

---

### 10. ThermostatComponent.IsOn

**Location:** `epinterface/sbem/components/space_use.py` line 216

**Evidence:** `ZoneOperationsComponent.add_conditioning_to_idf_zone` always calls `add_thermostat_to_idf_zone` without checking `self.SpaceUse.Thermostat.IsOn`. The thermostat is always added to the zone.

**Recommendation:** (c) Implement – skip thermostat/HVAC when `IsOn` is False; or (b) Deprecate if thermostat is always required for conditioning.

---

### 11. ZoneHVACComponent.add_conditioning_to_idf_zone

**Location:** `epinterface/sbem/components/systems.py` lines 197–215

**Evidence:** Stub that returns `idf` unchanged. Actual logic is in `ZoneOperationsComponent.add_conditioning_to_idf_zone`. This method is never called.

**Recommendation:** (b) Deprecate with TODO – remove or delegate to Operations.

---

## Verification Script

Run the verification script from repo root:

```bash
python -m epinterface.sbem.noop_field_review.verify_field_usage
```

Note: The script reports all references (including definitions, Prisma, interface). Manual trace-through of the construction path is required to confirm no-op status.

---

## Cross-Check: Prisma and interface.py

### Prisma Schema

- **EnvironmentalData:** `Cost`, `RateUnit`, `Life`, `EmbodiedCarbon` – stored for Glazings and ConstructionMaterials.
- **Infiltration:** `ConstantCoefficient`, `TemperatureCoefficient`, `WindVelocityCoefficient`, `WindVelocitySquaredCoefficient`, `AFNAirMassFlowCoefficientCrack` – all present in schema.
- **ConstructionMaterial:** `TemperatureCoefficientThermalConductivity`, `Type` – stored.
- **GlazingConstructionSimple:** `Type` – stored.
- **ConstructionAssembly:** `VegetationLayer`, `Type` – stored.
- **EnvelopeAssembly:** `ExternalFloorAssembly` – stored and connected in interface.

### interface.py

- **Materials (lines 436–450):** Reads `TemperatureCoefficientThermalConductivity`, `Type` from Excel/DB and passes to `constructionmaterial.create`. These are not used in `ep_material`.
- **Glazing (lines 456–466):** Reads `Type` from `Window_choices` and passes to `glazingconstructionsimple.create`. Not used in `add_to_idf`.
- **Infiltration (lines 552–567):** Hardcodes `ConstantCoefficient`, `TemperatureCoefficient`, etc. to 0.0 when creating infiltration. Confirms these are not sourced from data and are no-ops in IDF.
- **Envelope assembly (line 515):** `ExternalFloorAssembly` is connected from `row["ExternalFloor"]` – data flows in but is never used in `handle_envelope`.

### Conclusion

- No-op fields are persisted and loaded; they do not affect IDF construction.
- Before removing any field: update Prisma schema, add migration, update `seed_fns.py`, `interface.py`, and Excel templates.
