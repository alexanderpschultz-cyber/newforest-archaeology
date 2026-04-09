"""Convert pixel positions to geographic coordinates."""

from pyproj import Transformer

# BNG (EPSG:27700) to WGS84 (EPSG:4326)
_transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def pixel_percent_to_bng(
    x_percent: float,
    y_percent: float,
    easting: int,
    northing: int,
    tile_size_m: int = 1000,
) -> tuple[float, float]:
    """Convert image percentage position to BNG coordinates.

    Tiles are 1km squares. The tile_id easting/northing is the SW corner.
    x_percent: 0=left, 100=right (maps to easting)
    y_percent: 0=top, 100=bottom (maps to northing, inverted)
    """
    feat_easting = easting + (x_percent / 100.0) * tile_size_m
    feat_northing = northing + ((100 - y_percent) / 100.0) * tile_size_m
    return feat_easting, feat_northing


def bng_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert BNG easting/northing to WGS84 lat/lon."""
    lon, lat = _transformer.transform(easting, northing)
    return lat, lon


def pixel_percent_to_wgs84(
    x_percent: float,
    y_percent: float,
    easting: int,
    northing: int,
) -> tuple[float, float]:
    """Convert image percentage position directly to WGS84 lat/lon."""
    e, n = pixel_percent_to_bng(x_percent, y_percent, easting, northing)
    return bng_to_wgs84(e, n)
