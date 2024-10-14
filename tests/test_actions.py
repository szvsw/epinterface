"""Test applying mutation actions."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from epinterface.climate_studio.actions import (
    ActionSequence,
    DeltaVal,
    ParameterPath,
    ReplaceWithExisting,
    ReplaceWithVal,
    get_dict_val_or_attr,
    set_dict_val_or_attr,
)
from epinterface.climate_studio.interface import (
    ClimateStudioLibraryV2,
    OpaqueConstruction,
    ZoneHotWater,
    ZoneLoad,
)


@pytest.fixture(scope="function")
def lib():
    """Load the test library."""
    with open(Path(__file__).parent / "data" / "test_lib.json") as f:
        lib_data = json.load(f)
    yield ClimateStudioLibraryV2.model_validate(lib_data)


@pytest.fixture(scope="function")
def lib_dict():
    """Load the test library as a dictionary."""
    return {"a": {"b": {"c": 1, "d": [1, {"e": 2}]}}, "f": {"g": "c"}}


def test_get_dict_val_or_attr():
    """Test getting a value from a dictionary, list, or attribute."""
    test_dict = {"a": 1}
    assert get_dict_val_or_attr(test_dict, "a") == 1
    test_list = [1, 2]
    assert get_dict_val_or_attr(test_list, 0) == 1

    class DummyClass(BaseModel):
        a: int = 1

    obj = DummyClass()
    assert get_dict_val_or_attr(obj, "a") == 1


def test_set_dict_val_or_attr():
    """Test setting a value in a dictionary, list, or attribute."""
    test_dict = {"a": 1}
    set_dict_val_or_attr(test_dict, "a", 2)
    assert test_dict["a"] == 2
    test_list = [1, 2]
    set_dict_val_or_attr(test_list, 0, 3)
    assert test_list[0] == 3

    class DummyClass(BaseModel):
        a: int = 1

    obj = DummyClass()
    set_dict_val_or_attr(obj, "a", 2)
    assert obj.a == 2


def test_parameter_path_get_from_dict(lib_dict):
    """Test getting a value from a dictionary."""
    pth = ParameterPath[float](path=["a", "b", "c"])
    assert pth.get_lib_val(lib_dict) == 1
    pth = ParameterPath[float](path=["a", "b"])
    assert pth.get_lib_val(lib_dict) == {"c": 1, "d": [1, {"e": 2}]}
    pth = ParameterPath[float](path=["a", "b", "d", 1, "e"])
    assert pth.get_lib_val(lib_dict) == 2
    pth = ParameterPath[float](path=["a", "b", "d", 0])
    assert pth.get_lib_val(lib_dict) == 1


def test_parameter_path_fail(lib_dict):
    """Test failing to get a value from a dictionary, list, or attribute."""
    # test that we fail to get a value that doesn't exist
    pth = ParameterPath[float](path=["a", "b", "d", 2])
    with pytest.raises(IndexError):
        pth.get_lib_val(lib_dict)

    pth = ParameterPath[float](path=["a", "c"])
    with pytest.raises(KeyError):
        pth.get_lib_val(lib_dict)

    class DummyClass(BaseModel):
        a: int = 1

    obj = DummyClass()
    pth = ParameterPath[float](path=["c"])

    with pytest.raises(AttributeError):
        pth.get_lib_val(obj)


def test_parameter_path_with_lib(lib: ClimateStudioLibraryV2):
    """Test getting a value from a library."""
    first_space_use_name = next(iter(lib.SpaceUses.keys()))
    lib.SpaceUses[first_space_use_name].HotWater.FlowRatePerPerson = 1.2345
    pth = ParameterPath[float](
        path=["SpaceUses", first_space_use_name, "HotWater", "FlowRatePerPerson"]
    )
    assert pth.get_lib_val(lib) == 1.2345


def test_get_obj_from_lib(lib: ClimateStudioLibraryV2):
    """Test getting an object from a library."""
    first_space_use_name = next(iter(lib.SpaceUses.keys()))
    pth = ParameterPath[ZoneHotWater](
        path=["SpaceUses", first_space_use_name, "HotWater"]
    )
    expected = lib.SpaceUses[first_space_use_name].HotWater
    assert pth.get_lib_val(lib) == expected


def test_getting_referenced_object_from_dict(lib_dict: dict):
    """Test getting a referenced object from a dictionary."""
    ref_pth = ParameterPath[str](path=["f", "g"])
    pth = ParameterPath[str](path=["a", "b", ref_pth])
    assert pth.get_lib_val(lib_dict) == lib_dict["a"]["b"]["c"]
    assert pth.get_lib_val(lib_dict) == 1


def test_getting_referenced_object_from_lib(lib: ClimateStudioLibraryV2):
    """Test getting a referenced object from a library."""
    first_space_use_name = next(iter(lib.SpaceUses.keys()))
    ref_pth = ParameterPath[str](
        path=["Envelopes", first_space_use_name, "Constructions", "FacadeConstruction"]
    )
    ref_name = ref_pth.get_lib_val(lib)
    expected = lib.OpaqueConstructions[ref_name]
    pth = ParameterPath[OpaqueConstruction](path=["OpaqueConstructions", ref_name])
    assert pth.get_lib_val(lib) == expected


def test_delta_val_on_dict(lib_dict: dict):
    """Test applying a delta value to a dictionary."""
    expected = lib_dict["a"]["b"]["c"] + 1
    action = DeltaVal[float](
        target=ParameterPath[float](path=["a", "b", "c"]),
        delta=1,
        op="+",
    )
    action.run(lib_dict)
    assert lib_dict["a"]["b"]["c"] == expected
    expected = lib_dict["a"]["b"]["c"] - 1
    action = DeltaVal[float](
        target=ParameterPath[float](path=["a", "b", "c"]),
        delta=-1,
        op="+",
    )
    action.run(lib_dict)

    expected = lib_dict["a"]["b"]["c"] * 3

    action = DeltaVal[float](
        target=ParameterPath[float](path=["a", "b", "c"]),
        delta=3,
        op="*",
    )
    action.run(lib_dict)
    assert lib_dict["a"]["b"]["c"] == expected

    expected = lib_dict["a"]["b"]["c"] / 2
    action = DeltaVal[float](
        target=ParameterPath[float](path=["a", "b", "c"]),
        delta=1 / 2,
        op="*",
    )
    action.run(lib_dict)
    assert pytest.approx(expected) == lib_dict["a"]["b"]["c"]


def test_delta_val_on_list_item():
    """Test applying a delta value to a list."""
    lib = {"a": [1, {"b": [2, 3, 4]}]}

    pth = ParameterPath[float](path=["a", 1, "b", 1])
    action = DeltaVal[float](
        target=pth,
        delta=1,
        op="+",
    )
    expected = 4
    action.run(lib)
    assert lib["a"][1]["b"][1] == expected


def test_delta_val_on_lib(lib: ClimateStudioLibraryV2):
    """Test applying a delta value to a library's first available space use hot water flow rate."""
    first_space_use_name = next(iter(lib.SpaceUses.keys()))
    initial_val = lib.SpaceUses[first_space_use_name].HotWater.FlowRatePerPerson
    expected = initial_val + 1
    action = DeltaVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", first_space_use_name, "HotWater", "FlowRatePerPerson"]
        ),
        delta=1,
        op="+",
    )
    action.run(lib)
    assert lib.SpaceUses[first_space_use_name].HotWater.FlowRatePerPerson == expected
    expected = expected - 1
    action = DeltaVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", first_space_use_name, "HotWater", "FlowRatePerPerson"]
        ),
        delta=-1,
        op="+",
    )
    action.run(lib)
    assert lib.SpaceUses[first_space_use_name].HotWater.FlowRatePerPerson == expected
    expected = expected * 3
    action = DeltaVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", first_space_use_name, "HotWater", "FlowRatePerPerson"]
        ),
        delta=3,
        op="*",
    )
    action.run(lib)
    assert lib.SpaceUses[first_space_use_name].HotWater.FlowRatePerPerson == expected
    expected = expected / 2
    action = DeltaVal[float](
        target=ParameterPath[float](
            path=["SpaceUses", first_space_use_name, "HotWater", "FlowRatePerPerson"]
        ),
        delta=1 / 2,
        op="*",
    )
    action.run(lib)
    assert (
        pytest.approx(expected)
        == lib.SpaceUses[first_space_use_name].HotWater.FlowRatePerPerson
    )


def test_repalce_with_val_on_dict(lib_dict: dict):
    """Test replacing a value in a dictionary."""
    expected = 5.0
    action = ReplaceWithVal[float](
        target=ParameterPath[float](path=["a", "b", "c"]),
        val=5,
    )
    action.run(lib_dict)
    assert lib_dict["a"]["b"]["c"] == expected

    expected = "test"
    action = ReplaceWithVal[str](
        target=ParameterPath[str](path=["f", "g"]),
        val="test",
    )
    action.run(lib_dict)
    assert lib_dict["f"]["g"] == expected
    expected = {"foo": "bar"}
    action = ReplaceWithVal[dict](
        target=ParameterPath[dict](path=["f"]),
        val={"foo": "bar"},
    )
    action.run(lib_dict)
    assert lib_dict["f"] == expected


def test_replace_with_existing_on_dict(lib_dict: dict):
    """Test replacing a value in a dictionary with the existing value."""
    source_pth = ParameterPath[float](path=["a", "b", "c"])
    target_pth = ParameterPath[float](path=["a", "b", "d", 0])
    action = ReplaceWithExisting[float](target=target_pth, source=source_pth)
    action.run(lib_dict)
    assert lib_dict["a"]["b"]["d"][0] == lib_dict["a"]["b"]["c"]


def test_replace_with_existing_on_lib(lib: ClimateStudioLibraryV2):
    """Test replacing a value in a library with the existing value."""
    first_space_use_name = next(iter(lib.SpaceUses.keys()))
    second_space_use_name = list(lib.SpaceUses.keys())[-1]
    assert first_space_use_name != second_space_use_name
    lib.SpaceUses[first_space_use_name].Loads.EquipmentIsOn = False
    lib.SpaceUses[second_space_use_name].Loads.EquipmentIsOn = True
    lib.SpaceUses[first_space_use_name].Loads.EquipmentPowerDensity = 0.5
    lib.SpaceUses[second_space_use_name].Loads.EquipmentPowerDensity = 1.0
    source_pth = ParameterPath[bool](
        path=["SpaceUses", first_space_use_name, "Loads", "EquipmentIsOn"]
    )
    target_pth = ParameterPath[bool](
        path=["SpaceUses", second_space_use_name, "Loads", "EquipmentIsOn"]
    )
    action = ReplaceWithExisting[bool](target=target_pth, source=source_pth)
    action.run(lib)
    assert (
        lib.SpaceUses[second_space_use_name].Loads.EquipmentIsOn
        == lib.SpaceUses[first_space_use_name].Loads.EquipmentIsOn
    )
    assert not lib.SpaceUses[second_space_use_name].Loads.EquipmentIsOn
    assert lib.SpaceUses[second_space_use_name].Loads.EquipmentPowerDensity == 1.0
    assert lib.SpaceUses[first_space_use_name].Loads.EquipmentPowerDensity == 0.5
    source_pth = ParameterPath[ZoneLoad](
        path=["SpaceUses", first_space_use_name, "Loads"]
    )
    target_pth = ParameterPath[ZoneLoad](
        path=["SpaceUses", second_space_use_name, "Loads"]
    )
    action = ReplaceWithExisting[ZoneLoad](target=target_pth, source=source_pth)
    action.run(lib)
    assert (
        lib.SpaceUses[second_space_use_name].Loads.EquipmentIsOn
        == lib.SpaceUses[first_space_use_name].Loads.EquipmentIsOn
    )
    assert not lib.SpaceUses[second_space_use_name].Loads.EquipmentIsOn
    assert lib.SpaceUses[second_space_use_name].Loads.EquipmentPowerDensity == 0.5
    assert lib.SpaceUses[first_space_use_name].Loads.EquipmentPowerDensity == 0.5
    assert (
        lib.SpaceUses[first_space_use_name].Loads
        == lib.SpaceUses[second_space_use_name].Loads
    )


def test_action_sequence(lib_dict: dict):
    """Test applying a sequence of actions."""
    actions = [
        DeltaVal[float](
            target=ParameterPath[float](path=["a", "b", "c"]),
            delta=1,
            op="+",
        ),
        ReplaceWithVal[float](
            target=ParameterPath[float](path=["a", "b", "d", 0]),
            val=5,
        ),
        ReplaceWithVal[str](
            target=ParameterPath[str](path=["f", "g"]),
            val="test",
        ),
    ]
    action_sequence = ActionSequence(actions=actions, name="action-sequence-test")
    action_sequence.run(lib_dict)
    assert lib_dict["a"]["b"]["c"] == 2
    assert lib_dict["a"]["b"]["d"][0] == 5
    assert lib_dict["f"]["g"] == "test"
