import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const source=fs.readFileSync('src/features/flow/lib/report-display.ts','utf8');
const bundle={exports:{}};vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:bundle,exports:bundle.exports},{timeout:100});
const h=bundle.exports,cases=JSON.parse(fs.readFileSync('tests/fixtures/cf019-flow-display-cases.json','utf8'));
for(const item of cases.numbers)test('shared display '+item.name,()=>{const input=structuredClone(item);assert.equal(h.displayNumber(item.value,item.precision,item.unit,item.scale),item.expected);assert.deepEqual(item,input);});
for(const [index,item] of cases.gauges.entries())test('shared gauge '+index,()=>assert.equal(h.gaugeVerdict(item.fore,item.inst),item.expected));
for(const [index,item] of cases.institutions.entries())test('shared partial institutional scope '+index,()=>assert.equal(h.institutionLeader(item.values.map((v,i)=>[['기금(연기금)','증권(금융투자)'][i],v])),item.expected));
test('nonfinite values are unavailable, never neutral/0; raw signed zero preserved',()=>{
 for(const v of [NaN,Infinity,-Infinity,false,{},[],undefined]){assert.equal(h.displayNumber(v),'자료 없음');assert.equal(h.displayDirection(v),'판단 보류');assert.equal(h.gaugeVerdict(v,1),'판단 보류');}
 const v=-0;assert.equal(h.displayNumber(v,1,'%'),'0.0%');assert.ok(Object.is(v,-0));assert.match(h.ZERO_LIMIT_NOTICE,/분모 미확인/);assert.match(h.STRENGTH_NOTICE,/100%/);
});
test('actual JSX uses helper/zero caveat/unknown days without rewriting interpretation (source assertion)',()=>{
 const jsx=fs.readFileSync('src/features/flow/components/flow-report-view.tsx','utf8');
 for(const name of ['displayNumber','gaugeVerdict','institutionLeader','STRENGTH_NOTICE','ZERO_LIMIT_NOTICE'])assert.ok(jsx.includes(name));
 assert.doesNotMatch(jsx,/ratio \?\? 0|r.days \?\? 0|세부 전반 순매도/);assert.match(jsx,/r.days === null \? "자료 없음"/);
 assert.match(jsx,/<Interpretation text=\{payload.interpretation\}/);assert.match(jsx,/저장 당시 수치·해석/);
});

test('invalid numeric cells cannot emit a directional price arrow; signed zero is neutral',()=>{
 for(const value of [null,true,'1',NaN,Infinity,-Infinity])assert.equal(h.displayArrow(value),'');
 assert.equal(h.displayArrow(-0),'― ');assert.equal(h.displayArrow(5e-324),'▲ ');assert.equal(h.displayArrow(-5e-324),'▼ ');
 const jsx=fs.readFileSync('src/features/flow/components/flow-report-view.tsx','utf8');assert.match(jsx,/displayNumber\(lastPrice.change_rate, 2, "%"\)/);assert.match(jsx,/consecSignal: days !== null/);
});
