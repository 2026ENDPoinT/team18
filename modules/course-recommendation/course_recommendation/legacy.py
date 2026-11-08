"""Scoring over a frozen, caller-provided snapshot; no service or database imports."""
import re

class InputTooLong(ValueError):
    pass

def _match(text, alias):
    # ASCII identifiers must be whole words, so Java does not match JavaScript.
    boundary = r'[A-Za-z0-9_]' if alias.isascii() else r'[\w]'
    suffix = r'(?!' + boundary + r')' if alias.isascii() else r'(?=$|[^\w]|(?:은|는|을|를|이|가|으로|와|과|도|만)(?:$|[^\w]))'
    return bool(re.search(r'(?<!' + boundary + r')' + re.escape(alias) + suffix, text, re.I))

def _negative(text, alias):
    return bool(re.search(re.escape(alias) + r'\s*(?:은|는|을|를|이|가)?\s*(?:말고|제외|아닌|안\s*하고|하지\s*않)', text, re.I))

def _normalized(values):
    total = sum(values.values())
    return {k: v / total for k, v in values.items()} if total else {}

def validate_equivalence_groups(catalog):
    """Validate explicit ordered alternatives; first ID is the preferred representation."""
    ids = set(catalog['course_ids'])
    seen = set()
    groups = catalog.get('equivalent_course_groups', [])
    if not isinstance(groups, list):
        raise ValueError('invalid course equivalence groups')
    for group in groups:
        if not isinstance(group, list) or len(group) < 2 or len(set(group)) != len(group) or not set(group) <= ids or seen.intersection(group):
            raise ValueError('invalid or overlapping course equivalence group')
        seen.update(group)
    return groups

def recommend_courses(input_snapshot, semantic_bundle, limit=5):
    """Return status, basis, selection status, weighted skills and course IDs.

    Snapshot must contain catalog_id, catalog_version, course_ids, completed_course_ids,
    selection_review_status, career_goal and optional target_role. Encoder is called once.
    InputTooLong is propagated so the caller can return an input validation error.
    """
    s, b = input_snapshot, semantic_bundle
    base = {'basis_version': b.get('bundle_version'), 'selection_review_status': s.get('selection_review_status'), 'goal_skills': [], 'courses': []}
    def result(status): return {'status': status, **base}
    try:
        catalog = b['catalogs'][s['catalog_id']]
        ids = s['course_ids']
        if (not isinstance(ids, list) or len(ids) != len(set(ids)) or set(ids) != set(catalog['course_ids'])
            or s['catalog_version'] != catalog['version'] or s.get('selection_review_status') not in ('confirmed', 'partial', 'unconfirmed')):
            return result('unavailable')
        groups = validate_equivalence_groups(catalog)
        goal = s['career_goal'].strip()
        if not goal: return result('no_match')
        role_input = s.get('target_role') or ''
        query = 'query: ' + goal + (' ' + role_input if role_input else '')
        vector = b['encoder'].encode(query)
        skills, roles = b['skills'], b['roles']
        sim = lambda a, v: sum(x*y for x,y in zip(a,v))
        if len(vector) != b['dimension']: return result('unavailable')
        excluded = {x['skill_id'] for x in skills if any(_negative(goal, a) for a in [x['name'], *x.get('aliases', [])])}
        excluded_roles = {x['role_id'] for x in roles if any(_negative(goal, a) for a in [x['name'], *x.get('aliases', [])])}
        # Complex negation needs human interpretation rather than a confident recommendation.
        if re.search(r'(?<!하지 )않|원하지|싫|빼고|제외', goal) and not (excluded or excluded_roles): return result('no_match')
        positive = [x['skill_id'] for x in skills if x['skill_id'] not in excluded and any(_match(goal, a) and not _negative(goal, a) for a in [x['name'], *x.get('aliases', [])])]
        ranked = sorted(((sim(vector, b['skill_vectors'][i]), x['skill_id']) for i,x in enumerate(skills) if x['skill_id'] not in excluded), reverse=True)
        direct = list(dict.fromkeys(positive + [sid for score,sid in ranked if score >= b['config']['skill_threshold']]))[:8]
        d = _normalized({sid: 1/(i+1) for i,sid in enumerate(direct)})
        selected = []
        if role_input:
            selected = [r for r in roles if r['role_id'] not in excluded_roles and any(_match(role_input, a) for a in [r['role_id'], r['name'], *r.get('aliases', [])])]
        else:
            selected = [r for r in roles if r['role_id'] not in excluded_roles and any(_match(goal, a) and not _negative(goal, a) for a in [r['name'], *r.get('aliases', [])])]
            if not selected and roles:
                ranked_roles = sorted(((sim(vector, b['role_vectors'][i]), i) for i,r in enumerate(roles) if r['role_id'] not in excluded_roles), reverse=True)
                if ranked_roles and ranked_roles[0][0] >= b['config']['role_threshold'] and (len(ranked_roles) == 1 or ranked_roles[0][0]-ranked_roles[1][0] >= b['config']['role_margin']): selected = [roles[ranked_roles[0][1]]]
        p = {}
        for role in selected:
            weights = _normalized({x['skill_id']: x['priority'] for x in role['skills'] if x['skill_id'] not in excluded})
            for sid, val in weights.items(): p[sid] = p.get(sid, 0) + val / len(selected)
        if d and p: combined = {k: .6*d.get(k, 0)+.4*p.get(k, 0) for k in d.keys() | p.keys()}
        else: combined = d or p
        weights = _normalized(dict(sorted(combined.items(), key=lambda x: (-x[1], x[0]))[:8]))
        base['goal_skills'] = [{'skill_id': k, 'priority_weight': v} for k,v in weights.items()]
        completed = set(s['completed_course_ids'])
        for group in groups:
            if completed.intersection(group): completed.update(group)
        scored = []
        for profile in catalog['profiles']:
            if profile['course_id'] in completed: continue
            score = sum(weights.get(t['skill_id'], 0)*t['coverage'] for t in profile['skills'])
            if score > 0 and score >= b['config']['course_threshold']:
                scored.append((score, profile['source_type'] == 'description', profile['course_id']))
        # Collapse only explicitly declared alternatives, never infer identity from names.
        by_id = {item[2]: item for item in scored}
        grouped = {cid for group in groups for cid in group}
        collapsed = [item for item in scored if item[2] not in grouped]
        for group in groups:
            available = [by_id[cid] for cid in group if cid in by_id]
            if available:
                best = max(available, key=lambda x: (x[0], x[1]))
                # Preferred ID is ordered first, but must itself have a positive profile.
                collapsed.append((best[0], best[1], available[0][2]))
        scored = collapsed
        scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
        base['courses'] = [{'course_id': cid, 'rank': i+1, 'score': score} for i,(score,_,cid) in enumerate(scored[:max(0,min(limit,5))])]
        return result('ok' if base['courses'] else 'no_match')
    except InputTooLong: raise
    except Exception: return result('unavailable')
