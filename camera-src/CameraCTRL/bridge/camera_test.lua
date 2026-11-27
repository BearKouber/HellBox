local factory=assert(loadfile(arg[1]))()
local focus_factory=assert(loadfile((arg[1]:match('^(.*[/\\])') or '')..'camera_focus.lua'))()
local evidence=assert(arg[2])
local target_environment={class=function() return {} end}
setfenv(assert(loadfile(evidence.."/chunk_00273bc0/chunk.ljbc")),target_environment)()
local target_command=target_environment.CameraTargetComponent.command_master
local vector_meta={}
local function vector(x,y,z) return setmetatable({x=x,y=y,z=z},vector_meta) end
vector_meta.__add=function(left,right) return vector(left.x+right.x,left.y+right.y,left.z+right.z) end
vector_meta.__mul=function(left,right) return vector(left.x*right,left.y*right,left.z*right) end
Vector3=setmetatable({lerp=function(left,right,weight) return vector(left.x+(right.x-left.x)*weight,left.y+(right.y-left.y)*weight,left.z+(right.z-left.z)*weight) end},{__call=function(_,...) return vector(...) end})
Quaternion=setmetatable({multiply=function() return {} end,forward=function() return vector(0,1,0) end,rotate=function(_,value) return value end},{__call=function() return {} end})
local function fixture(with_vehicle)
    local units={[42]=true,[99]=true,[100]=true,[88]=true}
    local now=1
    Application={time_since_launch=function() return now end}
    local position=vector(0,0,0)
    local positions,keys={},{}
    Keyboard={button_index=function(key) return key end,button=function(key) return keys[key] and 1 or 0 end}
    local owner=true
    local draws,updates,destroyed,network={},{},0,{}
    local camera_positions={}
    local resources,flow_events,particle_units,particle_transforms={},{},{},{}
    local inside=true
    local projection
    local fail_ui=false
    local next_unit=100
    Unit={alive=function(unit) return units[unit] or false end,world_position=function(unit) assert(units[unit],'stale unit');return positions[unit] or position end,world_rotation=function() return {} end,
        flow_event=function(unit,event) flow_events[#flow_events+1]={unit=unit,event=event} end}
    World={spawn_unit=function(_,resource) next_unit=next_unit+1;units[next_unit]=true;resources[next_unit]=resource;return next_unit end,
        destroy_unit=function(_,unit) units[unit]=nil;destroyed=destroyed+1 end,update_unit=function() end,
        are_particles_playing=function(_,particle) return particle_units[particle]~=nil end,
        link_particles=function(_,particle,unit,node,transform) particle_units[particle]=unit;particle_transforms[particle]=transform.scale end}
    Matrix4x4={identity=function() return {scale=1} end,set_element=function(transform,_,_,value) transform.scale=value end}
    Camera={set_local_position=function(camera,unit,value) camera_positions[camera]=vector(value.x,value.y,value.z) end,
        set_local_rotation=function() end,set_vertical_fov=function() end}
    local viewport={camera_unit=100,get_world_proxy=function() return {get_world=function() return "world" end} end,
        get_camera=function(self) return self.camera_unit end,
        render=function(self) draws[#draws+1]=self.camera_unit end,
        window=function() return 1000,800 end,
        world_to_screen=function(self) return self.camera_unit end,world_to_viewport=function(self) return projection or self.camera_unit end,
        screen_to_world=function(self) return self.camera_unit end}
    CameraManager={viewport=viewport,targets={[42]={bias=1},[99]={bias=1}},state="follow",min_follow_distance=17,
        follow_distance=25,follow_spin=0,follow_angle=1,fov=1,follow_offset={x=0,y=0,z=0},
        camera=function(self) return self.viewport:get_camera() end,camera_unit=function(self) return self.viewport.camera_unit end,
        get_viewport=function(self) return self.viewport end,world_to_screen=function(self) return self.viewport:world_to_screen() end,
        world_to_viewport=function(self) return self.viewport:world_to_viewport() end,screen_to_world=function(self) return self.viewport:screen_to_world() end,
        is_position_inside_frustum=function(self) assert(self.viewport.camera_unit==100);return inside end,
        camera_particles={},generated_level={environment_name="forest",shading_environment="day"},
        add_camera_particle=function(self,key,path,aspect)
            if not self.camera_particles[key] then
                self.camera_particles[key]=path
                local transform=Matrix4x4.identity()
                if aspect then Matrix4x4.set_element(transform,1,1,(1000/800)/(16/9)) end
                World.link_particles("world",path,self.viewport.camera_unit,0,transform,"destroy")
            end
        end,
        update=function(self)
            updates[#updates+1]={own=self.targets[42]~=nil,remote=self.targets[99]~=nil,camera=self:camera()}
        end}
    InputComponent={update_masters=function() assert(CameraManager:camera()~=100);assert(CameraManager.follow_distance==17) end}
    Hud={draw_plugins=function()
            if fail_ui then error("fixture_ui_failure") end
            return viewport:world_to_viewport(),nil,"tail"
        end,
        pre_update_and_draw_hud=function(_,dt,pads,view) return view:world_to_viewport() end}
    TextChat={update=function() return viewport:world_to_viewport() end}
    CharacterComponent={update_masters=function(_,position) return viewport:world_to_viewport(position) end}
    CameraTargetComponent={command_master=target_command}
    MoverComponent={command_master=function(_,unit,ctx,name,value) assert(name=="keep_inside_screen");ctx.state.keep_inside_screen=value end}
    local target={state={active=true,look_ahead=0,is_reverse=false},network_fields={{name="active"},{name="look_ahead"},{name="is_reverse"}},go_id=42}
    local mover={state={keep_inside_screen=true}}
    local character={state={}}
    local remote={state={active=true},go_id=99}
    local groups={camera_target={master={[42]=target,[99]=remote},slave={[42]={state={active=true}}}},mover={master={[42]=mover}},character={master={[42]=character}}}
    local replicator={network_session={}}
    function replicator:write_fields(context) network[context.go_id]=context.state.active end
    GameSession={game_object_field=function(_,id) return network[id] end}
    local game={players={{player_go={exists=function() return true end,owned=function() return owner end,get=function() return 42 end}}},
        entity_manager={components={camera_target={replicator=replicator},mover={},character={players_in_no_strat_zone={}}},component_name_to_contexts=groups}}
    Boot={state_machine={current_state_name="game",state=game}}
    EntityAux={has_component_master=function(unit,name) return groups[name] and groups[name].master[unit] end}
    local host={resources={}}
    function host:claim(id,key) if self.resources[key] then return false end self.resources[key]=id;return true end
    function host:release(id,key) if self.resources[key]==id then self.resources[key]=nil end end
    local modes,vehicles
    if with_vehicle then
        local dir=arg[1]:match('^(.*[/\\])') or ''
        modes=assert(loadfile(dir..'peer_modes.lua'))()()
        vehicles=assert(loadfile(dir..'vehicles.lua'))()(modes)
    end
    local camera=factory(host,modes,vehicles,focus_factory)
    local manager=CameraManager
    return {camera=camera,game=game,target=target,mover=mover,character=character,remote=remote,viewport=viewport,manager=manager,groups=groups,
        inside=function(value) inside=value end,owner=function(value) owner=value end,
        time=function(value) now=value end,positions=positions,units=units,keys=keys,
        position=function(value) position=value end,camera_positions=camera_positions,resources=resources,flow_events=flow_events,
        particle_units=particle_units,particle_transforms=particle_transforms,
        projection=function(value) projection=value end,fail_ui=function(value) fail_ui=value end,
        destroy_count=function() return destroyed end,updates=updates,draws=draws,host=host,
        frame=function(mask)
            local first=camera.tick(mask,0.016)
            groups.camera_target.slave[42].state.active=target.state.active
            if not target.state.active then manager.targets[42]=nil else manager.targets[42]={bias=1} end
            manager:update(0.016)
            viewport:render()
            return camera.tick(mask,0.016),first
        end}
end
local test=fixture()
local result=test.frame(1)
assert(result.applied==1,result.detail)
assert(not test.target.state.active and test.remote.state.active and test.mover.state.keep_inside_screen)
assert(test.updates[1].remote and not test.updates[1].own and test.updates[1].camera==100)
assert(test.draws[1]~=100 and test.manager:camera()==test.draws[1])
    assert(test.viewport:world_to_screen()==100)
    assert(test.viewport:world_to_viewport()==100)
    assert(test.viewport:screen_to_world()==100)
    assert(Hud.draw_plugins({})==test.manager:camera())
    assert(TextChat.update({})==test.manager:camera())
assert(test.manager:is_position_inside_frustum(vector(0,0,0)))
InputComponent.update_masters({})
assert(test.manager.follow_distance==25)
assert(test.frame(3).applied==3 and not test.mover.state.keep_inside_screen)
test.inside(false)
assert(test.frame(0).detail=="return_to_team")
assert(not test.target.state.active and not test.mover.state.keep_inside_screen)
test.inside(true)
assert(test.frame(0).owned==0)
assert(test.target.state.active and test.mover.state.keep_inside_screen and test.destroy_count()==1)
assert(test.manager:camera()==100 and next(test.host.resources)==nil)
print("PASS two cameras, personal projection, team boundary, far cancellation and restoration")
test=fixture();assert(test.frame(1).applied==1)
CameraTargetComponent.command_master({},42,test.target,"deactivate")
CameraTargetComponent.command_master({},99,test.remote,"activate")
assert(test.frame(0).owned==0 and not test.target.state.active and test.remote.state.active)
print("PASS latest native activation intent and remote command pass-through")
test=fixture();test.frame(3);test.character.state.current_seat_unit=99
assert(test.frame(3).owned==0 and test.target.state.active and test.mover.state.keep_inside_screen)
print("PASS vehicle suspension without disabling shared vehicle target")
test=fixture();test.frame(3);local old=test.target.state
Boot.state_machine.state={players={}}
assert(test.camera.tick(3,0).owned~=3)
assert(old.active==false and test.destroy_count()==0 and next(test.host.resources)==nil)
print("PASS world change drops old handles and restores wrappers without touching old world")
test=fixture();test.host.resources["CameraManager.world_to_screen"]="captain"
result=test.frame(1)
assert(result.applied==0 and test.target.state.active and test.mover.state.keep_inside_screen,result.detail)
test.camera.tick(0,0)
assert(test.host.resources["CameraManager.world_to_screen"]=="captain")
print("PASS shared hook conflict fails without changing avatar")
test=fixture();test.manager.targets[99]=nil;assert(test.frame(1).applied==1)
assert(test.updates[1].own and not test.updates[1].remote)
assert(test.manager.targets[42]==nil)
print("PASS zero remaining targets use local-only reference fallback")

test=fixture();test.target.state.active=false
assert(test.frame(1).owned==0 and test.destroy_count()==0)
assert(test.manager:camera()==100 and next(test.host.resources)==nil)
print("PASS inactive native camera target is not overridden")

test=fixture();test.frame(3);test.inside(false);test.character.state.is_dead=true
assert(test.manager:camera()==100)
assert(test.frame(3).detail=='spectator_wait' and not test.target.state.active)
assert(test.mover.state.keep_inside_screen and test.destroy_count()==0)
assert(test.camera.contains(test.game,vector(0,0,0))==nil)
test.time(3.1)
assert(test.frame(3).detail=='spectator_no_teammate')
test.character.state.is_dead=false
assert(test.frame(3).detail=='spectator_no_teammate')
CameraTargetComponent.command_master({},42,test.target,"activate")
assert(test.frame(3).applied==3)
assert(test.frame(0).detail=="return_to_team")
test.inside(true);assert(test.frame(0).owned==0)
print("PASS death hold, no teammates, gameplay restoration, native respawn and spectator exclusion from escort coverage")

test=fixture();test.frame(3);test.inside(false);test.manager.state="cinematic"
assert(test.manager:camera()==100)
assert(test.frame(3).owned==0 and test.target.state.active and test.mover.state.keep_inside_screen)
assert(next(test.host.resources)==nil)
test.manager.state="follow"
assert(test.frame(1).applied==1)
test.inside(true);assert(test.frame(0).owned==0)
print("PASS cutscene outside team frame suspends and returns native view immediately")

test=fixture();test.frame(3);test.inside(false)
CameraTargetComponent.command_master({},42,test.target,"deactivate")
assert(test.frame(3).owned==0 and not test.target.state.active)
assert(test.mover.state.keep_inside_screen and next(test.host.resources)==nil)
print("PASS native deactivation bypasses pending return without undoing native intent")

test=fixture();test.manager.world_to_screen=nil
result=test.frame(1)
assert(result.applied==0 and result.owned==0 and result.detail:find("missing_method",1,true))
assert(next(test.host.resources)==nil and test.target.state.active and test.destroy_count()==1)
print("PASS missing method releases all claims and local camera")

test=fixture();test.frame(3)
Camera.set_local_position=function() error("fixture_render_failure") end
result=test.frame(3)
assert(result.applied==0 and result.owned==0 and result.detail:find("fixture_render_failure",1,true))
assert(test.target.state.active and test.mover.state.keep_inside_screen and next(test.host.resources)==nil)
assert(test.frame(3).owned==0 and test.destroy_count()==1)
assert(test.frame(0).detail=="off")
Camera.set_local_position=function() end
assert(test.frame(3).applied==3)
assert(test.frame(0).owned==0)
print("PASS rendering failure restores within the team frame")

test=fixture();test.frame(3)
local replicator=test.game.entity_manager.components.camera_target.replicator
local write_fields=replicator.write_fields
replicator.write_fields=function() error("fixture_replication_failure") end
result=test.frame(0)
assert(result.applied==0 and result.owned==3 and result.detail:find("fixture_replication_failure",1,true))
assert(not test.mover.state.keep_inside_screen and next(test.host.resources)~=nil)
replicator.write_fields=write_fields
result=test.frame(0)
assert(result.owned==0 and test.target.state.active and test.mover.state.keep_inside_screen)
assert(next(test.host.resources)==nil)
print("PASS failed restoration retains ownership and retries instead of falsely reporting restored")

test=fixture();test.frame(3);test.inside(false)
Camera.set_local_position=function() error("fixture_remote_render_failure") end
result=test.frame(3)
assert(result.applied==0 and result.owned==3 and result.detail:find("camera_error_pending_return:",1,true))
assert(not test.target.state.active and not test.mover.state.keep_inside_screen)
test.inside(true)
result=test.frame(3)
assert(result.applied==0 and result.owned==0 and result.detail:find("camera_error:",1,true))
assert(test.target.state.active and test.mover.state.keep_inside_screen and next(test.host.resources)==nil)
print("PASS rendering failure outside team frame reports pending ownership without pulling teammates")

test=fixture()
-- HellBox 2026-11-19: personal camera follows like the vanilla single-player camera
-- (goal = position + forward * look_ahead + (-1,-1,0), chased at follow_position_interp per second).
test.target.state.look_ahead=5
assert(test.frame(1).applied==1)
local display=test.manager:camera()
local function center()
    local actual=assert(test.camera_positions[display])
    return vector(actual.x,actual.y+17,actual.z)
end
local c=center()
assert(c.x==-1 and c.y==4 and c.z==0,"vanilla look-ahead and offset on the first frame")
test.position(vector(10,0,0))
test.time(2)
assert(test.camera.tick(1,0.016).applied==1)
c=center()
assert(c.x>-1 and c.x<9 and c.y==4,"chases the player instead of locking onto it")
local chased=c.x
test.viewport:render()
assert(center().x==chased,"repeated renders in one frame cannot accelerate the chase")
test.time(60);test.viewport:render()
c=center()
assert(math.abs(c.x-9)<1e-6 and math.abs(c.y-4)<1e-6,"settles on the goal")
test.target.state.is_reverse=true
test.time(120);test.viewport:render()
assert(math.abs(center().y+6)<1e-6,"reverse looks backwards")
test.target.state.look_ahead=0
test.time(180);test.viewport:render()
assert(math.abs(center().y+1)<1e-6,"no look-ahead: only the vanilla offset")
assert(test.remote.state.active)
assert(test.frame(0).owned==0)
print("PASS vanilla chase, look-ahead, reverse and single-step smoothing across repeated render calls")

test=fixture();test.frame(1)
local projected,empty,tail=Hud.draw_plugins({})
assert(projected==test.manager:camera() and empty==nil and tail=="tail")
test.fail_ui(true)
assert(not pcall(Hud.draw_plugins,{}))
assert(test.viewport:world_to_viewport()==100)
assert(test.manager:is_position_inside_frustum(vector(0,0,0)))
test.fail_ui(false)
assert(TextChat.update({})==test.manager:camera())
test.projection(vector(650,10,250))
projected=Hud.pre_update_and_draw_hud({},0,{},test.viewport)
assert(projected.x==650 and projected.z==250)
for _,point in ipairs({vector(-100,-10,900),vector(1100,-10,900),vector(-100,-10,-100),vector(1100,-10,-100)}) do
    test.projection(point)
    projected=Hud.pre_update_and_draw_hud({},0,{},test.viewport)
    assert((projected.x-500)*(point.x-500)<0 and (projected.z-400)*(point.z-400)<0)
    assert(projected.x<0 or projected.x>1000 or projected.z<0 or projected.z>800)
end
test.projection(vector(500,0,400))
projected=Hud.pre_update_and_draw_hud({},0,{},test.viewport)
assert(projected.x==500 and projected.z<0)
test.projection(nil)
assert(test.frame(0).owned==0)
assert(Hud.draw_plugins({})==100 and TextChat.update({})==100)
assert(Hud.pre_update_and_draw_hud({},0,{},test.viewport)==100)
assert(next(test.host.resources)==nil)
print("PASS UI-only cached projection, error restoration, rear markers in four quadrants and cleanup")

test=fixture()
local character_controller=test.game.entity_manager.components.character
character_controller.players_in_no_strat_zone[42]=true
test.frame(3)
display=test.manager:camera()
assert(test.resources[display]=="gameobjects/camera")
assert(test.flow_events[1].unit==display and test.flow_events[1].event=="on_enter_no_strat_zone")
local events=#test.flow_events
test.frame(3)
assert(#test.flow_events==events)
character_controller.players_in_no_strat_zone[42]=nil
character_controller.players_in_no_strat_zone[99]=true
test.frame(3)
assert(test.flow_events[#test.flow_events].event=="on_exit_no_strat_zone")
assert(test.frame(0).owned==0)
assert(test.flow_events[#test.flow_events].unit==100 and test.flow_events[#test.flow_events].event=="on_enter_no_strat_zone")
print("PASS native game camera resource, initial jammer effect, own-state transitions and team effect restoration")

test=fixture();test.frame(3)
assert(CharacterComponent.update_masters({},vector(0,0,0))==test.manager:camera())
assert(CharacterComponent.update_masters({},vector(100,0,0))==100)
assert(test.viewport:world_to_viewport(vector(0,0,0))==100)
test.inside(false)
assert(not test.manager:is_position_inside_frustum(vector(0,0,0)))
assert(test.frame(0).detail=="return_to_team")
test.inside(true);test.frame(0)
assert(CharacterComponent.update_masters({},vector(0,0,0))==100)
print("PASS own recovery projection only; remote character, movement and return boundaries stay native")

test=fixture()
EnvironmentAreaSettings={forest={day={mist={camera_particle="weather"}}}}
test.manager:add_camera_particle("mist",201,false)
assert(test.particle_units[201]==100)
test.frame(1);display=test.manager:camera()
assert(test.particle_units[201]==display and test.particle_transforms[201]==1)
test.manager:add_camera_particle("hurt",202,true)
assert(test.particle_units[202]==display and test.particle_transforms[202]==(1000/800)/(16/9))
test.manager.camera_particles.hurt=nil
test.frame(0)
assert(test.particle_units[201]==100 and test.particle_units[202]==100)
test.manager:add_camera_particle("new",203,false)
assert(test.particle_units[203]==100 and next(test.host.resources)==nil)
print("PASS existing environment particles, new screen effects, aspect ratio and fading-particle restoration")
local seated=fixture(true)
local groups=seated.groups
local vehicle_target={state={active=true,look_ahead=0,is_reverse=false},go_id=88}
local vehicle_mover={state={keep_inside_screen=true}}
groups.camera_target.master[88]=vehicle_target
groups.mover.master[88]=vehicle_mover
groups.vehicle={master={[88]={}}}
groups.seat={master={[88]={state={seated_units={[1]=42}}}}}
seated.frame(3)
seated.character.state.current_seat_unit=88
CameraTargetComponent.command_master({},42,seated.target,'deactivate')
local result=seated.frame(3)
assert(result.detail=='vehicle_unlocked',result.detail)
assert(seated.manager:camera()~=100 and not vehicle_target.state.active and not vehicle_mover.state.keep_inside_screen)
assert(seated.mover.state.keep_inside_screen and not seated.target.state.active)
assert(seated.target.state.is_reverse and seated.target.state.look_ahead>=8)
seated.inside(false)
assert(seated.frame(0).detail=='vehicle_return_to_team')
assert(seated.manager:camera()~=100 and not vehicle_target.state.active and not vehicle_mover.state.keep_inside_screen)
seated.inside(true)
assert(seated.frame(0).owned==0)
assert(vehicle_target.state.active and vehicle_mover.state.keep_inside_screen)
assert(not seated.target.state.active and not seated.target.state.is_reverse and seated.target.state.look_ahead==0)
assert(next(seated.host.resources)==nil)
print('PASS integrated seated view, separate avatar/vehicle movers, mode publication and pending cancellation')
result=seated.frame(3)
assert(result.detail=='vehicle_unlocked',result.detail)
seated.character.state.current_seat_unit=nil
groups.seat.master[88].state.seated_units[1]=nil
CameraTargetComponent.command_master({},42,seated.target,'activate')
assert(seated.frame(3).applied==3)
assert(not vehicle_target.state.active and vehicle_mover.state.keep_inside_screen and not seated.mover.state.keep_inside_screen)
seated.frame(0)
print('PASS enabling while seated and leaving vehicle restores separate records')

for _,ending in ipairs({'activate','timeout','death','disable'}) do
    local exiting=fixture(true)
    local contexts=exiting.groups
    contexts.camera_target.master[88]={state={active=true,look_ahead=0,is_reverse=false},go_id=88}
    contexts.mover.master[88]={state={keep_inside_screen=true}}
    contexts.vehicle={master={[88]={}}}
    contexts.seat={master={[88]={state={seated_units={[1]=42}}}}}
    exiting.character.state.current_seat_unit=88
    exiting.target.state.active=false
    assert(exiting.frame(3).applied==3)
    local display=exiting.manager:camera()
    exiting.character.state.current_seat_unit=nil
    contexts.seat.master[88].state.seated_units[1]=nil
    assert(exiting.frame(3).applied==3)
    assert(exiting.manager:camera()==display and exiting.destroy_count()==0)
    assert(exiting.draws[#exiting.draws]==display and not exiting.target.state.active and exiting.remote.state.active)
    assert(not contexts.camera_target.master[88].state.active)
    if ending=='activate' then
        CameraTargetComponent.command_master({},42,exiting.target,'activate')
        exiting.time(2)
        assert(exiting.frame(3).applied==3 and exiting.manager:camera()==display and exiting.destroy_count()==0)
        exiting.frame(0)
    else
        if ending=='timeout' then exiting.time(1.26)
        elseif ending=='death' then exiting.character.state.is_dead=true end
        if ending=='death' then
            assert(exiting.frame(3).detail=='spectator_wait')
            assert(exiting.manager:camera()==display)
        end
        assert(exiting.frame((ending=='disable' or ending=='death') and 0 or 3).owned==0)
        assert(exiting.manager:camera()==100 and exiting.destroy_count()==1)
    end
end
print('PASS delayed dismount activation retains private camera without flicker; timeout, death and disable clean up')

-- HellBox 2026-11-26：原版下车动作（seat_info 还在）播完才 activate；动作 1.2 秒也不能收掉自己的镜头（以前 0.25 秒就收，镜头拉到队友那边）
local function seated_fixture()
    local exiting=fixture(true)
    local contexts=exiting.groups
    contexts.camera_target.master[88]={state={active=true,look_ahead=0,is_reverse=false},go_id=88}
    contexts.mover.master[88]={state={keep_inside_screen=true}}
    contexts.vehicle={master={[88]={}}}
    contexts.seat={master={[88]={state={seated_units={[1]=42}}}}}
    exiting.character.state.current_seat_unit=88
    exiting.target.state.active=false
    assert(exiting.frame(3).applied==3)
    return exiting,contexts
end
do
    local exiting,contexts=seated_fixture()
    local display=exiting.manager:camera()
    exiting.character.state.current_seat_unit=nil
    exiting.character.state.seat_info={exit_time=1.2}
    contexts.seat.master[88].state.seated_units[1]=nil
    assert(exiting.frame(3).applied==3)
    for _,t in ipairs({1.2,1.5,2.0}) do
        exiting.time(t)
        assert(exiting.frame(3).applied==3,'exit animation at '..t)
        assert(exiting.manager:camera()==display and exiting.destroy_count()==0,'camera kept at '..t)
        assert(exiting.draws[#exiting.draws]==display and not exiting.target.state.active)
        assert(not exiting.mover.state.keep_inside_screen,'limit kept during exit')
    end
    exiting.character.state.seat_info=nil
    CameraTargetComponent.command_master({},42,exiting.target,'activate')
    assert(exiting.frame(3).applied==3 and exiting.manager:camera()==display and exiting.destroy_count()==0)
    print('PASS long dismount animation keeps private camera until native activation')
end
do
    -- 动作卡住（seat_info 一直不清）：最多 3 秒后照原来收掉
    local exiting,contexts=seated_fixture()
    exiting.character.state.current_seat_unit=nil
    exiting.character.state.seat_info={exit_time=9}
    contexts.seat.master[88].state.seated_units[1]=nil
    assert(exiting.frame(3).applied==3)
    for t=1.5,3.9,0.2 do exiting.time(t);assert(exiting.frame(3).applied==3,'held at '..t) end
    exiting.time(4.3)
    assert(exiting.frame(3).owned==0)
    assert(exiting.manager:camera()==100 and exiting.destroy_count()==1)
    print('PASS stuck dismount animation gives up after 3 seconds')
end

local coverage=fixture()
assert(coverage.camera.contains(coverage.game,vector(0,0,0))==nil)
coverage.frame(3)
for _,projected in ipairs({vector(500,1,400),vector(0,1,0),vector(1000,1,800)}) do
    coverage.projection(projected)
    assert(coverage.camera.contains(coverage.game,vector(0,0,0)))
end
for _,projected in ipairs({vector(-1,1,400),vector(1001,1,400),vector(500,1,-1),vector(500,1,801),vector(500,0,400),vector(500,-1,400)}) do
    coverage.projection(projected)
    assert(coverage.camera.contains(coverage.game,vector(0,0,0))==false)
end
coverage.manager.screen_resolution={width=900,height=700}
coverage.projection(vector(901,1,400))
assert(coverage.camera.contains(coverage.game,vector(0,0,0))==false)
coverage.projection(vector(900,1,700))
assert(coverage.camera.contains(coverage.game,vector(0,0,0)))
coverage.character.state.is_dead=true
assert(coverage.camera.contains(coverage.game,vector(0,0,0))==nil)
coverage.frame(0)
assert(coverage.camera.contains(coverage.game,vector(0,0,0))==nil)
print('PASS personal coverage uses visible projection bounds and rejects behind-camera, dead and inactive views')

-- HellBox 2026-11-19: while split screen publishes its mode to peers, the avatar's look_ahead/is_reverse fields
-- carry the signal (8..15, reverse). The personal camera must use the real values kept in mode_wire, not the carrier.
local carrier=fixture(true)
carrier.target.state.look_ahead=0
assert(carrier.frame(3).applied>=1)
local carrier_view=carrier.manager:camera()
print("CARRIER state",carrier.target.state.look_ahead,carrier.target.state.is_reverse)
for step=1,8 do
    carrier.time(1+step*0.5)
    carrier.frame(3)
    local at=carrier.camera_positions[carrier_view]
    assert(math.abs(at.x+1)<1e-6 and math.abs(at.y+17+1)<1e-6,
        "carrier look-ahead must not move the camera ("..tostring(at.x)..","..tostring(at.y)..")")
end
carrier.frame(0)
print('PASS peer-mode carrier in look_ahead/is_reverse never pushes the personal camera')

-- HellBox 2026-11-19: vanilla camera shake (CameraManager.update -> camera_shaker:update(dt, ground)) reaches the personal camera.
local shaky=fixture()
local shake_calls,shake_value=0,nil
local Shaker={}
Shaker.__index=Shaker
function Shaker:has_shakes() return shake_value~=nil end
function Shaker:update(dt,ground) shake_calls=shake_calls+1;return shake_value end
shaky.manager.camera_shaker=setmetatable({},Shaker)
local plain_update=shaky.manager.update
shaky.manager.update=function(self,dt)
    plain_update(self,dt)
    if self.camera_shaker:has_shakes() then self.camera_shaker:update(dt,vector(0,0,0)) end
end
assert(shaky.frame(1).applied==1)
local shaky_view=shaky.manager:camera()
local calm=shaky.camera_positions[shaky_view]
local calm_x,calm_z=calm.x,calm.z
shake_value=vector(0.3,0.2,0) -- shaker returns (sideways, up/down) in x,y; vanilla uses Vector3(x,0,y)
shaky.frame(1)
local shaken=shaky.camera_positions[shaky_view]
assert(math.abs(shaken.x-calm_x-0.3)<1e-6 and math.abs(shaken.z-calm_z-0.2)<1e-6,"shake offset applied to the personal camera")
assert(shake_calls==1,"shake advanced once per frame, not per render ("..shake_calls..")")
assert(rawget(shaky.manager.camera_shaker,"update")==nil,"shaker method restored after the team update")
shake_value=nil
shaky.frame(1)
local after=shaky.camera_positions[shaky_view]
assert(math.abs(after.x-calm_x)<1e-6 and math.abs(after.z-calm_z)<1e-6,"no shake once it has ended")
shaky.frame(0)
print('PASS vanilla camera shake reaches the personal camera once per frame and ends cleanly')

local smooth=fixture()
smooth.groups.vehicle={master={[88]={}}}
smooth.positions[42]=vector(0,0,0);smooth.positions[88]=vector(10,0,0)
smooth.frame(1)
local view=smooth.manager:camera()
smooth.character.state.current_seat_unit=88
smooth.frame(1)
assert(smooth.camera_positions[view].x==-1)
smooth.time(1.25);smooth.frame(1)
assert(smooth.camera_positions[view].x==4)
-- Multiple renders in one frame cannot accelerate interpolation.
smooth.viewport:render();assert(smooth.camera_positions[view].x==4)
smooth.positions[88]=vector(20,0,0)
smooth.time(1.5);smooth.frame(1)
assert(smooth.camera_positions[view].x==19)
smooth.positions[88]=vector(25,0,0);smooth.viewport:render()
assert(smooth.camera_positions[view].x==19)
smooth.time(2.5);smooth.frame(1)
local driving=smooth.camera_positions[view].x
assert(driving>19 and driving<24,"after boarding the vehicle is chased at the vanilla rate")
smooth.frame(0)
print('PASS boarding uses 0.5 second wall-clock smoothstep, then chases the moving vehicle like vanilla')

local watching=fixture()
local function peer(unit)
    return {player_go={exists=function() return true end,owned=function() return false end,get=function() return unit end}}
end
watching.units[98]=true
watching.game.players[2]=peer(99);watching.game.players[3]=peer(98)
watching.positions[99]=vector(100,0,0);watching.positions[98]=vector(200,0,0)
watching.frame(3);view=watching.manager:camera()
-- Slave health can announce death before character state, and the corpse may disappear entirely.
watching.groups.health={slave={[42]={state={is_dead=true}},[99]={state={is_dead=false}},[98]={state={is_dead=false}}}}
assert(watching.frame(3).detail=='spectator_wait')
watching.units[42]=nil
watching.groups.character.master[42]=nil;watching.groups.mover.master[42]=nil
watching.time(2.99);assert(watching.frame(3).detail=='spectator_wait')
assert(watching.camera_positions[view].x==-1) -- HellBox: vanilla follow offset (-1,-1)
watching.time(3);assert(watching.frame(3).detail=='spectator_follow')
assert(watching.camera_positions[view].x==100 and watching.remote.state.active)
assert(not watching.updates[#watching.updates].own and watching.updates[#watching.updates].camera==100)
watching.keys.d=true;watching.frame(3);assert(watching.camera_positions[view].x==200)
watching.frame(3);assert(watching.camera_positions[view].x==200)
watching.keys.d=false;watching.frame(3)
watching.keys.w=true;watching.frame(3);assert(watching.camera_positions[view].x==100)
watching.keys.w=false;watching.frame(3)
watching.game.text_chat={active=true};watching.keys.s=true;watching.frame(3)
assert(watching.camera_positions[view].x==100)
watching.game.text_chat.active=false;watching.frame(3);assert(watching.camera_positions[view].x==100)
watching.keys.s=false;watching.frame(3)
watching.keys.a=true;watching.frame(3);assert(watching.camera_positions[view].x==200)
watching.game.players[3]=nil;watching.frame(3);assert(watching.camera_positions[view].x==100)
watching.groups.health.slave[99].state.is_dead=true
assert(watching.frame(3).detail=='spectator_no_teammate')
assert(watching.camera_positions[view].x==100)
watching.frame(0)
assert(watching.manager:camera()==100 and next(watching.host.resources)==nil and watching.destroy_count()==1)
print('PASS destroyed corpse, slave death state, unmodified peers, key edges, chat suppression, disconnected/dead targets and cancellation')

for _,ending in ipairs({'world','owner','cinematic','respawn'}) do
    local dying=fixture();dying.frame(3);dying.character.state.is_dead=true;dying.frame(3)
    dying.units[42]=nil
    if ending=='world' then Boot.state_machine.state={players={}}
    elseif ending=='owner' then dying.owner(false)
    elseif ending=='cinematic' then dying.manager.state='cinematic'
    else
        dying.units[88]=true
        dying.game.players[1].player_go.get=function() return 88 end
        dying.groups.character.master[88]={state={}}
        dying.groups.camera_target.master[88]={state={active=true},network_fields={{name='active'}},go_id=88}
        dying.groups.camera_target.slave[88]={state={active=false}}
        dying.groups.mover.master[88]={state={keep_inside_screen=true}}
    end
    result=dying.camera.tick(3,0)
    if ending=='respawn' then
        assert(result.applied==3,result.detail)
        assert(dying.destroy_count()==1 and dying.manager:camera()~=100)
        assert(dying.camera.tick(0,0).owned==0)
    else assert(result.owned==0,result.detail) end
    assert(next(dying.host.resources)==nil)
end
print('PASS spectator world/ownership/cutscene cleanup and new-avatar rebinding without old unit access')

local joining=fixture(true);assert(joining.frame(3).applied==3)
local display=joining.manager:camera()
joining.game.players[2]=peer(99)
CameraTargetComponent.command_master({},99,joining.remote,'activate')
assert(joining.frame(3).applied==3 and joining.remote.state.active)
joining.owner(false)
assert(joining.camera.tick(3,0).applied==0)
assert(joining.destroy_count()==0 and not joining.target.state.active)
joining.owner(true)
assert(joining.frame(3).applied==3 and joining.manager:camera()==display)
joining.frame(0)
assert(joining.target.state.active and joining.mover.state.keep_inside_screen)
assert(joining.target.state.look_ahead==0 and joining.target.state.is_reverse==false)
print('PASS guest joining and temporary local ownership loss recover without losing native baseline or mode carrier')

for _,replacement in ipairs({'missing','state','context'}) do
    local rebound=fixture(true);rebound.frame(3)
    local old=rebound.mover
    if replacement=='missing' then
        rebound.groups.mover.master[42]=nil
        assert(rebound.camera.tick(3,0).detail=='waiting_own_master')
        rebound.groups.mover.master[42]=old
    elseif replacement=='state' then old.state={keep_inside_screen=true}
    else rebound.groups.mover.master[42]={state={keep_inside_screen=true}} end
    local current=rebound.groups.mover.master[42]
    assert(rebound.frame(3).applied==3 and not current.state.keep_inside_screen)
    rebound.frame(0)
    assert(current.state.keep_inside_screen and rebound.target.state.active)
    assert(rebound.target.state.look_ahead==0 and not rebound.target.state.is_reverse)
end
print('PASS missing/rebuilt mover contexts recover and cancel against current contexts')

local pending=fixture();pending.frame(3);pending.owner(false)
assert(pending.camera.tick(0,0).owned==3)
pending.owner(true);pending.inside(false)
assert(pending.frame(0).detail=='return_to_team' and not pending.mover.state.keep_inside_screen)
pending.inside(true);assert(pending.frame(0).owned==0)
assert(pending.target.state.active and pending.mover.state.keep_inside_screen)
print('PASS cancellation during identity gap waits for authority and preserves distant return rule')

local native=fixture();native.frame(3);native.owner(false);native.camera.tick(3,0)
CameraTargetComponent.command_master({},42,native.target,'deactivate')
native.owner(true)
assert(native.frame(3).owned==0 and not native.target.state.active)
assert(native.mover.state.keep_inside_screen)
print('PASS native deactivation during synchronization is respected on recovery')

local replaced=fixture(true);replaced.frame(3)
replaced.target.state={active=false,look_ahead=0,is_reverse=false}
assert(replaced.camera.tick(3,0).detail=='waiting_own_master')
assert(not replaced.target.state.active)
CameraTargetComponent.command_master({},42,replaced.target,'activate')
assert(replaced.frame(3).applied==3)
replaced.frame(0)
assert(replaced.target.state.active and replaced.target.state.look_ahead==0 and not replaced.target.state.is_reverse)
print('PASS replacement inactive target waits for native activation and gets a fresh baseline')

local changed=fixture();changed.frame(3)
changed.game.players[1].player_go.get=function() return 88 end
changed.groups.camera_target.master[88]={state={active=false},network_fields={{name='active'}},go_id=88}
changed.groups.mover.master[88]={state={keep_inside_screen=true}}
changed.groups.character.master[88]={state={}}
assert(changed.camera.tick(3,0).owned==0)
assert(changed.groups.mover.master[88].state.keep_inside_screen and not changed.groups.camera_target.master[88].state.active)
assert(next(changed.host.resources)==nil)
print('PASS recovery never carries old unlock baseline into another avatar')

local ambiguous=fixture();ambiguous.frame(3)
ambiguous.game.players[2]={player_go={exists=function() return true end,owned=function() return true end,get=function() return 99 end}}
assert(ambiguous.camera.tick(3,0).detail=='local_players=2')
assert(ambiguous.camera.tick(3,0).applied==0 and ambiguous.remote.state.active)
ambiguous.game.players[2]=peer(99)
assert(ambiguous.frame(3).applied==3 and ambiguous.remote.state.active)
ambiguous.frame(0)
print('PASS ambiguous local ownership never selects the guest and resumes only when unique')

local waiting=fixture();waiting.frame(3)
waiting.mover.state={keep_inside_screen=true}
local controller=waiting.game.entity_manager.components.camera_target
local session=controller.replicator.network_session;controller.replicator.network_session=nil
assert(waiting.camera.tick(3,0).detail=='waiting_own_master' and waiting.mover.state.keep_inside_screen)
controller.replicator.network_session=session
assert(waiting.frame(3).applied==3 and not waiting.mover.state.keep_inside_screen)
waiting.frame(0)
print('PASS rebinding waits for network publishing readiness without latching an error')
