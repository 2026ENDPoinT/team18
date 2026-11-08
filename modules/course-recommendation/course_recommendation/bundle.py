"""Validate all bundle identities and load a single local ONNX session."""
import hashlib
import json
import threading
from pathlib import Path
from .core import InputTooLong, validate_equivalence_groups

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))

class Encoder:
    def __init__(self, path, dimension):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(path/'tokenizer.json'))
        self.tokenizer.no_truncation()
        options = ort.SessionOptions(); options.intra_op_num_threads = 1; options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(path/'encoder.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
        self.lock = threading.Lock(); self.dimension = dimension
    def encode(self, text):
        import numpy as np
        tokens = self.tokenizer.encode(text)
        if len(tokens.ids) > 256: raise InputTooLong('입력을 256 토큰 이하로 줄여 주세요.')
        arrays = {'input_ids': np.array([tokens.ids], dtype=np.int64), 'attention_mask': np.array([tokens.attention_mask], dtype=np.int64), 'token_type_ids': np.array([tokens.type_ids], dtype=np.int64)}
        with self.lock: output = self.session.run(None, {x.name: arrays[x.name] for x in self.session.get_inputs()})[0]
        mask = arrays['attention_mask'][..., None]
        vec = (output * mask).sum(axis=1) / mask.sum(axis=1)
        norm = np.linalg.norm(vec)
        if vec.shape != (1,self.dimension) or not np.isfinite(norm) or norm == 0: raise ValueError('invalid model output')
        return (vec[0] / norm).tolist()

def load_bundle(path):
    import numpy as np
    p = Path(path); m = read(p/'manifest.json')
    for name, expected in m['sha256'].items():
        if Path(name).name != name or digest(p/name) != expected: raise ValueError('bundle hash mismatch: '+name)
    required = {'encoder.onnx','tokenizer.json','skills.json','roles.json','course_profiles.json','lookup_vectors.npz','config.json'}
    if not required <= m['sha256'].keys() or not m.get('model_revision') or not m.get('bundle_version'): raise ValueError('incomplete manifest')
    skills, roles, catalogs, config = (read(p/n) for n in ('skills.json','roles.json','course_profiles.json','config.json'))
    skill_ids = [x['skill_id'] for x in skills]; role_ids = [x['role_id'] for x in roles]
    if len(skill_ids)!=len(set(skill_ids)) or len(role_ids)!=len(set(role_ids)): raise ValueError('duplicate IDs')
    if m['skill_ids'] != skill_ids or m['role_ids'] != role_ids: raise ValueError('vector row order mismatch')
    for r in roles:
        if len({x['skill_id'] for x in r['skills']}) != len(r['skills']) or any(x['skill_id'] not in skill_ids or x['priority'] <= 0 for x in r['skills']): raise ValueError('invalid role skills')
    for catalog in catalogs.values():
        ids = catalog['course_ids']; profiles = catalog['profiles']
        if len(ids)!=len(set(ids)) or len({x['course_id'] for x in profiles})!=len(profiles) or not {x['course_id'] for x in profiles} <= set(ids): raise ValueError('invalid catalog membership')
        validate_equivalence_groups(catalog)
        for profile in profiles:
            tags = profile['skills']
            if profile['source_type'] not in ('description','name_inferred') or len({x['skill_id'] for x in tags}) != len(tags) or any(x['skill_id'] not in skill_ids or x['coverage'] not in (0.5,1.0) for x in tags): raise ValueError('invalid course tags')
    with np.load(p/'lookup_vectors.npz', allow_pickle=False) as data:
        sv, rv = data['skills'], data['roles']
        dim = m['dimension']
        for a, count in ((sv,len(skills)),(rv,len(roles))):
            if a.shape != (count,dim) or not np.isfinite(a).all() or not np.allclose(np.linalg.norm(a,axis=1),1,atol=1e-4): raise ValueError('invalid vectors')
        sv, rv = sv.tolist(), rv.tolist()
    if any(not isinstance(config.get(k),(int,float)) or not -1 <= config[k] <= 1 for k in ('skill_threshold','role_threshold','role_margin','course_threshold')): raise ValueError('invalid thresholds')
    return dict(bundle_version=m['bundle_version'], model_revision=m['model_revision'], bundle_hashes=m['sha256'], dimension=dim, skills=skills, roles=roles, catalogs=catalogs, config=config, skill_vectors=sv, role_vectors=rv, encoder=Encoder(p,dim))
