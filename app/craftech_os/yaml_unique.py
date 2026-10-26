"""YAML loading that rejects duplicate mapping keys instead of keeping the last one."""

import yaml


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    # Before construct_mapping flattens "<<" merges: an explicit key may override a merged one.
    seen = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ValueError(f"duplicated key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load(text: str):
    """Like yaml.safe_load; ValueError on a duplicate mapping key."""
    return yaml.load(text, Loader=_UniqueKeyLoader)
