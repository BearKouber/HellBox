local factory=assert(loadfile(arg[1]))()
local time=0
Application={time_since_launch=function() return time end}
EntityAux={owner=function() return 7 end}
local modes=factory()
local slave={state={active=false,look_ahead=0,is_reverse=false}}
local game={entity_manager={component_name_to_contexts={camera_target={slave={[42]=slave}}}}}
local state={active=false,look_ahead=2,is_reverse=false}
local current={target_state=state,target={network_fields={{name="active"},{name="look_ahead"},{name="is_reverse"}}},
    target_controller={replicator={write_fields=function()
        for key,value in pairs(state) do slave.state[key]=value end
    end}}}
assert(modes.read(game,42)==0)
assert(modes.publish(current,3))
assert(modes.read(game,42)==0)
time=0.5;modes.publish(current,3);assert(modes.read(game,42)==0)
time=1;modes.publish(current,3);assert(modes.read(game,42)==3)
time=1.1;modes.publish(current,1);assert(modes.read(game,42)==1)
time=3.2;assert(modes.read(game,42)==0)
print('PASS unknown/ordinary clients stay public; two heartbeat transitions; immediate restriction; stale consent expires')
time=3.5;modes.publish(current,3);modes.read(game,42)
time=4;modes.publish(current,3);modes.read(game,42)
time=4.5;modes.publish(current,3);assert(modes.read(game,42)==3)
EntityAux.owner=function() return 8 end
assert(modes.read(game,42)==0)
slave.state.active=true;assert(modes.read(game,42)==0)
print('PASS new owner and active target invalidate remote mode')
modes.command(current,function(_,_,_,command,value)
    assert(command=='look_ahead' and state.look_ahead==2 and state.is_reverse==false)
    state.look_ahead=value
end,{},42,current.target,'look_ahead',4)
assert(state.look_ahead>=8 and state.is_reverse)
modes.restore(current)
assert(state.look_ahead==4 and state.is_reverse==false and not current.mode_wire)
print('PASS latest native look-ahead intent restored, carrier never becomes restoration baseline')
-- The extracted native slave update must not pass the marker to CameraManager.
local env={class=function() return {} end, pairs=pairs,Vector3={equal=function() return false end,zero=function() return {} end},
    Unit={world_position=function() return {} end},CameraManager={}}
setfenv(assert(loadfile(arg[2]..'/chunk_0029290c/chunk.ljbc')),env)()
local writes=0
env.CameraManager.set_target_properties=function() writes=writes+1 end
env.CameraTargetComponent.update_slaves({}, {[42]={state={active=false,was_active=false,look_ahead=15,is_reverse=true}}},0)
assert(writes==0)
print('PASS original inactive target ignores mode carrier without updating public camera properties')
