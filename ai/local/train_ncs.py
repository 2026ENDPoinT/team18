"""Classify NCS competency definitions into broad categories on CUDA.

Source: HRD Korea NCS account statistics, not job postings or recommendations.
"""
import argparse, csv, hashlib, json, random, re
from collections import Counter, defaultdict
from pathlib import Path
import torch
from torch import nn

p=argparse.ArgumentParser(); p.add_argument('--data',default='ai/local/data/ncs.csv'); p.add_argument('--output',default='ai/models/ncs-category'); p.add_argument('--epochs',type=int,default=50); args=p.parse_args()
if not torch.cuda.is_available(): raise RuntimeError('CUDA GPU가 필요합니다.')
source=Path(args.data); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
by_desc=defaultdict(set)
with source.open(encoding='cp949',newline='') as f:
    for r in csv.DictReader(f):
        name=r['능력단위명'].strip(); text=' '.join(r['능력단위정의'].split()); category=r['NCS대분류코드명'].strip()
        if len(text)>=15 and name and category: by_desc[text].add((name,category))
# Discard ambiguous duplicate definitions; group by competency name so the same
# competency cannot be shared between training and evaluation.
by_name=defaultdict(list); dropped_ambiguous=0
for text, pairs in by_desc.items():
    if len({cat for _,cat in pairs}) != 1 or len({name for name,_ in pairs}) != 1: dropped_ambiguous+=1; continue
    name,cat=next(iter(pairs)); by_name[name].append((text,cat))
groups=[]
for name,rows in by_name.items():
    if len({category for _,category in rows}) == 1: groups.append((name,rows))
random.Random(42).shuffle(groups)
n=int(len(groups)*0.7); nv=int(len(groups)*0.15)
splits=[groups[:n],groups[n:n+nv],groups[n+nv:]]
categories=sorted({category for _,rows in splits[0] for _,category in rows}); mapping={c:i for i,c in enumerate(categories)}
def flatten(gs): return [(text,category) for _,rows in gs for text,category in rows if category in mapping]
train,val,test=map(flatten,splits); vocab=8192
def matrix(rows):
    x=torch.zeros((len(rows),vocab),dtype=torch.float32)
    for i,(text,_) in enumerate(rows):
        text=re.sub(r'\s+',' ',text.lower())
        for gram in set(text[j:j+2] for j in range(len(text)-1)):
            slot=int.from_bytes(hashlib.blake2b(gram.encode(),digest_size=8).digest(),'little')%vocab; x[i,slot]=1
    return x.cuda(),torch.tensor([mapping[c] for _,c in rows],device='cuda')
X,Y=matrix(train); VX,VY=matrix(val); TX,TY=matrix(test)
torch.manual_seed(42); torch.cuda.manual_seed_all(42)
model=nn.Linear(vocab,len(categories)).cuda(); optimizer=torch.optim.AdamW(model.parameters(),lr=.005,weight_decay=.01)
best=float('inf'); best_epoch=0; state=None
for epoch in range(args.epochs):
    model.train(); optimizer.zero_grad(); loss=nn.functional.cross_entropy(model(X),Y); loss.backward(); optimizer.step()
    model.eval()
    with torch.no_grad(): score=nn.functional.cross_entropy(model(VX),VY).item()
    if score<best: best=score; best_epoch=epoch+1; state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
model.load_state_dict(state); model.eval()
with torch.no_grad():
    logits=model(TX); top1=(logits.argmax(1)==TY).float().mean().item(); top3=(logits.topk(3,dim=1).indices==TY[:,None]).any(dim=1).float().mean().item()
    majority=Counter(c for _,c in train).most_common(1)[0][0]; baseline=sum(c==majority for _,c in test)/len(test)
report={'source':'한국산업인력공단 NCS 분류별 계좌 통계 2025-09-14','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'seed':42,'groups':{'train':len(splits[0]),'validation':len(splits[1]),'test':len(splits[2])},'examples':{'train':len(train),'validation':len(val),'test':len(test)},'ambiguous_definitions_removed':dropped_ambiguous,'categories':len(categories),'best_epoch':best_epoch,'accuracy':round(top1,4),'top3_accuracy':round(top3,4),'majority_baseline':round(baseline,4),'note':'정의 텍스트에서 NCS 대분류를 예측하는 시험. 채용 공고·개인 진로 추천 성능 아님.'}
torch.save({'state_dict':state,'categories':categories,'features':'blake2b char-bigram 8192'},out/'model.pt')
(out/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
