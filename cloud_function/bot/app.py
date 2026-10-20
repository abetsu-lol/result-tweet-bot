"""One daily run: for each account, collect its new games, then post them when due."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache

from . import collect, config, gcp, publish
from .ddragon import DataDragon
from .riot import RiotClient
from .x import XClient


def log(severity, message, **fields):
    """Structured log line (Cloud Logging reads severity from JSON on stdout). Never pass secrets."""
    print(json.dumps({"severity": severity, "message": message, **fields}, ensure_ascii=False), flush=True)


def run(now=None, *, env=None, session=None, riot=None, champions=None, x_client_factory=None):
    now = now or datetime.now(timezone.utc)
    settings = config.Settings.from_env(env) if env is not None else config.Settings.from_env()
    session = session or gcp.authorized_session()
    secrets = gcp.SecretStore(session)
    bucket = gcp.Bucket(session, settings.data_bucket)

    accounts = config.parse_accounts(secrets.latest(settings.secret_accounts))
    riot = riot or RiotClient(secrets.latest(settings.secret_riot_api_key))
    champions = champions or DataDragon()

    @lru_cache(maxsize=1)
    def x_app_credentials():  # only read when actually posting
        return config.parse_x_app_credentials(secrets.latest(settings.secret_x_app_credentials))

    x_client_factory = x_client_factory or (lambda account: XClient(x_app_credentials(), account.x))
    log("INFO", "run started", accounts=len(accounts), dry_run=settings.dry_run,
        post_schedule=settings.post_schedule, post_format=settings.post_format, post_layout=settings.post_layout)

    failed = []
    for account in accounts:
        step = "collection"
        try:  # one account's failure must not stop the others
            log("INFO", "collected", **asdict(collect.collect(account, riot, bucket, now)))
            step = "publishing"
            log("INFO", "published", **asdict(
                publish.publish(account, settings, bucket, champions, x_client_factory, now)))
        except Exception as error:
            failed.append(account.id)
            log("ERROR", f"{step} failed", account_id=account.id, error=f"{type(error).__name__}: {error}")

    if failed:
        raise RuntimeError(f"run failed for: {', '.join(failed)}")
    return "ok"
