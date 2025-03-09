"""A module for automatically fetching and composing SBEM objects."""

from typing import Any, ClassVar, TypeVar, get_origin

import networkx as nx
from pydantic import BaseModel, Field, create_model

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.zones import ZoneComponent

# Input a row of key/value pairs.

# compound action: concat the values of requested keys with a separator; there can also be an aggregate action and a breakpoint action which can be used as a tansform of the value, e.g. certain keys might get mapped onto the same value, e.g. high and medium both get mapped onto not_low

"""Tree construction:

Every node in the tree may or may not have a compound action specified.
--> If it is specified, then we will select the deep tree for the requested compounded key.  There will be options for if the key is not found ( e.g. fallbacks or raises.)
--> if it is specified, it will be loaded before it's children, but it's children (may) overwrite if specified.
--> If it is not specified, then it's children must be specified to avoid construction failure.

Branching:
Handle node, then handle its children.

Base case:
Start at root node.
"""


FieldT = TypeVar("FieldT", str, float, int, bool)
FieldT2 = TypeVar("FieldT2", str, float, int, bool)

NumericalFieldT = TypeVar("NumericalFieldT", float, int)


# class NamedData(BaseModel, Generic[FieldT]):
#     name: str

#     def pick(self, x: dict[str, FieldT | Any]) -> FieldT:
#         if self.name not in x:
#             raise ValueError(f"{self.name} is not in the dictionary.")
#         return x[self.name]


# class TransformedSemanticField(NamedData, ABC, Generic[FieldT, FieldT2]):
#     field: NamedData[FieldT]

#     @abstractmethod
#     def transform(self, x: FieldT) -> FieldT2:
#         pass


# class MappedField(Generic[FieldT, FieldT2], TransformedSemanticField[FieldT, FieldT2]):
#     str_map: dict[FieldT, FieldT2]
#     default: FieldT2 | None = None

#     def transform(self, x: FieldT) -> FieldT2:
#         if x not in self.str_map and self.default is None:
#             msg = f"{self.field.name} has no default value and `{x}` is not in the str_map."
#             raise ValueError(msg)
#         elif x not in self.str_map and self.default is not None:
#             return self.default
#         return self.str_map[x]


# class CompoundKey(BaseModel):
#     fields: list[NamedData]


class ComponentNameConstructor(BaseModel):
    """A constructor for the name of a component. based off of a list of source fields."""

    source_fields: list[str] = Field(default_factory=list)

    def construct_name(self, x: dict[str, Any]) -> str:
        """Construct the name of a component based off of a dictionary of source fields."""
        for field in self.source_fields:
            if field not in x:
                # TODO: implement things like fallback values, e.g. if a field is not found, should we assume a value for that field?
                # should we silently fail?
                # should we warn? should we raise?
                msg = f"{field} is not in the source fields."
                raise ValueError(msg)
        return "_".join(x[field] for field in self.source_fields)


NamedObjectT = TypeVar("NamedObjectT", bound=NamedObject)

# bind the Link type to a type where the first two type parameters are unknown but the third is a NamedObjectT


def construct_graph(root_node: type[NamedObject] = ZoneComponent):
    """Construct a graph of the SBEM objects.

    Nodes are fields of of SBEM NamedObjects, with edges representing the type of the child field as stored in the parent field.
    """
    g = nx.DiGraph()

    def handle_obj_class(g: nx.DiGraph, field_name: str, obj_class: type[NamedObject]):
        for child_field_name, child_annotation in obj_class.__annotations__.items():
            if isinstance(child_annotation, NamedObject.__class__) and issubclass(
                child_annotation, NamedObject
            ):
                g.add_edge(
                    field_name, child_field_name, data={"type": child_annotation}
                )
                handle_obj_class(g, child_field_name, child_annotation)

            elif hasattr(
                child_annotation, "__args__"
            ):  # but if it's a list, we want to skip
                if get_origin(child_annotation) in [list, tuple, dict]:
                    # TODO: special handling for list/dict cases using an additional entry in the edge data.
                    continue
                for note in child_annotation.__args__:
                    if isinstance(note, NamedObject.__class__) and issubclass(
                        note, NamedObject
                    ):
                        g.add_edge(field_name, child_field_name, data={"type": note})
                        handle_obj_class(g, child_field_name, note)
                        break

    handle_obj_class(g, "root", root_node)
    return g


def construct_pydantic_models_from_graph(g: nx.DiGraph, use_children: bool = True):  # noqa: C901
    """Abstractly constructs a pydantic model from a graph of SBEM hierarchies."""
    # we want to construct a pydantic model that will look, e.g. like this when serialized:
    resolved_field_types = {}

    def get_field_type_for_edge(
        g: nx.DiGraph,
        target_node_name: str,
        target_node_type: type[NamedObject],
        use_children: bool,
    ):
        if target_node_type not in resolved_field_types:
            # target_node = g.nodes[target_node_name]
            # target_node_is_leaf = len(list(g.successors(target_node_name))) == 0
            # if target_node_is_leaf:
            #     resolved_field_types[target_node_type] = ComponentNameConstructor
            # else:
            #     resolved_field_types[target_node_type] = handle_node(
            #         g, target_node_name, use_children
            #     )
            resolved_field_types[target_node_type] = handle_node(
                g, target_node_name, use_children, target_node_type
            )
        return (resolved_field_types[target_node_type] | None, None)

    def handle_node(
        g: nx.DiGraph, node: str, use_children: bool, validator: type[NamedObject]
    ):
        edges_starting_at_node = g.edges(node, data=True)
        node_fields = {}
        for _parent_name, child_name, data in edges_starting_at_node:
            node_fields[child_name] = get_field_type_for_edge(
                g, child_name, data["data"]["type"], use_children=use_children
            )
        this_selector = (
            (ComponentNameConstructor | None, None)
            if node != "root"
            else (ComponentNameConstructor, ...)
        )

        class BaseModelWithValidator(BaseModel):
            ValClass: ClassVar[type[NamedObject]] = validator
            selector: ComponentNameConstructor | None

            @classmethod
            def get_deep_fetcher(cls):
                return deep_fetcher.get_deep_fetcher(cls.ValClass)

            def get_component(self, context: dict):
                component_name = (
                    self.selector.construct_name(context)
                    if self.selector is not None
                    else None
                )
                children_components = {}
                for (
                    child_name,
                    child_annotation,
                ) in self.ValClass.__annotations__.items():
                    if isinstance(
                        child_annotation, BaseModelWithValidator.__class__
                    ) and issubclass(child_annotation, BaseModelWithValidator):
                        child_selector: BaseModelWithValidator = getattr(
                            self, child_name
                        )
                        children_components[child_name] = child_selector.get_component(
                            context=context
                        )

                if component_name is None:
                    component = self.ValClass(**children_components)
                else:
                    fetcher = self.get_deep_fetcher()
                    _record, component_base = fetcher.get_deep_object(component_name)
                    component = self.ValClass(
                        **component_base.model_dump(), **children_components
                    )
                return component

        if use_children:
            children_model = create_model(
                f"{node}Selector",
                **node_fields,
            )

            return create_model(
                f"{node}Selector",
                children=(children_model | None, None),
                selector=this_selector,
                __base__=BaseModelWithValidator,
            )
        else:
            # we want to add a classvar to the model which stores the validator

            return create_model(
                f"{node}Selector",
                **node_fields,
                selector=this_selector,
                __base__=BaseModelWithValidator,
            )

    return handle_node(g, "root", use_children=use_children, validator=ZoneComponent)


if __name__ == "__main__":
    import yaml

    from epinterface.sbem.prisma.client import deep_fetcher

    g = construct_graph()

    SelectorModel = construct_pydantic_models_from_graph(g, use_children=False)

    ma_selector = SelectorModel(
        **{
            "Envelope": {
                "Infiltration": {
                    "selector": ComponentNameConstructor(
                        source_fields=["weatherization"]
                    )
                },
                "Window": {
                    "selector": ComponentNameConstructor(source_fields=["windows"])
                },
                "Assemblies": {
                    "selector": ComponentNameConstructor(
                        source_fields=[
                            "roof_and_attic",
                            "basement",
                            "wall_insulation",
                        ]
                    ),
                },
            },
            "Operations": {
                "SpaceUse": {
                    "Occupancy": {
                        "selector": ComponentNameConstructor(
                            source_fields=["typology", "age"]
                        ),
                    },
                    "Lighting": {
                        "selector": ComponentNameConstructor(
                            source_fields=["typology", "lighting_type"]
                        ),
                    },
                    "Equipment": {
                        "selector": ComponentNameConstructor(
                            source_fields=["typology", "age", "equipment_type"]
                        ),
                    },
                    "WaterUse": {
                        "selector": ComponentNameConstructor(
                            source_fields=["typology"]
                        ),
                    },
                    "Thermostat": {
                        "selector": ComponentNameConstructor(
                            source_fields=[
                                "typology",
                                "age",
                                "thermostat_controls",
                            ]
                        ),
                    },
                },
                "DHW": {
                    "selector": ComponentNameConstructor(
                        source_fields=["hot_water_system"]
                    ),
                },
                "HVAC": {
                    "Ventilation": {
                        "selector": ComponentNameConstructor(
                            source_fields=[
                                "typology",
                                "age",
                                "distribution_system_insulation",
                            ]
                        ),
                    },
                    "ConditioningSystems": {
                        "Cooling": {
                            "selector": ComponentNameConstructor(
                                source_fields=[
                                    "cooling_system",
                                    "distribution_system_insulation",
                                ]
                            ),
                        },
                        "Heating": {
                            "selector": ComponentNameConstructor(
                                source_fields=[
                                    "heating_system",
                                    "distribution_system_insulation",
                                ]
                            ),
                        },
                    },
                },
            },
        },
        selector=ComponentNameConstructor(),
    )
    print(
        yaml.safe_dump(ma_selector.model_dump(mode="json", exclude_none=True), indent=2)
    )

    # for node in g.nodes:
    #     if node == "root":
    #         continue
    #     path_to_root = nx.shortest_path(g, "root", node)[1:]
    #     sel = reduce(
    #         lambda x, y: getattr(x, y) if hasattr(x, y) else None,
    #         path_to_root,
    #         ma_selector,
    #     )
    #     if sel is not None:
    #         print(sel.selector if hasattr(sel, "selector") else "None")
    #     else:
    #         print("None")
    # print(ma_selector.ValClass)
    # key = "Operations"
    # key2 = "SpaceUse"
    # key3 = "Occupancy"
    # print(getattr(getattr(getattr(ma_selector, key), key2), key3))
    from epinterface.sbem.prisma.client import prisma_settings

    with prisma_settings.db:
        # db = prisma_settings.db

        # db.connect()
        print(ma_selector.get_component({"typology": "office", "age": 10}))
        # db.disconnect()
