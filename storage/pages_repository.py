"""
MongoDB repository for Spark Pages (P03).

Stores page metadata, sections, and collections in watchtower.spark_pages.
Supports CRUD operations, search, folders, tags, version history, and collaboration.
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

Collection = Any  # pymongo collection type


class PagesRepository:
    """MongoDB persistence for Spark Pages."""

    _indexes_ensured: bool = False

    def __init__(self, collection: Collection):
        self._coll = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient querying."""
        if PagesRepository._indexes_ensured:
            return
        try:
            # Primary indexes
            self._coll.create_index([("id", 1)], unique=True)
            self._coll.create_index([("created_at", -1)])
            self._coll.create_index([("created_by", 1), ("created_at", -1)])
            
            # Search and filtering indexes
            self._coll.create_index([("query", "text"), ("title", "text")])
            self._coll.create_index([("template", 1)])
            self._coll.create_index([("status", 1)])
            self._coll.create_index([("folder_id", 1)])
            self._coll.create_index([("tags", 1)])
            
            # Collaboration indexes
            self._coll.create_index([("shared_with", 1)])
            self._coll.create_index([("deleted", 1), ("created_at", -1)])
            
            PagesRepository._indexes_ensured = True
        except Exception as e:
            # Indexes might already exist
            if "already exists" not in str(e).lower():
                print(f"[PagesRepository] Warning: Failed to create indexes: {e}")

    def save_page(self, page: Dict[str, Any]) -> str:
        """
        Save a new page or update existing one.
        
        Args:
            page: Page document with id, title, query, template, sections, etc.
            
        Returns:
            Page ID
        """
        page_id = page.get("id")
        if not page_id:
            raise ValueError("Page must have an 'id' field")
        
        # Add timestamps
        now = datetime.utcnow()
        if "created_at" not in page:
            page["created_at"] = now
        page["updated_at"] = now
        
        # Ensure deleted flag exists
        if "deleted" not in page:
            page["deleted"] = False
        
        # Store datetime objects for MongoDB
        if isinstance(page.get("created_at"), str):
            try:
                page["created_at"] = datetime.fromisoformat(page["created_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                page["created_at"] = now
        
        # Upsert (insert or update)
        self._coll.update_one(
            {"id": page_id},
            {"$set": page},
            upsert=True
        )
        
        return page_id

    def get_page(self, page_id: str, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single page by ID.
        
        Args:
            page_id: Page identifier
            include_deleted: If False, returns None for deleted pages
            
        Returns:
            Page document or None if not found
        """
        query: Dict[str, Any] = {"id": page_id}
        if not include_deleted:
            query["deleted"] = {"$ne": True}
        
        page = self._coll.find_one(query, {"_id": 0})
        if page:
            self._normalize_timestamps(page)
        return page

    def get_pages(
        self,
        created_by: Optional[str] = None,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        template: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Query pages with various filters.
        
        Args:
            created_by: Filter by creator
            folder_id: Filter by folder/collection
            tags: Filter by tags (matches any)
            template: Filter by template type
            status: Filter by status
            search_query: Text search in query/title
            limit: Maximum results to return
            skip: Number of results to skip (for pagination)
            include_deleted: Include deleted pages
            
        Returns:
            List of page documents
        """
        query: Dict[str, Any] = {}
        
        if not include_deleted:
            query["deleted"] = {"$ne": True}
        
        if created_by:
            query["created_by"] = created_by
        
        if folder_id:
            query["folder_id"] = folder_id
        
        if tags:
            query["tags"] = {"$in": tags}
        
        if template:
            query["template"] = template
        
        if status:
            query["status"] = status
        
        if search_query:
            query["$text"] = {"$search": search_query}
        
        cursor = (
            self._coll.find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        
        pages = []
        for page in cursor:
            self._normalize_timestamps(page)
            pages.append(page)
        
        return pages

    def count_pages(
        self,
        created_by: Optional[str] = None,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        include_deleted: bool = False
    ) -> int:
        """Count pages matching filters."""
        query: Dict[str, Any] = {}
        
        if not include_deleted:
            query["deleted"] = {"$ne": True}
        
        if created_by:
            query["created_by"] = created_by
        
        if folder_id:
            query["folder_id"] = folder_id
        
        if tags:
            query["tags"] = {"$in": tags}
        
        return self._coll.count_documents(query)

    def delete_page(self, page_id: str, hard_delete: bool = False) -> bool:
        """
        Delete a page (soft delete by default, or permanent removal).
        
        Args:
            page_id: Page identifier
            hard_delete: If True, permanently removes from database
            
        Returns:
            True if page was deleted, False if not found
        """
        if hard_delete:
            result = self._coll.delete_one({"id": page_id})
            return result.deleted_count > 0
        else:
            # Soft delete - just mark as deleted
            result = self._coll.update_one(
                {"id": page_id},
                {"$set": {"deleted": True, "deleted_at": datetime.utcnow()}}
            )
            return result.modified_count > 0

    def update_page_metadata(
        self,
        page_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update specific fields of a page.
        
        Args:
            page_id: Page identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if page was updated, False if not found
        """
        # Prevent overwriting critical fields
        forbidden = {"id", "created_at"}
        updates = {k: v for k, v in updates.items() if k not in forbidden}
        
        if not updates:
            return False
        
        updates["updated_at"] = datetime.utcnow()
        
        result = self._coll.update_one(
            {"id": page_id, "deleted": {"$ne": True}},
            {"$set": updates}
        )
        
        return result.modified_count > 0

    def add_version(self, page_id: str, version: Dict[str, Any]) -> bool:
        """
        Add a version to page's version history.
        
        Args:
            page_id: Page identifier
            version: Version metadata dict
            
        Returns:
            True if version was added
        """
        if "timestamp" not in version:
            version["timestamp"] = datetime.utcnow()
        
        result = self._coll.update_one(
            {"id": page_id, "deleted": {"$ne": True}},
            {
                "$push": {"metadata.versions": version},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0

    def add_comment(self, page_id: str, comment: Dict[str, Any]) -> bool:
        """
        Add a comment to a page.
        
        Args:
            page_id: Page identifier
            comment: Comment dict with user, text, timestamp
            
        Returns:
            True if comment was added
        """
        if "timestamp" not in comment:
            comment["timestamp"] = datetime.utcnow()
        
        result = self._coll.update_one(
            {"id": page_id, "deleted": {"$ne": True}},
            {
                "$push": {"comments": comment},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0

    def share_page(
        self,
        page_id: str,
        user_id: str,
        permission: str = "view"
    ) -> bool:
        """
        Share page with a user.
        
        Args:
            page_id: Page identifier
            user_id: User to share with
            permission: 'view' or 'edit'
            
        Returns:
            True if page was shared
        """
        share_entry = {
            "user_id": user_id,
            "permission": permission,
            "shared_at": datetime.utcnow()
        }
        
        result = self._coll.update_one(
            {"id": page_id, "deleted": {"$ne": True}},
            {
                "$addToSet": {"shared_with": share_entry},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all non-deleted pages."""
        tags = self._coll.distinct("tags", {"deleted": {"$ne": True}})
        return sorted(tags)

    def get_all_folders(self) -> List[str]:
        """Get all unique folder IDs across all non-deleted pages."""
        folders = self._coll.distinct("folder_id", {"deleted": {"$ne": True}})
        return [f for f in folders if f]  # Filter out None/empty

    @staticmethod
    def _normalize_timestamps(page: Dict[str, Any]) -> None:
        """Convert datetime objects to ISO strings for JSON serialization."""
        for field in ["created_at", "updated_at", "deleted_at"]:
            if field in page and isinstance(page[field], datetime):
                page[field] = page[field].isoformat() + "Z"
        
        # Normalize timestamps in nested structures
        if "metadata" in page and "versions" in page["metadata"]:
            for version in page["metadata"]["versions"]:
                if "timestamp" in version and isinstance(version["timestamp"], datetime):
                    version["timestamp"] = version["timestamp"].isoformat() + "Z"
        
        if "comments" in page:
            for comment in page["comments"]:
                if "timestamp" in comment and isinstance(comment["timestamp"], datetime):
                    comment["timestamp"] = comment["timestamp"].isoformat() + "Z"


def get_pages_repository() -> Optional[PagesRepository]:
    """
    Get PagesRepository instance connected to MongoDB.
    
    Returns:
        PagesRepository instance, or None if MongoDB is unavailable
    """
    try:
        from pymongo import MongoClient

        from config.settings_loader import settings
        
        wt = settings.get("watchtower", {})
        uri = wt.get("mongodb_uri", "mongodb://localhost:27017")
        
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        db = client["watchtower"]
        collection = db["spark_pages"]
        
        return PagesRepository(collection)
    except Exception as e:
        print(f"[PagesRepository] Failed to connect to MongoDB: {e}")
        return None
