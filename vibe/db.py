"""Simple MongoDB wrapper with safe fallback (in-memory lists) if no MongoDB available."""
from typing import Optional


class MongoClientWrapper:
    def __init__(self, mongo_uri: Optional[str] = None):
        self.mongo_uri = mongo_uri
        self._client = None
        self._db = None
        self._collections = {}
        self._available = False
        if mongo_uri:
            try:
                from pymongo import MongoClient
                self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                # trigger server selection
                self._client.server_info()
                self._db = self._client.get_database('vibemind_db')
                self._available = True
            except Exception:
                self._available = False

    def get_collection(self, name: str):
        """Return a collection-like object. If MongoDB is available, return the
        real pymongo collection. Otherwise return an in-memory collection wrapper
        that implements a minimal subset of the pymongo API used by the app.
        """
        if self._available and self._db:
            return self._db.get_collection(name)

        # fallback in-memory collection wrapper
        if name not in self._collections:
            self._collections[name] = _InMemoryCollection()
        return self._collections[name]

    def available(self) -> bool:
        return self._available


class _InMemoryCursor:
    def __init__(self, docs):
        # docs is a list; create a shallow copy for sorting/limiting
        self._docs = list(docs)

    def sort(self, key, direction=1):
        reverse = direction < 0
        try:
            self._docs.sort(key=lambda d: d.get(key, None), reverse=reverse)
        except Exception:
            pass
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self):
        return len(self._docs)


class _InMemoryCollection:
    def __init__(self):
        self._docs = []
        self._next_id = 1

    def _match(self, doc, query):
        if not query:
            return True
        # basic equality matching and $text search support
        for k, v in (query.items() if isinstance(query, dict) else []):
            if k == "$text" and isinstance(v, dict):
                search = v.get("$search", "").lower()
                # search common text fields
                hay = " ".join(str(doc.get(f, "")).lower() for f in ("title", "content", "text", "user_prompt"))
                if search not in hay:
                    return False
            else:
                # simple equality
                if k not in doc or doc.get(k) != v:
                    return False
        return True

    def insert_one(self, doc: dict):
        if "_id" not in doc:
            doc = dict(doc)
            doc["_id"] = f"inmem_{self._next_id}"
            self._next_id += 1
        self._docs.append(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    def find(self, query: Optional[dict] = None):
        # very small subset of find behavior: return cursor supporting sort/limit
        matched = []
        if query is None:
            matched = list(self._docs)
        else:
            # support text search shortcut
            if "$text" in query and isinstance(query["$text"], dict):
                search = query["$text"].get("$search", "").lower()
                for d in self._docs:
                    hay = " ".join(str(d.get(f, "")).lower() for f in ("title", "content", "text", "user_prompt"))
                    if search in hay:
                        matched.append(d)
            else:
                for d in self._docs:
                    ok = True
                    for k, v in query.items():
                        if d.get(k) != v:
                            ok = False
                            break
                    if ok:
                        matched.append(d)

        return _InMemoryCursor(matched)

    def find_one(self, query: Optional[dict] = None):
        for d in self._docs:
            if query is None:
                return d
            ok = True
            for k, v in query.items():
                if k not in d or d.get(k) != v:
                    ok = False
                    break
            if ok:
                return d
        return None

    def count_documents(self, query: Optional[dict] = None):
        return len(list(self.find(query)))

    def create_index(self, *args, **kwargs):
        # no-op for in-memory
        return None

    def update_one(self, filter_q: dict, update: dict):
        doc = self.find_one(filter_q)
        if not doc:
            return None
        # support $set and $inc
        if "$set" in update:
            for k, v in update["$set"].items():
                doc[k] = v
        if "$inc" in update:
            for k, v in update["$inc"].items():
                doc[k] = doc.get(k, 0) + v
        return type("R", (), {"matched_count": 1, "modified_count": 1})()

    def aggregate(self, pipeline):
        # very limited support used by analytics: unwind->group->sort->limit
        results = list(self._docs)
        for stage in pipeline:
            if "$unwind" in stage:
                field = stage["$unwind"].lstrip("$")
                unwound = []
                for d in results:
                    arr = d.get(field) or []
                    for item in arr:
                        new = dict(d)
                        new[field] = item
                        unwound.append(new)
                results = unwound
            elif "$group" in stage:
                gid = stage["$group"].get("_id")
                key = None
                if isinstance(gid, str) and gid.startswith("$"):
                    key = gid.lstrip("$")
                groups = {}
                for d in results:
                    gk = d.get(key)
                    groups.setdefault(gk, {"_id": gk, "count": 0})
                    groups[gk]["count"] += 1
                results = list(groups.values())
            elif "$sort" in stage:
                s = stage["$sort"]
                # take first key
                for k, v in s.items():
                    results.sort(key=lambda x: x.get(k, 0), reverse=(v < 0))
            elif "$limit" in stage:
                results = results[: stage["$limit"]]
        return results

    def available(self) -> bool:
        return self._available
