"""Fixed local defaults with no secrets."""

from .expression_catalog import CANONICAL_CUE_CATALOG_ID

APP_VERSION = "0.6.2"
HEA_ENDPOINT = "https://hea-world.com/api/reachymini/chat"
HEA_DIRECTORY_URL = "https://cdn.hea-world.com/heas/prod/hea_directory.json"
HEA_CREATOR_ID = "hea-world"
HEA_ID = "heaguide-web-001"
HEA_BEHAVIOR_CATALOG_ID = "default"
CUE_CATALOG_ID = CANONICAL_CUE_CATALOG_ID
# Production and app now share the same canonical 24-cue contract. Legacy
# aliases remain server-side for already-installed 0.3 clients.
CUE_SET_VERSION = CUE_CATALOG_ID

MAX_USER_INPUT_CHARS = 6_000
MAX_ANSWER_CHARS = 24_000
MAX_SSE_FRAME_BYTES = 32_768
MAX_SSE_EVENTS = 256
MAX_SENTENCES = 8
MAX_TURN_SECONDS = 90.0
HEA_DIRECTORY_MAX_BYTES = 2_000_000
HEA_DIRECTORY_MAX_ENTRIES = 1_000

SPEECH_RATE_WPM = 185
MAX_SPEECH_SENTENCE_CHARS = 1_500
MAX_SPEECH_SENTENCE_SECONDS = 15.0
MAX_SPEECH_TURN_SECONDS = 45.0
MAX_SPEECH_SYNTHESIS_SECONDS = 8.0
MAX_SPEECH_BYTES = 2_000_000
