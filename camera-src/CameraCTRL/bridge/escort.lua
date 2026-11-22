return function(host,transfer,modes,camera)
    local record,problem
    local remote_protection_radius=30
    local resource="NpcEscortComponent.update_derived_master"
    local function game_now()
        local machine=Boot and Boot.state_machine
        return machine and machine.current_state_name=="game" and machine.state or nil
    end
    local function cleanup()
        if not record then return end
        if record.class.update_derived_master==record.wrapper then
            rawset(record.class,"update_derived_master",record.prior)
        end
        host:release("camera",resource)
        record=nil
    end
    local function allowance(current,unit,context,dt,full)
        if transfer then transfer.prepare(unit,context) end
        if not full or game_now()~=current.game or not Unit.alive(unit)
            or not EntityAux.has_component_master(unit,"npc_escort") then return end
        local state=context.state
        if not state or state.finished or state.in_goal then return end
        local npc_health=EntityAux.state(unit,"health")
        if not npc_health or npc_health.is_dead then return end
        local manager=CameraManager
        if not manager or manager.state~="follow" or not manager.viewport or not manager.ground_position then return end
        local position=Unit.world_position(unit,0)
        local function public_contains(point)
            return manager.viewport:world_to_viewport(point).y>0
                and manager:is_position_inside_frustum(point,0,0,0,0)
        end
        local covered=public_contains(position) or (camera and camera.contains(current.game,position))
        if not covered and modes then
            for _,player in ipairs(current.game.players or {}) do
                local go=player.player_go
                local avatar=go and go:exists() and not go:owned() and go:get("avatar_unit")
                local health=avatar and Unit.alive(avatar) and EntityAux.state(avatar,"health")
                if health and not health.is_dead and modes.read(current.game,avatar)>0 then
                    local groups=current.game.entity_manager.component_name_to_contexts
                    local characters=groups.character
                    local character=characters and ((characters.master or {})[avatar] or (characters.slave or {})[avatar])
                    local seat=character and character.state.current_seat_unit
                    local center=Unit.world_position(seat and Unit.alive(seat) and seat or avatar,0)
                    local delta=position-center
                    if delta.x*delta.x+delta.y*delta.y+delta.z*delta.z<=remote_protection_radius*remote_protection_radius then
                        covered=true;break
                    end
                end
            end
        end
        if not covered then return end
        local settings=context.settings and context.settings.npc_escort_info
        local limit=settings and settings.outside_screen_kill_time
        local elapsed=dt+(state.full_update_dt or 0)
        if type(limit)~="number" or limit<0 or limit~=limit or limit==math.huge
            or type(state.outside_screen_timer)~="number" or elapsed<0 or elapsed~=elapsed or elapsed==math.huge then return end
        return state,limit,elapsed
    end
    local function sync_flags(current,unit,context)
        -- Stop clears follow_unit before the next derived update. Replication
        -- must not depend on having a follower or receiving a full AI update.
        if game_now()~=current.game or not Unit.alive(unit)
            or not EntityAux.has_component_master(unit,"npc_escort") then return end
        local manager=current.game.entity_manager
        local groups=manager and manager.component_name_to_contexts
        local group=groups and groups.npc_escort
        if not group or not group.master or group.master[unit]~=context then return end
        local slave=group.slave and group.slave[unit]
        local state=context.state
        if not state or not slave or not slave.state then return end
        for _,field in pairs(context.network_fields or {}) do
            local name=field.name
            if (name=="following_unit" or name=="activated" or name=="in_goal")
                and type(state[name])=="boolean" and state[name]~=slave.state[name] then
                -- Let BaseComponent perform both network and local slave copies.
                state.dirty=true
                return
            end
        end
    end
    return {tick=function()
        local game=game_now()
        if record and (record.game~=game or record.class~=NpcEscortComponent) then cleanup() end
        if not game then problem=nil;return end
        if modes then
            for _,player in ipairs(game.players or {}) do
                local go=player.player_go
                local unit=go and go:exists() and not go:owned() and go:get("avatar_unit")
                if unit and Unit.alive(unit) then modes.read(game,unit) end
            end
        end
        if record then return problem end
        local class=NpcEscortComponent
        if type(class)~="table" or type(class.update_derived_master)~="function" then return end
        if not host:claim("camera",resource) then return "hook_busy:"..resource end
        local current={game=game,class=class,prior=rawget(class,"update_derived_master"),native=class.update_derived_master}
        current.wrapper=function(controller,unit,context,dt,full,...)
            local entering_state=context.state
            local was_in_goal=entering_state and entering_state.in_goal
            local ok,state,limit,elapsed=pcall(allowance,current,unit,context,dt,full)
            if not ok then problem=tostring(state);state=nil end
            local previous,temporary
            if state then
                previous=state.outside_screen_timer
                temporary=limit+elapsed
                state.outside_screen_timer=temporary
            end
            local function finish(success,...)
                if state and context.state==state then
                    if not success or state.outside_screen_timer==temporary then state.outside_screen_timer=previous
                    elseif state.outside_screen_timer==temporary-elapsed then state.outside_screen_timer=limit end
                    if success then state.dirty=true end
                end
                if not success then error((...)) end
                -- The approach joint is outside the shelter. Once the native logic
                -- accepts arrival, retain the shelter centre for the final walk-in,
                -- even when that destination is outside the shared camera.
                if entering_state and context.state==entering_state and not was_in_goal
                    and entering_state.in_goal and entering_state.goal_unit
                    and Unit.alive(entering_state.goal_unit) then
                    entering_state.goal_joint_position=Vector3Aux.box(
                        entering_state.goal_joint_position or {},Unit.world_position(entering_state.goal_unit,0))
                end
                local ok,message=pcall(sync_flags,current,unit,context)
                if not ok then problem=tostring(message) end
                return ...
            end
            return finish(pcall(current.native,controller,unit,context,dt,full,...))
        end
        record=current
        class.update_derived_master=current.wrapper
    end}
end
