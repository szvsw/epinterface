"""Tests for the weather module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from epinterface.data import DefaultEPWZipPath
from epinterface.weather import BaseWeather, WeatherUrl


@pytest.fixture(scope="function")
def chicopee_epwzip_bytes():
    """The bytes of the Chicopee weather file."""
    with open(
        Path(__file__).parent
        / "data"
        / "USA_MA_Chicopee-Westover.Metro.AP.744910_TMYx.2009-2023.zip",
        "rb",
    ) as f:
        return f.read()


@pytest.fixture(scope="function")
def default_epwzip_bytes():
    """The bytes of the default weather file."""
    with open(DefaultEPWZipPath, "rb") as f:
        return f.read()


@pytest.fixture(scope="function")
def temporary_weather_dir():
    """A temporary directory for weather files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_weather_file_download_from_file(temporary_weather_dir: Path):
    """Test that the weather file is downloaded from the file and cached."""
    weather = BaseWeather(Weather=DefaultEPWZipPath)  # pyright: ignore [reportCallIssue]
    epw_path, ddy_path = weather.fetch_weather(temporary_weather_dir)
    assert epw_path.exists()
    assert ddy_path.exists()
    assert epw_path.suffix == ".epw"
    assert ddy_path.suffix == ".ddy"
    assert temporary_weather_dir in epw_path.parents
    assert temporary_weather_dir in ddy_path.parents
    assert Path(DefaultEPWZipPath).stem == epw_path.stem

    # we will now run it again, but we want to check that zipfile is not called
    with patch("epinterface.weather.zipfile.ZipFile") as mock_zipfile:
        epw_path, ddy_path = weather.fetch_weather(temporary_weather_dir)
        assert not mock_zipfile.called
        assert epw_path.exists()
        assert ddy_path.exists()
        assert epw_path.suffix == ".epw"
        assert ddy_path.suffix == ".ddy"
        assert temporary_weather_dir in epw_path.parents
        assert temporary_weather_dir in ddy_path.parents
        assert Path(DefaultEPWZipPath).stem == epw_path.stem


@patch("epinterface.weather.httpx.Client.get")
def test_weather_file_download_from_url(
    mock_get: Mock,
    temporary_weather_dir: Path,
    chicopee_epwzip_bytes: bytes,
    default_epwzip_bytes: bytes,
):
    """Test that the weather file is downloaded from the URL and cached."""
    mock_get.side_effect = [
        httpx.Response(
            status_code=200,
            content=default_epwzip_bytes,
        ),
        httpx.Response(
            status_code=200,
            content=chicopee_epwzip_bytes,
        ),
    ]
    weather = BaseWeather(
        Weather=WeatherUrl(  # pyright: ignore [reportCallIssue]
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
        )
    )

    epw_path, ddy_path = weather.fetch_weather(temporary_weather_dir)
    assert mock_get.call_count == 1
    assert (
        mock_get.call_args[0][0]
        == "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
    )
    assert epw_path.exists()
    assert ddy_path.exists()
    assert epw_path.suffix == ".epw"
    assert ddy_path.suffix == ".ddy"
    assert temporary_weather_dir in epw_path.parents
    assert temporary_weather_dir in ddy_path.parents
    assert (
        epw_path
        == temporary_weather_dir
        / "WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.epw"
    )

    assert (
        ddy_path
        == temporary_weather_dir
        / "WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.ddy"
    )

    # we will now run it again, but we want to check that neither zipfile.ZipFile nor httpx.Client.get are called
    with patch("epinterface.weather.zipfile.ZipFile") as mock_zipfile:
        epw_path, ddy_path = weather.fetch_weather(temporary_weather_dir)
        assert not mock_zipfile.called
        assert mock_get.call_count == 1

    new_weather = WeatherUrl(  # pyright: ignore [reportCallIssue]
        "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Chicopee-Westover.Metro.AP.744910_TMYx.2009-2023.zip"
    )
    weather = BaseWeather(Weather=new_weather)
    chicopee_epw_path, chicopee_ddy_path = weather.fetch_weather(temporary_weather_dir)
    assert mock_get.call_count == 2
    assert chicopee_epw_path.exists()
    assert chicopee_ddy_path.exists()
    assert chicopee_epw_path.suffix == ".epw"
    assert chicopee_ddy_path.suffix == ".ddy"
    assert temporary_weather_dir in chicopee_epw_path.parents
    assert temporary_weather_dir in chicopee_ddy_path.parents
    assert Path(str(new_weather)).stem == chicopee_epw_path.stem
    assert epw_path.exists()
    assert ddy_path.exists()
    assert "boston" in epw_path.stem.lower()
    assert "chicopee" in chicopee_epw_path.stem.lower()

    with patch("epinterface.weather.zipfile.ZipFile") as mock_zipfile:
        chicopee_epw_path, chicopee_ddy_path = weather.fetch_weather(
            temporary_weather_dir
        )
        assert not mock_zipfile.called
        assert mock_get.call_count == 2


@patch("epinterface.weather.httpx.Client.get")
def test_weather_file_download_from_url_with_missing_files(
    mock_get: Mock,
    temporary_weather_dir: Path,
    chicopee_epwzip_bytes: bytes,
):
    """Test that the weather file is downloaded from the URL and cached."""
    mock_get.return_value = httpx.Response(
        status_code=200,
        content=chicopee_epwzip_bytes,
    )

    weather = BaseWeather(
        Weather=WeatherUrl(  # pyright: ignore [reportCallIssue]
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
        )
    )

    with pytest.raises(FileNotFoundError, match=r".*Boston.*2009-2023\.epw.*not found"):
        weather.fetch_weather(temporary_weather_dir)
    assert mock_get.call_count == 1
