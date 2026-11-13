import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { helpExamples, helpForPath } from '../../src/components/help/examples.mjs';
import { resultTabs } from '../../src/features/roadmap/resultPresentation.mjs';

test('all input pages and every result tab have a distinct, readable screenshot and alternative text',()=>{
 const keys=[...Object.values(helpForPath),...resultTabs.map(tab=>'result-'+tab.key)];
 assert.equal(keys.length,8);const hashes=new Set();
 for(const key of keys){
  const example=helpExamples[key];assert.ok(example.title&&example.alt.length>30&&example.description);
  const png=readFileSync(new URL(`../../public/help/${key}.png`,import.meta.url));
  assert.equal(png.subarray(1,4).toString(),'PNG');
  assert.ok(png.readUInt32BE(16)>=1000&&png.readUInt32BE(20)>=600,'capture has readable source resolution');
  hashes.add(createHash('sha256').update(png).digest('hex'));
 }
 assert.equal(hashes.size,8,'one screenshot cannot be reused for different steps');
});
