"""Operations components for the SBEM library."""

from archetypal.idfclass import IDF

from epinterface.sbem.common import MetadataMixin, NamedObject
from epinterface.sbem.components import (
    DHWComponent,
    ZoneHVACComponent,
    ZoneSpaceUseComponent,
)


class ZoneOperationsComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Zone use consolidation across space use, HVAC, DHW."""

    SpaceUse: ZoneSpaceUseComponent
    HVAC: ZoneHVACComponent
    DHW: DHWComponent

    def add_space_use_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the loads to an IDF zone.

        This will add the people, equipment, and lights to the zone.

        nb: remember to add the schedules.

        Args:
            idf (IDF): The IDF object to add the loads to.
            target_zone_name (str): The name of the zone to add the loads to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.SpaceUse.add_loads_to_idf_zone(idf, target_zone_name)
        return idf

    def add_conditioning_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the conditioning to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the conditioning to.
            target_zone_name (str): The name of the zone to add the conditioning to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.HVAC.add_conditioning_to_idf_zone(idf, target_zone_name)
        return idf

    def add_hot_water_to_idf_zone(
        self, idf: IDF, target_zone_name: str, zone_area: float
    ) -> IDF:
        """Add the hot water to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the hot water to.
            target_zone_name (str): The name of the zone to add the hot water to.
            zone_area (float): The area of the zone.

        Returns:
            idf (IDF): The updated IDF object.

        """
        total_people = self.SpaceUse.OccupancyDensity * zone_area
        idf = self.DHW.add_water_to_idf_zone(
            idf, target_zone_name, total_ppl=total_people
        )
        return idf
