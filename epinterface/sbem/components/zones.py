"""Zone components."""

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.envelope import ZoneEnvelopeComponent
from epinterface.sbem.components.operations import ZoneOperationsComponent


class ZoneComponent(NamedObject):
    """Zone definition."""

    Operations: ZoneOperationsComponent
    Envelope: ZoneEnvelopeComponent
