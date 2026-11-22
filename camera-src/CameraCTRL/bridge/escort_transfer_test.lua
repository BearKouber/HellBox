local factory=assert(loadfile(arg[1]))()
local protector_factory=assert(loadfile(arg[2]))()
local vector_meta={}
local function vector(horizontal,vertical,height) return setmetatable({x=horizontal,y=vertical,z=height},vector_meta) end
vector_meta.__sub=function(left,right) return vector(left.x-right.x,left.y-right.y,left.z-right.z) end
vector_meta.__add=function(left,right) return vector(left.x+right.x,left.y+right.y,left.z+right.z) end
vector_meta.__mul=function(left,right) return vector(left.x*right,left.y*right,left.z*right) end
Vector3=setmetatable({up=function() return vector(0,0,1) end,forward=function() return vector(0,1,0) end},
    {__call=function(_,...) return vector(...) end})
Vector3Aux={unbox=function(value) return value end}
Quaternion={forward=function() return vector(0,1,0) end,look=function() return {} end}
PhysicsWorld={overlap=function() end}
local environment=setmetatable({class=function() return {} end,require=function() end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
setfenv(assert(loadfile(arg[3].."/chunk_001e5231/chunk.ljbc")),environment)()
local native_interactor=environment.InteractorComponent.update_masters
setfenv(assert(loadfile(arg[3].."/chunk_00295397/chunk.ljbc")),environment)()
local native_escort=environment.NpcEscortComponent.update_derived_master
local function fixture()
    local now=0
    local positions={[1]=vector(100,100,0),[2]=vector(102,100,0),[3]=vector(103,100,0),[4]=vector(104,100,0),[5]=vector(100,101,0)}
    local owners={[1]="local",[2]="host",[3]="host",[4]="host",[5]="host"}
    local levels={}
    local health={}
    for unit in pairs(positions) do health[unit]={is_dead=false,is_downed=false,is_dodging=false} end
    local contexts={npc_escort={master={},slave={}},objective_escort={master={},slave={[5]={state={
        mission_state="pending",npc_units={}}}}}}
    for _,unit in ipairs({2,3,4}) do contexts.npc_escort.slave[unit]={state={objective_name="escort_a",following_unit=false,in_goal=false,
        health_state=health[unit],require_handshake=false,on_interact=function()
            return {interact_event=health[unit].is_downed and "help_up" or "salute",interact_time=0.4}
        end}} end
    local input={enabled=true,do_interact=true,interactable_unit=2,interactable_component="npc_escort",health_state=health[1]}
    local inputs={[1]={state=input}}
    local requests,commands,rpcs={},{},{}
    Application={time_since_launch=function() return now end}
    Network={peer_id=function() return "local" end}
    Unit={alive=function(unit) return positions[unit]~=nil end,world_position=function(unit) return positions[unit] end,
        world_rotation=function() return {} end,num_actors=function() return 0 end,
        has_data=function() return true end,get_data=function() return "escort_a" end,level=function(unit) return levels[unit] or 1 end}
    EntityAux={owner=function(unit) return owners[unit] end,has_interface=function() return true end,
        has_component_master=function(unit) return owners[unit]=="local" end,
        queue_command_master=function(unit,component,command,value)
            commands[#commands+1]={unit,component,command,value}
            if component=="objective_escort" and command=="register_npc" then
                local objective=contexts.objective_escort.master[5]
                if objective then objective.state.npc_units[#objective.state.npc_units+1]=value end
            end
        end,
        state=function(unit,name)
            if name=="health" then return health[unit] end
            local entry=contexts.npc_escort.master[unit] or contexts.npc_escort.slave[unit]
            return entry and entry.state
        end}
    CameraManager={state="follow",ground_position=vector(0,0,0),viewport={world_to_viewport=function(_,position)
        return vector(position.x,1,position.y)
    end},is_position_inside_frustum=function(_,position) return math.abs(position.x)<20 and math.abs(position.y)<20 end}
    local npc={migrate_unit_to_me=function(_,unit) requests[#requests+1]=unit end,
        entity_manager={get_slave_entities=function(_,name)
            if name=="objective_escort" then return contexts.objective_escort.master end
            return {}
        end},
        queue_command_master=function(_,unit,component,command,value) EntityAux.queue_command_master(unit,component,command,value) end}
    local objective_requests={}
    local objective={migrate_unit_to_me=function(_,unit)
            objective_requests[#objective_requests+1]=unit
            owners[unit]="local"
            local entry=contexts.objective_escort.slave[unit]
            contexts.objective_escort.slave[unit]=nil
            contexts.objective_escort.master[unit]=entry
        end}
    local game={entity_manager={component_name_to_contexts=contexts,components={npc_escort=npc,objective_escort=objective}},
        players={{player_go={exists=function() return true end,owned=function() return true end,get=function() return 1 end}}}}
    Boot={state_machine={current_state_name="game",state=game}}
    InteractorComponent={update_masters=native_interactor}
    NpcEscortComponent={update_derived_master=native_escort}
    local host={resources={}}
    function host:claim(owner,key) if self.resources[key] then return false end;self.resources[key]=owner;return true end
    function host:release(_,key) self.resources[key]=nil end
    local transfer=factory(host)
    local protector=protector_factory(host,transfer,nil,{contains=function(_,position)
        return math.abs(position.x-positions[1].x)<20 and math.abs(position.y-positions[1].y)<20
    end})
    transfer.tick(true);protector.tick()
    local controller={world_proxy={is_active=function() return true end},
        queue_command_master=function(_,...) commands[#commands+1]={...} end,
        trigger_rpc_event_to=function(_,...) rpcs[#rpcs+1]={...} end}
    local function acquire(unit)
        owners[unit]="local"
        local entry=contexts.npc_escort.slave[unit]
        contexts.npc_escort.slave[unit]=nil;contexts.npc_escort.master[unit]=entry
        entry.state.was_migrated=true;entry.state.registered_at_objective=false
        entry.state.full_update_dt=0;entry.state.outside_screen_timer=0.01
        entry.settings={npc_escort_info={outside_screen_kill_time=10}}
        NpcEscortComponent.update_derived_master(npc,unit,entry,0.2,false)
        assert(entry.state.registered_at_objective and entry.state.master==5,"acquire unit="..unit.." registered="..tostring(entry.state.registered_at_objective).." master="..tostring(entry.state.master))
        NpcEscortComponent.update_derived_master(npc,unit,entry,0.2,true)
        return entry
    end
    return {input=input,transfer=transfer,protector=protector,requests=requests,objective_requests=objective_requests,rpcs=rpcs,commands=commands,
        contexts=contexts,owners=owners,health=health,positions=positions,levels=levels,host=host,game=game,acquire=acquire,
        time=function(value) now=value end,update=function() InteractorComponent.update_masters(controller,inputs,0.1) end}
end
local test=fixture();test.update()
assert(#test.objective_requests==1 and #test.requests==0 and #test.rpcs==0)
test.input.do_interact=true;test.update();assert(#test.requests==3 and #test.rpcs==0,"after objective migration requests="..#test.requests.." rpcs="..#test.rpcs)
for _,unit in ipairs({2,3}) do test.acquire(unit) end
test.update();assert(#test.rpcs==0)
test.acquire(4);test.update()
assert(#test.rpcs==1 and test.rpcs[1][1]=="local" and test.rpcs[1][2]=="rpc_on_interact")
for _,command in ipairs(test.commands) do assert(command[3]~="set_hitpoints") end
test.update();assert(#test.rpcs==1)
test.input.do_interact=true;test.update();assert(#test.rpcs==1)
test.time(3);test.update()
test.input.do_interact=true;test.update();assert(#test.rpcs==2)
print("PASS original interactor dispatch waits for the entire group, replays once, permits later stop")
print("PASS original escort migration update preserves registration and survives before follow, including partial update")

test=fixture();test.game.entity_manager.components.objective_escort.migrate_unit_to_me=function(_,unit) test.objective_requests[#test.objective_requests+1]=unit end
test.update();test.time(2.1);test.update();test.time(4.2);test.update();test.time(6.3);test.update()
assert(#test.objective_requests==3 and #test.requests==0 and #test.rpcs==0,"objective retries="..#test.objective_requests.." npc retries="..#test.requests.." rpcs="..#test.rpcs)
test.time(10.1);test.update();assert(test.transfer.tick(true):find("timeout") and #test.rpcs==0)
print("PASS bounded retries and timeout never dispatch unprotected interaction")

test=fixture();test.update();test.owners[3]="other_client";test.time(3);test.update()
assert(test.transfer.tick(true)=="escort_owner_changed" and #test.requests==0 and #test.rpcs==0)
test=fixture();test.contexts.npc_escort.slave[3].state.following_unit=true;test.update()
assert(test.transfer.tick(true)=="escort_already_following" and #test.requests==0 and #test.rpcs==0)
print("PASS another escort owner or existing follower is never stolen")

test=fixture();test.update();test.input.interactable_unit=nil;test.update()
assert(#test.rpcs==0 and test.transfer.tick(true))
test=fixture();test.update();test.health[1].is_dead=true;test.update();assert(#test.rpcs==0)
test=fixture();test.update();test.transfer.tick(false)
assert(InteractorComponent.update_masters==native_interactor)
Boot.state_machine.current_state_name="menu";test.protector.tick();assert(next(test.host.resources)==nil)
print("PASS cancellation, player death, disabling and task exit release pending interaction and hooks")

test=fixture();test.game.entity_manager.components.objective_escort.migrate_unit_to_me=function() error("migration_failed") end
test.update();assert(test.transfer.tick(true):find("migration_failed") and #test.rpcs==0)
print("PASS migration errors are visible and fail without dispatching the interaction")

local function other_site(test)
    for _,unit in ipairs({6,7}) do
        test.positions[unit]=vector(200,200,0)
        test.levels[unit]=2;test.owners[unit]="host";test.health[unit]={is_dead=false}
    end
    test.contexts.objective_escort.slave[6]={state={mission_state="pending",npc_units={}}}
    test.contexts.npc_escort.slave[7]={state={objective_name="escort_a",following_unit=false,in_goal=false}}
end
test=fixture();other_site(test);test.update()
assert(#test.objective_requests==1 and test.objective_requests[1]==5 and not test.transfer.tick(true))
test.update();assert(#test.requests==3)
for _,unit in ipairs(test.requests) do assert(unit~=7) end
for _,unit in ipairs({2,3,4}) do test.acquire(unit) end
test.update();assert(#test.rpcs==1 and test.owners[6]=="host" and test.owners[7]=="host")
print("PASS same-name escort sites in distinct level instances migrate only the clicked group")

test=fixture();other_site(test);test.levels[6]=1;test.update()
assert(test.transfer.tick(true)=="escort_ambiguous_objective" and #test.objective_requests==0 and #test.rpcs==0)
print("PASS ambiguity within the same level still blocks migration")

test=fixture();other_site(test);test.game.is_server=true
for _,name in ipairs({"objective_escort","npc_escort"}) do
    local group=test.contexts[name]
    for unit,entry in pairs(group.slave) do group.master[unit]=entry;test.owners[unit]="local" end
    group.slave={}
end
-- A local group can be spread out while following; transfer distance must not block stop/follow.
test.positions[4]=vector(150,100,0)
test.contexts.npc_escort.master[4].state.following_unit=true
test.update()
assert(#test.rpcs==1 and #test.requests==0 and #test.objective_requests==0 and not test.transfer.tick(true))
test.input.do_interact=true;test.update();assert(#test.rpcs==2)
print("PASS solo host with two same-name sites uses native interaction without migration or distance rejection")

test=fixture();test.positions[4]=vector(150,100,0);test.update()
assert(test.transfer.tick(true)=="escort_group_too_far" and #test.objective_requests==0 and #test.rpcs==0)
print("PASS remote migration still rejects a scattered group before transferring ownership")

for _,local_owner in ipairs({false,true}) do
    test=fixture()
    test.health[2].is_downed=true
    test.contexts.npc_escort.slave[3].state.following_unit=true
    test.positions[4]=vector(150,100,0)
    test.contexts.objective_escort.slave[5].state.mission_state="finished"
    if local_owner then test.owners[2]="local" end
    assert(not CameraManager:is_position_inside_frustum(test.positions[2]))
    test.update()
    local rpc=assert(test.rpcs[1])
    assert(#test.rpcs==1 and rpc[1]==(local_owner and "local" or "host") and rpc[2]=="rpc_on_interact")
    assert(rpc[3]==2 and rpc[5]==1 and rpc[6]=="npc_escort" and test.input.interact_event=="help_up")
    assert(#test.requests==0 and #test.objective_requests==0 and not test.transfer.tick(true))
    local has_master=EntityAux.has_component_master
    EntityAux.has_component_master=function(unit) return test.owners[unit]==rpc[1] end
    local receiver={name="npc_escort",queue_command_master=function(_,unit,component,command,player)
        assert(unit==2 and component=="npc_escort" and command=="interact" and player==1)
        environment.NpcEscortComponent.command_derived_master({},unit,test.contexts.npc_escort.slave[unit],command,player)
    end}
    local before=#test.commands
    environment.NpcEscortComponent.rpc_on_interact(receiver,"local",rpc[3],rpc[4],rpc[5])
    EntityAux.has_component_master=has_master
    assert(#test.commands==before+1)
    local command=test.commands[#test.commands]
    assert(command[1]==2 and command[2]=="health" and command[3]=="set_hitpoints" and command[4]==20)
end
print("PASS off-screen help uses original owner RPC and native health command without whole-group migration")

test=fixture();test.update();test.update();test.acquire(2)
test.health[2].is_downed=true;test.input.do_interact=false;test.update()
assert(#test.rpcs==0 and test.transfer.status()==nil)
assert(test.transfer.prepare(2,test.contexts.npc_escort.master[2])==1)
test.input.do_interact=true;test.update()
assert(#test.rpcs==1 and test.input.interact_event=="help_up")
test.input.do_interact=false;test.health[2].is_downed=false
test.time(3);test.update()
assert(#test.rpcs==1 and test.transfer.prepare(2,test.contexts.npc_escort.master[2])==nil)
print("PASS downing cancels pending follow replay while retaining bounded migration protection; no synthetic help")

test=fixture();test.update();test.update()
for _,unit in ipairs({2,3,4}) do test.acquire(unit) end
test.update();assert(#test.rpcs==1)
test.health[2].is_downed=true;test.input.do_interact=true;test.update()
assert(#test.rpcs==2 and test.input.interact_event=="help_up")
print("PASS help is not swallowed by the post-transfer duplicate-follow suppression window")

for _,condition in ipairs({"disabled","player_dead","npc_dead","other_component"}) do
    test=fixture();test.health[2].is_downed=true
    if condition=="disabled" then test.input.enabled=false
    elseif condition=="player_dead" then test.health[1].is_dead=true;test.input.enabled=false
    elseif condition=="npc_dead" then test.health[2].is_dead=true;test.positions[2]=nil
    else test.input.interactable_component="other";test.input.do_interact=false end
    test.update()
    assert(#test.requests==0 and #test.rpcs==0,condition)
end
print("PASS help bypass never manufactures interaction for disabled, dead or unrelated targets")
