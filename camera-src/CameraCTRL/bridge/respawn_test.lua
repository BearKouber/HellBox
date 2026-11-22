local factory=assert(loadfile(arg[1]))()
Vector3=function(x,y,z) return {x=x,y=y,z=z} end
Vector3Aux={unbox=function(value) return Vector3(value.x,value.y,value.z) end}
local calls={}
local local_go={exists=function() return true end,owned=function() return true end}
local remote_go={exists=function() return true end,owned=function() return false end}
local game={has_faded_in=true,respawn_position=Vector3(100,200,3),players={
    {player_go=local_go,has_sent_respawn_request=true},{player_go=remote_go,has_sent_respawn_request=true}
}}
local native=function(owner,position,index,pad,...)
    calls[#calls+1]={owner=owner,position=position,index=index,pad=pad,extra=(...)}
    return 1,nil,"tail"
end
local class={spawn_local_player=native}
setmetatable(game,{__index=class})
Boot={state_machine={current_state_name="game",state=game}}
local host={resources={}}
function host:claim(owner,key) if self.resources[key] then return false end self.resources[key]=owner;return true end
function host:release(owner,key) if self.resources[key]==owner then self.resources[key]=nil end end
local module=factory(host)
module.tick(true)
local first,empty,tail=game:spawn_local_player(Vector3(0,0,0),1,0,"extra")
local position=calls[#calls].position
assert(first==1 and empty==nil and tail=="tail" and calls[#calls].extra=="extra")
local distance=(position.x-100)^2+(position.y-200)^2
assert(distance>=1 and distance<=4 and position.z==3)
assert(game.respawn_position.x==100 and game.players[1].has_sent_respawn_request)
print("PASS local dead player returns to original beacon vicinity with native scatter and return values")

local unchanged=Vector3(101,200,3)
game:spawn_local_player(unchanged,1,0);assert(calls[#calls].position==unchanged)
unchanged=Vector3(0,0,0)
game:spawn_local_player(unchanged,2,0);assert(calls[#calls].position==unchanged)
game.players[1].has_sent_respawn_request=false
game:spawn_local_player(unchanged,1,0);assert(calls[#calls].position==unchanged)
game.players[1].has_sent_respawn_request=true;game.has_faded_in=false
game:spawn_local_player(unchanged,1,0);assert(calls[#calls].position==unchanged)
game.has_faded_in=true;game.players[2].player_go=local_go
game:spawn_local_player(unchanged,1,0);assert(calls[#calls].position==unchanged)
game.players[2].player_go=remote_go
print("PASS valid landing, remote player, initial spawn and local co-op are untouched")

module.tick(false)
assert(rawget(game,"spawn_local_player")==nil and next(host.resources)==nil)
game:spawn_local_player(unchanged,1,0);assert(calls[#calls].position==unchanged)
module.tick(true)
Boot.state_machine.state={}
module.tick(true)
assert(rawget(game,"spawn_local_player")==nil and next(host.resources)==nil)
print("PASS cancellation and world change restore inherited spawn method")

Boot.state_machine.state=game
module.tick(true)
local unbox=Vector3Aux.unbox
Vector3Aux.unbox=function() error("broken_anchor") end
game:spawn_local_player(unchanged,1,0)
assert(calls[#calls].position==unchanged and module.tick(true):find("broken_anchor",1,true))
Vector3Aux.unbox=unbox
module.tick(false)
assert(rawget(game,"spawn_local_player")==nil)
host.resources["StateGame.spawn_local_player"]="other"
assert(not pcall(module.tick,true) and rawget(game,"spawn_local_player")==nil)
print("PASS failed anchor falls back to native spawn and hook conflict leaves original method intact")
