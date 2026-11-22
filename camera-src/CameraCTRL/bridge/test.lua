local source=assert(loadfile(arg[1]))
local files,now={},0
local native_calls=0
update=function() native_calls=native_calls+1 end
Application={time_since_launch=function() return now end}
local own={exists=function() return true end,owned=function() return true end,get=function() return 42 end}
local remote={exists=own.exists,owned=function() return false end,get=function() return 99 end}
local camera={state={active=true},network_fields={{name="active"}}}
local mover={state={keep_inside_screen=true,is_inside_screen=true}}
local game={players={{player_go=own},{player_go=remote}},entity_manager={component_name_to_contexts={
    camera_target={master={[42]=camera}},mover={master={[42]=mover}}
}}}
Boot={state_machine={current_state_name="menu",state=game}}
Unit={alive=function(unit) return unit==42 end}
EntityAux={has_component_master=function(unit) return unit==42 end}
CameraManager={targets={[42]={},[99]={}},state="follow"}
os={getenv=function() return "fixture" end,time=function() return 123 end,
    remove=function(path) files[path]=nil end,rename=function(a,b) files[b],files[a]=files[a],nil end}
io={open=function(path,mode)
    if mode=="rb" then if not files[path] then return end
        return {read=function(_,count) return files[path]:sub(1,count) end,close=function() end}
    end
    return {write=function(_,s) files[path]=s end,close=function() end}
end}
source();assert(CameraCTRLBridgeLoadOk,CameraCTRLBridgeLoadError)
local dispatch=update
source();assert(update==dispatch)
local root="fixture/Arrowhead/Helldivers/camera_ctrl_v1/"
local function request(nonce)
    files[root.."camera-request.txt"]="CAM1\n"..nonce.."\nINSPECT\nEND\n"
    now=now+0.25;update(0.25)
    return assert(files[root.."camera-status.txt"])
end
assert(request("first"):find("\nmenu\n",1,true))
Boot.state_machine.current_state_name="game"
local report=request("second")
assert(report:find("players=2",1,true) and report:find("active_network_field=true",1,true))
assert(report:find("own_target=true",1,true))
assert(camera.state.active and mover.state.keep_inside_screen and CameraManager.targets[99])
game.players[3]={player_go=own}
assert(request("third"):find("local_players=2",1,true))
files[root.."camera-request.txt"]="CAM1\ninvalid\nWRITE\nEND\n"
now=now+0.25;update(0.25)
assert(files[root.."camera-status.txt"]:find("\nthird\n",1,true))
assert(native_calls==4)
print("PASS independent Camera module: fresh nonce, menu, ownership, local co-op rejection, read-only scope")
game.players[3]=nil
local function control(nonce,session,client,serial,mask)
    files[root.."control-request.txt"]=table.concat({"CAM2",nonce,session,client,tostring(serial),tostring(mask),"END",""},"\n")
    now=now+0.25;update(0.25)
    return files[root.."control-status.txt"]
end
local handshake=control("hello","-","one",1,0)
assert(handshake:find("\nhello\n"..CameraCTRLBridge.session.."\n1\n",1,true))
local session=CameraCTRLBridge.session
local accepted=control("enable",session,"one",2,1)
assert(accepted:find("\n2\n1\n",1,true))
assert(control("steal",session,"two",3,3)==accepted)
assert(control("old","wrongsession","one",3,3)==accepted)
assert(control("invalid",session,"one",3,2)==accepted)
files[root.."control-request.txt"]=table.concat({"CAM2","enable",session,"one","2","1","END",""},"\n")
now=now+6;update(0.25)
assert(files[root.."control-status.txt"]:find("\n2\n0\n",1,true))
assert(control("renew",session,"two",1,3):find("\nrenew\n",1,true))
assert(control("cancel",session,"two",2,0):find("\n2\n0\n0\n0\n",1,true))
print("PASS control handshake, session, owner lease, replay rejection, expiry and cancellation")
local expanded=control("hostfeature",session,"two",3,4)
assert(expanded:find("\n3\n4\n0\n0\n",1,true) and expanded:find("spawn=host_only",1,true))
assert(control("badcombination",session,"two",4,6)==expanded)
assert(control("unknownbit",session,"two",4,8)==expanded)
assert(control("combined",session,"two",4,7):find("\n4\n7\n",1,true))
now=now+6;update(0.25)
assert(files[root.."control-status.txt"]:find("\n4\n0\n0\n0\n",1,true))
print("PASS host bit accepted, client reports unavailable, invalid masks rejected and lease clears all features")

local function configured(serial,encounter,patrol,session_value)
    files[root.."control-request.txt"]=table.concat({"CAM2","settings"..serial,session_value or session,"two",
        tostring(serial),"4","SPAWN",tostring(encounter),tostring(patrol),"END",""},"\n")
    now=now+0.25;update(0.25)
    return files[root.."control-status.txt"]
end
assert(configured(10,8,5):find(";spawn_config:1;spawn_multipliers:8/5",1,true))
local accepted_config=files[root.."control-status.txt"]
assert(configured(11,0,4)==accepted_config)
assert(configured(11,4,101)==accepted_config)
assert(configured(11,4,4,"wrong")==accepted_config)
assert(configured(10,2,2)==accepted_config)
assert(configured(11,2,4):find("spawn_multipliers:2/4",1,true))
assert(control("legacy",session,"two",12,0):find("spawn_multipliers:2/4",1,true))
print("PASS multiplier protocol validates ranges, session and replay, reports applied settings, and accepts legacy cancellation")
