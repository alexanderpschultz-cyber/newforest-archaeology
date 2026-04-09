from pathlib import Path

# Paths
DATA_DIR = Path.home() / "NewForest"
PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "detections.db"
OUTPUT_DIR = PROJECT_DIR / "output"
COMPOSITES_DIR = PROJECT_DIR / "composites"

# Layer directories
LAYERS = {
    "slope": DATA_DIR / "slope",
    "LRM": DATA_DIR / "LRM",
    "multiHS": DATA_DIR / "multiHS",
    "openpos": DATA_DIR / "openpos",
    "CVAT": DATA_DIR / "CVAT",
}

# Layer file suffixes (as they appear in filenames)
LAYER_SUFFIXES = {
    "slope": "",
    "LRM": "_LRM",
    "multiHS": "_MultiHS",
    "openpos": "_openpos",
    "CVAT": "_CVAT",
}

# Patch generation
PATCH_SIZE = 512
PATCH_OVERLAP = 64

# Ollama
OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "gemma4:26b"
REQUEST_DELAY_SECONDS = 5  # pause between Ollama requests to not starve security camera queue

# Detection prompts — kept short because Gemma 4 returns empty with long prompts + images
COARSE_PROMPT = """LIDAR slope image of 1km tile, New Forest UK. Brighter=steeper. Any archaeological features (barrows, enclosures, trackways, earthworks, field systems)? JSON: {"has_features": true/false, "summary": "...", "regions_of_interest": ["..."]}"""

FINE_PROMPT = """LIDAR slope image, New Forest UK. Brighter=steeper. List archaeological features (barrows, enclosures, trackways, earthworks, field systems, platforms, hearths). JSON only: {"features": [{"type": "", "confidence": "high/medium/low", "x_percent": 0, "y_percent": 0, "description": ""}]}. If none: {"features": []}"""
