local factory=assert(loadfile(arg[1]))()
local vector_meta={}
local function vector(x,y,z) return setmetatable({x=x,y=y,z=z},vector_meta) end
vector_meta.__add=function(left,right) return vector(left.x+right.x,left.y+right.y,left.z+right.z) end
vector_meta.__sub=function(left,right) return vector(left.x-right.x,left.y-right.y,left.z-right.z) end
Vector3=setmetatable({distance=function(left,right)
    return math.sqrt((left.x-right.x)^2+(left.y-right.y)^2+(left.z-right.z)^2)
end,normalize=function(value)
    local length=math.sqrt(value.x^2+value.y^2+value.z^2)
    return vector(value.x/length,value.y/length,value.z/length)
end},{__call=function(_,...) return vector(...) end})
Vector3Aux={box=function(target,value) target.x=value.x;target.y=value.y;target.z=value.z;return target end,
    unbox=function(value) return vector(value.x,value.y,value.z) end}
Log={info=function() end}
local environment=setmetatable({class=function() return {} end,require=function() end,
    Profiler={start=function() end,stop=function() end}},{__index=_G})
setfenv(assert(loadfile(assert(arg[2]).."/chunk_000cb9db/chunk.ljbc")),environment)()
local function fixture(count,multiplier)
    local now=0
    Application={time_since_launch=function() return now end}
    EnemyGroupSettings={infantry={units={{amount=2}}},tank={units={{amount=1}}}}
    local infantry={group_info="infantry",speed_wander=1}
    local tank={group_info="tank",speed_wander=1}
    local patrol={patrols={},max_num_patrols=30,patrol_spawn_interval=2,
        applicable_patrol_groups={infantry,tank},add_patrol=environment.PatrolManager.add_patrol,
        level={get_closest_position_on_level=function(_,position) return position end}}
    local players={}
    for index=1,count do players[index]={unit=index,x=(index-1)*100,y=0,z=0} end
    local current={patrol=patrol,players=players,zones={[1]={}}}
    local blocked={}
    local admitted=0
    local function region(position)
        local selected,distance
        for index,player in ipairs(players) do
            local delta=math.abs(position.x-player.x)
            if not distance or delta<distance then selected,distance=index,delta end
        end
        return selected
    end
    current.patrol_regions={groups=function() return #players,region end,
        multipliers=function()
            local regional=math.max(1,multiplier/4)
            return regional,math.min(multiplier,math.max(1,#players)*regional)
        end,
        admit=function(position,size,settings)
            admitted=admitted+1
            assert(size==EnemyGroupSettings[settings.group_info].units[1].amount)
            return not blocked[region(position)] and settings.group_info~="tank"
        end}
    current.patrol_point=function(position)
        local center=players[region(position)]
        return vector(center.x+12,center.y,0)
    end
    current.patrol_visible=function(position,margin)
        local center=players[region(position)]
        return math.abs(position.x-center.x)<=10-20*margin and math.abs(position.y-center.y)<=10-20*margin
    end
    local cleanup=factory(current)
    return {current=current,patrol=patrol,players=players,blocked=blocked,cleanup=cleanup,
        advance=function() now=now+2;current.supply_tick() end,admissions=function() return admitted end,
        set_multiplier=function(value) multiplier=value end}
end
local test=fixture(4,4)
for index=1,30 do test.patrol:add_patrol(vector(1000+index,1000,0),vector(1,0,0),nil,"infantry") end
test.current.supply_tick()
assert(#test.patrol.patrols==31 and test.patrol.max_num_patrols==30)
test.current.supply_tick();assert(#test.patrol.patrols==31)
for index=1,3 do test.advance() end
assert(#test.patrol.patrols==34)
for index=31,34 do
    local entry=test.patrol.patrols[index]
    assert(entry.position.x==(index-31)*100+12 and entry.target_position.x==(index-31)*100)
    assert(entry.patrol_settings.group_info=="infantry" and entry.amount==2 and entry.direction.x==-1)
end
test.advance();assert(#test.patrol.patrols==34)
assert(test.admissions()>0)
test.cleanup();assert(#test.patrol.patrols==30)
print("PASS native add_patrol supplies four separate regions fairly, skips capped types, keeps cadence and restores unused entries")

test=fixture(1,4)
local originals={}
for index=1,30 do test.patrol:add_patrol(vector(1000+index,1000,0),vector(1,0,0),nil,"infantry");originals[index]=test.patrol.patrols[index] end
test.current.supply_tick()
assert(#test.patrol.patrols==30 and test.patrol.patrols[30].position.x==12 and test.patrol.max_num_patrols==30)
test.cleanup()
local found={}
for _,entry in ipairs(test.patrol.patrols) do found[entry]=true end
for _,entry in ipairs(originals) do assert(found[entry]) end
print("PASS full native pool recycles only an idle distant virtual route and cancellation restores its original record")

test=fixture(1,4)
test.current.zones={}
test.current.supply_tick();assert(#test.patrol.patrols==0)
test.current.zones={[1]={}};test.advance();assert(#test.patrol.patrols==1)
test.patrol.patrols[1].spawned=true
test.patrol.patrols[1].remaining_spawns=2
test.patrol.patrols[1].units={{unit=50}}
test.cleanup()
assert(#test.patrol.patrols==1 and test.patrol.patrols[1].units[1].unit==50)
assert(test.patrol.patrols[1].remaining_spawns==2 and not test.patrol.patrols[1].target_position)
print("PASS native same-screen baseline stays unchanged and cancellation never removes spawned or queued units")

test=fixture(2,4)
test.current.supply_tick()
local alarm_target={x=80,y=0,z=0}
test.patrol.patrols[1].target_position=alarm_target
test.cleanup();assert(#test.patrol.patrols==1 and test.patrol.patrols[1].target_position==alarm_target)
test=fixture(2,4)
test.blocked[1]=true
test.current.supply_tick()
assert(#test.patrol.patrols==1 and test.patrol.patrols[1].position.x==112)
test.patrol.disabled=true;test.advance();assert(#test.patrol.patrols==1)
test.cleanup()
print("PASS native alarm replacements survive cleanup, saturated regions do not starve other regions, disabled tasks add nothing")

test=fixture(2,4)
test.current.supply_tick();test.advance()
assert(#test.patrol.patrols==2)
table.remove(test.players,2)
test.advance()
assert(#test.patrol.patrols==1 and test.patrol.patrols[1].position.x==12)
test.cleanup()
test=fixture(2,12)
for index=1,6 do test.advance() end
assert(#test.patrol.patrols==6)
test.set_multiplier(4);test.advance()
assert(#test.patrol.patrols==1)
test.cleanup()
print("PASS region merge and lower multiplier release only owned virtual reserves before using the new regional target")

test=fixture(1,4)
for index=1,30 do test.patrol:add_patrol(vector(1000+index,1000,0),vector(1,0,0),nil,"infantry") end
local original=test.patrol.patrols[30]
test.patrol.add_patrol=function() error("native_add_failure") end
assert(not pcall(test.current.supply_tick))
assert(test.patrol.max_num_patrols==30 and #test.patrol.patrols==30 and test.patrol.patrols[30]==original)
test=fixture(1,4)
test.patrol.level.get_closest_position_on_level=function() return vector(0,0,0) end
test.current.supply_tick()
assert(#test.patrol.patrols==0 and test.current.supply_detail():find("invalid_edge",1,true))
print("PASS native errors restore the temporary pool ceiling and recycled route, terrain-clamped visible candidates are rejected")

test=fixture(2,4)
test.current.supply_tick()
test.patrol.destroyed=true
test.patrol.patrols=nil
test.cleanup()
test.cleanup()
assert(test.patrol.patrols==nil)
print("PASS mission teardown discards owned routes without reading or recreating destroyed patrol tables")
