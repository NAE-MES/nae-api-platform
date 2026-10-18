"""Content-versioned URLs keep cached assets aligned with rendered HTML."""
from hashlib import sha256
from pathlib import Path

PROTOTYPE_ROOT = Path(__file__).resolve().parents[2] / "prototype"


def _asset_url(name: str) -> str:
    version = sha256((PROTOTYPE_ROOT / name).read_bytes()).hexdigest()[:12]
    return f"/prototype-assets/{name}?v={version}"


STYLESHEET_URL = _asset_url("styles.css")
MAP_POPUP_URL = _asset_url("map-popup.js")
MAP_TERRITORY_URL = _asset_url("map-territories.js")
