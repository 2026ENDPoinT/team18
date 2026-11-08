"""Experimental single-inference recommendation with opt-in structured diagnostics."""
import math
import copy
from .legacy import InputTooLong, validate_equivalence_groups, _normalized
from .interpret import interpret, normalize, occurrences

def recommend_with_trace(s, b, limit=5):
    s=copy.deepcopy(s)
    base={'basis_version':b.get('bundle_version'),'selection_review_status':s.get('selection_review_status'),'goal_skills':[],'courses':[]}
    trace={'bundle_version':b.get('bundle_version'),'model_revision':b.get('model_revision'),'bundle_hashes':b.get('bundle_hashes'), 'config':b.get('config'), 'status_reason':None,'matching':{},'skill_candidates':[],'role_candidates':[],'weights':[],'course_candidates':[]}
    def done(status,reason): trace['status_reason']=reason; return {'status':status,**base},trace
    try:
        cat=b['catalogs'][s['catalog_id']]; ids=s['course_ids']
        if not isinstance(ids,list) or len(ids)!=len(set(ids)) or set(ids)!=set(cat['course_ids']) or s['catalog_version']!=cat['version'] or s.get('selection_review_status') not in ('confirmed','partial','unconfirmed'):
            return done('unavailable','snapshot_catalog_mismatch')
        groups=validate_equivalence_groups(cat)
        goal=normalize(s['career_goal']); role_input=normalize(s.get('target_role') or '')
        if not goal: return done('no_match','empty_goal')
        matching=interpret(goal,b['skills'],b['roles']); trace['matching']=matching
        if matching['ambiguous']: return done('no_match','ambiguous_goal')
        vector=b['encoder'].encode('query: '+goal+(' '+role_input if role_input else ''))
        if len(vector)!=b['dimension'] or not all(math.isfinite(v) for v in vector): return done('unavailable','invalid_vector')
        sim=lambda a,v: sum(x*y for x,y in zip(a,v))
        skills=b['skills']; roles=b['roles']; config=b['config']
        ss=sorted(((sim(vector,b['skill_vectors'][i]),x['skill_id']) for i,x in enumerate(skills)),key=lambda x:(-x[0],x[1]))
        rs=sorted(((sim(vector,b['role_vectors'][i]),x['role_id']) for i,x in enumerate(roles)),key=lambda x:(-x[0],x[1]))
        excluded=set(matching['excluded_skills']); blocked=set(matching['blocked_direct']); ex_roles=set(matching['excluded_roles'])
        trace['skill_candidates']=[{'skill_id':sid,'similarity':score,'excluded':sid in excluded,'blocked':sid in blocked} for score,sid in ss[:10]]
        trace['role_candidates']=[{'role_id':rid,'similarity':score,'excluded':rid in ex_roles} for score,rid in rs[:10]]
        positive=[sid for sid in matching['positive_skills'] if sid not in excluded and sid not in blocked]
        direct=list(dict.fromkeys(positive+[sid for score,sid in ss if score>=config['skill_threshold'] and sid not in excluded and sid not in blocked]))[:8]
        trace['direct_sources']=[{'skill_id':sid,'sources':(['alias_or_context'] if sid in positive else []) + (['semantic'] if any(x==sid and score>=config['skill_threshold'] for score,x in ss) else [])} for sid in direct]
        d=_normalized({sid:1/(i+1) for i,sid in enumerate(direct)})
        eligible_roles=[r for r in roles if r['role_id'] not in ex_roles]
        if role_input:
            selected=[r for r in eligible_roles if any(occurrences(role_input,a) for a in [r['role_id'],r['name'],*r.get('aliases',[])])]
            source='selected_role' if selected else 'unknown_selected_role'
        else:
            selected=[r for r in eligible_roles if r['role_id'] in matching['positive_roles']]
            source='alias' if selected else 'none'
            if not selected and matching['context']['api_goal']:
                selected=[r for r in eligible_roles if r['role_id']=='backend']; source='context_api' if selected else 'none'
            if not selected:
                eligible_scores=[(score,rid) for score,rid in rs if rid not in ex_roles]
                margin=eligible_scores[0][0]-eligible_scores[1][0] if len(eligible_scores)>1 else None
                if eligible_scores and eligible_scores[0][0]>=config['role_threshold'] and (margin is None or margin>=config['role_margin']):
                    selected=[r for r in eligible_roles if r['role_id']==eligible_scores[0][1]]; source='semantic'
        eligible_scores=[(score,rid) for score,rid in rs if rid not in ex_roles]
        trace['role_selection']={'source':source,'selected':[r['role_id'] for r in selected], 'top_margin':eligible_scores[0][0]-eligible_scores[1][0] if len(eligible_scores)>1 else None}
        p={}
        for role in selected:
            part=_normalized({t['skill_id']:t['priority'] for t in role['skills'] if t['skill_id'] not in excluded})
            for sid,val in part.items(): p[sid]=p.get(sid,0)+val/len(selected)
        combined={sid:(.6*d.get(sid,0)+.4*p.get(sid,0) if d and p else d.get(sid,0)+p.get(sid,0)) for sid in d.keys()|p.keys() if sid not in excluded}
        weights=_normalized(dict(sorted(combined.items(),key=lambda x:(-x[1],x[0]))[:8]))
        trace['weights']=[{'skill_id':sid,'direct_contribution':(.6 if p else 1)*d.get(sid,0),'role_contribution':(.4 if d else 1)*p.get(sid,0),'final_weight':weights.get(sid,0)} for sid in sorted(combined)]
        base['goal_skills']=[{'skill_id':sid,'priority_weight':weight} for sid,weight in weights.items()]
        if not weights: return done('no_match','excluded_all' if excluded or ex_roles else 'no_skill_candidates')
        completed=set(s['completed_course_ids'])
        for g in groups:
            if completed.intersection(g): completed.update(g)
        scored=[]; positive_count=0
        for profile in cat['profiles']:
            cid=profile['course_id']; score=sum(weights.get(t['skill_id'],0)*t['coverage'] for t in profile['skills'])
            reason='completed' if cid in completed else 'zero_score' if score<=0 else 'below_threshold' if score<config['course_threshold'] else 'candidate'
            if reason!='completed' and score>0: positive_count+=1
            trace['course_candidates'].append({'course_id':cid,'score':score,'reason':reason,'source_type':profile['source_type'],'tie_break':'score desc, description first, course_id asc'})
            if reason=='candidate': scored.append((score,profile['source_type']=='description',cid))
        by_id={x[2]:x for x in scored}; grouped={cid for g in groups for cid in g}; collapsed=[x for x in scored if x[2] not in grouped]
        for g in groups:
            available=[by_id[cid] for cid in g if cid in by_id]
            if available:
                best=max(available,key=lambda x:(x[0],x[1])); collapsed.append((best[0],best[1],available[0][2]))
        collapsed.sort(key=lambda x:(-x[0],-x[1],x[2]))
        base['courses']=[{'course_id':cid,'rank':i+1,'score':score} for i,(score,_,cid) in enumerate(collapsed[:max(0,min(limit,5))])]
        rank_by_id={x['course_id']:x['rank'] for x in base['courses']}
        for item in trace['course_candidates']:
            item['rank']=rank_by_id.get(item['course_id'])
            if item['reason']=='candidate' and item['rank'] is None: item['reason']='not_selected_or_equivalent'
        if not base['courses']: return done('no_match','below_course_threshold' if positive_count else 'no_linked_courses')
        return done('ok','matched')
    except InputTooLong: raise
    except Exception: return done('unavailable','bundle_or_model_error')
