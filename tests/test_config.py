import json

import pytest

from bot import config

ENV = {
    "DATA_BUCKET": "bucket", "SECRET_RIOT_API_KEY": "projects/p/secrets/riot-api-key",
    "SECRET_X_APP_CREDENTIALS": "projects/p/secrets/x-app-credentials", "SECRET_ACCOUNTS": "projects/p/secrets/accounts",
}


def account(**overrides):
    item = {
        "id": "main",
        "riot": {"game_name": "名前", "tag_line": "JP1", "platform": "jp1"},
        "x": {"access_token": "at-secret", "access_token_secret": "ats-secret", "root_post_id": "2112236264892313956"},
    }
    item.update(overrides)
    return item


def test_settings_defaults_keep_posting_off():
    settings = config.Settings.from_env(ENV)
    assert settings.dry_run is True
    assert (settings.post_schedule, settings.post_format, settings.post_layout) == ("daily", "image", "per_game")
    assert config.Settings.from_env({**ENV, "DRY_RUN": "false"}).dry_run is False


@pytest.mark.parametrize("key,value", [("POST_SCHEDULE", "monthly"), ("POST_SCHEDULE", "weekly:XYZ"),
                                       ("POST_FORMAT", "video"), ("POST_LAYOUT", "grid")])
def test_settings_reject_unknown_post_options(key, value):
    with pytest.raises(config.ConfigError):
        config.Settings.from_env({**ENV, key: value})


def test_settings_require_resource_names():
    with pytest.raises(config.ConfigError, match="DATA_BUCKET"):
        config.Settings.from_env({k: v for k, v in ENV.items() if k != "DATA_BUCKET"})


def test_accounts_parse_and_derive_region():
    [parsed] = config.parse_accounts(json.dumps([account()]))
    assert parsed.riot.region == "asia"
    assert parsed.riot.game_name == "名前"
    assert parsed.x.root_post_id == "2112236264892313956"


def test_account_repr_hides_tokens():
    [parsed] = config.parse_accounts(json.dumps([account()]))
    assert "secret" not in repr(parsed)


@pytest.mark.parametrize("item,message", [
    (account(id="Main"), "id must contain"),
    (account(riot={"game_name": "a", "tag_line": "b", "platform": "xx1"}), "platform is unknown"),
    (account(x={"access_token": "a", "access_token_secret": "b", "root_post_id": "abc"}), "root_post_id"),
    (account(x={"access_token": "a", "root_post_id": "1"}), "access_token_secret is missing"),
])
def test_accounts_errors_name_the_field_without_values(item, message):
    with pytest.raises(config.ConfigError, match=message) as error:
        config.parse_accounts(json.dumps([item]))
    assert "secret" not in str(error.value).replace("access_token_secret", "")


def test_accounts_reject_duplicates_and_empty():
    with pytest.raises(config.ConfigError, match="duplicated"):
        config.parse_accounts(json.dumps([account(), account()]))
    with pytest.raises(config.ConfigError, match="non-empty"):
        config.parse_accounts("[]")


def test_accounts_reject_invalid_json():
    with pytest.raises(config.ConfigError, match="not valid JSON"):
        config.parse_accounts("{not json")


def test_explicit_region_wins_and_tag_hash_is_stripped():
    [parsed] = config.parse_accounts(json.dumps([account(
        riot={"game_name": "a", "tag_line": "#JP1", "platform": "jp1", "region": "sea"})]))
    assert (parsed.riot.region, parsed.riot.tag_line) == ("sea", "JP1")
