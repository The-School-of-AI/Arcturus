"""
GDPR Session Data Manager: export and delete user session data across all stores.

Covers all 6 data stores that hold session-keyed data:
1. Session files (data/conversation_history/)
2. MongoDB spans (watchtower.spans)
3. Qdrant vectors (filtered by session_id)
4. Neo4J knowledge graph (Session node + connected subgraph)
5. Chronicle checkpoints (memory/chronicle_checkpoints/{session_id}/)
6. MongoDB audit log (entries referencing the session)
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("watchtower.data_manager")

# Default paths
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_CONVERSATION_HISTORY = _DATA_DIR / "conversation_history"
_CHECKPOINT_DIR = Path(__file__).resolve().parent.parent.parent / "memory" / "chronicle_checkpoints"
_EVENTS_DIR = Path(__file__).resolve().parent.parent.parent / "memory" / "chronicle_events"

Collection = Any  # pymongo collection type


class SessionDataManager:
    """Export and delete session data across all Arcturus data stores."""

    def __init__(
        self,
        spans_collection: Optional[Collection] = None,
        audit_collection: Optional[Collection] = None,
        conversation_dir: Optional[Path] = None,
        checkpoint_dir: Optional[Path] = None,
        events_dir: Optional[Path] = None,
    ):
        self._spans_coll = spans_collection
        self._audit_coll = audit_collection
        self._conv_dir = conversation_dir or _CONVERSATION_HISTORY
        self._checkpoint_dir = checkpoint_dir or _CHECKPOINT_DIR
        self._events_dir = events_dir or _EVENTS_DIR

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self, session_id: str) -> Dict[str, Any]:
        """
        Collect all data for a session across all stores.

        Returns a JSON-serializable dict with data from each store.
        Each store operation is wrapped in try/except so partial failures
        don't block the rest.
        """
        result: Dict[str, Any] = {
            "session_id": session_id,
            "exported_at": datetime.utcnow().isoformat(),
            "stores": {},
        }

        # 1. Session files
        result["stores"]["session_files"] = self._export_session_files(session_id)

        # 2. MongoDB spans
        result["stores"]["mongodb_spans"] = self._export_spans(session_id)

        # 3. Qdrant vectors
        result["stores"]["qdrant_vectors"] = self._export_qdrant(session_id)

        # 4. Neo4J knowledge graph
        result["stores"]["neo4j_graph"] = self._export_neo4j(session_id)

        # 5. Chronicle checkpoints
        result["stores"]["chronicle_checkpoints"] = self._export_checkpoints(session_id)

        # 6. Audit log entries
        result["stores"]["audit_log"] = self._export_audit(session_id)

        return result

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, session_id: str) -> Dict[str, Any]:
        """
        Purge all data for a session across all stores.

        Returns a summary dict with counts of what was deleted per store.
        """
        summary: Dict[str, Any] = {
            "session_id": session_id,
            "deleted_at": datetime.utcnow().isoformat(),
            "stores": {},
        }

        summary["stores"]["session_files"] = self._delete_session_files(session_id)
        summary["stores"]["mongodb_spans"] = self._delete_spans(session_id)
        summary["stores"]["qdrant_vectors"] = self._delete_qdrant(session_id)
        summary["stores"]["neo4j_graph"] = self._delete_neo4j(session_id)
        summary["stores"]["chronicle_checkpoints"] = self._delete_checkpoints(session_id)
        summary["stores"]["audit_log"] = self._delete_audit(session_id)

        return summary

    # ------------------------------------------------------------------
    # Store-specific: Session files
    # ------------------------------------------------------------------

    def _find_session_files(self, session_id: str) -> List[Path]:
        """Find all session_*.json files matching this session_id."""
        if not self._conv_dir.exists():
            return []
        return list(self._conv_dir.rglob(f"session_{session_id}.json"))

    def _export_session_files(self, session_id: str) -> Dict[str, Any]:
        try:
            files = self._find_session_files(session_id)
            if not files:
                return {"count": 0, "data": []}
            data = []
            for f in files:
                try:
                    content = json.loads(f.read_text(encoding="utf-8"))
                    data.append({"path": str(f), "content": content})
                except (json.JSONDecodeError, OSError) as e:
                    data.append({"path": str(f), "error": str(e)})
            return {"count": len(files), "data": data}
        except Exception as e:
            logger.warning("Export session files failed: %s", e)
            return {"count": 0, "error": str(e)}

    def _delete_session_files(self, session_id: str) -> Dict[str, Any]:
        try:
            files = self._find_session_files(session_id)
            deleted = 0
            for f in files:
                try:
                    f.unlink()
                    deleted += 1
                except OSError:
                    pass
            return {"deleted": deleted}
        except Exception as e:
            logger.warning("Delete session files failed: %s", e)
            return {"deleted": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Store-specific: MongoDB spans
    # ------------------------------------------------------------------

    def _export_spans(self, session_id: str) -> Dict[str, Any]:
        if not self._spans_coll:
            return {"count": 0, "note": "MongoDB not available"}
        try:
            cursor = self._spans_coll.find(
                {"attributes.session_id": session_id}, {"_id": 0}
            ).sort("start_time", -1).limit(5000)
            spans = []
            for doc in cursor:
                # Convert datetime to ISO string
                for key in ("start_time", "end_time"):
                    if key in doc and isinstance(doc[key], datetime):
                        doc[key] = doc[key].isoformat()
                spans.append(doc)
            return {"count": len(spans), "data": spans}
        except Exception as e:
            logger.warning("Export spans failed: %s", e)
            return {"count": 0, "error": str(e)}

    def _delete_spans(self, session_id: str) -> Dict[str, Any]:
        if not self._spans_coll:
            return {"deleted": 0, "note": "MongoDB not available"}
        try:
            result = self._spans_coll.delete_many({"attributes.session_id": session_id})
            return {"deleted": result.deleted_count}
        except Exception as e:
            logger.warning("Delete spans failed: %s", e)
            return {"deleted": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Store-specific: Qdrant
    # ------------------------------------------------------------------

    def _export_qdrant(self, session_id: str) -> Dict[str, Any]:
        try:
            from memory.backends.qdrant_store import QdrantVectorStore
            store = QdrantVectorStore()
            memories = store.get_all(filter_metadata={"session_id": session_id})
            return {"count": len(memories), "data": memories}
        except ImportError:
            return {"count": 0, "note": "Qdrant client not available"}
        except Exception as e:
            logger.warning("Export Qdrant failed: %s", e)
            return {"count": 0, "error": str(e)}

    def _delete_qdrant(self, session_id: str) -> Dict[str, Any]:
        try:
            from memory.backends.qdrant_store import QdrantVectorStore
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            store = QdrantVectorStore()
            # First get IDs to count, then delete
            memories = store.get_all(filter_metadata={"session_id": session_id})
            if not memories:
                return {"deleted": 0}
            point_ids = [m["id"] for m in memories]
            store.client.delete(
                collection_name=store.collection_name,
                points_selector=point_ids,
            )
            return {"deleted": len(point_ids)}
        except ImportError:
            return {"deleted": 0, "note": "Qdrant client not available"}
        except Exception as e:
            logger.warning("Delete Qdrant failed: %s", e)
            return {"deleted": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Store-specific: Neo4J
    # ------------------------------------------------------------------

    def _export_neo4j(self, session_id: str) -> Dict[str, Any]:
        try:
            from memory.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            if not kg or not kg.enabled:
                return {"count": 0, "note": "Knowledge graph not enabled"}
            # Query session node and connected memories/entities
            with kg._driver.session() as neo_session:
                result = neo_session.run(
                    """
                    MATCH (s:Session {session_id: $session_id})
                    OPTIONAL MATCH (s)-[r]->(n)
                    RETURN s, collect({rel: type(r), node_labels: labels(n), node_props: properties(n)}) as connected
                    """,
                    session_id=session_id,
                )
                record = result.single()
                if not record:
                    return {"count": 0, "data": None}
                session_props = dict(record["s"]) if record["s"] else {}
                connected = record["connected"] or []
                return {
                    "count": 1 + len(connected),
                    "data": {"session": session_props, "connected": connected},
                }
        except ImportError:
            return {"count": 0, "note": "Neo4J driver not available"}
        except Exception as e:
            logger.warning("Export Neo4J failed: %s", e)
            return {"count": 0, "error": str(e)}

    def _delete_neo4j(self, session_id: str) -> Dict[str, Any]:
        try:
            from memory.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            if not kg or not kg.enabled:
                return {"deleted": 0, "note": "Knowledge graph not enabled"}
            with kg._driver.session() as neo_session:
                # Delete session node and all directly connected relationships
                result = neo_session.run(
                    """
                    MATCH (s:Session {session_id: $session_id})
                    OPTIONAL MATCH (s)-[r]-()
                    DELETE r, s
                    RETURN count(r) as rels_deleted
                    """,
                    session_id=session_id,
                )
                record = result.single()
                rels = record["rels_deleted"] if record else 0
                return {"deleted": 1, "relationships_deleted": rels}
        except ImportError:
            return {"deleted": 0, "note": "Neo4J driver not available"}
        except Exception as e:
            logger.warning("Delete Neo4J failed: %s", e)
            return {"deleted": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Store-specific: Chronicle checkpoints
    # ------------------------------------------------------------------

    def _export_checkpoints(self, session_id: str) -> Dict[str, Any]:
        try:
            cp_dir = self._checkpoint_dir / session_id
            ev_file = self._events_dir / f"events_{session_id}.ndjson"
            data: Dict[str, Any] = {"checkpoints": [], "events": []}

            if cp_dir.exists():
                for f in cp_dir.glob("checkpoint_*.json"):
                    try:
                        data["checkpoints"].append(json.loads(f.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError):
                        pass

            if ev_file.exists():
                for line in ev_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            data["events"].append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            count = len(data["checkpoints"]) + len(data["events"])
            return {"count": count, "data": data}
        except Exception as e:
            logger.warning("Export checkpoints failed: %s", e)
            return {"count": 0, "error": str(e)}

    def _delete_checkpoints(self, session_id: str) -> Dict[str, Any]:
        try:
            deleted = 0
            cp_dir = self._checkpoint_dir / session_id
            if cp_dir.exists():
                file_count = sum(1 for _ in cp_dir.rglob("*") if _.is_file())
                shutil.rmtree(cp_dir)
                deleted += file_count

            ev_file = self._events_dir / f"events_{session_id}.ndjson"
            if ev_file.exists():
                ev_file.unlink()
                deleted += 1

            return {"deleted": deleted}
        except Exception as e:
            logger.warning("Delete checkpoints failed: %s", e)
            return {"deleted": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Store-specific: Audit log
    # ------------------------------------------------------------------

    def _export_audit(self, session_id: str) -> Dict[str, Any]:
        if not self._audit_coll:
            return {"count": 0, "note": "Audit collection not available"}
        try:
            cursor = self._audit_coll.find(
                {"resource": {"$regex": session_id}}, {"_id": 0}
            ).sort("timestamp", -1).limit(1000)
            entries = []
            for doc in cursor:
                if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                    doc["timestamp"] = doc["timestamp"].isoformat()
                entries.append(doc)
            return {"count": len(entries), "data": entries}
        except Exception as e:
            logger.warning("Export audit failed: %s", e)
            return {"count": 0, "error": str(e)}

    def _delete_audit(self, session_id: str) -> Dict[str, Any]:
        if not self._audit_coll:
            return {"deleted": 0, "note": "Audit collection not available"}
        try:
            result = self._audit_coll.delete_many({"resource": {"$regex": session_id}})
            return {"deleted": result.deleted_count}
        except Exception as e:
            logger.warning("Delete audit failed: %s", e)
            return {"deleted": 0, "error": str(e)}
