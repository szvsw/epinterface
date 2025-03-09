"""A module for automatically fetching and composing SBEM objects."""

import uuid
from typing import Any, ClassVar, Literal, TypeVar, get_origin

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


def construct_graph(root_node: type[NamedObject]):
    """Construct a graph of the SBEM objects.

    Nodes are fields of of SBEM NamedObjects, with edges representing the type of the child field as stored in the parent field.

    It begins with checking the root node's fields, then recurses into the child fields which are also NamedObjects.

    Note that currently, lists/dicts/tuples of NamedObjects are not supported.

    Args:
        root_node (type[NamedObject]): The root node of the graph.

    Returns:
        graph (nx.DiGraph): A graph of the SBEM objects.
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


def recursive_tree_dict_merge(d1: dict, d2: dict):
    """Merge two dictionaries recursively.

    The behavior is as follows:
    - Every key/tree in d2 is merged into d1.
    - If a key is found in both dictionaries, the value from d2 is used.
    - If a key is found in d1 but not in d2, the value from d1 is used.
    - If a key is found in d2 but not in d1, the value from d2 is used.

    Args:
        d1 (dict): The base dictionary.
        d2 (dict): The dictionary to merge.
    """
    for key, value in d2.items():
        if key not in d1:
            msg = f"{key} is not in the d1 target dictionary."
            raise ValueError(msg)
        if isinstance(value, dict):
            if not isinstance(d1[key], dict) and d1[key] is not None:
                msg = f"{key} is not a dict in the d1 target dictionary."
                raise ValueError(msg)
            recursive_tree_dict_merge(d1[key], value)
        else:
            d1[key] = value


def construct_composer_model(  # noqa: C901
    g: nx.DiGraph,
    root_validator: type[NamedObject],
    use_children: bool = True,
    extra_handling: Literal["ignore", "forbid"] = "forbid",
):
    """Abstractly constructs a composition model from a graph of SBEM hierarchies.

    The ComposerModel.get_component(x: dict) method can be used to generate a composition of SBEM
    objects through the hierarchy, starting with the root node, and then substituting child nodes as they
    become available.

    Args:
        g (nx.DiGraph): The graph to construct the model from.
        root_validator (type[NamedObject]): The root validator type.
        use_children (bool): Whether to use `children` nesting keys (more verbose structure)
        extra_handling (Literal["ignore", "forbid"]): Whether to allow extra fields when validating provided serialized schemas.

    Returns:
        A pydantic model that can be used to execute component mapping and composition.
    """
    from epinterface.sbem.prisma.client import deep_fetcher

    # Cache to avoid recomputing the same field types - e.g. once
    # we have computed the field type for a Occupancy.Schedule,
    # we can immediately return it for Lighting.Schedule, Thermostat.HeatingSchedule, etc.
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

    # TODO: figure out how to abstract this so that the root node type passed in can be used to
    # give type safety assurances on the selector.get_component() method..
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

        class BaseModelWithValidator(BaseModel, extra=extra_handling):
            ValClass: ClassVar[type[NamedObject]] = validator
            selector: ComponentNameConstructor | None

            # TODO: we should allow fetching from in mem caches
            # so that this becomes abstracted and decoupled from the
            # database logic.
            @classmethod
            def get_deep_fetcher(cls):
                return deep_fetcher.get_deep_fetcher(cls.ValClass)

            def get_component(self, context: dict, allow_unvalidated: bool = False):
                component_name = (
                    self.selector.construct_name(context)
                    if self.selector is not None
                    else None
                )
                children_components = {}
                for field_name in self.model_dump():
                    field_selector = getattr(self, field_name)
                    if (
                        not isinstance(field_selector, ComponentNameConstructor)
                        and field_selector is not None
                    ):
                        children_components[field_name] = field_selector.get_component(
                            context=context,
                            allow_unvalidated=True,
                        )

                if component_name is None:
                    component_name = f"{self.ValClass.__name__}_{str(uuid.uuid4())[:8]}"
                    try:
                        component = self.ValClass(
                            Name=component_name, **children_components
                        )
                    except Exception:
                        if allow_unvalidated:
                            return {"Name": component_name, **children_components}
                        else:
                            raise
                else:
                    fetcher = self.get_deep_fetcher()
                    _record, component_base = fetcher.get_deep_object(component_name)
                    data = component_base.model_dump(exclude_none=True)

                    recursive_tree_dict_merge(data, children_components)

                    component = self.ValClass(**data)
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

    return handle_node(g, "root", use_children=use_children, validator=root_validator)


if __name__ == "__main__":
    import yaml

    root_node_class = ZoneComponent
    g = construct_graph(root_node_class)

    SelectorModel = construct_composer_model(
        g,
        root_validator=root_node_class,
        use_children=False,
    )

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
    from pathlib import Path

    from epinterface.sbem.prisma.client import prisma_settings

    prisma_settings.database_path = Path("massachusetts.db")

    with prisma_settings.db:
        # db = prisma_settings.db

        # db.connect()
        print(ma_selector.get_component({"typology": "office", "age": 10}))
        # db.disconnect()
