"""Fetch completed evaluation evidence from the configured instance, verifying SHA256.

Credentials are read only through the repository's existing environment helper.
Partial model runs are reported as pending and never presented as scored runs.
"""
import argparse
import hashlib
import json
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
from _rdmd_ssh_target import connect, host_from_env, port_from_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = '/data/modelstore/rdmd-evolution'
    run = root + '/runs/minimal-evolution-sft-seed20260923'
    args.out.mkdir(parents=True, exist_ok=True)
    client = connect()
    try:
        sftp = client.open_sftp()
        paths = [run + '/run_manifest.json', run + '/trainer_state.json',
                 root + '/eval-audit-new.json', root + '/eval/queue.log',
                 root + '/eval/queue.exit', root + '/eval/batch-pilot-check.json',
                 root + '/eval/post-training-audit.json', root + '/eval/evaluation-environment.json']
        paths.extend(root + '/eval-code-20260924/' + f for f in
                     ('evaluate.py', 'engine.py', 'model_io.py', 'config.json', 'compare.py'))
        completed = []
        pending = []
        for split in ('holdout', 'test'):
            for arm in ('h3', 'sft', 'rule_search', 'no_change', 'copy_exec'):
                name = f'{arm}-{split}-batch'
                folder = root + '/eval/' + name
                try:
                    sftp.stat(folder + '/summary.json')
                except OSError:
                    pending.append(name)
                    continue
                completed.append(name)
                paths.extend(folder + '/' + f for f in
                             ('summary.json', 'provenance.json', 'predictions.jsonl', 'requests.jsonl'))
            paths.append(root + '/eval/comparison-' + split + '.json')
        fetched = {}
        cached = {}
        for remote in paths:
            try:
                sftp.stat(remote)
            except OSError:
                continue
            relative = remote[len(root) + 1:]
            local = args.out / relative
            local.parent.mkdir(parents=True, exist_ok=True)
            staging = local.with_name(local.name + '.part')
            _, stdout, stderr = client.exec_command('sha256sum -- ' + shlex.quote(remote), timeout=30)
            output = stdout.read().decode()
            error = stderr.read().decode()
            if stdout.channel.recv_exit_status() or not output.split():
                raise ValueError('remote_hash_failed:' + relative + ':' + error)
            remote_digest = output.split()[0]
            if local.is_file() and hashlib.sha256(local.read_bytes()).hexdigest() == remote_digest:
                cached[remote_digest] = local
            else:
                if remote_digest in cached:
                    shutil.copyfile(cached[remote_digest], staging)
                else:
                    sftp.get(remote, str(staging))
                digest = hashlib.sha256(staging.read_bytes()).hexdigest()
                if remote_digest != digest:
                    raise ValueError('download_hash_mismatch:' + relative)
                staging.replace(local)
                cached[remote_digest] = local
            if hashlib.sha256(local.read_bytes()).hexdigest() != remote_digest:
                raise ValueError('download_hash_mismatch:' + relative + ':' + error)
            fetched[relative] = {'sha256': remote_digest, 'bytes': local.stat().st_size}
        snapshot = {'timeUTC': datetime.now(timezone.utc).isoformat(),
                    'endpoint': f'{host_from_env()}:{port_from_env()}',
                    'completed': completed, 'pending': pending, 'files': fetched}
        (args.out / 'snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf8')
        print(json.dumps({'completed': completed, 'pending': pending, 'files': len(fetched)}))
    finally:
        client.close()


if __name__ == '__main__':
    main()
