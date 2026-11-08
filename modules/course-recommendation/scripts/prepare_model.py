"""Download a pinned HF revision and export token embeddings; run offline at deployment."""
import argparse
from pathlib import Path
import torch
from transformers import AutoModel, AutoTokenizer
from onnxruntime.quantization import quantize_dynamic, QuantType

p = argparse.ArgumentParser(); p.add_argument('--revision', required=True, help='full immutable Hugging Face commit SHA'); p.add_argument('--output', required=True); p.add_argument('--int8', action='store_true'); args = p.parse_args()
if len(args.revision) != 40 or any(c not in '0123456789abcdef' for c in args.revision): p.error('revision must be a full lowercase commit SHA')
out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
tokenizer=AutoTokenizer.from_pretrained('intfloat/multilingual-e5-small', revision=args.revision, use_fast=True)
tokenizer.backend_tokenizer.save(str(out/'tokenizer.json'))
model=AutoModel.from_pretrained('intfloat/multilingual-e5-small', revision=args.revision).eval()
class Wrapper(torch.nn.Module):
    def __init__(self, inner): super().__init__(); self.inner=inner
    def forward(self, input_ids, attention_mask): return self.inner(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
sample=tokenizer('query: 테스트',return_tensors='pt')
torch.onnx.export(Wrapper(model), (sample['input_ids'], sample['attention_mask']), str(out/'encoder.fp32.onnx'), input_names=['input_ids','attention_mask'], output_names=['last_hidden_state'], dynamic_axes={'input_ids':{0:'batch',1:'sequence'},'attention_mask':{0:'batch',1:'sequence'},'last_hidden_state':{0:'batch',1:'sequence'}}, opset_version=17, dynamo=False)
if args.int8: quantize_dynamic(str(out/'encoder.fp32.onnx'),str(out/'encoder.onnx'),weight_type=QuantType.QInt8)
else: (out/'encoder.fp32.onnx').replace(out/'encoder.onnx')
(out/'model_revision.txt').write_text(args.revision+'\n')
