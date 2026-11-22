return function(current)
    local patrol=current.patrol
    local regions=current.patrol_regions
    local owned,served={},{}
    local serial,next_time=0,0
    local last_count,last_multiplier
    local detail="waiting"
    local function vector(position) return Vector3(position.x,position.y,position.z) end
    local function idle(entry)
        return not entry.spawned and not entry.remove and (entry.remaining_spawns or 0)==0
            and #(entry.units or {})==0
    end
    local function release(entry,info,index)
        if idle(entry) and entry.target_position==info.target then
            if info.replaced then patrol.patrols[index]=info.replaced
            else table.remove(patrol.patrols,index) end
        elseif entry.spawned and entry.target_position==info.target then
            entry.target_position=nil
        end
        owned[entry]=nil
    end
    local function cleanup()
        if patrol.destroyed or type(patrol.patrols)~="table" then owned={};return end
        for index=#patrol.patrols,1,-1 do
            local entry=patrol.patrols[index]
            if owned[entry] then release(entry,owned[entry],index) end
        end
        owned={}
    end
    local function group_size(settings)
        local size=0
        for _,member in ipairs(assert(EnemyGroupSettings[settings.group_info]).units) do size=size+member.amount end
        return size
    end
    local function update()
        local now=Application.time_since_launch()
        if now<next_time then return end
        next_time=now+math.max(0.1,assert(patrol.patrol_spawn_interval))
        local count,region=regions.groups()
        local regional,total=regions.multipliers("patrol",count)
        if last_count and (count<last_count or total<last_multiplier) then cleanup() end
        last_count,last_multiplier=count,total
        local present={}
        for index=#patrol.patrols,1,-1 do
            local entry=patrol.patrols[index]
            present[entry]=true
            local info=owned[entry]
            if info and (now-info.time>=30 or entry.remove or entry.target_position~=info.target
                or (entry.spawned and (entry.remaining_spawns or 0)==0)) then release(entry,info,index) end
        end
        for entry in pairs(owned) do if not present[entry] then owned[entry]=nil end end
        if count==0 or patrol.disabled or patrol.patrols_disabled then detail="disabled";return end
        if count==1 and not next(current.zones) and regional==1 then detail="native_same_screen";return end
        local candidates,seen={},{}
        local retained={}
        for _,player in ipairs(current.players) do
            retained[player.unit]=served[player.unit]
            local target=region(player)
            local candidate=seen[target]
            if not candidate then
                candidate={player=player,target=target,serial=0,players={}}
                candidates[#candidates+1]=candidate;seen[target]=candidate
            end
            candidate.players[#candidate.players+1]=player.unit
            candidate.serial=math.max(candidate.serial,served[player.unit] or 0)
        end
        served=retained
        table.sort(candidates,function(left,right)
            if left.serial~=right.serial then return left.serial<right.serial end
            return left.target<right.target
        end)
        detail="covered_or_capped"
        for _,candidate in ipairs(candidates) do
            local near=0
            for _,entry in ipairs(patrol.patrols) do
                if idle(entry) and entry.position then
                    local position=Vector3Aux.unbox(entry.position)
                    if region(position)==candidate.target and current.patrol_visible(position,-0.5)
                        and regions.admit(position,entry.amount,entry.patrol_settings) then near=near+1 end
                end
            end
            if near<math.max(1,math.ceil(regional)) then
                local center=vector(candidate.player)
                local angle=math.random()*math.pi*2
                local position=current.patrol_point(center+Vector3(math.cos(angle),math.sin(angle),0))
                local choices=patrol.applicable_patrol_groups
                local settings
                if #choices>0 then
                    local first=math.random(#choices)
                    for offset=0,#choices-1 do
                        local choice=choices[(first+offset-1)%#choices+1]
                        if regions.admit(position,group_size(choice),choice) then settings=choice;break end
                    end
                end
                if settings and region(position)==candidate.target then
                    local limit=math.max(1,math.floor(patrol.max_num_patrols*total))
                    local replaced,replace_index
                    if #patrol.patrols>=limit then
                        local farthest=-1
                        for index,entry in ipairs(patrol.patrols) do
                            if idle(entry) and not entry.target_position and not entry.target_unit and not owned[entry]
                                and entry.position and not current.patrol_visible(Vector3Aux.unbox(entry.position),-0.5) then
                                local distance=Vector3.distance(Vector3Aux.unbox(entry.position),center)
                                if distance>farthest then replaced,replace_index,farthest=entry,index,distance end
                            end
                        end
                        if not replaced then detail="pool_busy" end
                    end
                    if #patrol.patrols<limit or replaced then
                        if replaced then table.remove(patrol.patrols,replace_index) end
                        local length=#patrol.patrols
                        local prior_limit=patrol.max_num_patrols
                        patrol.max_num_patrols=math.max(limit,length+1)
                        local ok,problem=pcall(patrol.add_patrol,patrol,position,Vector3.normalize(center-position),nil,settings.group_info)
                        patrol.max_num_patrols=prior_limit
                        local entry=patrol.patrols[length+1]
                        if not ok or not entry then
                            if replaced then table.insert(patrol.patrols,replace_index,replaced) end
                            if not ok then error(problem) end
                            detail="native_declined";return
                        end
                        local target=Vector3Aux.box({},center)
                        entry.target_position=target
                        owned[entry]={target=target,replaced=replaced,time=now}
                        local placed=Vector3Aux.unbox(entry.position)
                        if current.patrol_visible(placed,0) or not current.patrol_visible(placed,-0.5)
                            or region(placed)~=candidate.target then
                            release(entry,owned[entry],length+1)
                            detail="invalid_edge";return
                        end
                        serial=serial+1
                        for _,unit in ipairs(candidate.players) do served[unit]=serial end
                        detail=string.format("region_%d:%.1f,%.1f:near_%d:pool_%d/%d",candidate.target,
                            placed.x,placed.y,near+1,#patrol.patrols,limit)
                        return
                    end
                end
            end
        end
    end
    current.supply_tick=update
    current.supply_detail=function() return ";patrol_supply:"..detail end
    return cleanup
end
