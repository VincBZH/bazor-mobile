"""Restore the most recent S2 transaction only when files still match it."""
import argparse,hashlib,json
from pathlib import Path
from apply_fix import atomic_write

def rollback(root):
    root=Path(root).resolve()
    choices=sorted((root/'backups').glob('SESSION_S2_*/manifest.json'))
    if not choices:raise ValueError('Aucune sauvegarde S2 disponible.')
    manifest=choices[-1];items=json.loads(manifest.read_text())
    for entry in items:
        path=root/entry['what'];backup=manifest.parent/entry['what']
        if not path.resolve().is_relative_to(root):raise ValueError('Chemin invalide.')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['after_sha256']:
            raise ValueError('Fichier modifié depuis S2 : '+entry['what']+'. Retour automatique interrompu.')
        if entry['before_sha256'] and (not backup.is_file() or hashlib.sha256(backup.read_bytes()).hexdigest()!=entry['before_sha256']):
            raise ValueError('Sauvegarde incohérente : '+entry['what'])
    for entry in items:
        path=root/entry['what'];backup=manifest.parent/entry['what']
        if entry['before_sha256']:atomic_write(path,backup.read_bytes())
        else:path.unlink()
    atomic_write(root/'logs/session-s2-rollback.json',json.dumps({'restored':str(manifest),'files':items},indent=2).encode())
    return 'Fichiers antérieurs restaurés. Relancer le Studio.'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=r'C:\AI\SimpleStudioV2');a=p.parse_args();print(rollback(a.root))
