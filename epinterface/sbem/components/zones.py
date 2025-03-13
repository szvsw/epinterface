"""Zone components."""

from archetypal.idfclass import IDF

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.envelope import ZoneEnvelopeComponent
from epinterface.sbem.components.operations import ZoneOperationsComponent


class ZoneComponent(NamedObject):
    """Zone definition."""

    Operations: ZoneOperationsComponent
    Envelope: ZoneEnvelopeComponent

    def add_to_idf_zone(self, idf: IDF, zone_name: str) -> IDF:
        """Add the zone to the IDF."""
        # TODO: consider lifting up the individual loads since the pass through method here
        # does not actually handle all of space use, given that it must synthesize
        # DHW and Operations.SpaceUse.WaterUse
        idf = self.Operations.SpaceUse.add_loads_to_idf_zone(idf, zone_name)
        idf = self.Operations.add_water_use_to_idf_zone(idf, zone_name)
        idf = self.Envelope.Infiltration.add_infiltration_to_idf_zone(idf, zone_name)
        return idf
