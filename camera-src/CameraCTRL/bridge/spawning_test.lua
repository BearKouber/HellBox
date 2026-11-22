local factory=assert(loadfile(arg[1]))()
local evidence=assert(arg[2])
local vector_meta={}
local function vector(x,y,z) return setmetatable({x=x,y=y,z=z},vector_meta) end
vector_meta.__add=function(left,right) return vector(left.x+right.x,left.y+right.y,left.z+right.z) end
vector_meta.__sub=function(left,right) return vector(left.x-right.x,left.y-right.y,left.z-right.z) end
vector_meta.__mul=function(left,right)
    if type(left)=="number" then left,right=right,left end
    return vector(left.x*right,left.y*right,left.z*right)
end
vector_meta.__div=function(left,right) return vector(left.x/right,left.y/right,left.z/right) end
Vector3=setmetatable({zero=function() return vector(0,0,0) end,distance=function(left,right)
    return math.sqrt((left.x-right.x)^2+(left.y-right.y)^2+(left.z-right.z)^2)
end},{__call=function(_,...) return vector(...) end})
Vector3Aux={unbox=function(value) return vector(value.x,value.y,value.z) end}
Quaternion=setmetatable({multiply=function() return {} end,rotate=function(_,value) return vector(value.x,value.y,20) end},{__call=function() return {} end})
local environment=setmetatable({class=function() return {} end,require=function() return {} end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
setfenv(assert(loadfile(evidence.."/chunk_0027583d/chunk.ljbc")),environment)()
local frustum=environment.CameraManager.is_position_inside_frustum
local function fixture()
    local now=0
    Application={time_since_launch=function() return now end}
    Network={peer_id=function() return "host" end}
    local units={[1]={x=0,y=0,z=0},[2]={x=0,y=0,z=0},[3]={x=0,y=0,z=0},[4]={x=0,y=0,z=0}}
    local enemies={}
    local owners={}
    local migrations={}
    local health={}
    local cameras={[100]={x=0,y=-17,z=20}}
    local next_camera=100
    local destroyed=0
    Unit={alive=function(unit) return units[unit]~=nil or enemies[unit]~=nil or cameras[unit]~=nil end,
        world_position=function(unit) return Vector3Aux.unbox(assert(units[unit])) end}
    World={spawn_unit=function(_,path)
        assert(path=="core/units/camera");next_camera=next_camera+1;cameras[next_camera]={x=0,y=0,z=0};return next_camera
    end,destroy_unit=function(_,unit) cameras[unit]=nil;destroyed=destroyed+1 end,update_unit=function() end}
    Camera={set_local_position=function(camera,unit,value)
        assert(camera==unit);cameras[unit]={x=value.x,y=value.y,z=value.z}
    end,set_local_rotation=function() end,set_vertical_fov=function() end}
    EntityAux={state=function(unit,name) assert(name=="health");return {is_dead=health[unit] or false} end,
        owner=function(unit) return owners[unit] end,go_id=function(unit) return unit+1000 end}
    local viewport={camera_unit=100,get_world_proxy=function() return {get_world=function() return "world" end} end,
        get_camera=function(self) return self.camera_unit end,world_to_viewport=function(self,position)
            local center=assert(cameras[self.camera_unit])
            return vector(500+(position.x-center.x)*50,10,400+(position.y-center.y-17)*50)
        end,screen_to_world=function(self,position)
            local center=assert(cameras[self.camera_unit])
            return vector(center.x+(position.x-500)/50,center.y+17+(position.y-400)/50,0)
        end}
    CameraManager={viewport=viewport,screen_resolution={width=1000,height=800},min_follow_distance=17,
        follow_spin=0,follow_angle=1,fov=1,state="follow",is_position_inside_frustum=frustum,
        position=cameras[100],get_closest_position_outside_frustum=environment.CameraManager.get_closest_position_outside_frustum}
    EnemyUtility={check_alert=function(state,range)
        if state.fail then error("native_alert_failure") end
        return state.distance<range and state.can_see_closest_target
            and CameraManager:is_position_inside_frustum(state.position)
    end}
    local patrol={calls=0,timer=0,patrols={},spawned=0,max_units=20,fail=false}
    function patrol:update_host(dt)
        self.calls=self.calls+1;self.timer=self.timer+dt
        if self.fail then error("native_patrol_failure") end
        for _,entry in ipairs(self.patrols) do
            if not entry.spawned and self.spawned<self.max_units
                and CameraManager:is_position_inside_frustum(entry.position,-0.5,-0.5,-0.5,-0.5) then
                entry.spawned=true;self.spawned=self.spawned+1
            end
            if entry.spawned then
                entry.visible=CameraManager:is_position_inside_frustum(entry.position,-0.1,-0.1,-0.1,-0.1)
            end
        end
        return 12,nil,"tail"
    end
    local spawn={calls=0}
    function spawn:get_spawn_points(position,radius,group)
        self.calls=self.calls+1
        group.queued_raycasts={{arg_a={x=100,y=0}},{arg_a={x=120,y=0}}}
        return 99,nil,"tail"
    end
    local encounter={calls=0,encounter_position={x=100,y=0,z=0},enemies=0,budget=10}
    function encounter:add_migrated_enemy() self.enemies=self.enemies+1 end
    function encounter:get_spawner_peer() return "client" end
    function encounter:get_center_of_players() return vector(50,0,0) end
    function encounter:can_spawn()
        self.calls=self.calls+1
        return self.enemies<self.budget and Vector3.distance(self:get_center_of_players(),Vector3Aux.unbox(self.encounter_position))<20
    end
    local game={is_server=true,entity_manager={get_slave_entities=function(_,name) return name=="enemy" and enemies or units end},
        network_router={receiver="receiver"},network_session_handler={migrate_game_object=function(_,identifier,peer,receiver)
            assert(peer=="host" and receiver=="receiver")
            migrations[#migrations+1]=identifier
            encounter:add_migrated_enemy(identifier-1000)
        end},
        patrol_manager=patrol,spawn_manager=spawn,encounter_manager=encounter}
    Boot={state_machine={current_state_name="game",state=game}}
    local host={resources={}}
    function host:claim(id,key) if self.resources[key] then return false end self.resources[key]=id;return true end
    function host:release(id,key) if self.resources[key]==id then self.resources[key]=nil end end
    return {module=factory(host),host=host,game=game,units=units,health=health,cameras=cameras,patrol=patrol,spawn=spawn,
        encounter=encounter,manager=CameraManager,destroyed=function() return destroyed end,
        enemies=enemies,owners=owners,migrations=migrations,advance=function(seconds) now=now+seconds end,
        alert=EnemyUtility.check_alert}
end
local test=fixture()
test.patrol.patrols={{position=vector(0,0,0)},{position=vector(100,0,0)}}
assert(test.module.tick(true).detail=="native_same_screen")
local value,empty,tail=test.patrol:update_host(1)
assert(value==12 and empty==nil and tail=="tail")
assert(test.patrol.calls==1 and test.patrol.timer==1 and test.patrol.spawned==1)
assert(not test.patrol.patrols[2].spawned and next(test.cameras,100)==nil)
print("PASS four same-screen players keep one native update and native patrol visibility")

test.units[2].x=100;test.units[3].x=100;test.units[4].x=100
assert(test.module.tick(true).detail=="expanded:3")
test.patrol:update_host(1)
assert(test.patrol.calls==2 and test.patrol.timer==2 and test.patrol.spawned==2)
assert(test.patrol.patrols[2].visible)
assert(not test.manager:is_position_inside_frustum(vector(100,0,0),-0.1,-0.1,-0.1,-0.1))
test.patrol:update_host(1)
assert(test.patrol.spawned==2)
test.patrol.max_units=2
test.patrol.patrols[3]={position=vector(101,0,0)}
test.patrol:update_host(1)
assert(test.patrol.spawned==2 and not test.patrol.patrols[3].spawned)
print("PASS overlapping remote regions activate each patrol once and preserve the native shared budget")

local group={force_outside_screen=true}
value,empty,tail=test.spawn:get_spawn_points(vector(100,0,0),1.25,group)
assert(value==99 and empty==nil and tail=="tail")
assert(test.spawn.calls==1 and #group.queued_raycasts==2 and group.queued_raycasts[2].arg_a.x==120)
assert(math.abs(group.queued_raycasts[1].arg_a.x-100)>10 or math.abs(group.queued_raycasts[1].arg_a.y)>8)
group={force_outside_screen=false};test.spawn:get_spawn_points(vector(100,0,0),1.25,group)
assert(#group.queued_raycasts==2)
print("PASS patrol spawn raycasts move outside extra visible regions without changing other spawn requests")

assert(test.encounter:can_spawn() and test.encounter.calls==1)
assert(test.encounter:get_center_of_players().x==50)
test.encounter.enemies=10
assert(not test.encounter:can_spawn())
assert(test.encounter.encounter_position.x==100)
print("PASS existing encounter accepts nearby separated player without duplicating waves or bypassing budget")

test.patrol.fail=true
assert(not pcall(test.patrol.update_host,test.patrol,1))
assert(not test.manager:is_position_inside_frustum(vector(100,0,0),-0.5,-0.5,-0.5,-0.5))
test.patrol.fail=false
test.units[2].x=0;test.units[3].x=0;test.units[4].x=0
assert(test.module.tick(true).detail=="native_same_screen" and test.destroyed()==3)
test.module.tick(false)
assert(next(test.host.resources)==nil and test.manager.is_position_inside_frustum==frustum)
print("PASS exception scope restoration, rejoin removes extra zones and cancellation restores all wrappers")

test=fixture();test.game.is_server=false
assert(test.module.tick(true).detail=="host_only" and next(test.host.resources)==nil)
test.game.is_server=true;test.units[2].x=100
assert(test.module.tick(true).applied==4)
test.game.is_server=false
assert(test.module.tick(true).owned==0 and next(test.host.resources)==nil and test.destroyed()==1)
print("PASS client rejection and loss of host authority restore immediately")

test=fixture();test.units[2].x=100;test.health[2]=true
assert(test.module.tick(true).detail=="native_same_screen")
test.health[2]=false;assert(test.module.tick(true).detail=="expanded:1")
Boot.state_machine.state={is_server=false}
assert(test.module.tick(true).owned==0 and next(test.host.resources)==nil and test.destroyed()==0)
print("PASS dead players excluded and old world handles discarded without destruction in new world")

test=fixture();test.units[2].x=100
assert(test.module.tick(true).applied==4)
test.patrol.destroyed=true
test.game.patrol_manager=nil
test.game.encounter_manager=nil
Boot.state_machine.current_state_name="menu"
assert(test.module.tick(true).detail=="waiting_task")
assert(next(test.host.resources)==nil and test.destroyed()==0)
assert(test.module.tick(false).detail=="off")
test.patrol.destroyed=nil
test.game.patrol_manager=test.patrol
test.game.encounter_manager=test.encounter
Boot.state_machine.current_state_name="game"
assert(test.module.tick(true).applied==4)
test.module.tick(false)
assert(next(test.host.resources)==nil)
print("PASS destroyed task releases hooks without touching old world and next task can enable again")

test=fixture();test.host.resources["SpawnManager.get_spawn_points"]="another"
assert(test.module.tick(true).detail:find("hook_busy",1,true))
assert(test.manager.is_position_inside_frustum==frustum)
assert(test.host.resources["PatrolManager.update_host"]==nil)
assert(test.host.resources["SpawnManager.get_spawn_points"]=="another")
test.host.resources["SpawnManager.get_spawn_points"]=nil
test.module.tick(false)
assert(test.module.tick(true).applied==4)
print("PASS partial installation conflict releases only own hooks and supports explicit retry")

test=fixture()
local enemy={position=vector(500,0,0),distance=5,can_see_closest_target=true}
assert(not EnemyUtility.check_alert(enemy,10))
test.module.tick(true)
assert(EnemyUtility.check_alert(enemy,10))
assert(not test.manager:is_position_inside_frustum(enemy.position))
enemy.distance=20;assert(not EnemyUtility.check_alert(enemy,10))
enemy.distance=5;enemy.can_see_closest_target=false;assert(not EnemyUtility.check_alert(enemy,10))
enemy.fail=true;assert(not pcall(EnemyUtility.check_alert,enemy,10))
assert(not test.manager:is_position_inside_frustum(enemy.position))
test.module.tick(false)
assert(EnemyUtility.check_alert==test.alert and test.encounter:get_spawner_peer()=="client")
print("PASS alarm screen gate alone is bypassed, distance and LOS remain, errors and cancellation restore scope")

test=fixture();test.enemies[50]={};test.owners[50]="client"
assert(test.module.tick(true).detail=="native_same_screen;alarm_pending:1")
assert(test.encounter:get_spawner_peer()=="host" and #test.migrations==1)
assert(test.encounter.enemies==0)
test.encounter:add_migrated_enemy(88);assert(test.encounter.enemies==1)
test.module.tick(true);assert(#test.migrations==1)
test.advance(1);test.module.tick(true);assert(#test.migrations==1)
test.owners[50]="host";test.advance(1)
assert(test.module.tick(true).detail=="native_same_screen")
test.enemies[51]={};test.owners[51]="client";test.health[51]=true;test.advance(1)
test.module.tick(true);assert(#test.migrations==1)
test.game.is_server=false;test.module.tick(true)
assert(test.encounter:get_spawner_peer()=="client" and EnemyUtility.check_alert==test.alert)
print("PASS new AI remains on host, living existing AI migrates once pending readback, host loss restores policy")

test=fixture();test.enemies[50]={};test.owners[50]="client"
test.module.tick(true)
for attempt=1,2 do test.advance(5);test.module.tick(true) end
assert(#test.migrations==3)
test.advance(5)
local failure=test.module.tick(true)
assert(failure.applied==0 and failure.detail:find("enemy_authority_timeout",1,true))
assert(EnemyUtility.check_alert==test.alert and next(test.host.resources)==nil)
print("PASS stalled ownership migration stops after bounded retries and releases wrappers")

test=fixture()
test.patrol.patrols={{position=vector(0,0,0),spawned=true},{position=vector(100,0,0)}}
test.patrol.spawned=1
for _,position in pairs(test.units) do position.x=100 end
test.module.tick(true)
test.patrol:update_host(1)
assert(not test.patrol.patrols[1].visible,"empty public camera must not retain distant patrols")
assert(test.patrol.patrols[2].spawned and test.patrol.patrols[2].visible)
test.patrol.patrols[3]={position=vector(1,0,0)}
test.patrol:update_host(1)
assert(not test.patrol.patrols[3].spawned,"empty public camera must not activate new patrols")
assert(test.manager:is_position_inside_frustum(vector(0,0,0),-0.1,-0.1,-0.1,-0.1))
test.units[1].x=0
test.patrol:update_host(1)
assert(test.patrol.patrols[1].visible and test.patrol.patrols[3].spawned)
test.module.tick(false)
print("PASS empty public camera stops patrol activation and retention, occupied camera and unrelated callers remain native")

local spawn_evidence=assert(arg[3],"spawn bytecode evidence directory required")
local spawn_environment=setmetatable({class=function() return {} end,require=function() return {} end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
Vector3Aux.box=function(target,position)
    target.x=position.x;target.y=position.y;target.z=position.z;return target
end
setfenv(assert(loadfile(spawn_evidence.."/chunk_0012e87d/chunk.ljbc")),spawn_environment)()
local spawn_points=spawn_environment.SpawnManager.get_spawn_points
test=fixture()
test.units[2].x=100
test.spawn.get_spawn_points=spawn_points
local request={force_outside_screen=true}
test.spawn:get_spawn_points(vector(100,0,0),1.25,request)
assert(#request.queued_raycasts>0)
for _,raycast in ipairs(request.queued_raycasts) do
    assert(math.abs(raycast.arg_a.x-100)<=5 and math.abs(raycast.arg_a.y)<=5)
end
test.module.tick(true)
request={force_outside_screen=true}
test.spawn:get_spawn_points(vector(100,0,0),1.25,request)
assert(#request.queued_raycasts>0,"remote native spawn points must move outside view instead of all being discarded")
for _,raycast in ipairs(request.queued_raycasts) do
    assert(math.abs(raycast.arg_a.x-100)>10 or math.abs(raycast.arg_a.y)>8)
    assert(math.abs(raycast.arg_a.x-100)<12 and math.abs(raycast.arg_a.y)<10)
    assert(raycast.arg_a.z==100 and raycast.arg_b.z==-1 and raycast.arg_c==500)
end
local public_request={force_outside_screen=true}
test.spawn:get_spawn_points(vector(0,0,0),1.25,public_request)
assert(#public_request.queued_raycasts>0,"public region must retain candidates while remote regions exist")
local unchanged={force_outside_screen=false}
test.spawn:get_spawn_points(vector(100,0,0),1.25,unchanged)
for _,raycast in ipairs(unchanged.queued_raycasts) do
    assert(math.abs(raycast.arg_a.x-100)<=5 and math.abs(raycast.arg_a.y)<=5)
end
local original_update=test.patrol.update_host
local original_outside=environment.CameraManager.get_closest_position_outside_frustum
assert(test.manager:get_closest_position_outside_frustum(vector(100,0,0)).x==100)
test.module.tick(false)
assert(test.manager.get_closest_position_outside_frustum==original_outside)
print("PASS original SpawnManager get_spawn_points retains off-screen candidates beside the remote player")

local patrol_environment=setmetatable({class=function() return {} end,require=function() end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
Vector3.normalize=function(value)
    local length=math.sqrt(value.x^2+value.y^2+value.z^2)
    return length>0 and value/length or vector(0,0,0)
end
Vector3.length_squared=function(value) return value.x^2+value.y^2+value.z^2 end
IS_DEV=false
array={remove_all_where=function(items,key,value)
    for index=#items,1,-1 do if items[index][key]==value then table.remove(items,index) end end
end}
setfenv(assert(loadfile(assert(arg[4],"patrol bytecode evidence directory required").."/chunk_000cb9db/chunk.ljbc")),patrol_environment)()
test=fixture()
test.units[2].x=100
test.spawn.get_spawn_points=spawn_points
test.patrol.update_host=patrol_environment.PatrolManager.update_host
test.patrol.update_positions_network_timer=0
test.patrol.update_positions_network_time=100
test.patrol.patrol_spawn_timer=100
test.patrol.full_update_index=0
local queued_points={}
function test.patrol:spawn_patrol(entry)
    local request={force_outside_screen=true}
    test.spawn:get_spawn_points(Vector3Aux.unbox(entry.position),1.25,request)
    queued_points[#queued_points+1]=request.queued_raycasts
    entry.spawned=true
end
for _,center in ipairs({0,100}) do
    test.patrol.patrols[#test.patrol.patrols+1]={position=vector(center-5,0,0),direction=vector(1,0,0),
        target_position=vector(center+20,0,0),patrol_settings={speed_wander=1,speed_chase=1}}
end
test.module.tick(true)
test.patrol:update_host(0.1)
test.patrol:update_host(0.1)
assert(#queued_points==2)
for index,points in ipairs(queued_points) do
    local center=(index-1)*100
    assert(#points>0,"both native patrol routes must retain spawn candidates")
    for _,raycast in ipairs(points) do
        assert(math.abs(raycast.arg_a.x-center)<16 and math.abs(raycast.arg_a.y)<14)
    end
    local entry=test.patrol.patrols[index]
    assert(entry.direction.x==1 and entry.direction.y==0 and entry.target_position.x==center+20)
end
test.module.tick(false)
print("PASS native PatrolManager movement and SpawnManager sampling keep both regions, directions and targets")

test=fixture()
test.units[2].x=100
test.units[50]={x=100,y=4,z=0}
local firing_events={}
local rpc_events=0
Unit.node=function() return 0 end
Unit.world_rotation=function() return {} end
Quaternion.forward=function() return vector(0,1,0) end
QuaternionAux={}
math.normalized_angle_from_direction=function() return 0 end
EnemyUtility.rotate_turret_towards=function() end
EntityStateMachine={animation_event=function(_,event) firing_events[#firing_events+1]=event end}
Color=function() return {} end
local ifv_environment=setmetatable({},{__index=_G})
setfenv(assert(loadfile(assert(arg[5],"IFV bytecode evidence directory required").."/chunk_004485b5/chunk.ljbc")),ifv_environment)()
local ifv_names={"CyborgIfvStateWander","CyborgIfvStateAttack","CyborgIfvStateBack",
    "CyborgIfvStateRunOver","CyborgIfvStateSpawnGroup","CyborgIfvStateConstitution"}
local native_updates={}
for _,name in ipairs(ifv_names) do
    _G[name]=ifv_environment[name]
    native_updates[name]=_G[name].update
end
local component={state={target_unit=2,health_state={is_dead=false},turret_state="aim",
    can_see_target=true,distance_to_target=4,turret_rotation=0},
    settings={enemy_info={attack_range_shoot_min=1,attack_range_shoot_max=10,
        turret_turn_cooldown=1,shoot_cooldown_time=8,shoot_events={{time=0},{time=0.1}}}}}
local context={debug_drawer={line=function() end},trigger_rpc_event=function() rpc_events=rpc_events+1 end}
local function update_ifv() CyborgIfvStateConstitution.update(50,component,0.2,context,false) end
update_ifv()
assert(component.state.turret_state=="aim" and #firing_events==0)
assert(test.module.tick(true).applied==4)
for _,name in ipairs(ifv_names) do assert(_G[name].update~=native_updates[name]) end
update_ifv()
assert(component.state.turret_state=="shoot" and firing_events[1]=="fire_charge" and rpc_events==1)
update_ifv()
assert(firing_events[2]=="fire_forward")
assert(not test.manager:is_position_inside_frustum(vector(100,4,0)))
component.state.turret_state="aim";component.state.can_see_target=false
update_ifv();assert(#firing_events==2)
component.state.can_see_target=true;component.state.distance_to_target=11
update_ifv();assert(#firing_events==2)
component.state.distance_to_target=0.5
update_ifv();assert(#firing_events==2)
component.state.distance_to_target=4;component.state.turret_rotation=0.25
update_ifv();assert(#firing_events==2)
component.state.turret_rotation=0;test.units[50].x=500
update_ifv();assert(#firing_events==2)
test.units[50].x=0;test.units[50].y=0
update_ifv();assert(firing_events[3]=="fire_charge")
component.state.turret_state="aim";test.units[50].x=100
Unit.node=function() error("ifv_test_failure") end
assert(not pcall(update_ifv))
assert(not test.manager:is_position_inside_frustum(vector(100,4,0)))
test.module.tick(false)
for _,name in ipairs(ifv_names) do assert(_G[name].update==native_updates[name]);_G[name]=nil end
assert(next(test.host.resources)==nil)
print("PASS native IFV turret fires in remote view, preserves LOS/range/alignment, public and unrelated views, and restores all six states")
