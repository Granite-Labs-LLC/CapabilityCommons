from __future__ import annotations

import abc

from capability_commons.schemas.search import SearchHit


class SearchAdapter(abc.ABC):
    @abc.abstractmethod
    async def index_version(self, version_id):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_version(self, version_id):
        raise NotImplementedError

    @abc.abstractmethod
    async def search(self, *, workspace_id, query, filters, top_k, object_types=None, only_published=True) -> list[SearchHit]:
        raise NotImplementedError

    @abc.abstractmethod
    async def fetch_segments(self, segment_ids):
        raise NotImplementedError
