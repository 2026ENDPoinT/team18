import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from course_recommendation import load_bundle, recommend_courses, InputTooLong
p=argparse.ArgumentParser(); p.add_argument('--bundle',required=True); p.add_argument('--input',required=True); a=p.parse_args()
try:
    b=load_bundle(a.bundle); s=json.loads(Path(a.input).read_text()); print(json.dumps(recommend_courses(s,b),ensure_ascii=False,indent=2))
except InputTooLong as e: print(str(e),file=sys.stderr); sys.exit(2)
except Exception as e: print('unavailable: bundle/model could not be loaded:',str(e),file=sys.stderr); sys.exit(1)
