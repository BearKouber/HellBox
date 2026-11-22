-- Real stop/follow command, derived update, Base writeback and HUD consumers.
-- luajit this.lua bridge/escort.lua <dev-directory>
local factory=assert(loadfile(arg[1]))()
local root=assert(arg[2])
local env=setmetatable({class=function() return {} end,require=function() end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
local function load(path) setfenv(assert(loadfile(root..path)),env)() end
load('/LuaSurvey/evidence/camera-escort-interact-20261110/chunk_00295397/chunk.ljbc')
local native=env.NpcEscortComponent
local group={master={},slave={}}
local game={players={},entity_manager={component_name_to_contexts={npc_escort=group}}}
Boot={state_machine={current_state_name='game',state=game}}
Unit={alive=function(unit) return group.master[unit]~=nil or unit==99 end}
EntityAux={has_component_master=function(unit,name) return name=='npc_escort' and group.master[unit]~=nil end,
    state=function() return {is_dead=false} end}
LocalizationManager={string=function(_,key) return key end}
load('/LuaSurvey/evidence/supply-sharing-foundation-20261031/chunk_0000a471/chunk.ljbc')
local writes,labels=0,{}
local controller={use_dirty_optimization=true,
    entity_manager={get_slave_entities=function() return {} end},
    replicator={write_fields=function() writes=writes+1 end},
    hud={draw_interactable=function(_,data,_,_,label) labels[data[1]]=label end}}
for unit=1,8 do
    -- Two four-person groups stand together and may share display/name strings.
    group.master[unit]={state={following_unit=true,follow_unit=99,activated=true,in_goal=false,
        registered_at_objective=true,full_update_dt=0,health_state={is_dead=false,is_downed=false}},
        settings={npc_escort_info={}},network_fields={{name='following_unit'},{name='activated'},{name='in_goal'}}}
    group.slave[unit]={settings={},state={following_unit=true,activated=true,in_goal=false,
        health_state={is_dead=false,is_downed=false,hitpoints=100,max_hitpoints=100}}}
end
local function draw(unit)
    labels[unit]=nil
    native.draw_ui(controller,{unit,group.slave[unit]},nil,nil)
    return labels[unit]
end
local function write()
    env.BaseComponent.write_game_objects(controller,group.master,group.slave)
end
local function command(unit,name)
    native.command_derived_master(controller,unit,group.master[unit],name,99)
end
command(1,'stop')
native.update_derived_master(controller,1,group.master[1],0.1,false)
write()
assert(group.master[1].state.following_unit==false and draw(1)=='follow_stop' and writes==0)
print('PASS original stop succeeds but HUD remains follow_stop when dirty writeback is skipped')

NpcEscortComponent={update_derived_master=native.update_derived_master}
local host={claim=function() return true end,release=function() end}
local module=factory(host);module.tick()
local function update(unit)
    return NpcEscortComponent.update_derived_master(controller,unit,group.master[unit],0.1,false)
end
for unit=1,4 do command(unit,'stop');assert(update(unit)) end
write()
assert(writes==4)
for unit=1,8 do
    assert(draw(unit)==(unit<=4 and 'follow' or 'follow_stop'))
    assert(not group.master[unit].state.dirty)
end
print('PASS stopping first group updates native HUD for all four members; second group stays following')
for unit=1,8 do update(unit) end
write();assert(writes==4,'stable flags must not trigger repeated writes')
for unit=1,4 do command(unit,'follow');update(unit) end
for unit=5,8 do command(unit,'stop');update(unit) end
write();assert(writes==12)
for unit=1,8 do assert(draw(unit)==(unit<=4 and 'follow_stop' or 'follow')) end
print('PASS follow/stop can alternate independently across two overlapping groups')

group.master[1].state.following_unit=false
group.master[1].state.follow_unit=nil
group.master[1].state.activated=false
assert(update(1)==false) -- native inactive early return must still publish flags
write();assert(draw(1)=='follow' and not group.slave[1].state.activated)
group.master[1].state.in_goal=true
update(1);write();assert(draw(1)==nil)
print('PASS inactive early return and delivery flags still reach the native HUD')

local stale=group.master[2]
command(2,'stop');group.master[2]={state=stale.state}
NpcEscortComponent.update_derived_master(controller,2,stale,0.1,false)
assert(not stale.state.dirty)
group.master[2]=stale
local saved=EntityAux.has_component_master
EntityAux.has_component_master=function() return false end
update(2);assert(not stale.state.dirty)
EntityAux.has_component_master=saved
local slave=group.slave[2];group.slave[2]=nil
update(2);assert(not stale.state.dirty)
group.slave[2]=slave
local registered=stale.state.registered_at_objective
stale.state.registered_at_objective=false
controller.entity_manager.get_slave_entities=function() error('native_failure') end
assert(not pcall(update,2) and not stale.state.dirty)
stale.state.registered_at_objective=registered
Boot.state_machine.current_state_name='menu';module.tick()
assert(NpcEscortComponent.update_derived_master==native.update_derived_master)
print('PASS stale context, lost authority, missing slave and failed native update do not publish flags')
