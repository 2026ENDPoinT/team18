"""GPU experiment: predict O*NET software categories from held-out occupations.

This is a US occupational data experiment, not a job-posting or Korean-market model.
"""
import argparse, csv, hashlib, json, random, re
from collections import Counter, defaultdict
from pathlib import Path
import torch
from torch import nn

p = argparse.ArgumentParser()
p.add_argument('--data', default='ai/local/data')
p.add_argument('--output', default='ai/models/onet-skills')
p.add_argument('--epochs', type=int, default=120)
p.add_argument('--balanced', action='store_true')
args = p.parse_args()
if not torch.cuda.is_available(): raise RuntimeError('CUDA 지원 GPU가 필요합니다.')
base = Path(args.data); out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
with (base/'occupation_data.csv').open(encoding='utf-8-sig', newline='') as f:
    occupations = {r['O*NET-SOC Code']:r for r in csv.DictReader(f)}
with (base/'software_skills.csv').open(encoding='utf-8-sig', newline='') as f:
    labels = defaultdict(set)
    for r in csv.DictReader(f):
        if r['O*NET-SOC Code'] in occupations and r['Element Name'].strip(): labels[r['O*NET-SOC Code']].add(r['Element Name'].strip())
ids = sorted(labels); random.Random(42).shuffle(ids)
n_train, n_val = int(len(ids)*0.7), int(len(ids)*0.15)
train, val, test = ids[:n_train], ids[n_train:n_train+n_val], ids[n_train+n_val:]
counts = Counter(label for code in train for label in labels[code])
classes = sorted(k for k,v in counts.items() if v >= 10)
vocab_size = 8192
def features(text):
    out = torch.zeros(vocab_size)
    for word in set(re.findall(r'[a-z0-9]+', text.lower())):
        index = int.from_bytes(hashlib.blake2b(word.encode(),digest_size=8).digest(),'little') % vocab_size
        out[index] = 1
    return out
def prepare(codes):
    x=torch.stack([features(occupations[c]['Title']+' '+occupations[c]['Description']) for c in codes]).cuda()
    y=torch.tensor([[float(k in labels[c]) for k in classes] for c in codes],device='cuda')
    return x,y
X,Y=prepare(train); VX,VY=prepare(val); TX,TY=prepare(test)
torch.manual_seed(42); torch.cuda.manual_seed_all(42)
model=nn.Linear(vocab_size,len(classes)).cuda()
opt=torch.optim.AdamW(model.parameters(),lr=0.005,weight_decay=0.01)
best=float('inf'); best_state=None; best_epoch=0
pos_weight = ((len(train)-Y.sum(dim=0))/Y.sum(dim=0).clamp(min=1)).sqrt() if args.balanced else None
for epoch in range(args.epochs):
    model.train(); opt.zero_grad(); loss=nn.functional.binary_cross_entropy_with_logits(model(X),Y,pos_weight=pos_weight); loss.backward(); opt.step()
    model.eval()
    with torch.no_grad(): validation=nn.functional.binary_cross_entropy_with_logits(model(VX),VY,pos_weight=pos_weight).item()
    if validation < best:
        best=validation; best_epoch=epoch+1; best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
model.load_state_dict(best_state); model.eval()
def evaluate(logits, truth):
    pred=logits.topk(3,dim=1).indices
    hits=truth.gather(1,pred).sum(dim=1)
    return {'precision_at_3':round((hits/3).mean().item(),4),'recall_at_3':round((hits/truth.sum(dim=1).clamp(min=1)).mean().item(),4),'examples':len(truth)}
with torch.no_grad():
    result=evaluate(model(TX),TY)
    baseline=evaluate(Y.mean(dim=0).expand(len(test),-1),TY)
    unsupported=sum(not any(k in labels[c] for k in classes) for c in test)
hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [base/'occupation_data.csv',base/'software_skills.csv']}
report={'source':'O*NET 31.0','seed':42,'balanced':args.balanced,'train_occupations':len(train),'validation_occupations':len(val),'test_occupations':len(test),'class_count':len(classes),'test_without_supported_labels':unsupported,'best_epoch':best_epoch,'model':result,'common_category_baseline':baseline,'sha256':hashes,'warning':'US occupation-level categories only, not Korean postings or student-specific recommendations.'}
torch.save({'state_dict':best_state,'classes':classes,'vocab_size':vocab_size,'source':'O*NET 31.0'},out/'model.pt')
(out/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
