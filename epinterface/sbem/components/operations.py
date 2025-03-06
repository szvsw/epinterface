"""Operations components for the SBEM library."""

from archetypal.idfclass import IDF

from epinterface.sbem.common import MetadataMixin, NamedObject
from epinterface.sbem.components.space_use import ZoneSpaceUseComponent
from epinterface.sbem.components.systems import DHWComponent, ZoneHVACComponent


class ZoneOperationsComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Zone use consolidation across space use, HVAC, DHW."""

    SpaceUse: ZoneSpaceUseComponent
    HVAC: ZoneHVACComponent
    DHW: DHWComponent

    def add_operations_to_idf_zone(
        self, idf: IDF, target_zone_name: str, zone_area: float
    ) -> IDF:
        """Add an entire operations component and its subchildren to an IDF zone.

        NB: the area is required because DHW needs it when computing flow rates.

        Args:
            idf (IDF): The IDF object to add the operations to.
            target_zone_name (str): The name of the zone to add the operations to.
            zone_area (float): The area of the zone.

        Returns:
            idf (IDF): The updated IDF object.
        """
        # TODO: remember to add schedules!
        self.SpaceUse.add_loads_to_idf_zone(idf, target_zone_name)
        self.HVAC.add_conditioning_to_idf_zone(idf, target_zone_name)
        total_people = self.SpaceUse.Occupancy.OccupancyDensity * zone_area
        self.DHW.add_water_to_idf_zone(idf, target_zone_name, total_ppl=total_people)
        return idf
