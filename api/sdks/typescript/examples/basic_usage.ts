import { GatewayClient } from "../src";

async function main() {
  const apiKey = process.env.ARCTURUS_GATEWAY_API_KEY;
  if (!apiKey) {
    throw new Error("Set ARCTURUS_GATEWAY_API_KEY before running this example");
  }

  const client = new GatewayClient({
    baseUrl: process.env.ARCTURUS_GATEWAY_BASE_URL ?? "http://127.0.0.1:8000",
    apiKey,
  });

  const search = await client.search("sdk typescript example");
  console.log("search status", search.statusCode);

  const page = await client.pagesGenerate("Gateway SDK demo", "overview");
  console.log("page metadata", page.metadata);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
