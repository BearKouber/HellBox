"""Exercise real installer binaries against temporary copies, never the live game.

python install_matrix.py <game-dir> <captain-bridge.exe> <camera-bridge.exe> <luajit.exe>
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
game,captain,camera,luajit=map(lambda s:Path(s).resolve(),sys.argv[1:])
spec=importlib.util.spec_from_file_location('survey',root.parent/'LuaSurvey/tools/dump_luajit_bundle.py')
survey=importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)
bundle='9e13b2414b41b842'
original=(game/'captain_bridge_backup'/f'{bundle}.original').read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(original)=='5ded3de9994ced0ee70597115c46c3604b754897b10de689c5b127ea8b1750a8'
out=root/'target/install-matrix'
out.mkdir(parents=True,exist_ok=True)
def records(raw):
    count=struct.unpack_from('<I',raw)[0]
    pos=260+16*count
    result={}
    for index in range(count):
        size=struct.unpack_from('<I',raw,pos+28)[0]
        ident=raw[pos:pos+16]
        assert ident==raw[260+16*index:276+16*index]
        result[ident]=raw[pos:pos+36+size]
        pos+=36+size
    assert pos==len(raw)
    return result
source_path=out/'original.bundle'
source_path.write_bytes(original)
baseline=records(survey.read_bundle(source_path)[0])
boot_id=bytes.fromhex('e217d12cfa8d4ea181dcbd8a618a0437')
results=[]
with tempfile.TemporaryDirectory(prefix='bridge-matrix-') as directory:
    fixture=Path(directory)
    env=dict(os.environ,APPDATA=str(fixture/'appdata'))
    (fixture/'contents').mkdir()
    path=fixture/'contents'/bundle
    path.write_bytes(original)
    # The real boot selector below is copied from the selected vanilla game's settings.
    settings=(game/'contents/settings.ini').read_text(encoding='utf-8')
    assert '05cd02202827e9a0' not in settings
    (fixture/'contents/settings.ini').write_text(settings,encoding='utf-8')
    def action(exe,operation,ids):
        completed=subprocess.run([str(exe),operation,str(fixture)],env=env,check=True,capture_output=True,text=True,encoding='utf-8')
        raw=survey.read_bundle(path)[0]
        current=records(raw)
        assert current.keys()==baseline.keys()
        assert all(current[key]==value for key,value in baseline.items() if key!=boot_id)
        label=f'{len(results):02d}-{operation}-'+('-'.join(ids) or 'none')
        chunk=out/(label+'.luac')
        chunk.write_bytes(current[boot_id][44:])
        subprocess.run([str(luajit),str(root/'tests/boot_modules.lua'),str(chunk),','.join(ids)],env=env,check=True)
        if not ids: assert path.read_bytes()==original
        results.append({'step':label,'bundle_sha256':sha(path.read_bytes()),'unchanged_resources':len(baseline)-1,'installer':completed.stdout.strip()})
    action(camera,'install',['camera'])
    action(captain,'install',['camera','captain'])
    action(camera,'install',['camera','captain'])
    action(captain,'uninstall',['camera'])
    action(camera,'uninstall',[])
    action(captain,'install',['captain'])
    action(camera,'install',['camera','captain'])
    action(camera,'uninstall',['captain'])
    action(captain,'uninstall',[])
    action(camera,'install',['camera'])
    installed=path.read_bytes()
    manifest=fixture/'helldivers_bridge_v1'/bundle/(sha(installed)+'.manifest')
    module_sha=manifest.read_text().splitlines()[3].split()[1]
    payload=manifest.parent/(module_sha+'.luac')
    good_payload=payload.read_bytes()
    payload.write_bytes(b'corrupt')
    rejected=subprocess.run([str(captain),'install',str(fixture)],env=env,capture_output=True)
    assert rejected.returncode!=0 and path.read_bytes()==installed
    payload.write_bytes(good_payload)
    action(camera,'uninstall',[])
    legacy=(game/'contents'/bundle).read_bytes()
    receipt=game/'captain_bridge_backup'/f'{bundle}.sha256'
    if receipt.exists() and sha(legacy) in receipt.read_text().splitlines() and legacy!=original:
        path.write_bytes(legacy)
        (fixture/'captain_bridge_backup'/f'{bundle}.sha256').write_text(sha(legacy))
        rejected=subprocess.run([str(camera),'install',str(fixture)],env=env,capture_output=True)
        assert rejected.returncode!=0 and path.read_bytes()==legacy
        action(captain,'install',['captain'])
        action(camera,'install',['camera','captain'])
        action(captain,'uninstall',['camera'])
        action(camera,'uninstall',[])
    # A foreign modification must not be overwritten by either installer.
    damaged=bytearray(original);damaged[-1]^=1;path.write_bytes(damaged)
    for exe in (captain,camera):
        rejected=subprocess.run([str(exe),'install',str(fixture)],env=env,capture_output=True)
        assert rejected.returncode!=0 and path.read_bytes()==damaged
(out/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'PASS {len(results)} install/uninstall steps, unchanged non-boot resources, foreign-mod refusal. Report: {out}')
