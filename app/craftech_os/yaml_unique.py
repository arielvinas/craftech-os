"""YAML loading that rejects duplicate mapping keys instead of keeping the last one."""

import yaml


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    mapping = loader.construct_mapping(node, deep=deep)
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ValueError(f"duplicated key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load(text: str):
    """Like yaml.safe_load; ValueError on a duplicate mapping key."""
    return yaml.load(text, Loader=_UniqueKeyLoader)
