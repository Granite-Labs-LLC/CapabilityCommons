from __future__ import annotations

import abc


class GraphAdapter(abc.ABC):
    @abc.abstractmethod
    async def neighbors(self, seed_nodes, edge_types, depth, filters=None):
        raise NotImplementedError

    @abc.abstractmethod
    async def paths_between(self, src, dst, edge_types, max_depth):
        raise NotImplementedError

    @abc.abstractmethod
    async def ordered_members(self, group_version_id):
        raise NotImplementedError

    @abc.abstractmethod
    async def reverse_prerequisites(self, version_ids):
        raise NotImplementedError
