# P15 Gateway TypeScript SDK (In-Repo)

## What It Provides
- Typed client wrapper for core `/api/v1` routes.
- Automatic `Idempotency-Key` for mutating operations.
- Structured error type (`GatewayApiError`).
- Header metadata extraction for usage/rate-limit/idempotency headers.

## Quick Usage
```ts
import { GatewayClient } from "./src";

const client = new GatewayClient({
  baseUrl: "http://127.0.0.1:8000",
  apiKey: process.env.ARCTURUS_GATEWAY_API_KEY,
});

const search = await client.search("gateway sdk");
console.log(search.body);

const page = await client.pagesGenerate("Q2 plan", "overview");
console.log(page.metadata.idempotencyStatus);
```

## Example Script
See [examples/basic_usage.ts](/Users/kushagara/Arcturus/api/sdks/typescript/examples/basic_usage.ts).
