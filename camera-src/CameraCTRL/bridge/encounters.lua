return function(current,hook,active)
    local owner=current.encounter
    local origins=setmetatable({},{__mode="k"})
    local originals={}
    local wave_origins={}
    local pending={}
    local alarms={}
    local context
    local context_alarm,alarm_serial=nil,0
    current.encounter_trace={}
    current.encounter_trace_serial=0
    local services,service_serial={},0
    local last_cost,last_budget=0,0
    local patrol_context
    local patrol_gate="not_checked"
    local function copy(position) return {x=position.x,y=position.y,z=position.z} end
    local function vector(position) return Vector3(position.x,position.y,position.z) end
    local function trace(stage,origin,position,identifier)
        current.encounter_trace_serial=current.encounter_trace_serial+1
        local function coordinates(value)
            return value and string.format("%.2f,%.2f,%.2f",value.x,value.y,value.z) or "-"
        end
        local entries=current.encounter_trace
        entries[#entries+1]=string.format("%d t=%.3f %s alarm=%s wave=%s origin=%s position=%s",
            current.encounter_trace_serial,Application.time_since_launch(),stage,
            tostring(origin and origin.alarm or "-"),tostring(identifier or "-"),coordinates(origin),coordinates(position))
        if #entries>96 then table.remove(entries,1) end
    end
    local function multipliers(kind,count)
        local configured=(current.settings or {encounter=2,patrol=4})[kind]
        local host=rawget(_G,'HelldiversBridgeHost')
        local policy=host and host.enemy_policy
        if policy and policy.abi==1 and policy.game==current.game
            and type(policy.expires)=='number' and policy.expires>=Application.time_since_launch()
            and type(policy[kind])=='number' and policy[kind]>=1 and policy[kind]<=100 then
            configured=policy[kind]
        end
        local regional=math.max(1,configured/4)
        return regional,math.min(configured,math.max(1,count)*regional)
    end
    local function encounter_expanded(count)
        local regional=multipliers("encounter",count)
        return count>1 or regional>1
    end
    local function admission_expanded(count)
        local patrol=multipliers("patrol",count)
        return encounter_expanded(count) or patrol>1
    end
    local function tag(wave,position)
        local tagged={}
        for key,value in pairs(wave) do tagged[key]=value end
        assert(owner.wave_sizes[wave],"missing_wave_size")
        owner.wave_sizes[tagged]=owner.wave_sizes[wave]
        originals[tagged]=wave;origins[tagged]=copy(position)
        origins[tagged].alarm=context_alarm
        return tagged
    end
    local function groups()
        local players=current.players
        local roots={}
        local function root(index)
            while roots[index]~=index do index=roots[index] end
            return index
        end
        for index in ipairs(players) do roots[index]=index end
        for left=1,#players do
            for right=left+1,#players do
                local first,second=players[left],players[right]
                local zone=current.zones[first.unit] or current.zones[second.unit]
                local overlap=not zone
                if zone then
                    local first_point=zone.viewport:world_to_viewport(vector(first))
                    local second_point=zone.viewport:world_to_viewport(vector(second))
                    local size=current.manager.screen_resolution
                    overlap=first_point.y>0 and second_point.y>0
                        and math.abs(first_point.x-second_point.x)<=size.width
                        and math.abs(first_point.z-second_point.z)<=size.height
                end
                if overlap then roots[root(right)]=root(left) end
            end
        end
        local count,seen=0,{}
        for index in ipairs(players) do
            roots[index]=root(index)
            if not seen[roots[index]] then count=count+1;seen[roots[index]]=true end
        end
        local function region(position)
            if not position then return nil end
            local nearest,distance
            for index,player in ipairs(players) do
                local delta=(position.x-player.x)^2+(position.y-player.y)^2
                if not distance or delta<distance then nearest,distance=roots[index],delta end
            end
            return nearest
        end
        return count,region
    end
    local function wrap(key,make,object)
        object=object or owner
        return hook(current,object,key,function(native)
            local wrapped=make(native)
            return function(self,...)
                if not active(current) then return native(self,...) end
                local function finish(ok,...)
                    if not ok then current.error="regional_"..key..":"..tostring((...));return end
                    return ...
                end
                return finish(pcall(wrapped,self,...))
            end
        end,(object==owner and "EncounterManager" or "PatrolManager")..".regional."..key)
    end
    local function positioned(position,callback,...)
        local previous=owner.encounter_position
        owner.encounter_position=Vector3Aux.box({},vector(position))
        local function finish(ok,...)
            owner.encounter_position=previous
            if not ok then error((...)) end
            return ...
        end
        return finish(pcall(callback,...))
    end
    local function reserve_cost(region,target)
        local cost,seen=0,{}
        for _,wave in ipairs(owner.selected_waves or {}) do
            local position=origins[wave]
            if not position or region(position)==target then cost=cost+wave.cost end
        end
        local function add(identifier,value,position)
            if identifier and value and not seen[identifier] and (not position or region(position)==target) then
                seen[identifier]=true;cost=cost+value
            end
        end
        for _,event in ipairs(owner.active_events) do
            add(event.wave_id,event.wave_cost,wave_origins[event.wave_id])
        end
        for identifier,request in pairs(pending) do
            if request.count>0 then add(identifier,request.cost,request.position) end
        end
        for _,entry in ipairs(owner.enemies) do
            if entry.unit and Unit.alive(entry.unit) then
                local health=EntityAux.state(entry.unit,"health")
                if not health or not health.is_dead then
                    add(entry.wave_id,entry.wave_cost,Unit.world_position(entry.unit,0))
                end
            end
        end
        return cost
    end
    local function encounter_pending(region,target)
        local tracked,local_pending=0,0
        for _,request in pairs(pending) do
            tracked=tracked+request.count
            if region(request.position)==target then local_pending=local_pending+request.count end
        end
        return local_pending+math.max(0,owner.num_queued_enemies-tracked)
    end
    local function patrol_usage(region,target,settings)
        local patrol=owner.patrol_manager
        local tracked_units,tracked_pending,tracked_groups=0,0,0
        local units,queued,types,virtual=0,0,0,0
        for _,entry in ipairs(patrol.patrols or {}) do
            local belongs=not entry.position or region(Vector3Aux.unbox(entry.position))==target
            if not entry.spawned then
                if belongs then virtual=virtual+1 end
            else
                local remaining=math.max(0,entry.remaining_spawns or 0)
                tracked_pending=tracked_pending+remaining
                if belongs then queued=queued+remaining end
                if settings and entry.patrol_settings.group_info==settings.group_info then
                    tracked_groups=tracked_groups+1
                    if belongs then types=types+1 end
                end
            end
            for _,member in ipairs(entry.units or {}) do
                if not member.is_dead then
                    tracked_units=tracked_units+1
                    if not member.unit or not Unit.alive(member.unit)
                        or region(Unit.world_position(member.unit,0))==target then units=units+1 end
                end
            end
        end
        units=units+math.max(0,(patrol.num_spawned_enemies or 0)-tracked_units)
        queued=queued+math.max(0,patrol:get_num_queued_enemies()-tracked_pending)
        if settings then
            types=types+math.max(0,(patrol.num_spawned_groups_per_type[settings.group_info] or 0)-tracked_groups)
        end
        return units,queued,types,virtual
    end
    local function global_limit(count)
        local base=assert(GameSettings.MAX_NUM_ALLOWED_ENEMIES,"missing_global_cap")
        local _,encounter=multipliers("encounter",count)
        local _,patrol=multipliers("patrol",count)
        return math.floor(base*math.max(encounter,patrol))
    end
    local function entity_capacity(count,region,target,size,local_patrol_pending)
        local global_base=assert(GameSettings.MAX_NUM_ALLOWED_ENEMIES,"missing_global_cap")
        assert(size>=0 and global_base>0,"invalid_capacity")
        local total,local_total=0,0
        for unit in owner.entity_manager:all_slaves_iterator("enemy") do
            total=total+1
            if not Unit.alive(unit) or region(Unit.world_position(unit,0))==target then local_total=local_total+1 end
        end
        if total+owner.num_queued_enemies+owner.patrol_manager:get_num_queued_enemies()+size>global_limit(count) then
            return false,"global_entities"
        end
        local encounter_multiplier=multipliers("encounter",count)
        local patrol_multiplier=multipliers("patrol",count)
        local regional_limit=math.floor(global_base*math.max(encounter_multiplier,patrol_multiplier))
        if local_total+encounter_pending(region,target)+local_patrol_pending+size>regional_limit then
            return false,"regional_entities"
        end
        return true,"allowed"
    end
    local function capacity(count,region,target,wave)
        local size=assert(owner.wave_sizes[wave],"missing_wave_size")
        local encounter_base=assert(owner.max_num_enemies,"missing_encounter_cap")
        assert(encounter_base>0,"invalid_encounter_cap")
        local _,patrol_pending=patrol_usage(region,target)
        if not entity_capacity(count,region,target,size,patrol_pending) then return false end
        local local_encounter=0
        for _,entry in ipairs(owner.enemies) do
            if not entry.unit or not Unit.alive(entry.unit) or region(Unit.world_position(entry.unit,0))==target then
                local_encounter=local_encounter+1
            end
        end
        local queued=owner.num_queued_enemies
        local regional,total=multipliers("encounter",count)
        return #owner.enemies+queued+size<=math.floor(encounter_base*total)
            and local_encounter+encounter_pending(region,target)+size<=math.floor(encounter_base*regional)
    end
    local function service_order(region)
        local latest={}
        for _,entry in ipairs(services) do
            local key=region(entry.position)
            if key and (not latest[key] or latest[key].serial<entry.serial) then latest[key]=entry end
        end
        services={}
        for _,entry in pairs(latest) do services[#services+1]=entry end
        return latest
    end
    assert(type(owner.enemies)=="table" and type(owner.active_events)=="table"
        and type(owner.wave_sizes)=="table","unsupported_encounter_tables")
    local patrol=current.patrol
    if patrol then
        assert(patrol==owner.patrol_manager and type(patrol.patrols)=="table","unsupported_patrol_tables")
        wrap("spawn_patrol",function(native)
            return function(self,entry,...)
                if self~=patrol then return native(self,entry,...) end
                local previous=patrol_context
                patrol_context=Vector3Aux.unbox(entry.position)
                local function finish(ok,...)
                    patrol_context=previous
                    if not ok then error((...)) end
                    return ...
                end
                return finish(pcall(native,self,entry,...))
            end
        end,patrol)
        wrap("can_spawn",function(native)
            return function(self,size,settings,...)
                local count,region=groups()
                local regional,total=multipliers("patrol",count)
                if self~=patrol or not patrol_context or not admission_expanded(count) then return native(self,size,settings,...) end
                local target=region(patrol_context)
                local units,queued,types=patrol_usage(region,target,settings)
                local function result(allowed,reason)
                    patrol_gate=tostring(target)..":"..reason
                    return allowed
                end
                local base=assert(self.max_num_patrol_units,"missing_patrol_cap")
                assert(base>0,"invalid_patrol_cap")
                if settings.max_spawned then
                    if types+1>math.floor(settings.max_spawned*regional) then return result(false,"regional_type") end
                    if (self.num_spawned_groups_per_type[settings.group_info] or 0)+1>math.floor(settings.max_spawned*total) then
                        return result(false,"global_type")
                    end
                end
                if units+queued+size>math.floor(base*regional) then return result(false,"regional_patrol") end
                if self.num_spawned_enemies+self.num_queued_enemies+size>math.floor(base*total) then
                    return result(false,"global_patrol")
                end
                return result(entity_capacity(count,region,target,size,queued))
            end
        end,patrol)
    end
    current.patrol_regions={groups=groups,multipliers=multipliers,usage=patrol_usage,
        admit=function(position,size,settings)
            local previous=patrol_context
            patrol_context=position
            local ok,allowed=pcall(patrol.can_spawn,patrol,size,settings)
            patrol_context=previous
            if not ok then error(allowed) end
            return allowed
        end}
    wrap("count_remaining_encounter",function(native)
        return function(self,...)
            if self~=owner or not active(current) or not context then return native(self,...) end
            local count,region=groups()
            if not encounter_expanded(count) then return native(self,...) end
            local cost=reserve_cost(region,region(context))
            local tracked=0
            for _,request in pairs(pending) do tracked=tracked+request.count end
            if owner.num_queued_enemies>tracked then cost=math.max(cost,native(self,...)) end
            return cost
        end
    end)
    wrap("build_encounter",function(native)
        return function(self,remaining,...)
            if self==owner and active(current) and context then
                local count=groups()
                if encounter_expanded(count) then remaining=self:count_remaining_encounter() end
            end
            local waves=native(self,remaining,...)
            if self==owner and active(current) and context then
                last_cost=remaining;last_budget=self.encounter_difficulty
                local count=groups()
                if encounter_expanded(count) then
                    local result={}
                    for index,wave in ipairs(waves) do
                        result[index]=tag(wave,context)
                    end
                    return result
                end
            end
            return waves
        end
    end)
    wrap("start_encounter",function(native)
        return function(self,position,...)
            if self~=owner or not active(current) then return native(self,position,...) end
            local count,region=groups()
            if not encounter_expanded(count) or not position or self.disabled or self.encounters_disabled then
                return native(self,position,...)
            end
            local now=Application.time_since_launch()
            local retained={}
            local blocked=false
            for _,alarm in ipairs(alarms) do
                if now-alarm.time<3 then
                    retained[#retained+1]=alarm
                    if region(alarm.position)==region(position) then blocked=true end
                end
            end
            alarms=retained
            if blocked then return end
            for index,wave in ipairs(self.selected_waves or {}) do
                if not origins[wave] then self.selected_waves[index]=tag(wave,Vector3Aux.unbox(self.encounter_position)) end
            end
            local previous=context
            local previous_alarm=context_alarm
            context=copy(position)
            alarm_serial=alarm_serial+1
            context_alarm=alarm_serial
            context.alarm=context_alarm
            trace("alarm",context,position)
            local timer=self.time_since_last_encounter_started
            self.time_since_last_encounter_started=math.max(timer,3)
            local function finish(ok,...)
                context=previous
                context_alarm=previous_alarm
                if not ok then self.time_since_last_encounter_started=timer;error((...)) end
                alarms[#alarms+1]={position=copy(position),time=now}
                return ...
            end
            return finish(pcall(native,self,position,...))
        end
    end)
    wrap("can_spawn",function(native)
        return function(self,wave,...)
            local position=origins[wave]
            local count,region=groups()
            if self==owner and not position and admission_expanded(count) and self.encounter_position then
                position=Vector3Aux.unbox(self.encounter_position)
            end
            if self==owner and active(current) and position then
                if admission_expanded(count) then
                    if not capacity(count,region,region(position),wave) then return false end
                    local nearest
                    for _,player in ipairs(current.players) do
                        local distance=Vector3.distance(Vector3(player.x,player.y,0),vector(position))
                        nearest=nearest and math.min(nearest,distance) or distance
                    end
                    return nearest~=nil and nearest<=self.remove_enemies_far_away_radius
                end
                return positioned(position,native,self,wave,...)
            end
            return native(self,wave,...)
        end
    end)
    wrap("spawn_group",function(native)
        return function(self,position,group,identifier,cost,...)
            local before=self.num_queued_enemies
            local requested=copy(position)
            local function finish(...)
                if self==owner and wave_origins[identifier] then
                    local request=pending[identifier] or {count=0,cost=cost,position=wave_origins[identifier]}
                    local added=math.max(0,self.num_queued_enemies-before)
                    request.count=request.count+added
                    if added>0 then trace("queued",request.position,requested,identifier) end
                    if request.count>0 then pending[identifier]=request end
                end
                return ...
            end
            return finish(native(self,position,group,identifier,cost,...))
        end
    end)
    local function completed(data,count)
        local request=data and pending[data.wave_id]
        if request then
            request.count=math.max(0,request.count-count)
            if request.count==0 then pending[data.wave_id]=nil end
        end
    end
    wrap("on_entity_spawned",function(native)
        return function(self,unit,path,position,rotation,data,...)
            local function finish(...)
                if self==owner then
                    local request=data and pending[data.wave_id]
                    if request then trace("spawned",request.position,position,data.wave_id) end
                    completed(data,1)
                end
                return ...
            end
            return finish(native(self,unit,path,position,rotation,data,...))
        end
    end)
    wrap("on_group_failed",function(native)
        return function(self,group,data,...)
            local function finish(...)
                if self==owner then
                    local request=data and pending[data.wave_id]
                    if request then trace("failed",request.position,group.position,data.wave_id) end
                    completed(data,#group.members)
                end
                return ...
            end
            return finish(native(self,group,data,...))
        end
    end)
    wrap("add_events",function(native)
        return function(self,wave,position,...)
            local origin=origins[wave]
            if self~=owner or not active(current) or not origin then return native(self,wave,position,...) end
            wave_origins[self.next_wave_id]=copy(origin)
            wave_origins[self.next_wave_id].alarm=origin.alarm
            trace("wave",origin,origin,self.next_wave_id)
            service_serial=service_serial+1
            services[#services+1]={position=copy(origin),serial=service_serial}
            return native(self,wave,vector(origin),...)
        end
    end)
    wrap("update",function(native)
        return function(self,dt,...)
            local delayed_timer
            local previous_waves,event_queue,event_barrier
            if self==owner and active(current) then
                local count,region=groups()
                local waves=self.selected_waves
                if (not waves or #waves==0) and #self.active_events>0 then
                    for _,event in ipairs(self.active_events) do
                        if wave_origins[event.wave_id] then
                            previous_waves=waves
                            event_barrier={}
                            event_queue={event_barrier}
                            self.selected_waves=event_queue
                            waves=event_queue
                            delayed_timer=self.wave_can_spawn_timer
                            self.wave_can_spawn_timer=math.max(delayed_timer,dt+1)
                            break
                        end
                    end
                end
                if not event_queue and waves and #self.active_events>0 then
                    for _,wave in ipairs(waves) do
                        if origins[wave] then
                            delayed_timer=self.wave_can_spawn_timer
                            self.wave_can_spawn_timer=math.max(delayed_timer,dt+1)
                            break
                        end
                    end
                end
                if count>1 and waves and #waves>1 and self.wave_duration<dt then
                    local selected,oldest
                    local latest=service_order(region)
                    for index,wave in ipairs(waves) do
                        local position=origins[wave]
                        if position and #self.active_events==0 and self:can_spawn(wave) then
                            local served=latest[region(position)]
                            local serial=served and served.serial or 0
                            if not oldest or serial<oldest then selected,oldest=index,serial end
                        end
                    end
                    if selected and selected~=1 then table.insert(waves,1,table.remove(waves,selected)) end
                end
            end
            local function finish(ok,...)
                if event_queue then
                    for index=#event_queue,1,-1 do
                        if event_queue[index]==event_barrier then table.remove(event_queue,index) end
                    end
                    if self.selected_waves==event_queue and #event_queue==0 then self.selected_waves=previous_waves end
                end
                if delayed_timer then self.wave_can_spawn_timer=math.max(0,delayed_timer-dt) end
                if not ok then error((...)) end
                if self==owner then
                    local kept={}
                    for _,wave in ipairs(self.selected_waves or {}) do kept[wave]=true end
                    if self.current_wave then kept[self.current_wave]=true end
                    for wave in pairs(originals) do
                        if not kept[wave] then self.wave_sizes[wave]=nil;originals[wave]=nil;origins[wave]=nil end
                    end
                    local identifiers={}
                    for _,event in ipairs(self.active_events) do identifiers[event.wave_id]=true end
                    for identifier in pairs(wave_origins) do
                        if not identifiers[identifier] then wave_origins[identifier]=nil end
                    end
                end
                return ...
            end
            return finish(pcall(native,self,dt,...))
        end
    end)
    current.regional_detail=function()
        local count,region=groups()
        local regional,multiplier=multipliers("encounter",count)
        local patrol_detail=""
        if patrol then
            local seen,regions={},{}
            for _,player in ipairs(current.players) do
                local target=region(player)
                if not seen[target] then
                    seen[target]=true
                    local units,queued,_,virtual=patrol_usage(region,target)
                    regions[#regions+1]=target..":"..units.."/"..queued.."/"..virtual
                end
            end
            local patrol_regional,patrol_total=multipliers("patrol",count)
            patrol_detail=";patrol_caps:"..math.floor(patrol.max_num_patrol_units*patrol_regional).."/"..math.floor(patrol.max_num_patrol_units*patrol_total)
                ..";patrol_regions:"..table.concat(regions,",")..";patrol_gate:"..patrol_gate
        end
        return ";regions:"..count..";regional_cost:"..tostring(last_cost).."/"..tostring(last_budget)
            ..";regional_caps:"..tostring(math.floor(owner.max_num_enemies*regional)).."/"..tostring(math.floor(owner.max_num_enemies*multiplier))
            ..";global_cap:"..tostring(global_limit(count))..patrol_detail
    end
    return function()
        if owner.destroyed or type(owner.wave_sizes)~="table" then return end
        for index,wave in ipairs(owner.selected_waves or {}) do
            if originals[wave] then owner.selected_waves[index]=originals[wave] end
        end
        owner.current_wave=originals[owner.current_wave] or owner.current_wave
        for wave in pairs(originals) do owner.wave_sizes[wave]=nil end
    end
end
