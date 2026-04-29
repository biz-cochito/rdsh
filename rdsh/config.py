import os

BASE_URL = "https://api.real-debrid.com/rest/1.0"
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 120
API_TOKEN_ENV_VAR = "REAL_DEBRID_API_TOKEN"


def get_api_token():
    return os.getenv(API_TOKEN_ENV_VAR)
