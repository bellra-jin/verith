"""Fixed CF-011 integration only. No host mount, HTTP tunnel or external provider.

prepare is source-only; run consumes a reviewed snapshot. Installation containers
are separate from the three runtime containers sharing the Node owner's net:none.
"""
from __future__ import annotations

import argparse
import asyncio
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
from contextlib import redirect_stderr, redirect_stdout

ROOT = Path(__file__).resolve().parents[2] if len(Path(__file__).resolve().parents)>2 else Path('/work')
BASE = 'a0e220f7e207b56f79ece93e2b9f9473199dae6b'
BRANCH = 'test/flow-live-synthetic-integration'
SELF = 'backend/scripts/cf011_next_backend_pg_check.py'
REPORT = 'docs/work/CF-011-flow-live-synthetic-integration.md'
PYTHON = 'docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b'
PYTHON_ID = 'sha256:4703adf8fdd93b1441114e4f87ce2c62f7373fc5f88bda6a546c551625bcc71c'
NODE = 'sha256:50e2bfc1d63c54b4925099d98a484ac1bcaa54a93e8efce53706f8a92fecf615'
PG = 'sha256:fa3d9bb7ee77f5c1f0bfb009a9df30243c040896825f3033b09a77101bb2ca95'
LOCK = '7beffafebfee13a5d5d09738813225464f35687347929a6d7819a58b4058b78e'
PROJECT = '91b2b71e68e5c02046cce1e7ad9d6a4ec7c44d8fccca998da544b316bb35e318'
DOCKER = '/Applications/Docker.app/Contents/Resources/bin/docker'
SOCKET = 'unix:///Users/parkjinhee/.docker/run/docker.sock'
PUBLIC = 'https://github.com/bellra-jin/verith.git'
ENV = ['PATH=/usr/local/bin:/usr/bin:/bin', 'HOME=/tmp/home', 'TMPDIR=/tmp',
       'LANG=C.UTF-8', 'TZ=UTC', 'OPENSSL_CONF=/dev/null',
       'PYTHONDONTWRITEBYTECODE=1', 'NEXT_TELEMETRY_DISABLED=1',
       'NPM_CONFIG_USERCONFIG=/tmp/user.npmrc', 'NPM_CONFIG_GLOBALCONFIG=/tmp/global.npmrc',
       'NPM_CONFIG_CACHE=/work/npm-cache']


class CheckFailure(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__('CF011 fixed failure')


def require(condition, code):
    if not condition:
        raise CheckFailure(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def cf010():
    """Reuse only reviewed pure source/namespace helpers, never its fixed entry."""
    path = ROOT/'frontend/scripts/check-docker-synthetic-demo.py'
    spec = importlib.util.spec_from_file_location('cf011_source_helpers', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args):
    return subprocess.run(['/usr/bin/git', '-C', str(ROOT), *args], check=True,
        capture_output=True, env={'PATH':'/usr/bin:/bin', 'HOME':'/nonexistent',
        'GIT_CONFIG_GLOBAL':'/dev/null', 'GIT_CONFIG_NOSYSTEM':'1', 'GIT_OPTIONAL_LOCKS':'0'}).stdout


def check_git():
    require(git('branch','--show-current').decode().strip()==BRANCH, 'branch')
    require(git('rev-parse','HEAD').decode().strip()==BASE, 'base')
    require(git('rev-parse','origin/develop').decode().strip()==BASE, 'remote_base')
    for flags in [('remote','get-url','--all','origin'),('remote','get-url','--push','--all','origin')]:
        require(git(*flags).decode().splitlines()==[PUBLIC], 'origin')
    require(git('worktree','list','--porcelain').count(b'worktree ')==1, 'worktrees')
    require(not git('diff','--cached','--name-only'), 'staged')
    changed={x[3:] for x in git('status','--porcelain=v1','-z','-uall').decode().split('\0') if x}
    require(changed<={SELF,REPORT}, 'scope')


def requirements(raw):
    """Export only this lock's runtime closure, Linux/aarch64 CPython3.12.

    Unknown markers fail instead of guessing or asking a resolver for new versions.
    pip receives exact versions/hashes, --no-deps and wheels-only.
    """
    lock=tomllib.loads(raw.decode()); packages={x['name']:x for x in lock['package']}
    yes={"implementation_name != 'PyPy'", "platform_python_implementation != 'PyPy'",
         "platform_python_implementation != 'PyPy' and sys_platform != 'cygwin' and sys_platform != 'win32'",
         "python_full_version < '3.13'",
         "platform_machine == 'AMD64' or platform_machine == 'WIN32' or platform_machine == 'aarch64' or platform_machine == 'amd64' or platform_machine == 'ppc64le' or platform_machine == 'win32' or platform_machine == 'x86_64'"}
    selected={}; todo=list(packages['verith-backend']['dependencies']); seen=set()
    while todo:
        dep=todo.pop(); marker=dep.get('marker')
        if marker=="sys_platform == 'win32'": continue
        require(marker is None or marker in yes, 'unknown_lock_marker')
        identity=(dep['name'],tuple(dep.get('extra',[])))
        if identity in seen: continue
        seen.add(identity); item=packages[dep['name']]
        require(item['source']=={'registry':'https://pypi.org/simple'}, 'package_registry')
        selected[item['name']]=item
        todo.extend(item.get('dependencies',[]))
        for extra in dep.get('extra',[]): todo.extend(item['optional-dependencies'][extra])
    lines=[]
    for name,item in sorted(selected.items()):
        hashes=[]
        for wheel in item.get('wheels',[]):
            require(wheel['url'].startswith('https://files.pythonhosted.org/') and re.fullmatch(r'sha256:[0-9a-f]{64}',wheel['hash']), 'wheel_source')
            hashes.append('--hash='+wheel['hash'])
        require(hashes and re.fullmatch(r'[a-z0-9-]+',name) and re.fullmatch(r'[0-9][a-zA-Z0-9.+-]*',item['version']), 'wheel_identity')
        lines.append(name+'=='+item['version']+' '+' '.join(sorted(set(hashes))))
    return ('\n'.join(lines)+'\n').encode(),len(selected)


def archive(entries):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w') as tar:
        for name,data in sorted(entries.items()):
            p=PurePosixPath(name)
            require(not p.is_absolute() and '..' not in p.parts, 'archive_path')
            info=tarfile.TarInfo(name); info.size=len(data); info.mode=0o644; info.uid=info.gid=1000
            tar.addfile(info,io.BytesIO(data))
    return out.getvalue()


def source_snapshot():
    h=cf010(); _,files=h.collect()
    frontend={p[9:]:b for p,b in files.items() if h.role_target(p)[0] in {'configuration','product','asset'}}
    backend={}; originals={}
    for record in git('ls-files','--stage','-z').decode().split('\0'):
        if not record: continue
        mode,name=record.split('\t',1)
        allowed=(name.startswith(('backend/src/','backend/db/')) and name.endswith('.py')) or name in {
            'backend/alembic.ini','backend/db/migrations/script.py.mako','backend/tests/db_safety.py',
            'backend/pyproject.toml','backend/uv.lock'}
        if allowed:
            require(mode.startswith('100644 ') and mode.endswith(' 0'), 'backend_source_mode')
            raw=h.stable_read(ROOT,name); backend[name[8:]]=raw; originals[name]=digest(raw)
    require(digest(backend['uv.lock'])==LOCK and digest(backend['pyproject.toml'])==PROJECT,'backend_lock')
    req,count=requirements(backend['uv.lock']); backend['cf011_check.py']=h.stable_read(ROOT,SELF)
    originals[SELF]=digest(backend['cf011_check.py'])
    for name,data in frontend.items(): originals['frontend/'+name]=digest(data)
    originals['frontend/scripts/check-docker-synthetic-demo.py']=digest(h.stable_read(ROOT,'frontend/scripts/check-docker-synthetic-demo.py'))
    return frontend,backend,originals,req,count


def prepare():
    check_git();frontend,backend,originals,req,count=source_snapshot()
    cp=Path(tempfile.mkdtemp(prefix='cf011-prepared-',dir='/tmp')).resolve(); cp.chmod(0o700)
    outputs={'frontend.tar':archive(frontend),'backend.tar':archive(backend),
        'node-install.tar':archive({k:frontend[k] for k in ('package.json','package-lock.json')}),
        'python-install.tar':archive({'requirements.txt':req}), 'next-start.mjs':NEXT_START.encode()}
    manifest={'schema':1,'base':BASE,'branch':BRANCH,'runner_sha256':originals[SELF],
        'node_image':NODE,'python_image':PYTHON,'python_id':PYTHON_ID,'pg_image':PG,
        'python_runtime_packages':count,'source':originals,
        'frontend':{k:digest(v) for k,v in frontend.items()},'backend':{k:digest(v) for k,v in backend.items()},
        'artifacts':{k:{'sha256':digest(v),'size':len(v)} for k,v in outputs.items()},
        'topology':'two bridge installers, then fresh Node owner network:none; Python and PG network container:<exact owner CID>; no publish/mount/socket',
        'phases':['pinned Python pull','two locked wheel/npm installations','remove installers',
                  'fresh network:none owner and two exact-CID namespace peers','source/namespace proofs',
                  'one build','restricted PG readonly attestation/migration','one live HTTP integration','source/network proofs','peers cleanup then owner']}
    for name,data in outputs.items(): (cp/name).write_bytes(data)
    (cp/'manifest.json').write_bytes(encoded(manifest))
    print(json.dumps({'phase':'prepared_no_runtime','directory':str(cp),'manifest_sha256':digest(encoded(manifest)),
        'runner_sha256':originals[SELF],'backend_files':len(backend),'frontend_files':len(frontend),'python_runtime_packages':count}))


HOST_FIELDS = ['ReadonlyRootfs','Privileged','CapDrop','CapAdd','SecurityOpt','NanoCpus',
    'Memory','PidsLimit','RestartPolicy','Tmpfs','Binds','VolumesFrom','Links',
    'PortBindings','PidMode','NetworkMode','IpcMode']
# Do not request Config.Env or a full inspect, even for our synthetic containers.
INSPECT = ('{"Id":{{json .Id}},"Name":{{json .Name}},"Created":{{json .Created}},"Image":{{json .Image}},'
    '"Mounts":{{json .Mounts}},"State":{"Running":{{json .State.Running}},"Status":{{json .State.Status}}},'
    '"Config":{"User":{{json .Config.User}},"Labels":{{json .Config.Labels}}},'
    '"NetworkSettings":{"Networks":{{json .NetworkSettings.Networks}},"Ports":{{json .NetworkSettings.Ports}}},'
    '"HostConfig":{'+','.join('"'+key+'":{{json .HostConfig.'+key+'}}' for key in HOST_FIELDS)+'}}')

SOURCE_PROOF = r"""
const fs=require('node:fs'),crypto=require('node:crypto');
const expected=JSON.parse(fs.readFileSync(0,'utf8'));
for(const [name,hash] of Object.entries(expected)){
 if(!name||name.startsWith('/')||name.split('/').some(v=>!v||v==='.'||v==='..'))throw Error('CF011 source path');
 let path='/work';for(const part of name.split('/')){path+='/'+part;if(fs.lstatSync(path).isSymbolicLink())throw Error('CF011 source symlink');}
 const fd=fs.openSync(path,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
 try{const before=fs.fstatSync(fd,{bigint:true});if(!before.isFile()||before.nlink!==1n||before.uid!==1000n)throw Error('CF011 source identity');const value=fs.readFileSync(fd),after=fs.fstatSync(fd,{bigint:true}),named=fs.lstatSync(path,{bigint:true});for(const k of ['dev','ino','size','mtimeNs','ctimeNs'])if(before[k]!==after[k]||before[k]!==named[k])throw Error('CF011 source race');if(crypto.createHash('sha256').update(value).digest('hex')!==hash)throw Error('CF011 source hash');}finally{fs.closeSync(fd);}
}
console.log(JSON.stringify({matched:true,sourceCount:Object.keys(expected).length}));
"""

PY_SOURCE_PROOF = """
import hashlib,json,os,pathlib,stat,sys
expected=json.load(sys.stdin)
for name,hash_ in expected.items():
 p=pathlib.PurePosixPath(name)
 assert not p.is_absolute() and '..' not in p.parts and str(p)==name
 current=pathlib.Path('/work')
 for part in p.parts:
  current/=part
  assert not current.is_symlink()
 fd=os.open(current,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as file:
  before=os.fstat(file.fileno());assert stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==1000
  value=file.read();after=os.fstat(file.fileno());named=current.lstat()
  fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  assert fields(before)==fields(after)==fields(named) and hashlib.sha256(value).hexdigest()==hash_
print(json.dumps({'matched':True,'sourceCount':len(expected)}))
"""


class Run:
    def __init__(self,cp):
        self.cp=cp; self.h=cf010(); self.manifest=json.loads(self.h.stable_read(cp,'manifest.json'))
        self.verify_sources(); self.owner='cf011-'+secrets.token_hex(12); self.nonce=secrets.token_hex(32)
        self.resource=digest(self.h.stable_read(cp,'manifest.json')); self.events=[]; self.receipts=[]
        self.deadline=time.monotonic()+1500; self.stage='initial';self.cleanup_deadline=None;self.creation_uncertain=False
        (cp/'cli-home/docker-config').mkdir(parents=True,mode=0o700)
        self.prefix=[DOCKER,'--host',SOCKET,'--config',str(cp/'cli-home/docker-config')]
        self.env={'PATH':'/usr/bin:/bin','HOME':str(cp/'cli-home'),'LANG':'C.UTF-8','TZ':'UTC'}

    def event(self,phase,**values):
        self.stage=phase; item={'phase':phase,'at':datetime.now(timezone.utc).isoformat(),**values}
        self.events.append(item); (self.cp/'events.json').write_bytes(encoded(self.events)); print(json.dumps(item),flush=True)

    def verify_sources(self):
        check_git()
        frontend,backend,originals,req,count=source_snapshot()
        require(self.manifest['base']==BASE and self.manifest['branch']==BRANCH and self.manifest['source']==originals,'source_set')
        require(self.manifest['frontend']=={k:digest(v) for k,v in frontend.items()} and self.manifest['backend']=={k:digest(v) for k,v in backend.items()},'source_manifest')
        expected={'frontend.tar':archive(frontend),'backend.tar':archive(backend),
            'node-install.tar':archive({k:frontend[k] for k in ('package.json','package-lock.json')}),
            'python-install.tar':archive({'requirements.txt':req}),'next-start.mjs':NEXT_START.encode()}
        require(set(self.manifest['artifacts'])==set(expected),'artifact_set')
        for name,hash_ in self.manifest['source'].items(): require(digest(self.h.stable_read(ROOT,name))==hash_,'source_drift')
        for name,item in self.manifest['artifacts'].items():
            data=self.h.stable_read(self.cp,name); require(len(data)==item['size'] and digest(data)==item['sha256'],'artifact_drift')
            require(data==expected[name],'artifact_origin')

    def call(self,args,*,data=None,seconds=20,allow=False,output=None,extra=None):
        budget=self.cleanup_deadline if self.cleanup_deadline is not None else self.deadline-90
        require(time.monotonic()+seconds<budget,'total_deadline')
        dest=os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') if output else io.BytesIO()
        with dest:
            result=subprocess.run(self.prefix+args,input=data,stdout=dest if output else subprocess.PIPE,
                stderr=subprocess.PIPE,env=self.env|(extra or {}),timeout=seconds)
        if not allow: require(result.returncode==0,'docker_operation')
        return result

    def image(self,image,expected):
        value=json.loads(self.call(['image','inspect',image,'--format','{"id":{{json .Id}},"os":{{json .Os}},"arch":{{json .Architecture}},"volumes":{{json .Config.Volumes}}}']).stdout)
        require(value['id']==expected and value['os']=='linux' and value['arch']=='arm64','image_id_platform')
        require((value['volumes'] or {})==({'/var/lib/postgresql/data':{}} if expected==PG else {}),'image_volumes')
        return value['id']

    def create(self,kind,image,network,*,pg_config=None):
        uid=999 if kind=='pg' else 1000; name=self.owner+'-'+kind
        tmpfs={'/work':'rw,exec,nosuid,nodev,size=3g,uid=1000,gid=1000,mode=0700',
               '/tmp':f'rw,noexec,nosuid,nodev,size=256m,uid={uid},gid={uid},mode=0700'}
        if kind=='pg': tmpfs={'/var/lib/postgresql/data':'rw,nosuid,nodev,size=512m,uid=999,gid=999,mode=0700',
            '/var/run/postgresql':'rw,nosuid,nodev,size=16m,uid=999,gid=999,mode=0700','/tmp':tmpfs['/tmp']}
        args=['create','--pull=never','--name',name,'--label','verith.cf011.owner='+self.owner,
            '--label','verith.cf011.resource='+self.resource,'--label','verith.cf011.nonce='+self.nonce,
            '--read-only','--user',f'{uid}:{uid}','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--restart=no','--memory','4g' if kind!='pg' else '512m','--cpus','2','--pids-limit','256','--network',network]
        for name_,options in tmpfs.items(): args+=['--tmpfs',name_+':'+options]
        extra={}
        if pg_config:
            extra={'POSTGRES_PASSWORD':pg_config['admin_password']}
            args+=['--env','POSTGRES_PASSWORD','--env','POSTGRES_USER='+pg_config['admin'],
                   '--env','POSTGRES_DB='+pg_config['database'],'--env','POSTGRES_HOST_AUTH_METHOD=scram-sha-256',
                   '--entrypoint','/usr/bin/timeout',image,'--signal=TERM','--kill-after=5','1200',
                   '/usr/local/bin/docker-entrypoint.sh','postgres','-c','listen_addresses=127.0.0.1',
                   '-c','verith.test_resource_id='+self.nonce]
        else: args+=['--workdir','/work','--entrypoint','/usr/bin/timeout',image,'--signal=TERM','--kill-after=5','1200','/bin/sleep','1200']
        before=datetime.now(timezone.utc); self.event('create_started',kind=kind)
        try:
            result=self.call(args,extra=extra,allow=True); after=datetime.now(timezone.utc); cid=result.stdout.decode().strip()
            require(result.returncode==0 and re.fullmatch('[0-9a-f]{64}',cid) is not None,'creation_uncertain')
        except BaseException:
            self.creation_uncertain=True;self.event('creation_uncertain',kind=kind);raise
        receipt={'kind':kind,'cid':cid,'name':name,'image':image,'network':network,'uid':uid,'tmpfs':tmpfs,
                 'before':before.isoformat(),'after':after.isoformat(),'created':None,'removed':False}
        self.receipts.append(receipt)
        fd=os.open(self.cp/'creation-receipts.json',os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as file:file.write(encoded({'owner':self.owner,'resource':self.resource,'nonce':self.nonce,'receipts':self.receipts}))
        self.verify(receipt); self.event('created',kind=kind,container_id=cid)
        self.call(['start',cid]); self.verify(receipt,running=True)
        return receipt

    def verify(self,r,*,running=False):
        # Raw inspect stays in memory; never print Env, labels, addresses or secrets.
        x=json.loads(self.call(['inspect',r['cid'],'--format',INSPECT]).stdout); h=x['HostConfig']; c=x['Config']
        require(x['Id']==r['cid'] and x['Name']=='/'+r['name'] and x['Image']==r['image'],'cid_identity')
        labels={'verith.cf011.owner':self.owner,'verith.cf011.resource':self.resource,'verith.cf011.nonce':self.nonce}
        require(all(c['Labels'].get(k)==v for k,v in labels.items()),'labels')
        stamp=self.h.docker_created_nanoseconds(x['Created']); lo=self.h.utc_nanoseconds(datetime.fromisoformat(r['before']))-2_000_000_000; hi=self.h.utc_nanoseconds(datetime.fromisoformat(r['after']))+2_000_000_000
        require(lo<=stamp<=hi and (r['created'] is None or r['created']==x['Created']),'creation_time'); r['created']=x['Created']
        require(c['User']==f"{r['uid']}:{r['uid']}" and h['ReadonlyRootfs'] and not h['Privileged'] and h['CapDrop']==['ALL'] and not h.get('CapAdd'),'privileges')
        require(h['SecurityOpt']==['no-new-privileges'] and h['RestartPolicy']['Name']=='no' and h['PidsLimit']==256 and h['NanoCpus']==2_000_000_000,'limits')
        require(h['Memory']==(512*1024**2 if r['kind']=='pg' else 4*1024**3) and h['Tmpfs']==r['tmpfs'],'memory_tmpfs')
        require(not x['Mounts'] and not h.get('Binds') and not h.get('VolumesFrom') and not h.get('Links') and not h.get('PortBindings') and not x['NetworkSettings'].get('Ports'),'mount_port')
        require(h['NetworkMode']==r['network'] and h.get('PidMode','')=='' and h.get('IpcMode') in {'private',''},'namespace_mode')
        if r['network'].startswith('container:'):
            owner=next(v for v in self.receipts if v['kind']=='node'); require(r['network']=='container:'+owner['cid'] and not owner['removed'],'namespace_owner')
        else: require(set(x['NetworkSettings']['Networks'])==({r['network']} if r['network'] in {'bridge','none'} else set()),'networks')
        require(not running or x['State']['Running'] is True,'not_running')

    def execute(self,r,phase,args,*,data=None,seconds=30,output=None,quiet=False):
        self.verify(r,running=True); self.event(phase+'_started')
        result=self.call(['exec','-i','--user',f"{r['uid']}:{r['uid']}",'--workdir','/work',r['cid'],
            '/usr/bin/env','-i',*ENV,*args],data=data,seconds=seconds,allow=True,output=output)
        raw=b'' if output else result.stdout
        # Backend catches errors itself; installation/build diagnostics contain no input credentials.
        log=raw+result.stderr if not quiet else raw
        (self.cp/(phase+'.log')).write_bytes(log)
        self.event(phase+'_finished',exit_code=result.returncode,log_sha256=digest(log))
        require(result.returncode==0,phase+'_failed'); return raw

    def copy(self,r,file):
        self.execute(r,'copy_'+file.replace('.','_'),['/bin/tar','-xf','-','-C','/work','--no-same-owner','--no-same-permissions'],data=self.h.stable_read(self.cp,file))

    def remove(self,r):
        if r['removed']: return
        self.verify(r); self.call(['rm','--force',r['cid']])
        result=self.call(['inspect','--format','{{.Id}}',r['cid']],allow=True)
        require(result.returncode!=0 and result.stdout.strip() in (b'',b'[]') and re.fullmatch(
            rb'(?:Error: No such object:|Error response from daemon: No such (?:object|container):)\s*'+r['cid'].encode(),result.stderr.strip()),'absence_uncertain')
        r['removed']=True; self.event('removed',kind=r['kind'],container_id=r['cid'],absence=True)

    def sql(self,pg,config,statement):
        self.verify(pg,running=True)
        return self.call(['exec','-i','--user','999:999',pg['cid'],'psql','-X','-v','ON_ERROR_STOP=1',
            '-U',config['admin'],'-d',config['database'],'-At'],data=statement.encode()).stdout

    def dependency_archive(self,name):
        path=self.cp/name
        with tarfile.open(path,'r:') as tar:
            seen=set()
            for member in tar:
                p=PurePosixPath(member.name)
                require(not p.is_absolute() and '..' not in p.parts and member.name not in seen,'dependency_path')
                seen.add(member.name)
                roots={'site'} if name=='pip-install.tar' else {'node_modules','package.json','package-lock.json'}
                require(p.parts and p.parts[0] in roots and not member.islnk() and (member.isfile() or member.isdir() or member.issym()),'dependency_type')
                if member.issym():
                    target=PurePosixPath(member.linkname);require(not target.is_absolute(),'dependency_link')
                    parts=list(p.parent.parts)
                    for part in target.parts:
                        if part=='..':require(len(parts)>1,'dependency_link_escape');parts.pop()
                        elif part!='.':parts.append(part)
        self.event('dependency_bundle_verified',bundle=name,size=path.stat().st_size,sha256=digest(self.h.stable_read(self.cp,name)))

    def perform(self):
        self.event('python_pull_started',digest=PYTHON.split('@')[1])
        self.call(['pull','--platform','linux/arm64',PYTHON],seconds=180)
        self.image(PYTHON,PYTHON_ID); self.image(NODE,NODE); self.image(PG,PG)
        for kind,image,input_,command,names in [
            ('npm-install',NODE,'node-install.tar',['npm','ci','--ignore-scripts','--no-audit','--no-fund','--registry=https://registry.npmjs.org'],['package.json','package-lock.json','node_modules']),
            ('pip-install',PYTHON_ID,'python-install.tar',['python','-I','-m','pip','--isolated','install','--disable-pip-version-check','--no-cache-dir','--no-compile','--no-deps','--only-binary=:all:','--require-hashes','--index-url','https://pypi.org/simple','--target','/work/site','-r','/work/requirements.txt'],['site'])]:
            r=self.create(kind,image,'bridge')
            self.execute(r,'setup_'+kind,['/bin/sh','-c','mkdir -m 700 /tmp/home; : > /tmp/user.npmrc; : > /tmp/global.npmrc'])
            self.copy(r,input_)
            if kind=='npm-install':self.execute(r,'node_lock_before',['node','-e',self.h.INSTALL_PROOF,self.h.PACKAGE_SHA,self.h.LOCK_SHA])
            self.execute(r,kind,command,seconds=360)
            if kind=='npm-install':self.execute(r,'node_lock_after',['node','-e',self.h.INSTALL_PROOF,self.h.PACKAGE_SHA,self.h.LOCK_SHA])
            self.execute(r,'archive_'+kind,['tar','-cf','-','-C','/work',*names],output=self.cp/(kind+'.tar'),seconds=60)
            self.dependency_archive(kind+'.tar')
            self.remove(r)
        node=self.create('node',NODE,'none'); py=self.create('python',PYTHON_ID,'container:'+node['cid'])
        self.copy(node,'frontend.tar'); self.copy(node,'npm-install.tar'); self.copy(py,'backend.tar'); self.copy(py,'pip-install.tar')
        self.execute(node,'setup_node',['node','-e',self.h.SETUP])
        self.execute(node,'namespace_before',['node','-e',self.h.NETWORK_PROOF])
        self.execute(node,'frontend_source_before',['node','-e',SOURCE_PROOF],data=encoded(self.manifest['frontend']))
        self.execute(py,'backend_source_before',['python','-I','-S','-B','-c',PY_SOURCE_PROOF],data=encoded(self.manifest['backend']))
        self.execute(node,'build',self.h.BUILD,seconds=430)
        self.execute(node,'copy_next_start',['node','-e',"require('fs').writeFileSync('/work/cf011-next.mjs',require('fs').readFileSync(0),{flag:'wx'});"],data=self.h.stable_read(self.cp,'next-start.mjs'))
        self.call(['exec','-d','--user','1000:1000','--workdir','/work',node['cid'],'/usr/bin/env','-i',*ENV,
            'CF011_NONCE='+self.nonce,'node','/work/cf011-next.mjs'])
        self.execute(node,'next_child_ready',['node','-e',NEXT_READY],data=self.nonce.encode(),seconds=40)
        config={'admin':'admin_'+secrets.token_hex(6),'database':'cf011_'+secrets.token_hex(6),
                'role':'role_'+secrets.token_hex(6),'password':secrets.token_hex(32),'admin_password':secrets.token_hex(32),
                'resource_id':self.nonce,'owner_cid':node['cid']}
        pg=self.create('pg',PG,'container:'+node['cid'],pg_config=config)
        for _ in range(100):
            result=self.call(['exec','--user','999:999',pg['cid'],'pg_isready','-h','127.0.0.1','-U',config['admin'],'-d',config['database']],allow=True)
            if result.returncode==0: break
            time.sleep(.1)
        else: raise CheckFailure('pg_readiness')
        identity=self.sql(pg,config,"BEGIN READ ONLY; SELECT current_database()||'|'||current_user||'|'||current_setting('verith.test_resource_id'); COMMIT;").decode().splitlines()
        expected=config['database']+'|'+config['admin']+'|'+self.nonce
        require(identity.count(expected)==1 and all(v in {'BEGIN','COMMIT',expected} for v in identity),'pg_identity')
        self.sql(pg,config,f"CREATE EXTENSION pgcrypto; CREATE EXTENSION vector; CREATE ROLE {config['role']} LOGIN PASSWORD '{config['password']}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS; REVOKE CONNECT ON DATABASE postgres FROM PUBLIC; REVOKE CONNECT ON DATABASE template1 FROM PUBLIC; GRANT CONNECT,TEMPORARY,CREATE ON DATABASE {config['database']} TO {config['role']}; GRANT USAGE,CREATE ON SCHEMA public TO {config['role']};")
        self.verify(node,running=True); self.verify(py,running=True); self.verify(pg,running=True)
        config['pg_cid']=pg['cid']; config['node_cid']=node['cid']
        output=self.execute(py,'live_integration',['python','-I','-S','-B','/work/cf011_check.py','backend'],data=encoded(config),seconds=195,quiet=True)
        result=json.loads(output); require(result.get('passed') is True and result.get('engine_calls')==1,'live_result')
        self.execute(node,'frontend_source_after',['node','-e',SOURCE_PROOF],data=encoded(self.manifest['frontend']))
        self.execute(py,'backend_source_after',['python','-I','-S','-B','-c',PY_SOURCE_PROOF],data=encoded(self.manifest['backend']))
        self.execute(node,'namespace_after',['node','-e',self.h.NETWORK_PROOF])
        self.verify_sources(); self.event('verification_passed',**result)


# No product overlay/readiness endpoint: proof belongs to this owned launcher's PID.
NEXT_START = r"""
import fs from 'node:fs';import {spawn} from 'node:child_process';
const nonce=process.env.CF011_NONCE;
if(process.getuid()!==1000||process.cwd()!=='/work'||!/^[a-f0-9]{64}$/.test(nonce))throw Error('CF011 identity');
const child=spawn(process.execPath,['/work/node_modules/next/dist/bin/next','start','--hostname','localhost','--port','3200'],{cwd:'/work',env:{PATH:'/usr/local/bin:/usr/bin:/bin',HOME:'/tmp/home',TMPDIR:'/tmp',NEXT_TELEMETRY_DISABLED:'1',OPENSSL_CONF:'/dev/null',NODE_ENV:'production',BACKEND_URL:'http://localhost:8200',FLOW_SYNTHETIC_DEMO_ENABLED:'true'},stdio:'ignore'});
fs.writeFileSync('/work/next-owner.json',JSON.stringify({pid:child.pid,nonce}),{flag:'wx',mode:0o600});
child.on('exit',code=>{process.exitCode=code||0;});
setTimeout(()=>{child.kill('SIGTERM');setTimeout(()=>child.kill('SIGKILL'),3000).unref();},210000).unref();
"""

NEXT_READY = r"""
const fs=require('node:fs'),nonce=fs.readFileSync(0,'utf8');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function owned(pid){
 if(!Number.isSafeInteger(pid)||pid<2)return false;
 try{
  if(fs.realpathSync('/proc/'+pid+'/cwd')!=='/work')return false;
  const cmd=fs.readFileSync('/proc/'+pid+'/cmdline','utf8');
  if(!cmd.includes('next-server')&&!cmd.includes('/work/node_modules/next/dist/bin/next'))return false;
  const sockets=new Set();
  for(const fd of fs.readdirSync('/proc/'+pid+'/fd')){
   try{const m=/^socket:\[(\d+)\]$/.exec(fs.readlinkSync('/proc/'+pid+'/fd/'+fd));if(m)sockets.add(m[1]);}catch(e){if(e.code!=='ENOENT')throw e;}
  }
  for(const table of ['tcp','tcp6'])for(const line of fs.readFileSync('/proc/net/'+table,'utf8').trim().split('\n').slice(1)){
   const fields=line.trim().split(/\s+/);
   if(fields[3]==='0A'&&parseInt(fields[1].split(':')[1],16)===3200&&sockets.has(fields[9]))return true;
  }
 }catch(e){if(!['ENOENT','ESRCH'].includes(e.code))throw e;}
 return false;
}
(async()=>{
 const end=Date.now()+30000;
 while(Date.now()<end){
  let receipt;
  try{const s=fs.lstatSync('/work/next-owner.json');if(!s.isFile()||s.nlink!==1||s.uid!==1000)throw Error('CF011 receipt');receipt=JSON.parse(fs.readFileSync('/work/next-owner.json','utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
  if(receipt){
   if(Object.keys(receipt).sort().join(',')!=='nonce,pid'||receipt.nonce!==nonce)throw Error('CF011 nonce');
   if(owned(receipt.pid)){console.log(JSON.stringify({childPid:receipt.pid,nonceMatched:true,listenerOwned:true}));return;}
  }
  await delay(100);
 }
 throw Error('CF011 owned Next readiness timeout');
})().catch(()=>{console.log(JSON.stringify({ready:false}));process.exitCode=1;});
"""


async def backend():
    """Only reached in the owned Python peer, with private stdin configuration."""
    config=json.load(sys.stdin)
    require(set(config)=={'admin','database','role','password','admin_password','resource_id','owner_cid','pg_cid','node_cid'},'config_keys')
    for key in ['owner_cid','pg_cid','node_cid']: require(re.fullmatch('[0-9a-f]{64}',config[key]),'config_identity')
    require(config['node_cid']==config['owner_cid'] and Path.cwd()==Path('/work') and os.getuid()==1000,'backend_identity')
    sys.path[:0]=['/work','/work/site']
    os.environ.clear(); os.environ.update(PATH='/usr/local/bin:/usr/bin:/bin',HOME='/tmp/home',TZ='UTC',
        DATABASE_URL=f"postgresql+asyncpg://{config['role']}:{config['password']}@127.0.0.1:5432/{config['database']}",
        ENABLE_NEWS_GRAPH='false',FLOW_SYNTHETIC_DEMO_ENABLED='true',FLOW_RUN_ADMISSION_ENABLED='false',
        GOOGLE_CLIENT_ID='cf011-synthetic.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET='synthetic-not-a-provider-key',
        AUTH_REDIRECT_URI='http://localhost:3200/api/auth/callback',AUTH_ORIGINS='http://localhost:3200',
        CORS_ORIGINS='http://localhost:3200',AUTH_ALLOW_LOCAL_HTTP='true')
    from pydantic_settings.sources import DotEnvSettingsSource
    DotEnvSettingsSource._read_env_files=lambda self:{}
    def audit(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes)):
            require(not any(x.startswith('.env') for x in Path(os.fsdecode(args[0])).parts),'private_dotenv')
    sys.addaudithook(audit)
    spec=importlib.util.spec_from_file_location('cf011_db_safety','/work/tests/db_safety.py')
    guard=importlib.util.module_from_spec(spec);sys.modules[spec.name]=guard;spec.loader.exec_module(guard)
    target=guard.ApprovedTestDatabase(os.environ['DATABASE_URL'],config['resource_id'],config['database'],config['role'],5432,'CF011 owned namespace')
    await guard.attest_database(target,all_restrictions=True)
    from sqlalchemy import event,text
    from alembic import command
    from alembic.config import Config
    from db.session import get_engine,get_session_factory
    engine=get_engine()
    @event.listens_for(engine.sync_engine,'connect')
    def attest_connection(dbapi,record):
        async def check(native):
            async with native.transaction(readonly=True):
                row=await native.fetchrow(guard.identity_query(True)); require(guard._identity_matches(row,target),'pool_identity')
        dbapi.run_async(check)
    async with engine.connect() as connection:
        await guard.attest_engine_connection(connection,target,all_restrictions=True)
        def migrate(sync):
            value=Config('/work/alembic.ini');value.set_main_option('script_location','/work/db/migrations')
            value.attributes.update(connection=sync,verified_test_mode=True);command.upgrade(value,'head')
        await connection.run_sync(migrate);await connection.commit()
    from uuid import uuid4
    from db.models.auth.models import AuthUser
    from src.modules.auth.application.session_service import issue_session
    factory=get_session_factory()
    async with factory() as session:
        a,b=AuthUser(id=uuid4()),AuthUser(id=uuid4());session.add_all([a,b]);await session.flush()
        ta,pa=await issue_session(session,a);tb,pb=await issue_session(session,b);await session.commit()
    from src.api.main import app
    from src.modules.flow.application import fake_execution_service
    original=fake_execution_service.fake_engine;calls=[];requests=[]
    async def counted(seal,execution_id):
        calls.append(str(execution_id));return await original(seal,execution_id)
    fake_execution_service.fake_engine=counted
    @app.middleware('http')
    async def observe(request,call_next):
        requests.append((request.method,request.url.path));return await call_next(request)
    import socket
    import uvicorn
    listener=socket.socket();listener.bind(('127.0.0.1',8200));listener.listen();listener.setblocking(False)
    server=uvicorn.Server(uvicorn.Config(app,access_log=False,log_level='critical',lifespan='on'))
    task=asyncio.create_task(server.serve(sockets=[listener]))
    try:
        for _ in range(100):
            if server.started:break
            require(not task.done(),'backend_exited');await asyncio.sleep(.05)
        require(server.started,'backend_readiness')
        async with asyncio.timeout(180):
            result=await live_checks(factory,ta,tb,pa.user_id,calls,requests)
    finally:
        server.should_exit=True
        try: await asyncio.wait_for(task,5)
        finally: listener.close();await engine.dispose()
    return result


async def live_checks(factory,token_a,token_b,user_a,calls,seen):
    import httpx
    from uuid import uuid4
    from sqlalchemy import text
    from src.modules.flow.api.synthetic_demo_schemas import DemoRunView
    base='http://localhost:3200';api='/api/private/flow/synthetic-demo/runs'
    async def database():
        async with factory() as session:
            counts=tuple([await session.scalar(text('SELECT count(*) FROM '+t)) for t in ('flow_runs','flow_input_snapshots','flow_fake_executions','flow_reports','agent_reports')])
            return counts
    def private(response):
        require(response.headers.get('cache-control')=='private, no-store' and {'cookie','origin'}<={x.strip().lower() for x in response.headers.get('vary','').split(',')},'private_headers')
    async with httpx.AsyncClient(base_url=base,timeout=15,trust_env=False,follow_redirects=False) as client:
        async def call(method,path,*,token=token_a,csrf=None,body=None,origin=base):
            headers={'origin':origin}
            if token is not None:headers['cookie']='verith_session='+token
            if csrf is not None:headers['x-csrf-token']=csrf
            return await client.request(method,path,headers=headers,json=body)
        for _ in range(100):
            try:
                ready=await client.get('/_not-found');break
            except httpx.ConnectError:await asyncio.sleep(.05)
        else:raise CheckFailure('next_readiness')
        first=await call('GET','/flow/demo');require(first.status_code==200 and 'Flow' in first.text,'demo_ssr')
        session=await call('GET','/api/auth/session');private(session);require(session.status_code==200,'session_http')
        principal=session.json();require(principal['user_id']==str(user_a),'session_owner');csrf=principal['csrf_token']
        body={'idempotency_key':str(uuid4()),'as_of':'2026-11-08T00:00:00Z','allow_fake':True}
        post=await call('POST',api,csrf=csrf,body=body);private(post);require(post.status_code in {200,202},'post_http')
        envelope=post.json();view=envelope['data'];run_id=view['run_id'];detail=api+'/'+run_id
        deadline=asyncio.get_running_loop().time()+15
        for _ in range(15):
            if view['stage'] in {'succeeded','failed','timed_out'}:break
            remaining=deadline-asyncio.get_running_loop().time();require(remaining>0,'terminal_deadline')
            r=await asyncio.wait_for(call('GET',detail),timeout=remaining);private(r);require(r.status_code==200,'poll_http');view=r.json()['data']
            if view['stage'] not in {'succeeded','failed','timed_out'}:
                remaining=deadline-asyncio.get_running_loop().time();require(remaining>0,'terminal_deadline');await asyncio.sleep(min(.5,remaining))
        parsed=DemoRunView.model_validate(view);require(parsed.stage=='succeeded' and parsed.result_stored and len(calls)==1,'stored_success')
        counts=await database();require(counts==(1,1,1,0,0),'stored_counts')
        async with factory() as connection:
            row=(await connection.execute(text('SELECT r.owner_user_id,s.input_sha256,e.result_json,e.result_sha256 FROM flow_runs r JOIN flow_input_snapshots s ON s.run_id=r.id JOIN flow_fake_executions e ON e.input_snapshot_id=s.id WHERE r.id=:id'),{'id':parsed.run_id})).one()
            require(str(row[0])==str(user_a) and row[1]==view['result']['input_sha256'] and digest(row[2].encode())==row[3]==view['result_sha256'] and json.loads(row[2])==view['result'],'stored_binding')
        refresh=await call('GET','/flow/demo?run_id='+run_id);require(refresh.status_code==200 and run_id in refresh.text,'same_url_ssr')
        get=await call('GET',detail);private(get);require(get.status_code==200 and get.json()['data']==view,'same_result')
        replay=await call('POST',api,csrf=csrf,body=body);private(replay)
        require(replay.status_code==200 and replay.json()['data']==view and replay.json()['request_id']!=envelope['request_id'] and len(calls)==1,'replay')
        denied=[await call('GET',detail,token=token_b),await call('GET',detail,token=None),
            await call('POST',api,token=None,body=body),await call('POST',api,body=body),
            await call('POST',api,csrf='invalid',body=body),await call('POST',api,csrf=csrf,body=body,origin='https://invalid.example')]
        require([r.status_code for r in denied]==[404,401,401,401,401,403],'denial_statuses')
        for response in denied:private(response);require(response.json().get('data') is None,'no_data_leak')
        require(await database()==counts and len(calls)==1,'denial_no_side_effect')
        require(('POST','/api/flow/synthetic-demo/runs') in seen and ('GET','/api/auth/session') in seen and ('GET','/api/flow/synthetic-demo/runs/'+run_id) in seen,'real_backend_http')
        return {'passed':True,'engine_calls':len(calls),'stored_rows':[1,1,1],'rejections':len(denied),
                'same_url':True,'replay':True,'actual_fastapi_http':True,'browser_executed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run','backend']);parser.add_argument('--prepared',type=Path)
    args=parser.parse_args()
    if args.mode=='backend':
        try:
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):result=asyncio.run(backend())
        except BaseException as error:
            print(json.dumps({'phase':'backend_failed','error_type':type(error).__name__ if type(error).__name__ in {'CheckFailure','TimeoutError','RuntimeError','UnsafeTestDatabase','OSError'} else 'other',
                'reason':error.code if isinstance(error,CheckFailure) else 'other'}),flush=True);raise SystemExit(1)
        print(json.dumps(result),flush=True)
        return
    if args.mode=='prepare': require(args.prepared is None,'prepare_argument');prepare();return
    require(args.prepared and args.prepared.is_absolute() and args.prepared.resolve()==args.prepared and args.prepared.parent==Path('/tmp').resolve() and args.prepared.name.startswith('cf011-prepared-'),'prepared_path')
    run=Run(args.prepared);exit_code=0
    try:run.perform()
    except BaseException as error:
        run.event('failed',failed_stage=run.stage,error_type=type(error).__name__,reason=error.code if isinstance(error,CheckFailure) else 'other');exit_code=1
    finally:
        for receipt in reversed(run.receipts):
            run.cleanup_deadline=time.monotonic()+65
            try:run.remove(receipt)
            except BaseException as error:run.event('cleanup_failed',container_id=receipt['cid'],error_type=type(error).__name__);exit_code=2
        run.cleanup_deadline=time.monotonic()+25
        try:
            remaining=run.call(['ps','-a','--filter','label=verith.cf011.owner='+run.owner,'--format','{{.ID}}']).stdout.splitlines()
            require(not remaining,'owner_resources_remaining');run.event('owner_resources_absent',remaining=0)
        except BaseException:run.event('cleanup_unconfirmed');exit_code=2
        if run.creation_uncertain:exit_code=2
    raise SystemExit(exit_code)


if __name__=='__main__':main()
