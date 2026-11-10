"""Frozen, deterministic fact-unit rubric. No LLM, fuzzy success, or output rewriting."""
import difflib, re, unicodedata
STATES=['preserved','mislinked','missing','indeterminate']

def compact(s):return ''.join(c for c in unicodedata.normalize('NFC',s) if not c.isspace())

def mapped(s):
    text=unicodedata.normalize('NFC',s);indices=[i for i,c in enumerate(text) if not c.isspace()]
    return text,''.join(text[i] for i in indices),indices

def excerpt(raw,indices,start,end):
    if not indices:return ''
    return raw[indices[max(0,start)]:indices[min(len(indices)-1,end-1)]+1]

def near(raw,needle):
    # Evidence retrieval only: never awards a successful fact.
    lines=raw.splitlines()
    if not lines:return ''
    best=max(range(len(lines)),key=lambda i:difflib.SequenceMatcher(None,compact(needle),compact(lines[i])).ratio())
    return '\n'.join(lines[max(0,best-1):best+3])

def technology(raw,f):
    name=f['name'];pattern=r'(?<![A-Za-z0-9_+#])'+r'\s+'.join(re.escape(x) for x in name.split(' '))+r'(?![A-Za-z0-9_+#])'
    match=re.search(pattern,unicodedata.normalize('NFC',raw))
    return {**f,'category':'technology','state':'preserved' if match else 'missing','evidence':match.group() if match else near(raw,name),'reason':'exact case and symbols with token boundary; whitespace only between words may wrap'}

def actions(text,f):
    anchors=[compact(x) for x in re.split(r'(?:와|과) ',f['action'])]
    pattern=r'.{0,24}?'.join(re.escape(x) for x in anchors)
    return list(re.finditer(pattern,text))

def roles(raw,f,all_roles):
    original,text,indices=mapped(raw);matches=actions(text,f)
    result={**f,'category':'roles','predicted_owner':None}
    if not matches:return {**result,'state':'missing','evidence':near(raw,f['action']),'reason':'complete primary action anchors not recoverable'}
    headings={owner:text.find(compact(label)) for owner,label in [('team','팀 전체 구현'),('self','내가 맡은 역할')]}
    all_matches=[m for other in all_roles for m in actions(text,other)]
    first_action=min((m.start() for m in all_matches),default=len(text))
    interleaved=f['presentation']=='heading_scope' and all(v>=0 and v<first_action for v in headings.values())
    decisions=[]
    for m in matches:
        start=m.start();prefix=text[max(0,start-120):start]
        # Last sentence boundary protects a preceding unrelated subject. A newline is not a sentence boundary.
        prefix=re.split(r'[.!?。]',prefix)[-1]
        # A column heading is not an inline grammatical subject.
        prefix=prefix.replace('내가맡은역할', ' ' * len('내가맡은역할'))
        owner_tokens=list(re.finditer(r'다른팀원(?:은|이)|팀원(?:은|이)|팀(?:은|이)|나(?:는|의)|내가',prefix))
        if owner_tokens:
            token=owner_tokens[-1].group();owner='self' if token.startswith(('나','내')) else 'team'
            decisions.append((owner,'explicit grammatical subject',max(0,start-len(prefix)),m.end()+12))
        elif f['presentation']=='heading_scope' and not interleaved:
            prior=[(pos,owner) for owner,pos in headings.items() if 0<=pos<start]
            if prior:
                pos,owner=max(prior);decisions.append((owner,'unique preceding column heading',pos,m.end()+12))
            else:decisions.append((None,'owner heading is absent',max(0,start-60),m.end()+25))
        else:decisions.append((None,'both column headings precede task bodies; text-only column ownership ambiguous' if interleaved else 'action remains but grammatical subject not recoverable',max(0,start-100),m.end()+45))
    wrong=[x for x in decisions if x[0] and x[0]!=f['owner']]
    correct=[x for x in decisions if x[0]==f['owner']]
    selected=(wrong or correct or decisions)[0]
    state='mislinked' if wrong else ('preserved' if correct else 'indeterminate')
    return {**result,'state':state,'predicted_owner':selected[0],'evidence':excerpt(original,indices,selected[2],selected[3]),'reason':selected[1]}

def metrics(raw,f):
    original,text,indices=mapped(raw);label=compact(f['name']);positions=[m.start() for m in re.finditer(re.escape(label),text)]
    result={**f,'category':'metrics','parsed_relation':None}
    if not positions:
        has_values=all(compact(v+f['unit']) in text for v in [f['before'],f['after']])
        return {**result,'state':'indeterminate' if has_values else 'missing','evidence':near(raw,f['statement']),'reason':'numeric evidence without a recoverable metric label' if has_values else 'metric label and complete tuple absent'}
    decisions=[]
    # A relation must start immediately after its metric, with explicit directed connector.
    # Parsed values/units are compared as a tuple, not searched independently across a page.
    number=r'([0-9]+(?:\.[0-9]+)?)';unit=r'([A-Za-z%/가-힣]+?)'
    relation=re.compile(r'^[:：]?'+number+unit+r'(→|⇒|->|에서)'+number+unit+r'(?=로|으로|[,.。]|증가|감소|한|측정|$)')
    labelled=re.compile(r'^개선전'+number+unit+r'개선후'+number+unit+r'(?=상태|합성|$)')
    # On charts, all values must stay attached to explicit before/after labels in textual order.
    for pos in positions:
        tail=text[pos+len(label):pos+len(label)+130]
        m=relation.match(tail);explicit=True
        if m:
            b,u1,connector,a,u2=m.groups()
        else:
            m=labelled.match(tail);explicit=False
            if m:b,u1,a,u2=m.groups();connector='개선 전 / 개선 후'
        if m:
            parsed={'metric':f['name'],'before':b,'after':a,'before_unit':u1,'after_unit':u2,'connector':connector}
            end=pos+len(label)+m.end()
            following=text[end:end+18]
            direction_words=re.findall(r'증가|감소',following)
            numeric_match=(b,a,u1,u2)==(f['before'],f['after'],f['unit'],f['unit'])
            direction_ok=not direction_words or direction_words[0]==f['direction']
            state='preserved' if numeric_match and direction_ok else 'mislinked'
            decisions.append((state,parsed,pos,end+min(18,len(following)),'metric / ordered values / units / direction parsed in one relation'))
        else:decisions.append(('indeterminate',None,pos,pos+len(label)+90,'metric remains, but no complete directed tuple or labelled before/after pair'))
    # Conflicting full tuples cannot be cured by another intact duplicate on the same page.
    selected=next((d for d in decisions if d[0]=='mislinked'),None) or next((d for d in decisions if d[0]=='preserved'),None) or decisions[0]
    return {**result,'state':selected[0],'parsed_relation':selected[1],'evidence':excerpt(original,indices,selected[2],selected[3]),'reason':selected[4]}

def score_facts(raw,facts):
    return [technology(raw,f) for f in facts['technology']]+[roles(raw,f,facts['roles']) for f in facts['roles']]+[metrics(raw,f) for f in facts['metrics']]
