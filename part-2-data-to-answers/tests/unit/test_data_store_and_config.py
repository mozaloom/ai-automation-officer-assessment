import io

from botocore.stub import Stubber
import boto3

from config import DEFAULT_MODEL_ID, Settings
from tools.availability import DataStore, local_loader, s3_loader, store_from_settings


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_store_caches_until_ttl(csv_text):
    calls, clock = [], Clock()
    store = DataStore(lambda: calls.append(1) or csv_text, ttl_seconds=60, clock=clock)
    first = store.get()
    assert store.get() is first and len(calls) == 1
    clock.now = 61
    assert store.get() is not first and len(calls) == 2


def test_store_serves_stale_data_when_reload_fails(csv_text):
    clock, ok = Clock(), {"fail": False}

    def loader():
        if ok["fail"]:
            raise OSError("s3 unavailable")
        return csv_text

    store = DataStore(loader, ttl_seconds=10, clock=clock)
    first = store.get()
    ok["fail"], clock.now = True, 11
    assert store.get() is first  # stale but available


def test_store_raises_when_first_load_fails():
    store = DataStore(lambda: (_ for _ in ()).throw(OSError("boom")))
    try:
        store.get()
    except OSError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected OSError")


def test_s3_loader_reads_the_object(csv_text):
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    with Stubber(client) as stub:
        stub.add_response("get_object", {"Body": _body(csv_text)}, {"Bucket": "bkt", "Key": "pos.csv"})
        assert s3_loader("bkt", "pos.csv", client)().startswith("store_id")


def _body(text):
    from botocore.response import StreamingBody

    raw = text.encode()
    return StreamingBody(io.BytesIO(raw), len(raw))


def test_local_loader_and_settings_choose_source(csv_text, tmp_path):
    path = tmp_path / "pos.csv"
    path.write_text(csv_text, encoding="utf-8")
    assert local_loader(path)().startswith("store_id")
    assert len(store_from_settings(Settings(data_path=path)).get().records) == 936


def test_settings_defaults_and_env_overrides():
    assert Settings.from_env({}).model_id == DEFAULT_MODEL_ID
    env = {"BEDROCK_MODEL_ID": "m", "DATA_S3_BUCKET": "b", "MAX_RECORDS": "7", "LOG_LEVEL": "debug", "AWS_REGION": "eu-west-1"}
    s = Settings.from_env(env)
    assert (s.model_id, s.data_bucket, s.max_records, s.log_level, s.region) == ("m", "b", 7, "DEBUG", "eu-west-1")
