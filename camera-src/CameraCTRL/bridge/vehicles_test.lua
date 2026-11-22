local factory=assert(loadfile(arg[1]))()
local inside=true
local remote_mode=0
Unit={alive=function(u) return u~=nil end,world_position=function() return {} end}
local target,mover={state={active=true}},{state={keep_inside_screen=true}}
local seats={state={seated_units={[1]=42}}}
local groups={camera_target={master={[88]=target}},mover={master={[88]=mover}},vehicle={master={[88]={}}},seat={master={[88]=seats}}}
local game={entity_manager={component_name_to_contexts=groups}}
Boot={state_machine={current_state_name='game',state=game}}
EntityAux={has_component_master=function(u,n) return groups[n] and groups[n].master and groups[n].master[u] end}
local writes=0
local current={game=game,unit=42,manager={targets={[99]={}},is_position_inside_frustum=function() return inside end},
    target_controller={replicator={write_fields=function() writes=writes+1 end}},mover_controller={},
    target_native=function(_,_,ctx,cmd) ctx.state.active=cmd=='activate' end,
    mover_native=function(_,_,ctx,cmd,value) assert(cmd=='keep_inside_screen');ctx.state.keep_inside_screen=value end}
local vehicles=factory({read=function() return remote_mode end})
assert(vehicles.tick(current,88,3)=='vehicle_unlocked')
assert(not target.state.active and not mover.state.keep_inside_screen)
seats.state.seated_units[2]=77
assert(vehicles.tick(current,88,3)=='vehicle_public_passenger')
assert(target.state.active and mover.state.keep_inside_screen)
remote_mode=1
assert(vehicles.tick(current,88,3)=='vehicle_team_boundary')
assert(not target.state.active and mover.state.keep_inside_screen)
remote_mode=3
assert(vehicles.tick(current,88,3)=='vehicle_unlocked')
assert(not target.state.active and not mover.state.keep_inside_screen)
inside=false;remote_mode=0
assert(vehicles.tick(current,88,3)=='vehicle_return_to_team')
assert(not target.state.active and not mover.state.keep_inside_screen)
inside=true
assert(vehicles.tick(current,88,3)=='vehicle_public_passenger')
assert(target.state.active and mover.state.keep_inside_screen)
print('PASS independent crew, ordinary passenger, limited passenger and far cancellation/return')
remote_mode=3;vehicles.tick(current,88,3)
assert(vehicles.target_command(current,88,target,'activate')=='deactivate')
assert(vehicles.mover_command(current,88,mover,'keep_inside_screen',true)==false)
vehicles.restore(current)
assert(target.state.active and mover.state.keep_inside_screen)
assert(vehicles.tick(current,88,3)=='vehicle_unlocked')
local writes_before=writes
groups.camera_target.master[88]=nil
assert(vehicles.tick(current,88,3)=='vehicle_waiting_owner')
vehicles.restore(current);assert(writes==writes_before)
print('PASS native commands cannot override policy; authority loss never writes stale vehicle')
groups.camera_target.master[88]=target
seats.state.seated_units[1]=77;seats.state.seated_units[2]=42
assert(vehicles.tick(current,88,3)=='vehicle_passenger')
assert(writes==writes_before)
print('PASS passenger cannot change driver vehicle policy')
target.state.active=true;mover.state.keep_inside_screen=true
seats.state.seated_units[1]=42;seats.state.seated_units[2]=nil
assert(vehicles.tick(current,88,3)=='vehicle_unlocked')
seats.state.seated_units[1]=77;seats.state.seated_units[2]=42
assert(vehicles.tick(current,88,3)=='vehicle_passenger')
assert(target.state.active and mover.state.keep_inside_screen)
seats.state.seated_units[1]=42;seats.state.seated_units[2]=nil
assert(vehicles.tick(current,88,3)=='vehicle_unlocked')
seats.state.seated_units[1]=nil
vehicles.tick(current,nil,3)
assert(not target.state.active and mover.state.keep_inside_screen)
print('PASS driver change relinquishes override; empty vehicle is never reactivated on exit')

target.state.active=true
seats.state.seated_units[1]=42;seats.state.seated_units[2]=nil
assert(vehicles.tick(current,88,3)=='vehicle_unlocked')
local public_writes=writes
seats.state.seated_units[1]=42;seats.state.seated_units[2]=77
remote_mode=0
assert(vehicles.tick(current,88,3)=='vehicle_public_passenger')
assert(writes==public_writes+1)
assert(target.state.active and mover.state.keep_inside_screen)
public_writes=writes
assert(vehicles.tick(current,88,3)=='vehicle_public_passenger')
assert(writes==public_writes)
assert(target.state.active and mover.state.keep_inside_screen)
print('PASS public passenger restores vehicle target and boundary; unchanged ticks skip explicit write_fields')
