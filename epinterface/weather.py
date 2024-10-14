"""Weather file fetching and caching."""

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated

import httpx
from pydantic import AfterValidator, AnyUrl, BaseModel, Field, UrlConstraints

logger = logging.getLogger(__name__)


class NotAZipError(ValueError):
    """Raised when a URL does not end with a .zip extension."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__("The URL provided does not end with a .zip extension.")


def check_path_ends_with_zip(url: AnyUrl):
    """Check that the path of the URL ends with a .zip extension.

    Args:
        url (AnyUrl): The URL to check.

    Raises:
        NotAZipError: If the URL does not end with a .zip extension.

    Returns:
        url (AnyUrl): The URL.
    """
    if not url.path:
        raise NotAZipError()
    if not url.path.endswith(".zip"):
        raise NotAZipError()
    return url


WeatherUrl = Annotated[
    Annotated[AnyUrl, UrlConstraints(allowed_schemes=["s3", "https", "http", "file"])],
    AfterValidator(check_path_ends_with_zip),
]


class BaseWeather(BaseModel):
    """A base class for fetching weather files.

    Responsible for fetching weather files from a URL and extracting the .epw and .ddy files.

    Also takes care of caching the weather files in a directory.
    """

    Weather: WeatherUrl = Field(
        default=WeatherUrl(  # pyright: ignore [reportCallIssue]
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
        )
    )

    async def fetch_weather(self, cache_dir: Path | str):
        """Fetch the weather file from the URL and extract the .epw and .ddy files.

        Args:
            cache_dir (Path | str): The directory to cache the weather files.

        Returns:
            epw_path (Path): The path to the .epw file.
            ddy_path (Path): The path to the .ddy file.
        """
        if isinstance(cache_dir, str):
            cache_dir = Path(cache_dir)

        if not self.Weather.path or not self.Weather.path.endswith(".zip"):
            raise NotAZipError()

        weather_path = Path(self.Weather.path).relative_to("/")
        weather_dir = cache_dir / weather_path.with_suffix("")
        epw_path = weather_dir / weather_path.with_suffix(".epw").name
        ddy_path = weather_dir / weather_path.with_suffix(".ddy").name
        weather_dir.mkdir(parents=True, exist_ok=True)
        if not epw_path.exists() or not ddy_path.exists():
            logger.info(f"Fetching weather file from {self.Weather}")
            # fetch the .zip file, unzip it, and extract the .epw and .ddy files
            client = httpx.AsyncClient()
            response = await client.get(str(self.Weather))
            with tempfile.TemporaryFile() as f:
                f.write(response.content)
                f.seek(0)
                with zipfile.ZipFile(f, "r") as z:
                    # z.extractall(weather_dir)
                    z.extract(epw_path.name, weather_dir)
                    z.extract(ddy_path.name, weather_dir)
            await client.aclose()
        else:
            logger.info(f"Using cached weather file from {weather_dir}")
        return epw_path, ddy_path
