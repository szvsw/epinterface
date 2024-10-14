"""Actions to modify a library object."""

from abc import abstractmethod
from collections.abc import Callable
from functools import reduce
from typing import Any, Generic, Literal, TypeVar, cast

from pydantic import BaseModel, Field

from epinterface.climate_studio.builder import Model
from epinterface.climate_studio.interface import ClimateStudioLibraryV2

LibT = TypeVar("LibT", dict[str, Any], ClimateStudioLibraryV2, Model, BaseModel)

# TODO: Major!
# allow operating on an object in conjunction with operating on a library


def get_dict_val_or_attr(obj, key):
    """Retrieve a value from a dictionary or list, or an attribute from an object.

    Args:
        obj (Union[dict, list, Any]): The object from which to retrieve the value or attribute.
        key (Any): The key or attribute name to retrieve.

    Returns:
        val (Any): The value associated with the key if `obj` is a dictionary or list,
             or the attribute value if `obj` is an object.
    """
    if isinstance(obj, dict | list):
        return obj[key]
    else:
        return getattr(obj, key)


def set_dict_val_or_attr(obj, key, val):
    """Sets a value in a dictionary or list, or sets an attribute on an object.

    If the provided object is a dictionary or list, the function sets the value
    at the specified key or index. If the object is not a dictionary or list,
    the function sets an attribute on the object with the specified key and value.

    Args:
        obj (Union[dict, list, object]): The object to modify.
        key (Union[str, int]): The key or attribute name to set.
        val (Any): The value to set.

    Raises:
        TypeError: If the object is a list and the key is not an integer.
    """
    if isinstance(obj, dict | list):
        obj[key] = val
    else:
        setattr(obj, key, val)


T = TypeVar("T")


class ParameterPath(BaseModel, Generic[T]):
    """Pathing to find a parameter in a library/object.

    ParameterPath is a generic class that represents a path consisting of strings, integers,
    or other ParameterPath instances. It provides methods to resolve the path and retrieve
    values from a given library.
    """

    path: list["str | int | ParameterPath[str] | ParameterPath[int]"] = Field(
        ..., description="The path to the parameter to select."
    )

    def resolved_path(self, lib: LibT):
        """Resolve the path to the parameter in the library.

        Args:
            lib (LibT): The library to search for the parameter.

        Returns:
            path (list[Any]): The resolved path to the parameter in the library.
        """
        return [
            p if isinstance(p, str | int) else p.get_lib_val(lib) for p in self.path
        ]

    def get_lib_val(self, lib: LibT) -> T:
        """Retrieves a value from a nested dictionary or object attribute path.

        Args:
            lib (LibT): The library object from which to retrieve the value.

        Returns:
            val (T): The value retrieved from the nested dictionary or object attribute path.
        """
        return cast(T, reduce(get_dict_val_or_attr, self.resolved_path(lib), lib))

    @property
    def parent_path(self):
        """Returns the parent path of the current path.

        Returns:
            parent_path (ParameterPath): The parent path of the current path.
        """
        # TODO: how can we type-narrow the generic parameterpath here?
        return ParameterPath(path=self.path[:-1])


Priority = Literal["low", "high"]


class Action(BaseModel, Generic[T]):
    """An action to modify a library object.

    This base class should be inherited by classes that represent actions to modify
    a library object. It provides an abstract method `run` that should be implemented
    by subclasses to perform the modification.
    """

    target: ParameterPath[T] = Field(
        ..., description="The path to the parameter to modify."
    )
    priority: Priority | None = Field(
        default=None,
        description="The priority of the action (low will execute if the new value is less than the old value).",
    )

    def run(self, lib: LibT) -> LibT:
        """Run the action to modify the library object.

        Args:
            lib (LibT): The library object to modify.

        Returns:
            lib (LibT): The modified library object.
        """
        new_val = self.new_val(lib)
        original_val = self.get_original_val(lib)
        if self.check_priority(original_val, new_val):
            original_obj = self.get_original_obj(lib)
            key = self.original_key
            set_dict_val_or_attr(original_obj, key, new_val)
        return lib

    def check_priority(self, original: T, new: T) -> bool:
        """Check if the new value should be applied based on the action priority.

        Args:
            original (T): The original value in the library object.
            new (T): The new value to apply.

        Returns:
            apply (bool): True if the new value should be applied, False otherwise.
        """
        if self.priority is None:
            return True

        if not isinstance(original, int | float) or not isinstance(new, int | float):
            msg = "priority comparison only supported for numerical values."
            raise TypeError(msg)

        if self.priority == "low":
            return original > new

        elif self.priority == "high":
            return original < new
        else:
            msg = f"Invalid priority value: {self.priority}"
            raise ValueError(msg)

    def get_original_val(self, lib: LibT) -> T:
        """Retrieve the original value from the library object.

        Args:
            lib (LibT): The library object from which to retrieve the original value.

        Returns:
            val (T): The original value from the library object.
        """
        return self.target.get_lib_val(lib)

    @property
    def original_key(self) -> str | int | ParameterPath:
        """Retrieve the key of the original value in the library object.

        Returns:
            key (str | int | ParameterPath): The key of the original value in the library object.
        """
        # TODO: handle cases where final key is a ParameterPath!!
        return self.target.path[-1]

    def get_original_obj(self, lib: LibT):
        """Retrieve the object containing the original value in the library object.

        Args:
            lib (LibT): The library object from which to retrieve the original object.

        Returns:
            obj (Any): The object containing the original value in the library object.
        """
        return self.target.parent_path.get_lib_val(lib)

    @abstractmethod
    def new_val(self, lib: LibT) -> T:
        """Calculate the new value to apply to the library object.

        NB: This method should be implemented by subclasses to calculate the new value.

        Args:
            lib (LibT): The library object on which to apply the new value.

        Returns:
            val (T): The new value to apply to the library object.
        """
        pass


class ReplaceWithExisting(Action[T]):
    """Replace a value in a library object with a value from another location in the library."""

    source: ParameterPath[T]

    def new_val(self, lib: LibT) -> T:
        """Retrieve the value from the source path to replace the target value.

        Args:
            lib (LibT): The library object from which to retrieve the new value.

        Returns:
            val (T): The new value to replace the target value.
        """
        return self.source.get_lib_val(lib)


class ReplaceWithVal(Action[T]):
    """Replace a value in a library object with a new value."""

    val: T

    def new_val(self, lib: LibT) -> T:
        """Returns the current value of the instance to use for updating.

        Args:
            lib (LibT): A library instance of type LibT.

        Returns:
            val (T): The current value of the instance.
        """
        return self.val


Numeric = TypeVar("Numeric", int, float)
Operation = Literal["+", "*"]


class DeltaVal(Action[Numeric]):
    """Add a value to a parameter in a library object."""

    delta: Numeric = Field(
        ..., description="The value to modify to the original value."
    )
    op: Operation = Field(
        ..., description="The operation to perform on the original value."
    )

    def new_val(self, lib: LibT) -> Numeric:
        """Calculate a new value by combining the original value from the given library with a delta.

        Args:
            lib (LibT): The library from which to retrieve the original value.

        Returns:
            new_val (Numeric): The new value obtained by combining the original value with the delta.
        """
        original_val = self.get_original_val(lib)

        return self.combine(original_val, self.delta)

    @property
    def combine(self) -> Callable[[Numeric, Numeric], Numeric]:
        """Combines two numeric values based on the specified operation.

        Supported operations:
            - "+": Addition
            - "*": Multiplication

        Returns:
            fn (Callable[[Numeric, Numeric], Numeric]): A function that takes two numeric arguments and returns a numeric result.

        Raises:
            ValueError: If the operation specified by `self.op` is not supported.

        """
        if self.op == "+":
            return lambda x, y: x + y
        elif self.op == "*":
            return lambda x, y: x * y
        else:
            msg = f"Invalid operation: {self.op}"
            raise ValueError(msg)


class ActionSequence(BaseModel):
    """A sequence of actions to perform on a library object."""

    name: str = Field(..., description="The name of the action sequence.")
    actions: list[DeltaVal | ReplaceWithExisting | ReplaceWithVal] = Field(
        ..., description="A sequence of actions to perform on a library object."
    )

    def run(self, lib: LibT) -> LibT:
        """Run the sequence of actions on the library object.

        Args:
            lib (LibT): The library object to modify.

        Returns:
            lib (LibT): The modified library object.
        """
        for action in self.actions:
            lib = action.run(lib)
        return lib


if __name__ == "__main__":
    import json

    from epinterface.climate_studio.interface import ZoneLoad

    lib_path = "notebooks/everett_lib.json"
    with open(lib_path) as f:
        lib_data = json.load(f)
    lib = ClimateStudioLibraryV2.model_validate(lib_data)
    sched_path = ParameterPath[str](
        path=["SpaceUses", "MA_SF_pre_1975", "Loads", "EquipmentAvailabilitySchedule"]
    )
    sched_data_path = ParameterPath[float](path=["Schedules", sched_path, "Values", 0])
    print(sched_data_path.get_lib_val(lib))
    print(sched_data_path.model_dump(mode="json"))
    import yaml

    print(yaml.dump(sched_data_path.model_dump(mode="dict")))

    action = ReplaceWithExisting[ZoneLoad](
        source=ParameterPath[ZoneLoad](path=["SpaceUses", "MA_SF_post_2003", "Loads"]),
        target=ParameterPath[ZoneLoad](path=["SpaceUses", "MA_SF_pre_1975", "Loads"]),
    )

    print(action.target.get_lib_val(lib).EquipmentPowerDensity)
    print(action.source.get_lib_val(lib).EquipmentPowerDensity)
    action.run(lib)
    print(action.target.get_lib_val(lib).EquipmentPowerDensity)
    print(action.source.get_lib_val(lib).EquipmentPowerDensity)

    action = ReplaceWithVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", "MA_SF_post_2003", "Loads", "EquipmentPowerDensity"]
        ),
        val=0.75,
    )
    action.run(lib)

    print(action.target.get_lib_val(lib))

    action = DeltaVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", "MA_SF_post_2003", "Loads", "EquipmentPowerDensity"]
        ),
        delta=0.25,
        op="+",
    )

    action.run(lib)
    print(action.target.get_lib_val(lib))

    action = DeltaVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", "MA_SF_post_2003", "Loads", "EquipmentPowerDensity"]
        ),
        delta=0.25,
        op="*",
        priority="low",
    )

    action.run(lib)
    print(action.target.get_lib_val(lib))

    ma_sf_pre_1975_ee_upgrade = ActionSequence(
        name="MA_SF_pre_1975_ee_upgrade",
        actions=[
            ReplaceWithVal[float](
                target=ParameterPath[float](
                    path=[
                        "SpaceUses",
                        "MA_SF_pre_1975",
                        "Loads",
                        "EquipmentPowerDensity",
                    ]  # TODO: ma_sf_pre_1975 should be determined from some other source, e.g. a Model
                    # one way of achieving that would be to have the model store rich objects rather than thin ones
                    # alternatively, run() method could be modified to accept a model object as well as the lib
                    # and then known when to pass it down to accessors
                ),
                val=2.3,
                priority="low",
            ),
            ReplaceWithVal[float](
                target=ParameterPath[float](
                    path=[
                        "SpaceUses",
                        "MA_SF_pre_1975",
                        "Loads",
                        "LightingPowerDensity",
                    ]
                ),
                val=2.1,
                priority="low",
            ),
            ReplaceWithVal[float](
                target=ParameterPath[float](
                    path=[
                        "Envelopes",
                        "MA_SF_pre_1975",
                        "Infiltration",
                        "InfiltrationAch",
                    ]
                ),
                val=0.1,
                priority="low",
            ),
        ],
    )
    ma_sf_pre_1975_ee_upgrade.run(lib)
    print(lib.Envelopes["MA_SF_pre_1975"].Infiltration.InfiltrationAch)

    ma_sf_pre_1975_ee_upgrade = ActionSequence(
        name="MA_SF_pre_1975_ee_upgrade",
        actions=[
            ReplaceWithVal[float](
                target=ParameterPath[float](
                    path=[
                        "lib",
                        "SpaceUses",
                        ParameterPath[str](path=["space_use_name"]),
                        "Loads",
                        "EquipmentPowerDensity",
                    ]  # TODO: ma_sf_pre_1975 should be determined from some other source, e.g. a Model
                    # one way of achieving that would be to have the model store rich objects rather than thin ones
                    # alternatively, run() method could be modified to accept a model object as well as the lib
                    # and then known when to pass it down to accessors
                ),
                val=2.3,
                priority="low",
            ),
            ReplaceWithVal[float](
                target=ParameterPath[float](
                    path=[
                        "lib",
                        "SpaceUses",
                        ParameterPath[str](path=["space_use_name"]),
                        "Loads",
                        "LightingPowerDensity",
                    ]
                ),
                val=2.1,
                priority="low",
            ),
            ReplaceWithVal[float](
                target=ParameterPath[float](
                    path=[
                        "lib",
                        "Envelopes",
                        ParameterPath[str](path=["envelope_name"]),
                        "Infiltration",
                        "InfiltrationAch",
                    ]
                ),
                val=0.1,
                priority="low",
            ),
        ],
    )
    from epinterface.climate_studio.builder import Model, ShoeboxGeometry

    lib = ClimateStudioLibraryV2.model_validate(lib_data)
    model = Model(
        geometry=ShoeboxGeometry(
            x=0,
            y=0,
            w=10,
            d=10,
            h=3.5,
            num_stories=3,
            zoning="core/perim",
            perim_depth=3,
            roof_height=None,
            basement=False,
            wwr=0.15,
        ),
        space_use_name="MA_SF_pre_1975",
        envelope_name="MA_SF_pre_1975",
        conditioned_basement=False,
        lib=lib,
    )
    model = ma_sf_pre_1975_ee_upgrade.run(model)
    print(ma_sf_pre_1975_ee_upgrade.actions[0].target.get_lib_val(model))
    str_ac = yaml.dump(ma_sf_pre_1975_ee_upgrade.model_dump(mode="dict"))
    action_sequence = ActionSequence.model_validate(yaml.safe_load(str_ac))
    print(action_sequence)
