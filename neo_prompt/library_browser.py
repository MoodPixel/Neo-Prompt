"""Paginated browsing, filtering by task collections and user categories."""
from __future__ import annotations

from typing import Any

COLLECTIONS: dict[str, tuple[str, ...]] = {
    'captions': ('all', 'batch', 'single', 'describe', 'recreate', 'edit', 'video', 'dataset'),
    'prompts': ('all', 'positive', 'negative', 'original', 'refinements'),
}


def _in_collection(kind: str, item: dict[str, Any], group: str) -> bool:
    if group == 'all':
        return True
    if kind == 'captions':
        origin = str(item.get('origin', '')).lower()
        if group == 'batch':
            return origin.startswith('batch')
        if group == 'single':
            return not origin.startswith('batch')
        return item.get('task') == group
    operation = item.get('operation', 'generate')
    if group == 'positive':
        return operation != 'negative'
    if group == 'negative':
        return operation == 'negative'
    if group == 'original':
        return operation == 'generate'
    if group == 'refinements':
        return operation in ('enhance', 'rewrite')
    return False


def browse(items: list[dict[str, Any]], *, kind: str, query: str = '',
           collection: str = 'all', sort: str = 'newest', offset: int = 0,
           limit: int = 20, category: str = '') -> dict[str, Any]:
    if kind not in COLLECTIONS:
        raise ValueError('Invalid Library tab')
    if collection not in COLLECTIONS[kind]:
        raise ValueError('Invalid Library collection')
    if sort not in ('newest', 'oldest', 'name'):
        raise ValueError('Invalid Library sorting')
    if offset < 0 or limit < 1 or limit > 100:
        raise ValueError('Invalid Library page')
    if len(category) > 64:
        raise ValueError('Invalid Library category')
    q = query.strip().casefold()
    if len(q) > 160:
        raise ValueError('Library search is too long')

    def matches(item: dict[str, Any]) -> bool:
        if not q:
            return True
        # The existing records have no user category yet; read metadata if present,
        # but never invent or write a category here.
        search = (item.get('title'), item.get('name'), item.get('text'),
                  item.get('source'), item.get('task'), item.get('operation'),
                  item.get('origin'), item.get('category'),
                  item.get('paired_positive_text'))
        return q in ' '.join(str(part or '') for part in search).casefold()

    matched = [item for item in items if matches(item)]
    categories = sorted({str(x.get('category') or 'General') for x in matched}, key=str.casefold)
    if category:
        matched = [x for x in matched if str(x.get('category') or 'General').casefold() == category.casefold()]
    counts = {key: sum(_in_collection(kind, x, key) for x in matched)
              for key in COLLECTIONS[kind]}
    filtered = [item for item in matched if _in_collection(kind, item, collection)]
    if sort == 'name':
        filtered.sort(key=lambda x: str(x.get('title') or x.get('name') or x.get('task') or '').casefold())
    else:
        filtered.sort(key=lambda x: (str(x.get('when', '')), str(x.get('id', ''))), reverse=(sort == 'newest'))
    return {'items': filtered[offset:offset + limit], 'total': len(filtered),
            'offset': offset, 'limit': limit, 'counts': counts, 'kind': kind,
            'collection': collection, 'sort': sort, 'category':category, 'categories':categories}
