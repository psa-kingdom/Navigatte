"""In-memory async MongoDB mock for unit and integration testing."""

import re
from bson import ObjectId


class MockCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, str):
            key = key_or_list
            reverse = direction == -1
            self.docs.sort(key=lambda d: (d.get(key) is None, d.get(key, "")), reverse=reverse)
        elif isinstance(key_or_list, list):
            for key, direction in reversed(key_or_list):
                reverse = direction == -1
                self.docs.sort(key=lambda d: (d.get(key) is None, d.get(key, "")), reverse=reverse)
        return self

    async def to_list(self, length=1000):
        return [dict(d) for d in self.docs[:length]]


class MockUpdateResult:
    def __init__(self, matched_count, modified_count, upserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class MockDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class MockCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []

    def _matches(self, doc, query):
        if not query:
            return True
        for key, val in query.items():
            if key == "$or":
                matched_or = False
                for sub_query in val:
                    if self._matches(doc, sub_query):
                        matched_or = True
                        break
                if not matched_or:
                    return False
                continue

            if isinstance(val, dict):
                if "$regex" in val:
                    pattern = val["$regex"]
                    options = val.get("$options", "")
                    flags = re.IGNORECASE if "i" in options else 0
                    doc_val = str(doc.get(key, ""))
                    if not re.search(pattern, doc_val, flags):
                        return False
                    continue
                if "$exists" in val:
                    exists = key in doc and doc[key] is not None
                    if exists != val["$exists"]:
                        return False
                    continue

            doc_val = doc.get(key)
            # Unwrap Enum values if present
            if hasattr(doc_val, "value"):
                doc_val = doc_val.value
            if hasattr(val, "value"):
                val = val.value

            if isinstance(doc_val, list):
                if val not in doc_val:
                    return False
            else:
                if doc_val != val and str(doc_val) != str(val):
                    return False
        return True

    async def create_index(self, *args, **kwargs):
        return "index_created"

    async def count_documents(self, query):
        return len([d for d in self.docs if self._matches(d, query)])

    async def distinct(self, key):
        items = set()
        for d in self.docs:
            val = d.get(key)
            if isinstance(val, list):
                items.update(val)
            elif val is not None:
                items.add(val)
        return list(items)

    async def find_one(self, query):
        for d in self.docs:
            if self._matches(d, query):
                return dict(d)
        return None

    def find(self, query=None, projection=None):
        matched = [d for d in self.docs if self._matches(d, query or {})]
        if projection and projection.get("_id") == 0:
            matched = [{k: v for k, v in d.items() if k != "_id"} for d in matched]
        return MockCursor(matched)

    async def insert_one(self, doc):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = ObjectId()
        self.docs.append(d)
        return MockUpdateResult(1, 1, d["_id"])

    async def insert_many(self, docs):
        for doc in docs:
            await self.insert_one(doc)
        return True

    async def update_one(self, query, update, upsert=False):
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                if "$set" in update:
                    for k, v in update["$set"].items():
                        d[k] = v
                if "$push" in update:
                    for k, v in update["$push"].items():
                        if k not in d or not isinstance(d[k], list):
                            d[k] = []
                        d[k].append(v)
                self.docs[i] = d
                return MockUpdateResult(1, 1)

        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            await self.insert_one(new_doc)
            return MockUpdateResult(0, 0, new_doc.get("_id"))

        return MockUpdateResult(0, 0)

    async def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                self.docs.pop(i)
                return MockDeleteResult(1)
        return MockDeleteResult(0)

    async def delete_many(self, query):
        initial_len = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, query)]
        return MockDeleteResult(initial_len - len(self.docs))


class MockDatabase:
    def __init__(self):
        self.admin_users = MockCollection("admin_users")
        self.login_attempts = MockCollection("login_attempts")
        self.projects = MockCollection("projects")
        self.enquiries = MockCollection("enquiries")
        self.status_checks = MockCollection("status_checks")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)
