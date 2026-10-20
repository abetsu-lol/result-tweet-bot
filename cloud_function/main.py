from bot.app import run


def daily_job(event, context):
    """Pub/Sub-triggered entry point, invoked daily by Cloud Scheduler (the payload is unused)."""
    return run()
