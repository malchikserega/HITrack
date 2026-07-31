"""Package URL normalization used as the canonical component identity."""


def component_identity(purl: str | None, package_type: str, name: str) -> str:
    if purl and purl.startswith('pkg:'):
        # A PURL version begins after the final @ and before qualifiers/subpath.
        base = purl.split('?', 1)[0].split('#', 1)[0]
        head, marker, _version = base.rpartition('@')
        return head if marker else base
    return f'legacy:{package_type or "unknown"}:{name.casefold()}'
