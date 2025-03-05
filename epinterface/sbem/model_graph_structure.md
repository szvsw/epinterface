# Referencing vs Hierarchical ORM

### Current Behavior

(all schedules are passed by reference)

```
ZoneSpaceUse -> Occupancy (deep object)
ZoneSpaceUse -> Lighting (deep object)
ZoneSpaceUse -> Equipment (deep object)
ZoneSpaceUse -> Thermostat (deep object)
ZoneSpaceUse -> WaterUse (deep object)

ConditioningSystems -> ThermalSystem (deep object)
ZoneHVAC -> ConditioningSystems (deep object)
ZoneHVAC -> Ventilation (deep object)

ZoneOperations -> ZoneSpaceUse (deep object)
ZoneOperations -> ZoneHVAC (deep object)
ZoneOperations -> DHW (deep object)

ConstructionLayer -> ConstructionMaterial (referenced)
ConstructionAssembly -> ConstructionLayer (deep object)
EnvelopeAssembly -> ConstructionAssembly (deep object)
ZoneEnvelope -> EnvelopeAssembly (deep object)
ZoneEnvelope -> Infiltration (deep object)
ZoneEnvelope -> GlazingConstructionSimple (deep object)

Model -> ZoneOperations (deep object)
Model -> ZoneEnvelope (deep object)
```
