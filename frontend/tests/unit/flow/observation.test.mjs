import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';

const root=path.resolve(import.meta.dirname,'../../..');
const helperSource=fs.readFileSync(path.join(root,'src/features/flow/lib/observation-window.ts'),'utf8');
const parsed=ts.createSourceFile('observation-window.ts',helperSource,ts.ScriptTarget.Latest,true,ts.ScriptKind.TS);
assert.equal(parsed.statements.some(n=>ts.isImportDeclaration(n)),false);
const js=ts.transpileModule(helperSource,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const bundle={exports:{}};
vm.runInNewContext(js,{module:bundle,exports:bundle.exports,require(){throw Error('unexpected pure helper import');}},{timeout:100});
const helper=bundle.exports;
const cases=JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/cf005-observation-cases.json'),'utf8')).cases;
for(const fixture of cases){
 test(`shared observation evidence: ${fixture.name}`,()=>{
  const input=structuredClone(fixture.signals),before=structuredClone(input);
  const result=helper.observationWindow(input,5,20);
  for(const key of ['status','shownRows','shortCount','longCount'])assert.equal(result[key],fixture.expected[key]);
  assert.deepEqual(JSON.parse(JSON.stringify(result.relations)),fixture.expected.relations);
  const rows=helper.safeDaily(input);
  assert.equal(rows!==null,fixture.expected.safeDaily);
  if(rows){
   assert.deepEqual(JSON.parse(JSON.stringify(rows)),JSON.parse(JSON.stringify(input.daily)));
   for(let i=0;i<rows.length;i++)for(const subject of ['개인','외국인','기관'])assert.ok(Object.is(rows[i][subject],input.daily[i][subject]));
  }
  if(result.status==='unknown')assert.match(result.notice,/미확인.*비교 보류/);
  else if(result.status==='insufficient')assert.match(result.notice,/부족.*비교 보류/);
  else assert.match(result.notice,/제공 자료 기준/);
  assert.match(result.interpretationNotice,/^저장 당시 해석/);
  const cells=helper.persistenceCells(input);
  for(const subject of ['개인','외국인','기관']){
   const claim=input.persistence?.[subject];
   assert.ok(Object.is(cells[subject].short,typeof claim?.sum_5==='number'&&Number.isFinite(claim.sum_5)?claim.sum_5:null));
   assert.ok(Object.is(cells[subject].long,typeof claim?.sum_20==='number'&&Number.isFinite(claim.sum_20)?claim.sum_20:null));
  }
  assert.deepEqual(input,before);
 });
}
for(const bad of [NaN,Infinity,-Infinity,true,'1',null])for(const where of ['cell','short','long']){
 test(`non-finite/type display defense: ${String(bad)} ${where}`,()=>{
  const input=structuredClone(cases[4].signals),before=structuredClone(input);
  if(where==='cell')input.daily[0]['개인']=bad;
  else input.persistence['개인'][where==='short'?'sum_5':'sum_20']=bad;
  const source=structuredClone(input);
  assert.equal(helper.observationWindow(input,5,20).status,'unknown');
  if(where==='cell')assert.equal(helper.safeDaily(input),null);
  else assert.equal(helper.persistenceCells(input)['개인'][where],null);
  assert.deepEqual(input,source);assert.notDeepEqual(input,before);
 });
}
test('display windows, canonical calendar and signed zero retain exact semantics',()=>{
 for(const [short,long] of [[0,20],[true,20],[5,false],[6,5],[5,21]])assert.equal(helper.observationWindow(cases[4].signals,short,long).status,'unknown');
 for(const value of ['2024-02-29','0001-01-01','9999-12-31'])assert.equal(helper.isoDate(value),true);
 for(const value of ['0000-01-01','2026-02-29','2026-01-01T00:00:00Z',null,{},true])assert.equal(helper.isoDate(value),false);
 assert.ok(Object.is(helper.persistenceCells({persistence:{개인:{sum_5:-0,sum_20:0}}})['개인'].short,-0));
});
test('TSX uses safe view before row/date/finite arithmetic and warns beside stored badges and text',()=>{
 const source=fs.readFileSync(path.join(root,'src/features/flow/components/flow-report-view.tsx'),'utf8');
 const tree=ts.createSourceFile('flow-report-view.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const declarations=[];
 function visit(node){if(ts.isVariableDeclaration(node))declarations.push(node);ts.forEachChild(node,visit);}
 visit(tree);
 const daily=declarations.find(n=>n.name.getText(tree)==='daily');
 assert.ok(ts.isCallExpression(daily.initializer));assert.equal(daily.initializer.expression.getText(tree),'safeDaily');
 const max=declarations.find(n=>n.name.getText(tree)==='dailyMax');assert.ok(daily.pos<max.pos);
 assert.ok(source.indexOf('const daily = safeDaily(s)')<source.indexOf('daily.map'));
 assert.doesNotMatch(source,/Number\(row\[name\] \?\? 0\)|String\(row.date/);
 assert.doesNotMatch(source,/sum_5: 0, sum_20: 0/);
 assert.match(source,/finiteNumber\(val\) \? fmtSigned\(val\) : "자료 없음"/);
 assert.match(source,/window.status === "sufficient_rows" && p.consistent === true/);
 const verify=source.slice(source.indexOf('<Card id="verify"'),source.indexOf('gates.map'));
 assert.match(verify,/저장 당시 수치·해석 대조 결과이며 기간 충족 보증이 아닙니다/);assert.match(verify,/window.notice/);
 assert.ok(source.indexOf('window.interpretationNotice')<source.indexOf('<Interpretation text={payload.interpretation} />'));
 assert.match(source,/payload.data_status === "data_limited"/);
 assert.doesNotMatch(source,/^['"]use client/m);
});
