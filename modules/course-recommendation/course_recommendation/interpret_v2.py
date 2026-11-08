"""Small, inspectable Korean goal rules. Matches return offsets, not input text."""
import re
import unicodedata

PARTICLES = r'(?:은|는|을|를|이|가|의|에|에서|으로|로|와|과|도|만|보다|보다는|뿐|이란|인|용|에서의)?'

def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip()

def occurrences(text, alias):
    alias = normalize(alias)
    if not alias: return []
    escaped = re.escape(alias).replace(r'\ ', r'\s+')
    left = r'(?<![A-Za-z0-9_])' if alias.isascii() else r'(?<![\w])'
    right = r'(?![A-Za-z0-9_])' if alias.isascii() else r'(?=$|[^\w]|'+PARTICLES+r'(?=$|[^\w]))'
    return [m.span() for m in re.finditer(left+escaped+right, text, re.I)]

def interpret(goal, skills, roles):
    text = normalize(goal)
    hits=[]
    for kind, records, id_key in (('skill',skills,'skill_id'),('role',roles,'role_id')):
        for record in records:
            for alias in dict.fromkeys([record['name'], *record.get('aliases',[])]):
                for start,end in occurrences(text,alias):
                    hits.append({'kind':kind,'id':record[id_key], 'start':start,'end':end,'alias_length':len(alias)})
    # Prefer longest overlapping alias in each namespace; separate role and skill matches may overlap.
    kept=[]
    for h in sorted(hits,key=lambda x:(-(x['end']-x['start']),x['start'],x['kind'],x['id'])):
        if not any(h['kind']==a['kind'] and h['start'] < a['end'] and a['start'] < h['end'] for a in kept): kept.append(h)
    kept.sort(key=lambda h:(h['start'],h['end'],h['kind'],h['id']))
    decisions=[]; excluded=set(); excluded_roles=set(); positive=[]; positive_roles=[]
    explicit_neg = re.compile(r'^\s*(?:(?:은|는|을|를|이|가|의|에|에서|으로|로|과|와|도|만)\s*)?(?:말고|빼고|제외(?:하고|한|해|하며)?|(?:아닌|아니라|아니고)|않(?:고|는|아)|싫|원하지\s*않|하지\s*않)',re.I)
    compare = re.compile(r'^\s*(?:보다(?:는)?)(?:\s|$)',re.I)
    ambiguous=bool(re.search(r'(?:할지|할까|인지).{0,30}(?:고민|모르|정하지|결정하지)|(?:중에서|중에).{0,20}(?:고민|모르|결정)',text))
    # A/B testing is a statistical experiment, not software testing.
    ab_test=bool(re.search(r'(?<![\w])a\s*/\s*b\s*테스트',text,re.I))
    api_goal=bool(re.search(r'(?:rest\s*)?api\s*(?:를|을|의)?\s*(?:설계|개발|구현|만들|제공)',text,re.I))
    mobile_environment=bool(re.search(r'모바일\s*(?:앱|애플리케이션)(?:에서|용|을\s*위해|을\s*위한)\s*(?:사용할|사용하는|쓸|위한)?\s*(?:rest\s*)?api',text,re.I))
    deploy_goal=bool(re.search(r'(?:모델|인공지능|ai).{0,20}(?:배포|서비스에\s*적용)',text,re.I))
    for h in kept:
        before=text[max(0,h['start']-12):h['start']]; after=text[h['end']:h['end']+40]
        scope_after = re.sub(r'^\s*(?:앱|애플리케이션|모델|연구)(?=\s|은|는|이|가|을|를)', '', after, flags=re.I) if h['id'] in ('mobile','ai') else after
        decision='positive'
        if explicit_neg.match(scope_after): decision='excluded'
        elif compare.match(after): decision='comparison_lower'
        if h['id']=='software_testing' and ab_test and re.search(r'a\s*/\s*b\s*$',before,re.I): decision='context_suppressed'
        if h['id']=='mobile' and mobile_environment: decision='context_suppressed'
        if h['id']=='ai' and deploy_goal and re.match(r'\s*(?:모델\s*)?연구\s*(?:가\s*)?아니',after): decision='context_suppressed'
        if decision=='excluded': (excluded if h['kind']=='skill' else excluded_roles).add(h['id'])
        elif decision=='positive': (positive if h['kind']=='skill' else positive_roles).append(h['id'])
        decisions.append({**h,'decision':decision})
    # Narrow contextual concepts are recognized only if supplied in the bundle vocabulary.
    available={x['skill_id'] for x in skills}
    contextual=[]
    if re.search(r'데이터(?:를|의|에서|로|를\s*이용해)?\s*.{0,16}분석',text):
        contextual += [x for x in ('data_analysis',) if x in available]
    if re.search(r'(?:사진|이미지|영상|시각).{0,22}(?:인식|구별|분류|분석|처리)',text):
        contextual += [x for x in ('computer_vision',) if x in available]
    if ab_test:
        contextual += [x for x in ('experiment_analysis','data_analysis','statistics') if x in available]
    if api_goal: contextual += [x for x in ('api_design',) if x in available]
    if deploy_goal: contextual += [x for x in ('model_deployment',) if x in available]
    # Suppression prevents irrelevant explicit context being resurrected via semantic matching.
    blocked={h['id'] for h in decisions if h['kind']=='skill' and h['decision']=='context_suppressed'}
    if any(h['decision']=='comparison_lower' for h in decisions) and not positive and not positive_roles and not contextual:
        ambiguous = True
    positive += [h['id'] for h in decisions if h['kind']=='skill' and h['decision']=='comparison_lower']
    if ab_test: blocked.add('software_testing')
    if mobile_environment: blocked.add('mobile')
    # Unrecognized exclusion scope is not safe to interpret confidently.
    neg_check=re.sub(r'뿐\s*아니라', '', text)
    uncertain_neg=bool(re.search(r'(?:제외|말고|빼고|싫|아닌|아니라|하지\s*않)',neg_check)) and not any(h['decision'] in ('excluded','context_suppressed') for h in decisions)
    if mobile_environment or deploy_goal: uncertain_neg=False if any(h['decision']=='context_suppressed' for h in decisions) else uncertain_neg
    return {'matches':decisions,'excluded_skills':sorted(excluded),'excluded_roles':sorted(excluded_roles),'blocked_direct':sorted(blocked),'positive_skills':list(dict.fromkeys(contextual+positive)), 'positive_roles':list(dict.fromkeys(positive_roles)), 'ambiguous':ambiguous or uncertain_neg,'ambiguity_reason':'unresolved_choice' if ambiguous else 'unresolved_exclusion' if uncertain_neg else None,'context':{'ab_test':ab_test,'api_goal':api_goal,'mobile_environment':mobile_environment,'deployment_goal':deploy_goal}}
