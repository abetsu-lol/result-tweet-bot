import base64

def daily_job(event, context):
    """Pub/Sub-triggered Cloud Function entry point.

    Args:
      event (dict): Event payload. `event['data']` is base64-encoded string if present.
      context: Metadata for the event.
    """
    payload = ""
    if event and 'data' in event:
        try:
            payload = base64.b64decode(event['data']).decode('utf-8')
        except Exception:
            payload = str(event['data'])
    print("Running daily job. payload=", payload)
    # TODO: implement your task here
    return 'ok'
