// Verify in a newly created env-free project copy; never load the real .env files.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const workspace=path.resolve(project,'../..');
const temporary=fs.mkdtempSync(path.join(workspace,'.cf002-port-check-'));
const environment={PATH:process.env.PATH,LANG:'en_US.UTF-8',NEXT_TELEMETRY_DISABLED:'1'};
function run(args) {execFileSync(process.execPath,args,{cwd:temporary,env:environment,stdio:'inherit'});}
try {
 for(const name of ['src','public','tests','package.json','package-lock.json','tsconfig.json','next.config.ts','postcss.config.mjs','eslint.config.mjs']) {
  const source=path.join(project,name);
  if(fs.existsSync(source))fs.cpSync(source,path.join(temporary,name),{recursive:true,filter:value=>!path.basename(value).startsWith('.env')});
 }
 fs.symlinkSync(path.join(project,'node_modules'),path.join(temporary,'node_modules'),'dir');
 const config=path.join(temporary,'next.config.ts');
 fs.writeFileSync(config,fs.readFileSync(config,'utf8').replace('const nextConfig: NextConfig = {',`const nextConfig: NextConfig = {\n  turbopack: {root: ${JSON.stringify(workspace)}},`));
 console.log('Env-free frontend copy: private env files copied = 0; inherited app configuration = 0');
 run(['--test','tests/disabled-routes.test.mjs','tests/session-proxy.test.mjs','tests/ports.test.mjs']);
 for(const file of ['tests/disabled-http.test.mjs','tests/session-http.test.mjs','tests/ports-http.test.mjs'])run(['--test',file]);
 run(['node_modules/next/dist/bin/next','build']);
 run(['node_modules/typescript/bin/tsc','--noEmit','--incremental','false']);
 run(['node_modules/eslint/bin/eslint.js','src/lib/session-backend.ts','src/lib/session-proxy.ts','src/lib/archive-pagination.ts','src/app/page.tsx','src/app/reports/flow/[reportId]/page.tsx','src/features/flow/components/session-controls.tsx','src/api/backend.ts','tests/ports.test.mjs','tests/ports-http.test.mjs']);
 console.log('Env-free frontend unit/HTTP/build/type/lint passed');
} finally {
 if(path.dirname(temporary)!==workspace || !path.basename(temporary).startsWith('.cf002-port-check-'))throw new Error('Refusing unexpected cleanup target');
 fs.rmSync(temporary,{recursive:true,force:true});
 console.log('Removed owned temporary frontend project');
}
