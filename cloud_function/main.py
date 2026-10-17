import base64

def daily_job(event, context):
    """Pub/Sub トリガーで起動される Cloud Function のエントリポイント。

    Args:
      event (dict): イベントのペイロード。`event['data']` がある場合は base64 エンコードされた文字列。
      context: イベントのメタデータ。
    """
    payload = ""
    if event and 'data' in event:
        try:
            payload = base64.b64decode(event['data']).decode('utf-8')
        except Exception:
            payload = str(event['data'])
    print("Running daily job. payload=", payload)
    # TODO: ここに処理を実装する
    return 'ok'
