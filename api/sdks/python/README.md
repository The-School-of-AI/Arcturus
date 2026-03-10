# P15 Gateway Python SDK (In-Repo)

## What It Provides
- Typed client wrapper for `/api/v1` gateway endpoints.
- Automatic `Idempotency-Key` generation for mutating calls.
- Structured error raising via `GatewayAPIError`.
- Access to gateway response metadata:
  - `X-Idempotency-*`
  - `X-Usage-*`
  - `X-RateLimit-*`

## Quick Usage
```python
from gateway_sdk import GatewayClient

with GatewayClient(base_url="http://127.0.0.1:8000", api_key="<API_KEY>") as client:
    result = client.pages_generate("Q2 planning", template="overview")
    print(result.body)
    print(result.metadata.idempotency_status)
```

## Admin Usage
```python
from gateway_sdk import GatewayClient

with GatewayClient(
    base_url="http://127.0.0.1:8000",
    admin_key="<ARCTURUS_GATEWAY_ADMIN_KEY>",
) as client:
    created = client.admin_create_key({
        "name": "sdk-demo",
        "scopes": ["search:read"],
    })
    print(created.body)
```

## Example Script
See [examples/basic_usage.py](/Users/kushagara/Arcturus/api/sdks/python/examples/basic_usage.py).
