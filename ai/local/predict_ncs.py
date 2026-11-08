"""Classify an NCS-style Korean competency definition, not a job recommendation."""
import argparse, hashlib, json, re
import torch
from torch import nn

p=argparse.ArgumentParser()
p.add_argument('text', help='NCS 능력단위 정의에 가까운 한국어 문장')
p.add_argument('--model',default='ai/models/ncs-category/model.pt')
args=p.parse_args()
checkpoint=torch.load(args.model,map_location='cpu',weights_only=True)
categories=checkpoint['categories']; state=checkpoint['state_dict']
model=nn.Linear(8192,len(categories)); model.load_state_dict(state); model.eval()
text=re.sub(r'\s+',' ',args.text.lower()); x=torch.zeros((1,8192))
for gram in set(text[j:j+2] for j in range(len(text)-1)):
    x[0,int.from_bytes(hashlib.blake2b(gram.encode(),digest_size=8).digest(),'little')%8192]=1
with torch.inference_mode():
    scores=torch.softmax(model(x),dim=1)[0]; indices=scores.topk(min(3,len(categories))).indices.tolist()
print(json.dumps({'predictions':[{'category':categories[i],'score':round(scores[i].item(),4)} for i in indices], 'notice':'NCS 능력단위 정의 분류 실험. 점수는 보정된 확률이나 취업 가능성을 의미하지 않습니다.'},ensure_ascii=False,indent=2))
