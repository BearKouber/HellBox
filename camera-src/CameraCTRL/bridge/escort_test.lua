local factory=assert(loadfile(arg[1]))()
local vector_meta={}
local function vector(x,y,z) return setmetatable({x=x,y=y,z=z},vector_meta) end
vector_meta.__add=function(left,right) return vector(left.x+right.x,left.y+right.y,left.z+right.z) end
vector_meta.__sub=function(left,right) return vector(left.x-right.x,left.y-right.y,left.z-right.z) end
Vector3=setmetatable({},{__call=function(_,...) return vector(...) end})
Vector3.distance=function(left,right) return math.sqrt((left.x-right.x)^2+(left.y-right.y)^2+(left.z-right.z)^2) end
Vector3Aux={unbox=function(value) return vector(value.x,value.y,value.z) end,
    box=function(destination,value)
        destination.x,destination.y,destination.z=value.x,value.y,value.z
        return destination
    end}
local environment=setmetatable({class=function() return {} end,require=function() end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
setfenv(assert(loadfile(arg[2].."/chunk_00295397/chunk.ljbc")),environment)()
local native=environment.NpcEscortComponent.update_derived_master
setfenv(assert(loadfile(arg[3].."/chunk_0027583d/chunk.ljbc")),environment)()
local frustum=environment.CameraManager.is_position_inside_frustum
environment.CameraManager=nil
local function fixture()
    local positions={[1]=vector(100,100,0),[2]=vector(102,100,0),[3]=vector(0,0,0)}
    local health={[1]={is_dead=false},[2]={is_dead=false},[3]={is_dead=false}}
    local master=true
    Unit={alive=function(unit) return positions[unit]~=nil end,world_position=function(unit) return positions[unit] end}
    EntityAux={state=function(unit,name) assert(name=="health");return health[unit] end,
        has_component_master=function(unit,name) return master and unit==2 and name=="npc_escort" end}
    CameraManager={state="follow",ground_position={x=0,y=0,z=0},screen_resolution={width=1000,height=800},
        viewport={world_to_viewport=function(_,position) return vector(500+position.x*50,10,400+position.y*50) end},
        is_position_inside_frustum=frustum}
    local commands={}
    local controller={entity_manager={get_slave_entities=function() return {} end},queue_command_master=function(_,unit,component,command,value)
        commands[#commands+1]={unit=unit,component=component,command=command,value=value}
    end}
    local context={state={follow_unit=1,following_unit=true,registered_at_objective=true,activated=true,
        full_update_dt=0,outside_screen_timer=0.1},settings={npc_escort_info={outside_screen_kill_time=5}}}
    local game={is_server=false,entity_manager={component_name_to_contexts={}},
        players={{player_go={exists=function() return true end,owned=function() return false end,get=function() return 1 end}}}}
    Boot={state_machine={current_state_name="game",state=game}}
    NpcEscortComponent={update_derived_master=native}
    local host={resources={}}
    function host:claim(owner,key) if self.resources[key] then return false end;self.resources[key]=owner;return true end
    function host:release(owner,key) if self.resources[key]==owner then self.resources[key]=nil end end
    local mode=3
    local local_visible=false
    local module=factory(host,nil,{read=function() return mode end},{contains=function() return local_visible end})
    return {module=module,host=host,game=game,context=context,positions=positions,health=health,commands=commands,
        controller=controller,master=function(value) master=value end,
        mode=function(value) mode=value end,local_visible=function(value) local_visible=value end,
        update=function(dt,full) return NpcEscortComponent.update_derived_master(controller,2,context,dt,full) end}
end
local test=fixture()
test.update(0.2,true)
assert(test.commands[1].command=="set_hitpoints" and test.commands[1].value==-100)
assert(not test.context.state.follow_unit)
print("PASS original escort bytecode reproduces off-screen timeout death beside a remote player")

test=fixture();test.module.tick()
for index=1,100 do assert(test.update(0.2,true)) end
assert(#test.commands==0 and test.context.state.follow_unit==1 and test.context.state.outside_screen_timer==5)
assert(not CameraManager:is_position_inside_frustum(test.positions[2]))
assert(CameraManager.ground_position.x==0 and CameraManager.viewport:world_to_viewport(vector(0,0,0)).x==500)
assert(test.context.state.dirty==true)
test.context.state.dirty=false
test.update(0.2,true)
assert(test.context.state.dirty==true)
print("PASS escorted local master requests native replication each full update without changing public camera")
test.context.state.full_update_dt=20
test.update(0.2,true)
assert(#test.commands==0 and test.context.state.outside_screen_timer==5 and test.context.state.full_update_dt==0)
print("PASS client-owned escort survives beyond timeout with accumulated delta while public camera stays unchanged")

test=fixture();test.health[2].is_downed=true;test.module.tick()
for index=1,50 do test.update(0.2,true) end
assert(#test.commands==0 and test.context.state.follow_unit==1 and test.context.state.outside_screen_timer==5)
assert(test.health[2].is_downed and not test.health[2].is_dead)
print("PASS locally owned downed follower outside public screen retains timeout protection without healing")

test=fixture();test.health[2].is_downed=true;test.context.state.follow_unit=nil;test.context.state.following_unit=false
test.module.tick();test.update(20,true)
assert(#test.commands==0 and test.context.state.outside_screen_timer==0.1)
print("PASS non-following downed NPC does not enter the native off-screen follow timeout branch")

test=fixture();test.game.is_server=true;test.module.tick()
test.update(0.2,true);assert(#test.commands==0)
test.positions[2]=vector(150,100,0)
test.update(6,true)
assert(test.commands[1].command=="set_hitpoints" and test.commands[1].value==-100)
print("PASS host-owned escort uses the same rule and an abandoned distant NPC still times out")

test=fixture();test.context.state.follow_unit=3;test.module.tick()
for index=1,50 do test.update(0.2,true) end
assert(#test.commands==0 and test.context.state.follow_unit==3 and test.context.state.outside_screen_timer==5)
print("PASS another independent player protects a hostage even when its escort remains in public view")

test=fixture();test.context.state.follow_unit=nil;test.context.state.was_migrated=true
test.health[2].is_downed=true;test.module.tick();test.update(6,true)
assert(#test.commands==0 and test.health[2].is_downed and test.context.state.outside_screen_timer==5)
print("PASS newly migrated downed hostage has protection without a follow target")

for _,mode in ipairs({1,3}) do
    test=fixture();test.mode(mode);test.positions[2]=vector(130,100,0);test.module.tick();test.update(6,true)
    assert(#test.commands==0)
    test.positions[2]=vector(130.01,100,0);test.update(6,true)
    assert(test.commands[1].value==-100)
end
print("PASS independent modes use an inclusive 30-unit radius and preserve timeout outside it")

test=fixture();test.module.tick();test.update(0.2,true);test.mode(0);test.update(6,true)
assert(test.commands[1].value==-100)
print("PASS disabled or expired remote mode no longer provides protection")

test=fixture();test.mode(0);test.local_visible(true);test.module.tick();test.update(6,true)
assert(#test.commands==0)
test.local_visible(false);test.update(6,true);assert(test.commands[1].value==-100)
test=fixture();test.game.players={};test.positions[2]=vector(0,0,0);test.module.tick();test.update(6,true)
assert(#test.commands==0 and test.context.state.outside_screen_timer==5)
print("PASS local independent screen and public screen protect without a nearby escort")

test=fixture();test.positions[1]=vector(200,200,0)
test.game.entity_manager.component_name_to_contexts.character={slave={[1]={state={current_seat_unit=3}}}}
test.positions[3]=vector(100,100,0);test.module.tick();test.update(6,true)
assert(#test.commands==0)
print("PASS a remote independent vehicle occupant protects around the current vehicle position")

test=fixture();test.module.tick();test.master(false)
test.update(0.2,true)
assert(test.commands[1].command=="set_hitpoints")
assert(test.context.state.dirty==nil)
test=fixture();test.game.players={};test.module.tick();test.update(0.2,true)
assert(test.commands[1].command=="set_hitpoints")
test=fixture();test.health[1].is_dead=true;test.module.tick();test.update(0.2,true)
assert(not test.context.state.follow_unit)
test=fixture();test.health[2].is_dead=true;test.module.tick()
assert(test.update(0.2,true)==false and test.health[2].is_dead)
print("PASS non-master, non-player follower and dead characters receive no protection or resurrection")

test=fixture();test.module.tick();test.update(0.2,false)
assert(test.context.state.outside_screen_timer==0.1 and test.context.state.full_update_dt==0.2)
assert(test.context.state.dirty==nil)
test.context.state.goal_unit=3;test.context.state.goal_joint_position=nil
test.update(0.2,true)
assert(test.context.state.outside_screen_timer==0.1 and #test.commands==0)
test.context.state.finished=true
assert(test.update(0.2,true)==false)
print("PASS partial update and goal/finished branches preserve original return values and timer state")

test=fixture()
test.context.state.goal_unit=3;test.context.state.goal_joint_position=vector(102,100,0)
test.context.state.modules={}
test.update(0.2,true)
assert(test.context.state.in_goal and test.context.state.goal_joint_position==nil)
test=fixture()
test.context.state.goal_unit=3;test.context.state.goal_joint_position=vector(102,100,0)
test.context.state.modules={};test.module.tick();test.update(0.2,true)
assert(test.context.state.in_goal and test.context.state.goal_joint_position.x==test.positions[3].x)
assert(test.context.state.goal_joint_position.y==test.positions[3].y)
assert(test.commands[1].command=="disable" and test.commands[2].command=="set_invincible")
print("PASS native arrival clears approach point; repair retains shelter centre and original arrival commands")

test=fixture();test.module.tick()
test.controller.entity_manager.get_slave_entities=function() error("native_escort_failure") end
assert(not pcall(test.update,0.2,true))
assert(test.context.state.outside_screen_timer==0.1)
assert(test.context.state.dirty==nil)
Boot.state_machine.current_state_name="menu";test.module.tick();test.module.tick()
assert(NpcEscortComponent.update_derived_master==native and next(test.host.resources)==nil)
Boot.state_machine.current_state_name="game";test.controller.entity_manager.get_slave_entities=function() return {} end
test.module.tick();test.update(0.2,true);assert(#test.commands==0)
print("PASS native failure restores temporary timer, task exit releases hook, next task reinstalls")

test=fixture();test.host.resources["NpcEscortComponent.update_derived_master"]="other"
assert(test.module.tick():find("hook_busy",1,true) and NpcEscortComponent.update_derived_master==native)
test.host.resources={};test.module.tick()
CameraManager.viewport.world_to_viewport=function() error("projection_failure") end
assert(not pcall(test.update,0.2,true))
assert(test.context.state.outside_screen_timer==0.1 and test.module.tick():find("projection_failure",1,true))
print("PASS conflicts preserve foreign hook and failed protection reports error while native behavior remains available")
