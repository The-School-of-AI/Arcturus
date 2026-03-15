from __future__ import annotations

import os

from gateway_sdk import GatewayClient


def main() -> None:
    base_url = os.getenv("ARCTURUS_GATEWAY_BASE_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("ARCTURUS_GATEWAY_API_KEY", "")

    if not api_key:
        raise SystemExit("Set ARCTURUS_GATEWAY_API_KEY before running this example")

    with GatewayClient(base_url=base_url, api_key=api_key) as client:
        search = client.search("gateway sdk example")
        print("search_status=", search.status_code)
        print("citations=", search.body.get("citations", []))

        page = client.pages_generate("SDK demo page", template="overview")
        print("page_id=", page.body.get("page_id"))
        print("idempotency_status=", page.metadata.idempotency_status)


if __name__ == "__main__":
    main()
