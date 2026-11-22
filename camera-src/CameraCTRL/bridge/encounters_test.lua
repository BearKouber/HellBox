local factory=assert(loadfile(arg[1]))()
local chunk=assert(arg[2]).."/chunk_003af5b3/chunk.ljbc"
local patrol_chunk=assert(arg[3],"patrol evidence directory required").."/chunk_000cb9db/chunk.ljbc"
local function fixture()
    local now=10
    local positions={[1]={x=0,y=0,z=0},[2]={x=100,y=0,z=0}}
    local dead={}
    local vector_meta={}
    local function vector(x,y,z) return setmetatable({x=x,y=y,z=z},vector_meta) end
    vector_meta.__sub=function(left,right) return vector(left.x-right.x,left.y-right.y,left.z-right.z) end
    Vector3=setmetatable({zero=function() return vector(0,0,0) end,
        distance=function(left,right) return math.sqrt((left.x-right.x)^2+(left.y-right.y)^2+(left.z-right.z)^2) end,
        length_squared=function(value) return value.x^2+value.y^2+value.z^2 end},
        {__call=function(_,...) return vector(...) end})
    Vector3Aux={box=function(target,value) target.x=value.x;target.y=value.y;target.z=value.z;return target end,
        unbox=function(value) return vector(value.x,value.y,value.z) end}
    Unit={alive=function(unit) return positions[unit]~=nil end,world_position=function(unit) return Vector3Aux.unbox(assert(positions[unit])) end}
    EntityAux={state=function(unit) return {is_dead=dead[unit]} end,owned=function() return true end,queue_command_master=function() end}
    Network={peer_id=function() return "host" end}
    NetworkGlobal={lobby={game_session_host=function() return "host" end}}
    Log={info=function() end}
    Application={time_since_launch=function() return now end}
    GameSettings={MAX_NUM_ALLOWED_ENEMIES=30}
    IS_DEV=false
    math.shuffle=function() end
    table.clone=function(source)
        local result={}
        for key,value in pairs(source) do result[key]=type(value)=="table" and table.clone(value) or value end
        return result
    end
    array={remove_at=table.remove,remove_where=function(items,key,value)
        for index=#items,1,-1 do if items[index][key]==value then table.remove(items,index) end end
    end}
    local environment=setmetatable({class=function() return {} end,require=function() end,
        Profiler={start=function() end,stop=function() end}},{__index=_G})
    setfenv(assert(loadfile(chunk)),environment)()
    local native=environment.EncounterManager
    setfenv(assert(loadfile(patrol_chunk)),environment)()
    local patrol_native=environment.PatrolManager
    local wave={name="native_heavy",cost=10,duration=1,events={{distance=0,delay=0,groups={{group="heavy",active=true}}}}}
    local other={name="native_light",cost=3,duration=1,events=wave.events}
    local owner=setmetatable({enemies={},active_events={},wave_sizes={[wave]=2,[other]=1},wave_order={"waves_hard"},
        waves_hard={wave},min_cost=10,num_encounters=0,num_queued_enemies=0,next_wave_id=0,
        time_since_last_encounter_started=10,wave_duration=-1,wave_can_spawn_timer=0,wave_spawn_interval=1,
        remove_enemies_far_away_timer=100,remove_enemies_interval=100,remove_enemies_far_away_radius=30,
        encounter_position={x=0,y=0,z=0},max_num_enemies=4,
        calculate_difficulty=function(self) self.encounter_difficulty=10 end,
        hint_manager={add_hint=function() end},network_router={transmit_to_all=function() end},
        get_spawner_peer=function() return "host" end,
        get_center_of_players=function(self) return Vector3Aux.unbox(self.encounter_position) end,
        patrol_manager=setmetatable({patrols={},num_spawned_enemies=0,num_queued_enemies=0,
            num_spawned_groups_per_type={},max_num_patrol_units=4},{__index=patrol_native})}, {__index=native})
    owner.entity_manager={all_slaves_iterator=function()
        local enemies={}
        for unit in pairs(positions) do if unit>10 then enemies[unit]=true end end
        return pairs(enemies)
    end}
    local queued={}
    owner.spawn_manager={queue_group_spawn=function(_,position,group,callback,data)
        queued[#queued+1]={position=Vector3Aux.unbox(position),callback=callback,data=data,members={{},{}}}
        return 2
    end}
    owner.patrol_manager.entity_manager=owner.entity_manager
    owner.patrol_manager.spawn_manager=owner.spawn_manager
    owner.patrol_manager.encounter_manager=owner
    EnemyGroupSettings={heavy={},scouts={units={{amount=2}}}}
    local current={encounter=owner,patrol=owner.patrol_manager,players={{unit=1,x=0,y=0,z=0},{unit=2,x=100,y=0,z=0}},
        zones={[2]={viewport={world_to_viewport=function(_,position) return vector(position.x,1,position.y) end}}},
        manager={screen_resolution={width=20,height=20}}}
    local hooks={}
    local enabled=true
    local release=factory(current,function(_,object,key,make)
        local previous=rawget(object,key)
        local original=assert(object[key])
        hooks[#hooks+1]={object=object,key=key,previous=previous}
        object[key]=make(original)
        return original
    end,function() return enabled and not current.error end)
    return {owner=owner,current=current,wave=wave,light=other,positions=positions,dead=dead,queued=queued,native=native,
        patrol_native=patrol_native,patrol=owner.patrol_manager,
        advance=function(seconds) now=now+seconds;owner.time_since_last_encounter_started=owner.time_since_last_encounter_started+seconds end,
        stop=function() enabled=false;release();for index=#hooks,1,-1 do
            local item=hooks[index];rawset(item.object,item.key,item.previous)
        end end}
end
local test=fixture()
test.owner:start_encounter(Vector3(0,0,0))
assert(test.owner.selected_waves[1]~=test.wave)
test.owner.destroyed=true
test.owner.selected_waves=nil
test.owner.current_wave=nil
test.owner.wave_sizes=nil
test.stop()
assert(test.owner.current_wave==nil and test.owner.wave_sizes==nil)
print("PASS destroyed encounter manager releases wrappers without restoring freed wave tables")

test=fixture()
local preflight_settings={group_info="scouts"}
assert(test.current.patrol_regions.admit(Vector3(100,0,0),2,preflight_settings))
assert(test.patrol.num_queued_enemies==0 and #test.queued==0)
test.patrol.num_spawned_enemies=4
test.patrol.patrols={{spawned=true,position={x=0,y=0,z=0},patrol_settings=preflight_settings,
    units={{unit=50},{unit=51},{unit=52},{unit=53}}}}
for unit=50,53 do test.positions[unit]={x=0,y=0,z=0} end
assert(not test.current.patrol_regions.admit(Vector3(0,0,0),2,preflight_settings))
assert(test.current.patrol_regions.admit(Vector3(100,0,0),2,preflight_settings))
assert(not test.patrol:can_spawn(2,preflight_settings),"preflight must restore context for unrelated native admission")
assert(test.patrol.num_queued_enemies==0 and #test.queued==0)
test.stop()
print("PASS supply preflight reuses regional admission without queue writes and restores native caller context")

test=fixture()
test.positions[50]={x=100,y=0,z=0}
test.owner.enemies={{unit=50,wave_id=20,wave_cost=10}}
test.owner:start_encounter(Vector3(0,0,0))
assert(#test.owner.selected_waves==1 and test.owner.selected_waves[1].cost==10)
assert(test.owner.selected_waves[1]~=test.wave and test.owner.wave_sizes[test.owner.selected_waves[1]]==2)
test.owner:start_encounter(Vector3(1,0,0));assert(#test.owner.selected_waves==1)
test.owner:start_encounter(Vector3(100,0,0));assert(#test.owner.selected_waves==1)
print("PASS native selection gets full local budget despite distant living wave, local alarm deduplicated")

test=fixture()
test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0))
assert(#test.owner.selected_waves==2)
test.owner:update(0.1)
assert(#test.queued==1 and test.queued[1].position.x==0,"queued="..#test.queued.." events="..#test.owner.active_events.." timer="..test.owner.wave_duration)
assert(test.owner.num_queued_enemies==2)
test.owner:update(2)
assert(#test.queued==2 and test.queued[2].position.x==100)
assert(test.owner.num_queued_enemies==4)
assert(test.queued[1].data.wave_id~=test.queued[2].data.wave_id)
test.owner:on_group_failed(test.queued[1],test.queued[1].data)
assert(test.owner.num_queued_enemies==2)
test.advance(4);test.owner:start_encounter(Vector3(100,0,0))
assert(not test.owner.selected_waves or #test.owner.selected_waves==0)
test.owner:on_group_failed(test.queued[2],test.queued[2].data)
test.advance(4);test.owner:start_encounter(Vector3(100,0,0))
assert(#test.owner.selected_waves==1)
print("PASS native update and group failure retain distinct landing positions, pending reservations and wave IDs")

test=fixture();test.current.players[2].x=0;test.current.zones={}
test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(0,0,0))
assert(#test.owner.selected_waves==1 and test.owner.selected_waves[1]==test.wave and test.owner.num_encounters==1)
print("PASS same screen uses native templates, native cooldown and one budget")

test=fixture();test.current.players[2].x=19
test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(19,0,0))
assert(test.owner.num_encounters==1)
print("PASS overlapping projected screens merge even while one player is outside shared screen")

test=fixture()
test.current.game={}
HelldiversBridgeHost={enemy_policy={abi=1,game=test.current.game,expires=11,encounter=8,patrol=12}}
local regional,total=test.current.patrol_regions.multipliers('patrol',2)
assert(regional==3 and total==6)
regional,total=test.current.patrol_regions.multipliers('encounter',1)
assert(regional==2 and total==2)
test.advance(2)
regional,total=test.current.patrol_regions.multipliers('patrol',2)
assert(regional==1 and total==2)
HelldiversBridgeHost.enemy_policy.expires=20
HelldiversBridgeHost.enemy_policy.game={}
regional,total=test.current.patrol_regions.multipliers('patrol',2)
assert(regional==1 and total==2)
HelldiversBridgeHost=nil
print('PASS EnemyEdit policy priority, same-screen cap, expiry and task isolation')

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0))
test.owner.num_queued_enemies=4;test.owner:update(0.1)
assert(#test.queued==0 and #test.owner.selected_waves==2 and test.owner.selected_waves[1].cost==10)
test.owner.num_queued_enemies=0;test.owner.wave_can_spawn_timer=0
for unit=11,70 do test.positions[unit]={x=0,y=0,z=0} end
test.owner:update(1);assert(#test.queued==0)
print("PASS unknown pending local quota and doubled global cap delay full waves without downgrading")

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0))
local size_count=0;for _ in pairs(test.owner.wave_sizes) do size_count=size_count+1 end
assert(size_count==4)
test.stop()
assert(test.owner.selected_waves[1]==test.wave and test.owner.selected_waves[2]==test.wave)
size_count=0;for _ in pairs(test.owner.wave_sizes) do size_count=size_count+1 end
assert(size_count==2 and test.owner.start_encounter==test.native.start_encounter)
print("PASS cancellation restores pending native wave templates and releases clone size entries")

test=fixture();test.owner.active_events={{wave_id=8,wave_cost=10,groups={},duration=0,delay=100}}
test.owner:start_encounter(Vector3(0,0,0))
assert(not test.owner.selected_waves or #test.owner.selected_waves==0)
print("PASS untagged pre-existing active events conservatively reserve budget")

test=fixture();test.owner.num_queued_enemies=1
test.positions[50]={x=100,y=0,z=0};test.owner.enemies={{unit=50,wave_id=9,wave_cost=10}}
test.owner:start_encounter(Vector3(0,0,0))
assert(#test.owner.selected_waves==0)
print("PASS unknown in-flight native spawns use conservative remaining cost")

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:update(0.1)
local queued=test.queued[1]
test.positions[51]={x=0,y=0,z=0};test.positions[52]={x=0,y=0,z=0}
test.owner:on_entity_spawned(51,"heavy",Vector3(0,0,0),{},queued.data,"host")
test.owner:on_entity_spawned(52,"heavy",Vector3(0,0,0),{},queued.data,"host")
assert(test.owner.num_queued_enemies==0 and #test.owner.enemies==2)
test.advance(4);test.owner:start_encounter(Vector3(0,0,0))
assert(#test.owner.selected_waves==0)
test.owner:start_encounter(Vector3(100,0,0));assert(#test.owner.selected_waves==1)
test.current.players[2].x=0;test.current.zones={};test.advance(4)
test.owner:start_encounter(Vector3(0,0,0));assert(#test.owner.selected_waves==1)
print("PASS spawned wave charged once locally, distant region independent, regroup resumes shared accounting")

test=fixture();test.current.players[3]={unit=3,x=200,y=0,z=0}
test.current.zones[3]=test.current.zones[2]
test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0));test.owner:start_encounter(Vector3(200,0,0))
assert(#test.owner.selected_waves==3)
test.owner:update(0.1);test.owner:on_group_failed(test.queued[1],test.queued[1].data)
test.owner:update(2);test.owner:on_group_failed(test.queued[2],test.queued[2].data)
test.owner:update(2)
assert(#test.queued==3 and test.queued[1].position.x==0 and test.queued[2].position.x==100 and test.queued[3].position.x==200)
print("PASS three separated regions preserve FIFO fairness and independent landing positions")

test=fixture();test.owner:start_encounter(Vector3(0,0,0))
local previous=test.owner.encounter_position
test.owner.wave_sizes[test.owner.selected_waves[1]]=nil
assert(not test.owner:can_spawn(test.owner.selected_waves[1]))
assert(test.owner.encounter_position==previous)
assert(test.current.error:find("regional_can_spawn",1,true))
print("PASS spawn-check exception restores position and disables regional hooks without escaping into game update")

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0))
test.owner.active_events={{wave_id=99,wave_cost=10,groups={{active=true,group="heavy"}},duration=0,delay=100}}
test.owner:update(0.1)
assert(#test.queued==0 and #test.owner.selected_waves==2)
print("PASS delayed native event reserves scheduling slot before additional regional wave admission")

test=fixture();test.owner.selected_waves={test.wave,test.wave}
test.owner:start_encounter(Vector3(100,0,0))
assert(test.owner.selected_waves[1]~=test.wave and test.owner.selected_waves[2]~=test.wave)
assert(test.owner.selected_waves[1]~=test.owner.selected_waves[2])
test.owner.selected_waves=nil;test.owner.enemies={};test.owner.active_events={}
test.current.players[2].x=0;test.current.zones={};test.advance(4)
test.owner:start_encounter(Vector3(0,0,0))
assert(test.owner.selected_waves[1]==test.wave)
test.owner:update(0.1);assert(test.queued[1].position.x==0)
print("PASS adopting existing repeated templates never attaches a persistent origin to native settings")

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0))
local first,second=test.owner.selected_waves[1],test.owner.selected_waves[2]
for unit=51,54 do
    test.positions[unit]={x=0,y=0,z=0}
    test.owner.enemies[#test.owner.enemies+1]={unit=unit,wave_id=1,wave_cost=10}
end
assert(not test.owner:can_spawn(first) and test.owner:can_spawn(second))
for unit=55,56 do
    test.positions[unit]={x=100,y=0,z=0}
    test.owner.enemies[#test.owner.enemies+1]={unit=unit,wave_id=2,wave_cost=10}
end
assert(test.owner:can_spawn(second))
test.positions[57]={x=100,y=0,z=0};test.owner.enemies[7]={unit=57,wave_id=2,wave_cost=10}
assert(not test.owner:can_spawn(second))
assert(test.owner.max_num_enemies==4 and GameSettings.MAX_NUM_ALLOWED_ENEMIES==30)
print("PASS each region gets one native encounter quota; other region can fill even when original shared cap is full")

test=fixture();test.current.players[3]={unit=3,x=200,y=0,z=0};test.current.players[4]={unit=4,x=300,y=0,z=0}
test.current.zones[3]=test.current.zones[2];test.current.zones[4]=test.current.zones[2]
test.owner:start_encounter(Vector3(200,0,0));local third=test.owner.selected_waves[1]
for unit=51,57 do
    test.positions[unit]={x=unit<55 and 0 or 100,y=0,z=0}
    test.owner.enemies[#test.owner.enemies+1]={unit=unit,wave_id=unit,wave_cost=1}
end
assert(not test.owner:can_spawn(third))
test.owner.enemies[7]=nil;test.positions[57]=nil
assert(test.owner:can_spawn(third))
assert(test.current.regional_detail():find(";regional_caps:4/8;global_cap:120",1,true))
print("PASS four separated regions still share exactly two native quotas, never four")

test=fixture();test.owner.max_num_enemies=100
test.owner:start_encounter(Vector3(100,0,0));local remote=test.owner.selected_waves[1]
for unit=11,68 do test.positions[unit]={x=unit<40 and 0 or 100,y=0,z=0} end
assert(not test.owner:can_spawn(remote))
test.positions[68]=nil
assert(test.owner:can_spawn(remote))
test.owner.patrol_manager.get_num_queued_enemies=function() return 1 end
assert(not test.owner:can_spawn(remote))
assert(GameSettings.MAX_NUM_ALLOWED_ENEMIES==30)
print("PASS total entity cap, per-region entity quota and queued patrol reservations enforced without editing GameSettings")

test=fixture();test.owner:start_encounter(Vector3(100,0,0));local separated=test.owner.selected_waves[1]
for unit=51,54 do
    test.positions[unit]={x=0,y=0,z=0};test.owner.enemies[#test.owner.enemies+1]={unit=unit}
end
assert(test.owner:can_spawn(separated))
test.current.players[2].x=0;test.current.zones={}
assert(not test.owner:can_spawn(separated))
assert(test.current.regional_detail():find(";regional_caps:4/4;global_cap:30",1,true))
assert(#test.owner.enemies==4)
test.stop();assert(test.owner.max_num_enemies==4 and GameSettings.MAX_NUM_ALLOWED_ENEMIES==30)
print("PASS regroup restores native admission caps without despawning existing enemies or changing global settings")

test=fixture();test.current.players[3]={unit=3,x=200,y=0,z=0};test.current.zones[3]=test.current.zones[2]
test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0));test.owner:start_encounter(Vector3(200,0,0))
local first,second,third=test.owner.selected_waves[1],test.owner.selected_waves[2],test.owner.selected_waves[3]
test.owner:add_events(first,Vector3(0,0,0));test.owner.active_events={}
test.owner:add_events(second,Vector3(100,0,0));test.owner.active_events={}
test.owner:update(0.1)
assert(test.owner.current_wave==third and test.queued[1].position.x==200)
print("PASS least-recently-served region wins over alternating first two regions")

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:start_encounter(Vector3(100,0,0))
local local_wave,remote_wave=test.owner.selected_waves[1],test.owner.selected_waves[2]
test.owner:add_events(local_wave,Vector3(0,0,0));local identifier=test.owner.next_wave_id-1
test.owner.active_events={}
test.owner:spawn_group(Vector3(0,0,0),{},identifier,10)
test.owner:spawn_group(Vector3(0,0,0),{},identifier,10)
assert(test.owner.num_queued_enemies==4)
assert(not test.owner:can_spawn(local_wave) and test.owner:can_spawn(remote_wave))
test.owner:on_group_failed(test.queued[1],test.queued[1].data)
assert(test.owner:can_spawn(local_wave))
test.positions[80]={x=100,y=0,z=0};test.owner:on_entity_spawned(80,"heavy",Vector3(100,0,0),{},test.queued[2].data,"host")
test.positions[81]={x=100,y=0,z=0};test.owner:on_entity_spawned(81,"heavy",Vector3(100,0,0),{},test.queued[2].data,"host")
assert(test.owner.num_queued_enemies==0)
assert(test.owner:can_spawn(local_wave) and test.owner:can_spawn(remote_wave))
test.positions[82]={x=100,y=0,z=0};test.owner.enemies[3]={unit=82}
assert(not test.owner:can_spawn(remote_wave))
print("PASS regional queued capacity releases on failure and follows actual positions after spawn completion")

local function patrol_entry(test,position,maximum)
    local entry={position={x=position,y=0,z=0},units={},remaining_spawns=0,
        patrol_settings={group_info="scouts",max_spawned=maximum},target_position={x=position,y=0,z=0}}
    test.patrol.patrols[#test.patrol.patrols+1]=entry
    return entry
end
local function finish_patrol(test,entry,first)
    for identifier=first,first+1 do
        test.positions[identifier]={x=entry.position.x,y=0,z=0}
        test.patrol:on_entity_spawned(identifier,"scouts",Vector3(entry.position.x,0,0),{},entry,"host")
    end
end

test=fixture()
local left=patrol_entry(test,0,2)
local left_more=patrol_entry(test,0,2)
assert(test.patrol:spawn_patrol(left));finish_patrol(test,left,51)
assert(test.patrol:spawn_patrol(left_more));finish_patrol(test,left_more,53)
local right=patrol_entry(test,100,2)
assert(not test.patrol_native.can_spawn(test.patrol,2,right.patrol_settings))
assert(test.patrol:spawn_patrol(right) and right.spawned)
assert(test.queued[3].position.x==100 and test.queued[3].callback==test.patrol and test.queued[3].data==right)
assert(not test.patrol:spawn_patrol(patrol_entry(test,0,2)))
finish_patrol(test,right,55)
assert(test.patrol.num_queued_enemies==0 and test.patrol.num_spawned_enemies==6)
assert(test.current.regional_detail():find("patrol_regions:1:4/0/1,2:2/0/0",1,true))
print("PASS original patrol gate reproduces shared-cap rejection; regional gate admits remote native spawn and callbacks")

test=fixture();test.current.players[2].x=0;test.current.zones={}
assert(test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(not test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(test.patrol.num_queued_enemies==4 and #test.queued==2)
print("PASS same-screen patrol spawning retains exactly one original quota including pending units")

test=fixture();test.current.players[3]={unit=3,x=200,y=0,z=0};test.current.players[4]={unit=4,x=300,y=0,z=0}
test.current.zones[3]=test.current.zones[2];test.current.zones[4]=test.current.zones[2]
for index=1,4 do
    assert(test.patrol:spawn_patrol(patrol_entry(test,(index-1)*100,2)))
    assert(test.patrol:spawn_patrol(patrol_entry(test,(index-1)*100,2)))
    assert(not test.patrol:spawn_patrol(patrol_entry(test,(index-1)*100)))
end
assert(test.patrol.num_queued_enemies==16 and #test.queued==8)
assert(not test.patrol:spawn_patrol(patrol_entry(test,300,2)))
assert(test.current.regional_detail():find(";patrol_caps:4/16",1,true))
test.current.players[2].x=0;test.current.players[3].x=0;test.current.players[4].x=0;test.current.zones={}
assert(not test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(test.patrol.num_queued_enemies==16)
test.stop();assert(test.patrol.spawn_patrol==test.patrol_native.spawn_patrol and test.patrol.max_num_patrol_units==4)
print("PASS patrol quota scales through four regions; regroup stops admission without deleting existing queues; cancellation restores")

test=fixture();left=patrol_entry(test,0);right=patrol_entry(test,100)
assert(test.patrol:spawn_patrol(left));assert(test.patrol:spawn_patrol(right))
test.patrol:on_group_failed(test.queued[1],left)
assert(test.patrol.num_queued_enemies==2 and not left.spawned)
assert(test.patrol:spawn_patrol(left))
assert(test.patrol.num_queued_enemies==4)
print("PASS native patrol failure frees pending regional reservation even when remaining_spawns retains old value")

test=fixture();left=patrol_entry(test,0,1);right=patrol_entry(test,100,1)
assert(test.patrol:spawn_patrol(left));assert(test.patrol:spawn_patrol(right))
assert(not test.patrol:spawn_patrol(patrol_entry(test,100,1)))
assert(test.current.regional_detail():find("patrol_gate:2:regional_type",1,true))
print("PASS per-type patrol limit applies once per region and reports rejection reason")

test=fixture();test.owner:start_encounter(Vector3(0,0,0));test.owner:update(0.1)
right=patrol_entry(test,100)
for identifier=11,40 do test.positions[identifier]={x=0,y=0,z=0} end
assert(test.patrol:spawn_patrol(right))
assert(not test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(test.current.regional_detail():find("patrol_gate:1:regional_entities",1,true))
for identifier=41,68 do test.positions[identifier]={x=100,y=0,z=0} end
assert(not test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(test.current.regional_detail():find("patrol_gate:2:global_entities",1,true))
print("PASS encounter reservations shared with patrol checks; distant queues isolated; regional and global entity caps enforced")

test=fixture();test.patrol.num_queued_enemies=4
assert(not test.patrol:spawn_patrol(patrol_entry(test,100)))
test.patrol.num_queued_enemies=0;test.patrol.max_num_patrol_units=nil
assert(not test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(test.current.error:find("missing_patrol_cap",1,true))
assert(test.patrol.num_queued_enemies==0)
print("PASS unknown patrol queues reserve conservatively; invalid capacity disables wrappers without admitting a group")

test=fixture();test.current.settings={encounter=8,patrol=8}
test.current.players[3]={unit=3,x=200,y=0,z=0};test.current.players[4]={unit=4,x=300,y=0,z=0}
test.current.zones[3]=test.current.zones[2];test.current.zones[4]=test.current.zones[2]
for region_index=1,4 do
    for group_index=1,4 do assert(test.patrol:spawn_patrol(patrol_entry(test,(region_index-1)*100))) end
    assert(not test.patrol:spawn_patrol(patrol_entry(test,(region_index-1)*100)))
end
assert(test.patrol.num_queued_enemies==32)
assert(test.current.regional_detail():find(";regional_caps:8/32;global_cap:240;patrol_caps:8/32",1,true))
test.current.settings={encounter=2,patrol=2}
assert(not test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(test.patrol.num_queued_enemies==32)
print("PASS configured eight means two per region, eight total; lowering config stops new admission without deleting pending spawns")

test=fixture();test.current.settings={encounter=8,patrol=2};test.current.players[2].x=0;test.current.zones={}
test.owner:start_encounter(Vector3(0,0,0));local configured_wave=test.owner.selected_waves[1]
for identifier=51,56 do test.positions[identifier]={x=0,y=0,z=0};test.owner.enemies[#test.owner.enemies+1]={unit=identifier} end
assert(test.owner:can_spawn(configured_wave))
test.positions[57]={x=0,y=0,z=0};test.owner.enemies[7]={unit=57}
assert(not test.owner:can_spawn(configured_wave))
assert(test.current.regional_detail():find(";regional_caps:8/8;global_cap:60;patrol_caps:4/4",1,true))
assert(test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(not test.patrol:spawn_patrol(patrol_entry(test,0)))
print("PASS high multiplier gives a single screen its configured regional allowance, with independent encounter and patrol settings")

test=fixture();test.current.settings={encounter=1,patrol=1}
assert(test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(test.patrol:spawn_patrol(patrol_entry(test,0)))
assert(not test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(test.current.regional_detail():find("patrol_gate:2:global_patrol",1,true))
test.current.settings={encounter=5,patrol=5}
assert(test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(not test.patrol:spawn_patrol(patrol_entry(test,100)))
assert(test.current.regional_detail():find(";regional_caps:5/10;global_cap:75;patrol_caps:5/10",1,true))
print("PASS total one limits separated regions; five yields 1.25 per region, with integral group admission and no rounding up")

test=fixture();test.stop();test.wave.events[1].delay=2
test.owner:start_encounter(Vector3(100,0,0));test.owner:update(0.1)
assert(test.owner.selected_waves==nil and #test.owner.active_events==1 and #test.queued==0)
test.owner:update(3)
assert(#test.queued==0 and test.owner.active_events[1].duration==0.1)
test.advance(4);test.owner:start_encounter(Vector3(0,0,0));test.owner:update(3)
assert(#test.queued==2 and test.queued[1].position.x==100 and test.queued[2].position.x==0)
print("PASS original bytecode reproduces stalled remote delayed event resumed by a new local alarm")

test=fixture();test.wave.events[1].delay=2
test.owner:start_encounter(Vector3(100,0,0));test.owner:update(0.1)
assert(test.owner.selected_waves==nil and #test.owner.active_events==1 and #test.queued==0)
test.owner:update(3)
assert(#test.queued==1 and test.queued[1].position.x==100,"delayed remote wave must progress without another alarm")
assert(test.owner.selected_waves==nil and #test.owner.active_events==0 and test.owner.next_wave_id==1)
test.owner:update(3);assert(#test.queued==1)
test.advance(4);test.owner:start_encounter(Vector3(0,0,0));test.owner:update(0.1);test.owner:update(3)
assert(#test.queued==2 and test.queued[2].position.x==0)
print("PASS delayed regional event progresses independently, once, at its own origin; next alarm stays local")

test=fixture();test.wave.events[1].delay=1
test.wave.events[1].groups={{group="heavy",active=true},{group="heavy",active=true,delay=3}}
test.owner.wave_sizes[test.wave]=4
test.owner:start_encounter(Vector3(100,0,0));test.owner:update(0.1)
test.owner:update(1.1);assert(#test.queued==1 and test.owner.selected_waves==nil)
test.owner:update(1);assert(#test.queued==1)
test.owner:update(2.1);assert(#test.queued==2 and #test.owner.active_events==0)
assert(test.queued[1].data.wave_id==test.queued[2].data.wave_id and test.owner.next_wave_id==1)
assert(test.queued[1].position.x==100 and test.queued[2].position.x==100)
assert(test.current.encounter_trace[1]:find("alarm=1",1,true))
assert(test.current.encounter_trace[4]:find("queued alarm=1 wave=0 origin=100.00",1,true))
print("PASS final wave retains per-group delays and source trace without adding or duplicating waves")

test=fixture();test.wave.events[1].delay=1
test.owner:start_encounter(Vector3(100,0,0));test.owner:update(0.1)
test.owner.selected_waves={};local empty=test.owner.selected_waves
test.owner.spawn_manager.queue_group_spawn=function() error("fixture_spawn_failure") end
test.owner:update(2)
assert(test.current.error:find("fixture_spawn_failure",1,true))
assert(test.owner.selected_waves==empty and #empty==0 and test.owner.wave_can_spawn_timer==0)
assert(test.owner.next_wave_id==1)
print("PASS event-only update restores temporary queue and admission timer even on a spawn exception")
return fixture
