"""Settings from environment variables and the account sets from Secret Manager."""
import json
import os
import re
from dataclasses import dataclass

# Riot platform (server) -> regional routing value for account-v1 / match-v5
PLATFORM_REGIONS = {
    "br1": "americas", "la1": "americas", "la2": "americas", "na1": "americas",
    "eun1": "europe", "euw1": "europe", "me1": "europe", "ru": "europe", "tr1": "europe",
    "jp1": "asia", "kr": "asia",
    "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea",
}

POST_SCHEDULES = re.compile(r"daily|weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)")


class ConfigError(Exception):
    """Invalid configuration. Messages never contain secret values."""


@dataclass(frozen=True)
class Settings:
    data_bucket: str
    secret_riot_api_key: str
    secret_x_app_credentials: str
    secret_accounts: str
    post_schedule: str
    post_format: str
    post_layout: str
    dry_run: bool

    @classmethod
    def from_env(cls, env=os.environ):
        missing = [k for k in ("DATA_BUCKET", "SECRET_RIOT_API_KEY", "SECRET_X_APP_CREDENTIALS", "SECRET_ACCOUNTS")
                   if not env.get(k)]
        if missing:
            raise ConfigError(f"missing environment variables: {', '.join(missing)}")
        settings = cls(
            data_bucket=env["DATA_BUCKET"],
            secret_riot_api_key=env["SECRET_RIOT_API_KEY"],
            secret_x_app_credentials=env["SECRET_X_APP_CREDENTIALS"],
            secret_accounts=env["SECRET_ACCOUNTS"],
            post_schedule=env.get("POST_SCHEDULE", "daily"),
            post_format=env.get("POST_FORMAT", "image"),
            post_layout=env.get("POST_LAYOUT", "per_game"),
            # Anything but an explicit "false" keeps posting off
            dry_run=env.get("DRY_RUN", "true").lower() != "false",
        )
        if not POST_SCHEDULES.fullmatch(settings.post_schedule):
            raise ConfigError("POST_SCHEDULE must be daily or weekly:<MON..SUN>")
        if settings.post_format not in ("image", "text"):
            raise ConfigError("POST_FORMAT must be image or text")
        if settings.post_layout not in ("per_game", "summary"):
            raise ConfigError("POST_LAYOUT must be per_game or summary")
        return settings


@dataclass(frozen=True)
class RiotAccount:
    game_name: str
    tag_line: str
    platform: str
    region: str


@dataclass(frozen=True)
class XAccount:
    access_token: str
    access_token_secret: str
    root_post_id: str

    def __repr__(self):  # keep tokens out of logs and tracebacks
        return f"XAccount(root_post_id={self.root_post_id!r})"


@dataclass(frozen=True)
class Account:
    id: str
    riot: RiotAccount
    x: XAccount


def parse_x_app_credentials(raw):
    """Parses X_APP_CREDENTIALS ({"consumer_key", "consumer_secret"}) without echoing values."""
    try:
        creds = json.loads(raw)
    except ValueError:
        raise ConfigError("x-app-credentials is not valid JSON") from None
    for key in ("consumer_key", "consumer_secret"):
        if not isinstance(creds, dict) or not isinstance(creds.get(key), str) or not creds[key].strip():
            raise ConfigError(f"x-app-credentials.{key} is missing")
    return {"consumer_key": creds["consumer_key"].strip(), "consumer_secret": creds["consumer_secret"].strip()}


def parse_accounts(raw):
    """Parses the ACCOUNTS JSON. Errors name the offending item, never its value."""
    try:
        items = json.loads(raw)
    except ValueError:
        raise ConfigError("accounts is not valid JSON") from None
    if not isinstance(items, list) or not items:
        raise ConfigError("accounts must be a non-empty array")

    accounts, seen = [], set()
    for i, item in enumerate(items):
        where = f"accounts[{i}]"

        def text(obj, key, path):
            value = obj.get(key) if isinstance(obj, dict) else None
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"{where}.{path}{key} is missing")
            return value.strip()

        account_id = text(item, "id", "")
        if not re.fullmatch(r"[a-z0-9-]+", account_id):
            raise ConfigError(f"{where}.id must contain only a-z, 0-9 and -")
        if account_id in seen:
            raise ConfigError(f"{where}.id is duplicated")
        seen.add(account_id)

        riot, x = item.get("riot"), item.get("x")
        platform = text(riot, "platform", "riot.")
        if platform not in PLATFORM_REGIONS:
            raise ConfigError(f"{where}.riot.platform is unknown")
        region = riot.get("region") or PLATFORM_REGIONS[platform]
        root_post_id = text(x, "root_post_id", "x.")
        if not root_post_id.isdigit():
            raise ConfigError(f"{where}.x.root_post_id is not a numeric post id")

        accounts.append(Account(
            id=account_id,
            riot=RiotAccount(text(riot, "game_name", "riot."), text(riot, "tag_line", "riot.").lstrip("#"),
                             platform, region),
            x=XAccount(text(x, "access_token", "x."), text(x, "access_token_secret", "x."), root_post_id),
        ))
    return accounts
