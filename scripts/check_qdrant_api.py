#!/usr/bin/env python3
"""Quick script to check Qdrant client API methods."""

from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

print("Available methods on QdrantClient:")
methods = [m for m in dir(client) if not m.startswith('_')]
for method in sorted(methods):
    if 'search' in method.lower() or 'query' in method.lower():
        print(f"  ⭐ {method}")
    else:
        print(f"     {method}")

print("\n" + "="*60)
print("Checking for search-related methods:")
print(f"  has 'search': {hasattr(client, 'search')}")
print(f"  has 'query_points': {hasattr(client, 'query_points')}")
print(f"  has 'query': {hasattr(client, 'query')}")

if hasattr(client, 'http'):
    print(f"\nHTTP client methods:")
    http_methods = [m for m in dir(client.http) if not m.startswith('_')]
    for method in sorted(http_methods):
        print(f"     {method}")

