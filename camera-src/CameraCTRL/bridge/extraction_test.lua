local factory=assert(loadfile(arg[1]))()
local path=arg[2]
local mt={}
local function vec(x,y,z) return setmetatable({x=x,y=y,z=z},mt) end
mt.__add=function(a,b) return vec(a.x+b.x,a.y+b.y,a.z+b.z) end
Vector3=setmetatable({zero=function() return vec(0,0,0) end,
    distance=function(a,b) return math.sqrt((a.x-b.x)^2+(a.y-b.y)^2+(a.z-b.z)^2) end},
    {__call=function(_,...) return vec(...) end})
class=function() return {} end;BaseComponent={}
Unit={world_position=function(u) return u.position end,alive=function(u) return u~=nil end}
EntityAux={state=function(u) return u.health end,owner=function() return 'objective-owner' end,
    has_component_master=function() return true end}
REAL_TIME_DT=1
assert(loadfile(path..'/chunk_001d7311/chunk.ljbc'))()
local native=ExtractBeaconComponent.update_masters
local game={}
Boot={state_machine={current_state_name='game',state=game}}
local claimed={}
local host={claim=function(_,_,key) assert(not claimed[key]);claimed[key]=true;return true end,
    release=function(_,_,key) claimed[key]=nil end}
local patch=factory(host)
patch.tick(true)
local near={position=vec(0,0,0),health={is_dead=false}}
local far={position=vec(200,0,0),health={is_dead=false}}
local players={[near]=true,[far]=true}
local rpc=0
local controller=setmetatable({name='extract_beacon',entity_manager={get_slave_entities=function() return players end},
    trigger_rpc_event_to=function(_,owner,event) assert(owner=='objective-owner' and event=='rpc_make_lz');rpc=rpc+1 end},
    {__index=ExtractBeaconComponent})
local function beacon(x,time)
    return {position=vec(x,0,0)}, {settings={extract_beacon_info={check_player_distance_interval=1,too_far_away_distance=30,too_far_away_time=5}},
        state={activated=true,was_activated=true,enabled=false,alert_timer=1000,check_player_distance_timer=0,
            extraction_timer=time or 100,extraction_time=time or 100,extract_unit={}}}
end
local a,ca=beacon(0)
local b,cb=beacon(400)
for _=1,5 do controller:update_masters({[a]=ca,[b]=cb},1) end
assert(ca.state.activated and ca.state.extraction_timer==95)
assert(not cb.state.activated and cb.state.enabled)
assert(rawget(controller,'get_center_of_players')==nil)
print('PASS real bytecode: per-beacon nearest living presence and native all-away cancellation')
near.health.is_dead=true
for _=1,5 do controller:update_masters({[a]=ca},1) end
assert(not ca.state.activated)
near.health.is_dead=false
a,ca=beacon(0,3)
for _=1,5 do controller:update_masters({[a]=ca},1) end
assert(rpc==1)
print('PASS dead player does not count; real completion RPC preserved exactly once')
EntityAux.has_component_master=function() return false end
a,ca=beacon(0)
for _=1,5 do controller:update_masters({[a]=ca},1) end
assert(not ca.state.activated)
assert(rawget(controller,'get_center_of_players')==nil)
EntityAux.has_component_master=function() return true end
print('PASS missing local authority uses the unchanged native center')
patch.tick(false);assert(ExtractBeaconComponent.update_masters==native and next(claimed)==nil)
ExtractBeaconComponent.update_masters=function() error('native-failure') end
patch.tick(true)
local ok=pcall(controller.update_masters,controller,{[a]=ca},1)
assert(not ok and rawget(controller,'get_center_of_players')==nil)
assert(patch.tick(true):find('native-failure',1,true))
patch.tick(false);assert(next(claimed)==nil)
print('PASS exception restores scoped helper; cancellation removes hook')
