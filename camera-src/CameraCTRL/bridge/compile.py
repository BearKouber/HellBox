"""Compile a standalone CameraCTRL module. Captain sources are not required."""
from pathlib import Path
import hashlib
import subprocess
import sys

root=Path(__file__).resolve().parent
source=root/'runtime.lua'
text=source.read_text(encoding='utf-8')
for name, label in [('peer_modes', 'PEER MODES'), ('vehicles', 'VEHICLES'), ('extraction', 'EXTRACTION'), ('camera_focus', 'CAMERA FOCUS'), ('view', 'VIEW')]:
    start, end = f'-- BEGIN GENERATED {label} FACTORY', f'-- END GENERATED {label} FACTORY'
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    factory = (root / f'{name}.lua').read_text(encoding='utf-8')
    text = before + start + f'\nlocal {name}_factory = (function()\n' + factory + '\nend)()\n' + end + after
start,end='-- BEGIN GENERATED ESCORT TRANSFER FACTORY','-- END GENERATED ESCORT TRANSFER FACTORY'
before,rest=text.split(start,1)
_,after=rest.split(end,1)
transfer=(root/'escort_transfer.lua').read_text(encoding='utf-8')
text=before+start+'\nlocal escort_transfer_factory = (function()\n'+transfer+'\nend)()\n'+end+after
start,end='-- BEGIN GENERATED ESCORT FACTORY','-- END GENERATED ESCORT FACTORY'
before,rest=text.split(start,1)
_,after=rest.split(end,1)
escort=(root/'escort.lua').read_text(encoding='utf-8')
text=before+start+'\nlocal escort_factory = (function()\n'+escort+'\nend)()\n'+end+after
host=(root.parent.parent/'BridgeCore/lua/host.lua').read_text(encoding='utf-8')
start,end='-- BEGIN GENERATED HOST FACTORY','-- END GENERATED HOST FACTORY'
before,rest=text.split(start,1)
_,after=rest.split(end,1)
text=before+start+'\nlocal get_host = (function()\n'+host+'\nend)()\n'+end+after
start,end='-- BEGIN GENERATED CAMERA FACTORY','-- END GENERATED CAMERA FACTORY'
before,rest=text.split(start,1)
_,after=rest.split(end,1)
camera=(root/'camera.lua').read_text(encoding='utf-8')
text=before+start+'\nlocal camera_factory = (function()\n'+camera+'\nend)()\n'+end+after
start,end='-- BEGIN GENERATED ENCOUNTER FACTORY','-- END GENERATED ENCOUNTER FACTORY'
before,rest=text.split(start,1)
_,after=rest.split(end,1)
encounters=(root/'encounters.lua').read_text(encoding='utf-8')
text=before+start+'\nlocal encounter_factory = (function()\n'+encounters+'\nend)()\n'+end+after
start,end='-- BEGIN GENERATED SPAWNING FACTORY','-- END GENERATED SPAWNING FACTORY'
begin,finish='-- BEGIN GENERATED SUPPLY FACTORY','-- END GENERATED SUPPLY FACTORY'
prefix,remaining=text.split(begin,1)
_,suffix=remaining.split(finish,1)
supply=(root/'patrol_supply.lua').read_text(encoding='utf-8')
text=prefix+begin+'\nlocal supply_factory = (function()\n'+supply+'\nend)()\n'+finish+suffix
before,rest=text.split(start,1)
_,after=rest.split(end,1)
spawning=(root/'spawning.lua').read_text(encoding='utf-8')
text=before+start+'\nlocal spawning_factory = (function()\n'+spawning+'\nend)()\n'+end+after
start,end='-- BEGIN GENERATED RESPAWN FACTORY','-- END GENERATED RESPAWN FACTORY'
before,rest=text.split(start,1)
_,after=rest.split(end,1)
respawn=(root/'respawn.lua').read_text(encoding='utf-8')
source.write_text(before+start+'\nlocal respawn_factory = (function()\n'+respawn+'\nend)()\n'+end+after,encoding='utf-8',newline='\n')
subprocess.run([str(Path(sys.argv[1]).resolve()),'-e',"local f=assert(loadfile('runtime.lua')); local o=assert(io.open('runtime.luac','wb')); o:write(string.dump(f,true)); assert(o:close())"],cwd=root,check=True)
blob=(root/'runtime.luac').read_bytes()
assert blob[:5]==b'\x1bLJ\x01\x02'
(root/'runtime.sha256').write_text(hashlib.sha256(source.read_bytes()).hexdigest()+'\n'+hashlib.sha256(blob).hexdigest()+'\n',encoding='ascii',newline='\n')
print(f'Compiled independent CameraCTRL module: {len(blob)} bytes')
