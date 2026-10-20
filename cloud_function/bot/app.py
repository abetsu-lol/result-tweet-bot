"""One daily run: collect every account's games; posting is added separately."""
import json
from dataclasses import asdict
from datetime import datetime, timezone

from . import collect, config, gcp
from .riot import RiotClient


def log(severity, message, **fields):
    """Structured log line (Cloud Logging reads severity from JSON on stdout). Never pass secrets."""
    print(json.dumps({"severity": severity, "message": message, **fields}, ensure_ascii=False), flush=True)


def run(now=None, *, env=None, session=None, riot=None):
    now = now or datetime.now(timezone.utc)
    settings = config.Settings.from_env(env) if env is not None else config.Settings.from_env()
    session = session or gcp.authorized_session()
    secrets = gcp.SecretStore(session)
    bucket = gcp.Bucket(session, settings.data_bucket)

    accounts = config.parse_accounts(secrets.latest(settings.secret_accounts))
    riot = riot or RiotClient(secrets.latest(settings.secret_riot_api_key))
    log("INFO", "run started", accounts=len(accounts), dry_run=settings.dry_run,
        post_schedule=settings.post_schedule)

    failed = []
    for account in accounts:
        try:
            result = collect.collect(account, riot, bucket, now)
            log("INFO", "collected", **asdict(result))
        except Exception as error:  # one account's failure must not stop the others
            failed.append(account.id)
            log("ERROR", "collection failed", account_id=account.id, error=f"{type(error).__name__}: {error}")

    if failed:
        raise RuntimeError(f"collection failed for: {', '.join(failed)}")
    return "ok"
