#!/usr/bin/env python3
"""
Orchestrate all migrations for Arcturus:

1. FAISS memories → Qdrant memories
2. RAG FAISS index → Qdrant RAG chunks
3. Qdrant memories → Neo4j knowledge graph
4. JSON hubs → Neo4j Fact/Evidence

Usage:
    # Default mode is "docker"
    uv run python scripts/migrate_all_memories.py
    uv run python scripts/migrate_all_memories.py docker
    uv run python scripts/migrate_all_memories.py cloud

Modes:
    - docker (default):
        * Runs `docker-compose up -d`
        * Optionally appends Qdrant + Neo4j + MNEMO_ENABLED=true to .env
        * Then runs all migrations in order

    - cloud:
        * Asks you to create Qdrant + Neo4j cloud accounts
          and configure the corresponding variables in .env (including MNEMO_ENABLED=true)
        * Once you confirm, runs all migrations in order
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent.resolve()


def run_command(cmd: list[str], cwd: Path | None = None) -> int:
    """Run a shell command and stream output."""
    print(f"\n$ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT),
            check=False,
        )
        if result.returncode != 0:
            print(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")
        return result.returncode
    except FileNotFoundError as e:
        print(f"Command not found: {cmd[0]} ({e})")
        return 1


def ensure_docker_services() -> bool:
    """Ensure Docker services are up via docker-compose."""
    print("=" * 60)
    print("Ensuring Docker services are running (docker-compose up -d)")
    print("=" * 60)
    code = run_command(["docker-compose", "up", "-d"], cwd=ROOT)
    if code != 0:
        print(
            "\nFailed to start Docker services with docker-compose. "
            "Please ensure Docker is installed and docker-compose is available."
        )
        return False
    print("\n✓ Docker services are up.")
    return True


def append_env_vars_for_docker() -> None:
    """
    Append Qdrant and Neo4j-related variables to .env for local Docker usage.

    Does NOT replace existing variables; simply appends at the end of the file
    after confirming with the user.
    """
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"\n.env file not found at {env_path}. Skipping env var append.")
        return

    docker_env_lines = [
        "",
        "# --- Added by migrate_all_memories.py (docker mode) ---",
        "VECTOR_STORE_PROVIDER=qdrant",
        "RAG_VECTOR_STORE_PROVIDER=qdrant",
        "EPISODIC_STORE_PROVIDER=qdrant",
        "QDRANT_URL=http://localhost:6333",
        "# QDRANT_API_KEY=your-local-or-cloud-api-key-if-needed",
        "NEO4J_ENABLED=true",
        "NEO4J_URI=bolt://localhost:7687",
        "NEO4J_USER=neo4j",
        "NEO4J_PASSWORD=arcturus-neo4j",
        "MNEMO_ENABLED=true",
        "VITE_ENABLE_LOCAL_MIGRATION=true",
        "# --- End migrate_all_memories.py section ---",
        "",
    ]

    print("\nThe following Qdrant/Neo4j/Mnemo variables can be appended to your .env:")
    print("-" * 60)
    for line in docker_env_lines:
        print(line)
    print("-" * 60)

    answer = input("Append these lines to .env? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Skipping .env modifications.")
        return

    try:
        with env_path.open("a", encoding="utf-8") as f:
            for line in docker_env_lines:
                f.write(line + "\n" if not line.endswith("\n") else line)
        print(f"\n✓ Appended Qdrant/Neo4j/Mnemo variables to {env_path}")
    except Exception as e:
        print(f"\nFailed to append to .env: {e}")


def prompt_cloud_setup() -> None:
    """
    Guide user to set up Qdrant and Neo4j cloud and configure .env.
    """
    print("=" * 60)
    print("Cloud mode selected")
    print("=" * 60)
    print(
        "\n1) Create a Qdrant Cloud cluster (or ensure you have one):\n"
        "   - Set the following in your .env:\n"
        "       QDRANT_URL=https://your-cluster.region.cloud.qdrant.io\n"
        "       QDRANT_API_KEY=your-qdrant-api-key\n"
        "       VECTOR_STORE_PROVIDER=qdrant\n"
        "       RAG_VECTOR_STORE_PROVIDER=qdrant\n"
        "       EPISODIC_STORE_PROVIDER=qdrant\n"
    )
    print(
        "2) Create / configure a Neo4j Aura (or self-hosted reachable) instance:\n"
        "   - Set the following in your .env:\n"
        "       NEO4J_ENABLED=true\n"
        "       NEO4J_URI=neo4j+s://your-neo4j-instance.databases.neo4j.io\n"
        "       NEO4J_USER=your-neo4j-username\n"
        "       NEO4J_PASSWORD=your-neo4j-password\n"
    )
    print(
        "3) Enable Mnemo (unified extraction + Fact/Evidence):\n"
        "   - Set in your .env:\n"
        "       MNEMO_ENABLED=true\n"
    )
    print(
        "4) Enable Local Migration:\n"
        "   - Set in your .env:\n"
        "       VITE_ENABLE_LOCAL_MIGRATION=true\n"
    )

    input(
        "Once you've created the accounts and updated .env with the above "
        "variables (including MNEMO_ENABLED=true), press Enter to continue with the migrations..."
    )


def run_migrations_in_order() -> int:
    """
    Run all migrations in the required order.

    1) FAISS → Qdrant (memories)
    2) RAG FAISS → Qdrant (RAG chunks)
    3) Qdrant memories → Neo4j
    4) JSON hubs → Neo4j Fact/Evidence
    """
    print("=" * 60)
    print("Running migrations in order")
    print("=" * 60)

    scripts = [
        "migrate_faiss_to_qdrant.py",
        "migrate_rag_faiss_to_qdrant.py",
        "migrate_episodic_to_qdrant.py",
        "migrate_memories_to_neo4j.py",
        "migrate_hubs_to_neo4j.py",
    ]

    for script_name in scripts:
        script_path = ROOT / "scripts" / script_name
        if not script_path.exists():
            print(f"\nScript not found: {script_path}. Aborting.")
            return 1

        print(f"\n=== Running {script_name} ===")
        code = run_command([sys.executable, str(script_path)], cwd=ROOT)
        if code != 0:
            print(f"\nAborting because {script_name} failed.")
            return code

    print("\n✓ All migrations completed successfully.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all Arcturus memory/RAG/Neo4j migrations in order.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["docker", "cloud"],
        default="docker",
        help='Environment mode: "docker" (default) or "cloud".',
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Ensure we run from project root
    os.chdir(ROOT)

    if args.mode == "docker":
        if not ensure_docker_services():
            return 1
        append_env_vars_for_docker()
    else:
        # cloud mode
        prompt_cloud_setup()

    return run_migrations_in_order()


if __name__ == "__main__":
    raise SystemExit(main())

