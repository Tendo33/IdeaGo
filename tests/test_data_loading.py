import json

from ideago.utils import read_json


def test_load_data_file(tmp_path) -> None:
    data_file_path = tmp_path / "test.json"
    payload = {"name": "test_data", "value": 123}
    data_file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with open(data_file_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["name"] == "test_data"

    data_sdk = read_json(data_file_path)
    assert data_sdk is not None
    assert data_sdk["value"] == 123
