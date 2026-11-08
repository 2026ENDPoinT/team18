"""Public API: verified legacy behavior unless experimental configuration is explicit."""
from .legacy import InputTooLong, validate_equivalence_groups, _match, _negative

def recommend_courses(input_snapshot, semantic_bundle, limit=5):
    if semantic_bundle.get('config',{}).get('interpretation_version') == 'experimental-v2':
        from .engine import recommend_with_trace
        return recommend_with_trace(input_snapshot, semantic_bundle, limit)[0]
    from .legacy import recommend_courses as legacy
    return legacy(input_snapshot, semantic_bundle, limit)
