"""Content-addressed training bundle upload. Never invokes the trainer.

Uses existing RDMD SSH environment, never stores or prints credentials.
"""
import argparse
import gzip
import hashlib
import io
import json
import shlex
import sys
import tarfile
from pathlib import Path
from prepare import HERE, sha

sys.path.insert(0,str(HERE.parents[1]/'scripts'))
from _rdmd_ssh_target import connect


def package():
    files=sorted(f for f in HERE.iterdir() if f.is_file() and f.suffix in ('.py','.json','.md','.sh'))
    files+=sorted((HERE/'data').glob('*'))
    mapping={f.relative_to(HERE).as_posix():{'sha256':sha(f),'bytes':f.stat().st_size} for f in files}
    manifest=json.dumps({'files':mapping},sort_keys=True,indent=2).encode()
    out=HERE/'runs'; out.mkdir(exist_ok=True)
    archive=out/'training-bundle.tar.gz'
    with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as compressed, tarfile.open(fileobj=compressed,mode='w') as tar:
        for f in files:
            info=tarfile.TarInfo(f.relative_to(HERE).as_posix()); info.size=f.stat().st_size; info.mtime=0; info.mode=0o644
            with f.open('rb') as handle: tar.addfile(info,handle)
        info=tarfile.TarInfo('bundle-manifest.json'); info.size=len(manifest); info.mode=0o644
        tar.addfile(info,io.BytesIO(manifest))
    return archive


def run(client, command, stdin=None, timeout=1800):
    si,so,se=client.exec_command(command,timeout=timeout)
    if stdin:
        si.write(stdin); si.channel.shutdown_write()
    # Both streams drained on a shared channel to avoid stderr deadlocks.
    channel=so.channel; output=[]; errors=[]
    import time
    start=time.monotonic()
    while True:
        if channel.recv_ready():
            chunk=channel.recv(65536).decode('utf8',errors='replace'); output.append(chunk); print(chunk,end='',flush=True)
        if channel.recv_stderr_ready():
            chunk=channel.recv_stderr(65536).decode('utf8',errors='replace'); errors.append(chunk); print(chunk,end='',file=sys.stderr,flush=True)
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready(): break
        if time.monotonic()-start>timeout:
            channel.close(); raise TimeoutError('remote_prepare_timeout')
        time.sleep(.1)
    return channel.recv_exit_status(),''.join(output),''.join(errors)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--preflight',action='store_true'); p.add_argument('--package-only',action='store_true')
    a=p.parse_args(); archive=package(); archive_sha=sha(archive)
    remote=f'/data/modelstore/rdmd-evolution/releases/{archive_sha[:16]}'
    remote_archive=f'/data/modelstore/rdmd-evolution/{archive_sha}.tar.gz'
    report_path=HERE/'runs'/'remote-deployment.json'
    if a.package_only:
        print(json.dumps({'archive':str(archive),'sha256':archive_sha,'bytes':archive.stat().st_size})); return
    client=connect(timeout=30)
    try:
        code,_,_=run(client,'mkdir -p /data/modelstore/rdmd-evolution/releases')
        if code: raise RuntimeError('remote_directory_failed')
        with client.open_sftp() as sftp:
            sftp.put(str(archive),remote_archive+'.part')
            sftp.posix_rename(remote_archive+'.part',remote_archive)
        script='''import hashlib,json,tarfile,pathlib
archive=pathlib.Path(ARCHIVE); root=pathlib.Path(ROOT)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==SHA
if not root.exists():
 root.mkdir()
 with tarfile.open(archive) as t:
  for member in t.getmembers():
   target=(root/member.name).resolve()
   assert target.is_relative_to(root.resolve()) and member.isfile(), member.name
  t.extractall(root)
manifest=json.loads((root/'bundle-manifest.json').read_text())
for name,info in manifest['files'].items():
 f=root/name
 assert f.stat().st_size==info['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==info['sha256'],name
print(json.dumps({'status':'BYTE_IDENTICAL','files':len(manifest['files']),'root':str(root)}))
'''.replace('ARCHIVE',repr(remote_archive)).replace('ROOT',repr(remote)).replace('SHA',repr(archive_sha))
        code,_,_=run(client,'/data/modelstore/rdmd-env/bin/python -',script)
        if code: raise RuntimeError('remote_hash_verification_failed')
        report={'remoteRoot':remote,'archiveSha256':archive_sha,'archiveBytes':archive.stat().st_size,'byteIdentical':True,'trainingStarted':False}
        if a.preflight:
            command=f'cd {shlex.quote(remote)} && /data/modelstore/rdmd-env/bin/python -m unittest discover -p test_engine.py -v && /data/modelstore/rdmd-env/bin/python train.py --out /data/modelstore/rdmd-evolution/runs/dry-run-placeholder && /data/modelstore/rdmd-env/bin/python preflight.py --out /data/modelstore/rdmd-evolution/preflight-{archive_sha[:16]}.json'
            code,_,_=run(client,command,timeout=1800)
            report['preflightExitCode']=code
            if code not in (0,3):
                report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
                raise RuntimeError('remote_preflight_failed_before_report; see remote stderr above')
            with client.open_sftp() as sftp:
                sftp.get(f'/data/modelstore/rdmd-evolution/preflight-{archive_sha[:16]}.json',str(HERE/'runs'/'remote-preflight.json'))
        report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        print(json.dumps(report))
    finally: client.close()


if __name__=='__main__': main()
