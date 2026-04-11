import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def _request(url: str, method: str = "GET", payload: dict = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def upsert_connector(connect_url: str, connector_payload: dict):
    name = connector_payload["name"]
    config = connector_payload["config"]
    config_url = f"{connect_url}/connectors/{name}/config"

    try:
        status, body = _request(config_url, method="PUT", payload=config)
        print(f"Connector upserted (status={status}): {name}")
        print(body)
    except urllib.error.HTTPError as exc:
        print(f"Failed to upsert connector: {exc}")
        detail = exc.read().decode("utf-8") if exc.fp else ""
        if detail:
            print(detail)
        raise


def main():
    parser = argparse.ArgumentParser(description="Register Debezium connector config")
    parser.add_argument(
        "--connect-url",
        default="http://localhost:8083",
        help="Kafka Connect REST URL",
    )
    parser.add_argument(
        "--config-path",
        default="infra/cdc/connectors/debezium-connector.json",
        help="Path to connector JSON config",
    )
    args = parser.parse_args()

    config_path = Path(args.config_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    upsert_connector(args.connect_url.rstrip("/"), payload)


if __name__ == "__main__":
    main()
