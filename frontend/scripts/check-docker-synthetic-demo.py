"""CF010 only: prepare reviewed public inputs, then one owned Docker build/HTTP run.

No arbitrary command/image/source/registry passthrough. Prepare performs no Docker
operations; run consumes the unchanged, independently reviewed prepared directory.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import stat
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'
PREPARED_PARENT = Path('/tmp').resolve()
BASE = '8d4b2f8f9ce916eeca77de55adbfb68d3006afce'
BRANCH = 'test/flow-docker-synthetic-http'
REMOTE = 'https://github.com/bellra-jin/verith.git'
IMAGE = 'sha256:50e2bfc1d63c54b4925099d98a484ac1bcaa54a93e8efce53706f8a92fecf615'
DIGEST = 'node@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9'
PACKAGE_SHA = '5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5'
LOCK_SHA = 'bb3a6a2b6c2e6374a4fa43ab8d3022ea678b0e60a003ff2b2aafb5610a7c7fed'
DOCKER = '/Applications/Docker.app/Contents/Resources/bin/docker'
ENDPOINT = 'unix:///Users/parkjinhee/.docker/run/docker.sock'
MANIFEST_PATH = 'frontend/scripts/cf010-public-source-manifest.json'
RUNNER_PATH = 'frontend/scripts/check-docker-synthetic-demo.py'
ADAPTER_PATH = 'frontend/tests/helpers/docker-synthetic-demo-http.mjs'
TESTS = ['frontend/tests/integration/bff/ports-http.test.mjs', 'frontend/tests/integration/bff/synthetic-demo-http.test.mjs']
SUITE = ['docker-tests/integration/bff/ports-http.test.mjs', 'docker-tests/integration/bff/synthetic-demo-http.test.mjs']
SCOPE = {RUNNER_PATH, ADAPTER_PATH, TESTS[1], MANIFEST_PATH, 'docs/documentation.md', 'docs/work/CF-010-docker-synthetic-demo.md'}
CONFIGS = {'package.json','package-lock.json','tsconfig.json','next.config.ts','postcss.config.mjs','eslint.config.mjs'}
ASSETS = {'file.svg','globe.svg','next.svg','vercel.svg','window.svg'}
PRIVATE = {'private','secret','secrets','credential','credentials','key','keys','dump','dumps','log','logs','cache','profile','backup','backups','node_modules','.next','.git'}
PRIVATE_ROUTE = 'frontend/src/app/api/private/[...path]/route.ts'
READY_TARGET = 'src/app/cf010-ready/route.ts'
READY = b"export const dynamic='force-dynamic';\nexport function GET(){return Response.json({nonce:process.env.CF010_READY_NONCE,pid:process.pid,cwd:process.cwd()});}\n"
ENV = ['PATH=/usr/local/bin:/usr/bin:/bin','HOME=/tmp/home','TMPDIR=/tmp','TZ=UTC','LANG=C.UTF-8','OPENSSL_CONF=/dev/null','NEXT_TELEMETRY_DISABLED=1','NO_UPDATE_NOTIFIER=1','NPM_CONFIG_USERCONFIG=/tmp/user.npmrc','NPM_CONFIG_GLOBALCONFIG=/tmp/global.npmrc','NPM_CONFIG_CACHE=/work/npm-cache']
INSTALL = ['/usr/bin/timeout','--signal=TERM','--kill-after=5','360','npm','ci','--ignore-scripts','--no-audit','--no-fund','--registry=https://registry.npmjs.org']
BUILD = ['/usr/bin/timeout','--signal=TERM','--kill-after=5','420','npm','run','build','--','--webpack']
HTTP = ['/usr/bin/timeout','--signal=TERM','--kill-after=5','450','node','--test','--test-reporter=tap','--test-concurrency=1',*SUITE]
TMPFS = {'/work':'rw,exec,nosuid,nodev,size=3g,uid=1000,gid=1000,mode=0700','/tmp':'rw,noexec,nosuid,nodev,size=256m,uid=1000,gid=1000,mode=0700'}
HOST_FIELDS = ['ReadonlyRootfs','Privileged','CapDrop','CapAdd','SecurityOpt','NanoCpus','Memory','PidsLimit','RestartPolicy','Tmpfs','Binds','VolumesFrom','Links','PortBindings','PidMode','NetworkMode','IpcMode']
INSPECT = ('{"id":{{json .Id}},"name":{{json .Name}},"created":{{json .Created}},"running":{{json .State.Running}},"image":{{json .Image}},"labels":{{json .Config.Labels}},"user":{{json .Config.User}},"host":{' + ','.join('"'+key+'":{{json .HostConfig.'+key+'}}' for key in HOST_FIELDS) + '},"mounts":{{json .Mounts}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}}}')

class CheckFailure(RuntimeError):
    pass

def require(value, label):
    if not value:
        raise CheckFailure(label)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stamp():
    return datetime.now(timezone.utc).isoformat()

def utc_nanoseconds(value):
    require(isinstance(value,datetime) and value.utcoffset()==timedelta(0),'creation window UTC required')
    elapsed=value-datetime(1970,1,1,tzinfo=timezone.utc)
    return (elapsed.days*86400+elapsed.seconds)*1000000000+elapsed.microseconds*1000

def docker_created_nanoseconds(value):
    require(isinstance(value,str),'Docker Created timestamp format')
    match=re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(?:Z|\+00:00)',value,re.ASCII)
    require(match is not None,'Docker Created timestamp format')
    try:whole=datetime.strptime(match.group(1),'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    except ValueError:raise CheckFailure('Docker Created timestamp value') from None
    return utc_nanoseconds(whole)+int((match.group(2) or '').ljust(9,'0'))

def git(*args):
    env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_OPTIONAL_LOCKS':'0'}
    return subprocess.run(['/usr/bin/git','-C',str(ROOT),*args],env=env,check=True,capture_output=True).stdout

def check_git():
    require(git('branch','--show-current').decode().strip()==BRANCH,'branch mismatch')
    require(git('rev-parse','HEAD').decode().strip()==BASE,'base mismatch')
    require(git('rev-parse','origin/develop').decode().strip()==BASE,'base reference changed')
    for args in [('remote','get-url','--all','origin'),('remote','get-url','--push','--all','origin')]:
        require(git(*args).decode().splitlines()==[REMOTE],'origin mismatch')
    require(git('worktree','list','--porcelain').count(b'worktree ')==1,'worktree mismatch')
    require(not git('diff','--cached','--name-only'),'staged changes')
    changed={entry[3:] for entry in git('status','--porcelain=v1','-z','-uall').decode().split('\0') if entry}
    require(changed<=SCOPE,'change outside exact scope')

def relative(name):
    p=PurePosixPath(name)
    require(isinstance(name,str) and not p.is_absolute() and str(p)==name and p.parts and all(part not in {'.','..'} and '\\' not in part and not any(ord(c)<32 for c in part) for part in p.parts),'unsafe relative path')
    return p

def stable_read(root, name):
    p=relative(name)
    require(root.is_absolute() and root.resolve(strict=True)==root,'noncanonical source root')
    fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid)
    root_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);directories=[root_fd];chain=[]
    try:
        root_before=os.fstat(root_fd);require(identity(root_before)==identity(root.lstat()),'root identity drift')
        parent=root_fd
        for part in p.parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);directories.append(child)
            chain.append((parent,part,child,identity(os.fstat(child))));parent=child
        named=os.stat(p.name,dir_fd=parent,follow_symlinks=False)
        require(stat.S_ISREG(named.st_mode) and named.st_nlink==1,'nonregular/linked source')
        fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        with os.fdopen(fd,'rb') as f:
            before=os.fstat(f.fileno());require(fields(before)==fields(named),'source replaced before open')
            data=f.read();after=os.fstat(f.fileno())
        require(fields(before)==fields(after)==fields(os.stat(p.name,dir_fd=parent,follow_symlinks=False)),'source identity drift')
        for parent,part,child,expected in chain:
            require(identity(os.fstat(child))==expected==identity(os.stat(part,dir_fd=parent,follow_symlinks=False)),'parent identity drift')
        require(identity(root_before)==identity(root.lstat()),'root identity drift')
        return data
    finally:
        for fd in reversed(directories):os.close(fd)

def role_target(source):
    p=relative(source)
    if source==ADAPTER_PATH:return 'adapter','docker-tests/helpers/safe-http.mjs'
    if source in TESTS:return 'http-test','docker-tests/integration/bff/'+p.name
    if p.parts[:2]==('frontend','src'):
        if source!=PRIVATE_ROUTE:
            require(not any(part.lower() in PRIVATE or set(re.split(r'[._-]',part.lower()))&PRIVATE or part.lower().startswith(('.env','.npmrc','credentials')) or any(part.lower().endswith(suffix) for suffix in ('.key','.pem','.sql','.log','.dump','.bak')) for part in p.parts),'private source name')
        if p.suffix in {'.ts','.tsx','.css','.ico'}:return 'product',str(PurePosixPath(*p.parts[1:]))
    if len(p.parts)==2 and p.parts[0]=='frontend' and p.name in CONFIGS:return 'configuration',p.name
    if len(p.parts)==3 and p.parts[:2]==('frontend','public') and p.name in ASSETS:return 'asset','public/'+p.name
    return None

def lock_check(package, lock):
    require(sha(package)==PACKAGE_SHA and sha(lock)==LOCK_SHA,'package/lock identity mismatch')
    d=json.loads(lock);require(d.get('lockfileVersion')==3,'lock version')
    for name,item in d['packages'].items():
        if name:relative(name)
        require(not item.get('link'),'linked lock dependency')
        if name:
            require(isinstance(item.get('resolved'),str) and item['resolved'].startswith('https://registry.npmjs.org/') and re.fullmatch(r'sha(?:256|384|512)-[A-Za-z0-9+/=]+',item.get('integrity','')),'unreviewed lock source')

def collect():
    rows={}
    for record in git('ls-files','--stage','-z').decode().split('\0'):
        if not record:continue
        metadata,source=record.split('\t',1)
        if not source.startswith('frontend/'):continue
        # Excluded names are classified without reading their contents.
        try:selection=role_target(source)
        except CheckFailure:continue
        if selection:
            require(metadata.startswith('100644 ') and metadata.endswith(' 0'),'unsupported tracked source')
            require(source not in rows,'duplicate source');rows[source]=selection
    rows[ADAPTER_PATH]=role_target(ADAPTER_PATH)
    require(all('frontend/'+p in rows for p in CONFIGS) and all(p in rows for p in TESTS),'required source missing')
    require(all('frontend/public/'+p in rows for p in ASSETS),'public asset missing')
    require(len({target for _,target in rows.values()})==len(rows),'duplicate target')
    data={p:stable_read(ROOT,p) for p in sorted(rows)}
    lock_check(data['frontend/package.json'],data['frontend/package-lock.json'])
    for p,raw in data.items():require(stable_read(ROOT,p)==raw,'source drift after collection')
    return rows,data

def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()

def archive(entries):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        for name,data in sorted(entries.items()):
            relative(name);info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600 if name=='.cf010-owner.json' else 0o644;info.uid=info.gid=1000;info.mtime=0;info.uname=info.gname='node';tar.addfile(info,io.BytesIO(data))
    return out.getvalue()

def create_args(owner, manifest_sha):
    args=['create','--pull=never','--name',owner,'--label','verith.cf010.owner='+owner,'--label','verith.cf010.resource='+manifest_sha,'--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--restart=no','--cpus','2','--memory','4g','--pids-limit','256','--network','bridge']
    for target,options in TMPFS.items():args+=['--tmpfs',target+':'+options]
    return args+['--workdir','/work','--entrypoint','/usr/bin/timeout',IMAGE,'--signal=TERM','--kill-after=5','1500','/bin/sleep','1500']

def execution_plan(cp, owner, manifest_sha):
    return {'docker_prefix':[DOCKER,'--host',ENDPOINT,'--config',str(cp/'cli-home/docker-config')], 'create_argv':create_args(owner,manifest_sha),'install':INSTALL,'build':BUILD,'http':HTTP,'exec_prefix':['exec','-i','--user','1000:1000','--workdir','/work','<exact-created-CID>','/usr/bin/env','-i',*ENV,'CF010_OWNER='+owner], 'network_off_argv':['network','disconnect','bridge','<exact-created-CID>'], 'namespace_proof':NETWORK_PROOF,'source_proof':VERIFY_SOURCE,'install_proof':INSTALL_PROOF,'setup':SETUP, 'copy_argv':['/bin/tar','--extract','--file','-','--directory','/work','--no-same-owner','--no-same-permissions'], 'limits':{'total_seconds':1500,'install_seconds':360,'build_seconds':420,'http_seconds':450},'network_sequence':['bridge for locked npm ci only','disconnect own CID; require zero connected networks and no external routes','build and local HTTP; never reconnect'], 'copy_sequence':['install-input.tar package/lock only','source-input.tar only after network-off'], 'cleanup':'verify exact CID/name/owner/resource/image/Created, rm --force, explicit No such container and exact label empty'}

def prepare():
    check_git();rows,data=collect()
    require(not (FRONTEND/'src/app/cf010-ready').exists() and not (FRONTEND/'src/app/cf010-ready').is_symlink(),'readiness source collision')
    require(not (FRONTEND/'.cf010-owner.json').exists() and not (FRONTEND/'.cf010-owner.json').is_symlink(),'ownership source collision')
    owner='cf010-'+secrets.token_hex(12);nonce=secrets.token_hex(32)
    marker=json_bytes({'schema':1,'owner':owner,'nonce':nonce,'root':'/work'})
    derived={READY_TARGET:READY,'.cf010-owner.json':marker}
    require(not set(derived)&{target for _,target in rows.values()},'derived target collision')
    manifest={'schema':1,'task':'CF-010','base':BASE,'image':IMAGE,'repo_digest':DIGEST,'platform':'linux/arm64','package_sha256':PACKAGE_SHA,'lock_sha256':LOCK_SHA,'suite':SUITE,'runner_sha256':sha(stable_read(ROOT,RUNNER_PATH)),'files':[{'source':p,'target':rows[p][1],'role':rows[p][0],'size':len(raw),'sha256':sha(raw)} for p,raw in data.items()],'derived':[{'target':p,'role':'readiness' if p==READY_TARGET else 'ownership','size':len(raw),'sha256':sha(raw)} for p,raw in sorted(derived.items())]}
    manifest_raw=json_bytes(manifest)
    cp=Path(tempfile.mkdtemp(prefix='cf010-prepared-',dir=PREPARED_PARENT)).resolve();cp.chmod(0o700)
    package={'package.json':data['frontend/package.json'],'package-lock.json':data['frontend/package-lock.json']}
    remaining={rows[p][1]:raw for p,raw in data.items() if rows[p][1] not in package}
    remaining.update(derived);remaining['cf010-source-manifest.json']=manifest_raw
    plan_raw=json_bytes(execution_plan(cp,owner,sha(manifest_raw)))
    payloads={'install-input.tar':archive(package),'source-input.tar':archive(remaining),'manifest.json':manifest_raw,'execution-plan.json':plan_raw}
    for name,raw in payloads.items():(cp/name).write_bytes(raw)
    metadata=cp.stat()
    record={'schema':1,'owner':owner,'directory_identity':[metadata.st_dev,metadata.st_ino,metadata.st_uid],'created_at':stamp(),'runner_sha256':manifest['runner_sha256'],'manifest_sha256':sha(manifest_raw),'artifacts':{name:{'size':len(raw),'sha256':sha(raw)} for name,raw in payloads.items()}}
    (cp/'prepared.json').write_bytes(json_bytes(record));(ROOT/MANIFEST_PATH).write_bytes(manifest_raw)
    verify_prepared(cp)  # Source/archive/plan validation only; no Docker call.
    print(json.dumps({'phase':'prepared_no_runtime','directory':str(cp),'manifest_sha256':sha(manifest_raw),'source_files':len(rows),'runner_sha256':record['runner_sha256'],'execution_plan_sha256':sha((cp/'execution-plan.json').read_bytes())}),flush=True)

VERIFY_SOURCE = r"""
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const manifestBytes=fs.readFileSync('/work/cf010-source-manifest.json');
if(crypto.createHash('sha256').update(manifestBytes).digest('hex')!==process.argv[1])throw Error('CF010 manifest hash');
const manifest=JSON.parse(manifestBytes);
for(const entry of [...manifest.files,...manifest.derived]){
 let current='/work';for(const part of entry.target.split('/')){if(!part||part==='.'||part==='..')throw Error('CF010 unsafe target');current=path.join(current,part);const s=fs.lstatSync(current);if(s.isSymbolicLink())throw Error('CF010 source symlink');}
 const fd=fs.openSync(current,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);try{const s=fs.fstatSync(fd,{bigint:true});if(!s.isFile()||s.nlink!==1n||s.uid!==1000n)throw Error('CF010 source identity');const bytes=fs.readFileSync(fd);const after=fs.fstatSync(fd,{bigint:true}),named=fs.lstatSync(current,{bigint:true});for(const k of ['dev','ino','size','mtimeNs','ctimeNs'])if(s[k]!==after[k]||s[k]!==named[k])throw Error('CF010 source drift');if(bytes.length!==entry.size||crypto.createHash('sha256').update(bytes).digest('hex')!==entry.sha256)throw Error('CF010 source hash');}finally{fs.closeSync(fd);}
}
console.log(JSON.stringify({phase:'container_source_hashes',files:manifest.files.length,derived:manifest.derived.length,status:'matched'}));
"""
INSTALL_PROOF = r"""
const fs=require('node:fs'),crypto=require('node:crypto');
for(const [name,hash] of [['package.json',process.argv[1]],['package-lock.json',process.argv[2]]]){const file='/work/'+name,s=fs.lstatSync(file);if(!s.isFile()||s.nlink!==1||s.uid!==1000||crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')!==hash)throw Error('CF010 install input hash');}
if(fs.existsSync('/work/.npmrc'))throw Error('CF010 project npmrc forbidden');
for(const file of ['/tmp/user.npmrc','/tmp/global.npmrc'])if(fs.readFileSync(file).length!==0)throw Error('CF010 npmrc drift');
const lock=JSON.parse(fs.readFileSync('/work/package-lock.json','utf8'));
if(lock.lockfileVersion!==3)throw Error('CF010 lock version');
for(const [name,item] of Object.entries(lock.packages))if(name&&(!item.resolved?.startsWith('https://registry.npmjs.org/')||!/^sha(256|384|512)-[A-Za-z0-9+/=]+$/.test(item.integrity)||item.link))throw Error('CF010 dependency source');
console.log(JSON.stringify({phase:'package_lock_verified',resolved:Object.keys(lock.packages).length-1}));
"""
NETWORK_PROOF = r"""
const fs=require('node:fs'),os=require('node:os');
const devText=fs.readFileSync('/proc/net/dev','utf8');
const devLines=devText.trim().split('\n'),devRows=devLines.slice(2);
const devices=devRows.map(v=>v.split(':')[0].trim());
const namePattern=/^[A-Za-z0-9_.:-]{1,32}$/,templates=new Set(['tunl0','gre0','gretap0','erspan0','ip_vti0','ip6_vti0','sit0','ip6tnl0','ip6gre0']);
console.log(JSON.stringify({phase:'namespace_interface_observation',lineCount:devLines.length,dataRowCount:devRows.length,colonMissingRowCount:devRows.filter(v=>!v.includes(':')).length,interfaceCount:devices.length,invalidNameCount:devices.filter(name=>!namePattern.test(name)).length,unknownInterfaceCount:devices.filter(name=>name!=='lo'&&!templates.has(name)).length}));
const deviceSet=new Set(devices);
if(devRows.some(v=>!v.includes(':'))||deviceSet.size!==devices.length||!deviceSet.has('lo')||devices.some(name=>!namePattern.test(name)||(name!=='lo'&&!templates.has(name))))throw Error('CF010 unknown or malformed interface');
const ipv4Lines=fs.readFileSync('/proc/net/route','utf8').trim().split('\n');
if(ipv4Lines[0].trim().split(/\s+/).join(',')!=='Iface,Destination,Gateway,Flags,RefCnt,Use,Metric,Mask,MTU,Window,IRTT')throw Error('CF010 IPv4 route header malformed');
const ipv4=ipv4Lines.slice(1).map(line=>line.trim().split(/\s+/));
if(ipv4.some(row=>row.length!==11||!namePattern.test(row[0])||![1,2,7].every(i=>/^[0-9a-fA-F]{8}$/.test(row[i]))||!/^[0-9a-fA-F]{4}$/.test(row[3])||![4,5,6,8,9,10].every(i=>/^[0-9]{1,20}$/.test(row[i]))))throw Error('CF010 IPv4 route row malformed');
const ipv6Text=fs.readFileSync('/proc/net/ipv6_route','utf8').trim();
const ipv6=ipv6Text===''?[]:ipv6Text.split('\n').map(line=>line.trim().split(/\s+/));
if(ipv6.some(row=>row.length!==10||![0,2,4].every(i=>/^[0-9a-fA-F]{32}$/.test(row[i]))||![1,3].every(i=>/^[0-9a-fA-F]{2}$/.test(row[i])&&Number.parseInt(row[i],16)<=128)||![5,6,7,8].every(i=>/^[0-9a-fA-F]{8}$/.test(row[i]))||!namePattern.test(row[9])))throw Error('CF010 IPv6 route row malformed');
console.log(JSON.stringify({phase:'namespace_route_observation',ipv4RowCount:ipv4.length,ipv4ExternalRouteCount:ipv4.filter(row=>row[0]!=='lo').length,ipv6RowCount:ipv6.length,ipv6ExternalRouteCount:ipv6.filter(row=>row[9]!=='lo').length}));
let addresses;
try{addresses=os.networkInterfaces();}catch{throw Error('CF010 interface address read failed');}
if(!addresses||typeof addresses!=='object'||Array.isArray(addresses)||Object.keys(addresses).some(name=>!namePattern.test(name)||!deviceSet.has(name)))throw Error('CF010 interface address set mismatch');
const states=[];
for(const name of devices){
 let rawFlags;
 try{rawFlags=fs.readFileSync('/sys/class/net/'+name+'/flags','utf8').trim();}catch{throw Error('CF010 interface flags read failed');}
 if(!/^0x[0-9a-fA-F]{1,8}$/.test(rawFlags))throw Error('CF010 interface flags malformed');
 const flags=Number.parseInt(rawFlags.slice(2),16),entries=Object.hasOwn(addresses,name)?addresses[name]:[];
 if(!Array.isArray(entries)||entries.some(entry=>!entry||typeof entry.address!=='string'||typeof entry.internal!=='boolean'||!['IPv4','IPv6'].includes(entry.family)))throw Error('CF010 interface addresses malformed');
 const isLoopback=entry=>{
  if(!entry.internal)return false;
  if(entry.family==='IPv6')return ['::1','0:0:0:0:0:0:0:1'].includes(entry.address.toLowerCase());
  const parts=entry.address.split('.');
  return parts.length===4&&parts[0]==='127'&&parts.every(part=>/^\d{1,3}$/.test(part)&&Number(part)<=255);
 };
 states.push({name,up:(flags&1)!==0,loopbackFlag:(flags&8)!==0,reportedIPv4AddressCount:entries.filter(entry=>entry.family==='IPv4').length,reportedIPv6AddressCount:entries.filter(entry=>entry.family==='IPv6').length,loopbackAddressesOnly:entries.every(isLoopback)});
}
const lo=states.find(state=>state.name==='lo'),nonLoopback=states.filter(state=>state.name!=='lo');
console.log(JSON.stringify({phase:'namespace_interface_state',interfaceCount:states.length,loopbackUp:lo.up,loopbackFlag:lo.loopbackFlag,loopbackReportedIPv4Count:lo.reportedIPv4AddressCount,loopbackReportedIPv6Count:lo.reportedIPv6AddressCount,loopbackAddressesOnly:lo.loopbackAddressesOnly,templateCount:nonLoopback.length,templateUpCount:nonLoopback.filter(state=>state.up).length,templateLoopbackFlagCount:nonLoopback.filter(state=>state.loopbackFlag).length,templateReportedIPv4AddressCount:nonLoopback.reduce((n,state)=>n+state.reportedIPv4AddressCount,0),templateReportedIPv6AddressCount:nonLoopback.reduce((n,state)=>n+state.reportedIPv6AddressCount,0)}));
for(const state of states){
 const count=state.reportedIPv4AddressCount+state.reportedIPv6AddressCount;
 if(state.name==='lo'){
  if(!state.up||!state.loopbackFlag||count===0||!state.loopbackAddressesOnly)throw Error('CF010 loopback state mismatch');
 }else if(state.up||state.loopbackFlag||count!==0)throw Error('CF010 template has connectivity state');
}
if(ipv4.some(row=>row[0]!=='lo'))throw Error('CF010 external route');
if(ipv6.some(row=>row[9]!=='lo'))throw Error('CF010 external IPv6 route');
console.log(JSON.stringify({phase:'namespace_network_off',interfaceCount:devices.length,templateCount:nonLoopback.length,ipv4RouteCount:ipv4.length,ipv6RouteCount:ipv6.length,readonlyStateVerified:true}));
"""

SETUP = r"""
const fs=require('node:fs');
if(process.getuid()!==1000||process.getgid()!==1000||process.cwd()!=='/work')throw Error('CF010 runtime identity');
for(const dir of ['/work','/tmp']){const s=fs.lstatSync(dir);if(!s.isDirectory()||s.isSymbolicLink()||s.uid!==1000||s.gid!==1000||(s.mode&0o777)!==0o700)throw Error('CF010 tmpfs ownership');}
fs.mkdirSync('/tmp/home',{mode:0o700});fs.writeFileSync('/tmp/user.npmrc','',{flag:'wx',mode:0o600});fs.writeFileSync('/tmp/global.npmrc','',{flag:'wx',mode:0o600});
console.log(JSON.stringify({phase:'runtime_identity',node:process.version,uid:process.getuid(),gid:process.getgid(),cwd:process.cwd()}));
"""

class DockerRun:
    def __init__(self, cp, record):
        self.cp=cp;self.record=record;self.owner=record['owner'];self.cid=None;self.created=None;self.requested=None;self.returned=None;self.creation_attempted=False;self.deadline=time.monotonic()+1500
        self.home=cp/'cli-home';self.home.mkdir(mode=0o700);self.config=self.home/'docker-config';self.config.mkdir(mode=0o700)
        self.env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(self.home),'DOCKER_CONFIG':str(self.config),'LANG':'en_US.UTF-8','TZ':'UTC'}
        require(stat.S_ISSOCK(Path(ENDPOINT.removeprefix('unix://')).stat().st_mode),'local Docker socket unavailable')
        self.events=[];self.stage='preflight'

    def event(self, phase, **fields):
        self.stage=phase;value={'phase':phase,'at':stamp(),**fields};self.events.append(value);print(json.dumps(value),flush=True);(self.cp/'events.json').write_bytes(json_bytes(self.events))

    def call(self, args, *, timeout=15, data=None, allow_failure=False, cleanup=False):
        remaining=self.deadline-time.monotonic()-(0 if cleanup else 60);require(remaining>0,'host deadline')
        limit=min(timeout,remaining)
        result=subprocess.run([DOCKER,'--host',ENDPOINT,'--config',str(self.config),*args],input=data,env=self.env,capture_output=True,timeout=limit)
        if not allow_failure:require(result.returncode==0,'Docker fixed operation failed')
        return result

    def inspect(self):
        return json.loads(self.call(['inspect','--format',INSPECT,self.cid]).stdout)

    def identity(self, info):
        require(info['id']==self.cid and info['name']=='/'+self.owner,'container identity mismatch')
        require(info['labels'].get('verith.cf010.owner')==self.owner and info['labels'].get('verith.cf010.resource')==self.record['manifest_sha256'],'owner label mismatch')
        require(info['image']==IMAGE,'container image mismatch')
        created=docker_created_nanoseconds(info['created'])
        require(utc_nanoseconds(self.requested-timedelta(seconds=2))<=created<=utc_nanoseconds(self.returned+timedelta(seconds=2)),'container creation time mismatch')
        if self.created is not None:require(info['created']==self.created,'container creation metadata drift')

    def verify(self, network):
        i=self.inspect();self.identity(i);h=i['host'];require(i['running'] is True,'container not running')
        require(i['user']=='1000:1000' and h['ReadonlyRootfs'] is True and h['Privileged'] is False,'container privilege mismatch')
        require(h['CapDrop']==['ALL'] and not h.get('CapAdd') and h['SecurityOpt']==['no-new-privileges'],'container security options')
        require(h['NanoCpus']==2000000000 and h['Memory']==4294967296 and h['PidsLimit']==256,'resource limits mismatch')
        require(h['RestartPolicy']['Name']=='no' and h['Tmpfs']==TMPFS,'restart/tmpfs mismatch')
        require(not i['mounts'] and not i['ports'] and not any(h.get(k) for k in ['Binds','VolumesFrom','Links','PortBindings','PidMode']),'host mount/port/namespace mismatch')
        require(h['NetworkMode']=='bridge' and h.get('IpcMode') in {'private',''},'namespace mismatch')
        require(set(i['networks'])==({'bridge'} if network else set()),'network phase mismatch')
        self.event('ownership_network_verified',container_id=self.cid,created_at=i['created'],networks=sorted(i['networks']),ports=i['ports'],mounts=0,read_only=True,user=i['user'])

    def execute(self, phase, argv, seconds, *, data=None):
        self.event(phase+'_started',argv=argv)
        started=time.monotonic()
        r=self.call(['exec','-i','--user','1000:1000','--workdir','/work',self.cid,'/usr/bin/env','-i',*ENV,'CF010_OWNER='+self.owner,*argv],timeout=seconds+10,data=data,allow_failure=True)
        output=r.stdout+r.stderr;(self.cp/(phase+'.log')).write_bytes(output)
        # The snapshot contains no credentials and this fixed environment never
        # inherits user npmrc/proxy/secrets. Keep output as bounded public logs.
        print(output.decode('utf8',errors='replace')[-5000:],flush=True)
        self.event(phase+'_finished',exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-started,3),log_sha256=sha(output))
        require(r.returncode==0,phase+' failed')
        return output.decode('utf8',errors='replace')

    def create(self):
        self.event('image_check_started')
        image=json.loads(self.call(['image','inspect','--format','{"id":{{json .Id}},"digests":{{json .RepoDigests}},"os":{{json .Os}},"arch":{{json .Architecture}},"volumes":{{json .Config.Volumes}}}',IMAGE]).stdout)
        require(image['id']==IMAGE and DIGEST in image['digests'] and image['os']=='linux' and image['arch']=='arm64' and not image['volumes'],'image metadata mismatch')
        self.event('image_verified',**image)
        args=create_args(self.owner,self.record['manifest_sha256']);self.event('creation_started',argv=args)
        self.requested=datetime.now(timezone.utc);self.creation_attempted=True;r=self.call(args);self.returned=datetime.now(timezone.utc)
        cid=r.stdout.decode().strip();require(re.fullmatch('[a-f0-9]{64}',cid),'container CID uncertain');self.cid=cid
        (self.cp/'creation.json').write_bytes(json_bytes({'container_id':cid,'owner':self.owner,'resource':self.record['manifest_sha256'],'requested_at':self.requested.isoformat(),'returned_at':self.returned.isoformat()}))
        i=self.inspect();self.identity(i);self.created=i['created'];self.event('container_created',container_id=cid,created_at=self.created)
        self.call(['start',cid]);self.verify(True)

    def cleanup(self):
        if self.cid is None:
            require(not self.creation_attempted,'creation outcome uncertain; no resource adoption')
            return
        self.event('cleanup_started',container_id=self.cid)
        # Never enumerate/adopt a resource by labels when creation CID is unknown.
        i=json.loads(self.call(['inspect','--format',INSPECT,self.cid],cleanup=True).stdout);self.identity(i)
        r=self.call(['rm','--force',self.cid],cleanup=True);require(r.returncode==0,'container removal failed')
        absent=self.call(['inspect','--format','{{.Id}}',self.cid],allow_failure=True,cleanup=True)
        require(absent.returncode!=0 and (b'No such object' in absent.stderr or b'No such container' in absent.stderr),'container absence uncertain')
        remaining=self.call(['ps','-a','--filter','label=verith.cf010.owner='+self.owner,'--format','{{.ID}}'],cleanup=True)
        require(not remaining.stdout.strip(),'owned label remaining')
        self.event('owned_container_removed',container_id=self.cid,rm_exit=r.returncode,absence=True,owner_label_remaining=0)

    def run(self):
        self.create();self.execute('identity',['node','-e',SETUP],15)
        self.execute('install_input',['/bin/tar','--extract','--file','-','--directory','/work','--no-same-owner','--no-same-permissions'],15,data=stable_read(self.cp,'install-input.tar'))
        self.execute('lock_before_install',['node','-e',INSTALL_PROOF,PACKAGE_SHA,LOCK_SHA],15)
        self.execute('npm_version',['npm','--version'],15)
        self.execute('install',INSTALL,360)
        self.execute('lock_after_install',['node','-e',INSTALL_PROOF,PACKAGE_SHA,LOCK_SHA],15)
        self.call(['network','disconnect','bridge',self.cid]);self.verify(False)
        self.execute('network_off',['node','-e',NETWORK_PROOF],15)
        self.execute('source_input',['/bin/tar','--extract','--file','-','--directory','/work','--no-same-owner','--no-same-permissions'],15,data=stable_read(self.cp,'source-input.tar'))
        self.execute('source_before',['node','-e',VERIFY_SOURCE,self.record['manifest_sha256']],15)
        self.execute('fresh_build_required',['node','-e',"if(require('node:fs').existsSync('/work/.next'))throw Error('CF010 stale build');"],15)
        self.execute('build',BUILD,420);self.verify(False);self.execute('network_before_http',['node','-e',NETWORK_PROOF],15)
        output=self.execute('http',HTTP,450)
        for field in ['tests','pass']:require(re.search(r'^# '+field+r' 2$',output,re.M),'HTTP exact test count')
        for field in ['fail','cancelled','skipped','todo']:require(re.search(r'^# '+field+r' 0$',output,re.M),'HTTP failure/skip')
        self.execute('source_after',['node','-e',VERIFY_SOURCE,self.record['manifest_sha256']],15);self.verify(False);self.execute('network_after_http',['node','-e',NETWORK_PROOF],15)
        verify_prepared(self.cp)
        self.event('verification_passed',tests=2,passed=2)


def verify_prepared(cp):
    require(cp.is_absolute() and cp.resolve(strict=True)==cp and cp.parent==PREPARED_PARENT and cp.name.startswith('cf010-prepared-'),'prepared directory mismatch')
    s=cp.lstat();require(stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and s.st_mode&0o777==0o700,'prepared directory ownership')
    record=json.loads(stable_read(cp,'prepared.json'));require(record['schema']==1 and record['directory_identity']==[s.st_dev,s.st_ino,s.st_uid] and re.fullmatch(r'cf010-[a-f0-9]{24}',record['owner']),'prepared identity mismatch')
    require(set(record['artifacts'])=={'install-input.tar','source-input.tar','manifest.json','execution-plan.json'},'prepared artifact set')
    for name,entry in record['artifacts'].items():
        data=stable_read(cp,name);require(len(data)==entry['size'] and sha(data)==entry['sha256'],'prepared artifact drift')
    require(record['runner_sha256']==sha(stable_read(ROOT,RUNNER_PATH)),'runner drift after review')
    manifest_raw=stable_read(cp,'manifest.json');require(sha(manifest_raw)==record['manifest_sha256'] and manifest_raw==stable_read(ROOT,MANIFEST_PATH),'manifest drift')
    manifest=json.loads(manifest_raw);rows,data=collect()
    require(manifest['schema']==1 and manifest['task']=='CF-010' and manifest['base']==BASE and manifest['image']==IMAGE and manifest['repo_digest']==DIGEST and manifest['platform']=='linux/arm64' and manifest['suite']==SUITE and manifest['package_sha256']==PACKAGE_SHA and manifest['lock_sha256']==LOCK_SHA and manifest['runner_sha256']==record['runner_sha256'],'manifest contract drift')
    require(len(manifest['files'])==len(rows) and {e['source'] for e in manifest['files']}==set(rows) and len({e['target'] for e in manifest['files']})==len(rows),'source selection drift')
    for entry in manifest['files']:
        raw=data[entry['source']];require(rows[entry['source']]==(entry['role'],entry['target']) and len(raw)==entry['size'] and sha(raw)==entry['sha256'],'source changed after review')
    require(len(manifest['derived'])==2 and {e['target'] for e in manifest['derived']}=={READY_TARGET,'.cf010-owner.json'},'derived target drift')
    require(stable_read(cp,'execution-plan.json')==json_bytes(execution_plan(cp,record['owner'],record['manifest_sha256'])),'execution argv drift')
    actual={}
    for name in ['install-input.tar','source-input.tar']:
        members=list(archive_members(stable_read(cp,name)));group=dict(members);require(len(group)==len(members),'duplicate archive target')
        if name=='install-input.tar':require(set(group)=={'package.json','package-lock.json'},'install archive contains other source')
        for target,raw in members:
            require(target not in actual,'duplicate archive target');actual[target]=raw
    marker=json.loads(actual['.cf010-owner.json']);require(set(marker)=={'schema','owner','nonce','root'} and marker['schema']==1 and marker['owner']==record['owner'] and marker['root']=='/work' and re.fullmatch('[a-f0-9]{64}',marker['nonce']),'marker identity')
    expected={rows[p][1]:raw for p,raw in data.items()};expected['cf010-source-manifest.json']=manifest_raw
    expected[READY_TARGET]=READY;expected['.cf010-owner.json']=json_bytes(marker)
    require(actual==expected,'archive/source mismatch')
    for entry in manifest['derived']:
        raw=actual[entry['target']];require(len(raw)==entry['size'] and sha(raw)==entry['sha256'],'derived input drift')
    check_git();return record

def archive_members(raw):
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tar:
        for member in tar:
            relative(member.name);require(member.isfile() and member.uid==1000 and member.gid==1000 and member.mode in {0o600,0o644},'unsafe archive member')
            yield member.name,tar.extractfile(member).read()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','run']);parser.add_argument('--prepared',type=Path)
    args=parser.parse_args();require((args.mode=='run')==(args.prepared is not None),'prepared argument only for run')
    if args.mode=='prepare':prepare();return
    record=verify_prepared(args.prepared);runner=DockerRun(args.prepared,record)
    old={};cleanup_failed=False;failed=False
    def interrupt(signum,frame):raise CheckFailure('interrupted')
    for signum in [signal.SIGINT,signal.SIGTERM]:old[signum]=signal.signal(signum,interrupt)
    try:runner.run()
    except Exception as error:
        failed=True;runner.event('failed',failed_stage=runner.stage,reason=str(error) if type(error) is CheckFailure else 'fixed_operation_failure',error_type=type(error).__name__ if type(error).__name__ in {'CheckFailure','TimeoutExpired','PermissionError','OSError'} else 'other',container_id=runner.cid)
    finally:
        for signum in old:signal.signal(signum,signal.SIG_IGN)
        try:runner.cleanup()
        except Exception as error:
            cleanup_failed=True;runner.event('resource_uncertain' if runner.creation_attempted and runner.cid is None else 'cleanup_failed',reason=str(error) if type(error) is CheckFailure else 'fixed_cleanup_failure',error_type=type(error).__name__ if type(error).__name__ in {'CheckFailure','TimeoutExpired','PermissionError','OSError'} else 'other',container_id=runner.cid,owner=runner.owner)
        for signum,handler in old.items():signal.signal(signum,handler)
    raise SystemExit(2 if cleanup_failed else 1 if failed else 0)

if __name__=='__main__':main()
