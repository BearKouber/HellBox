return function(host)
    local record,problem
    local resource="InteractorComponent.update_masters"
    local function game_now()
        local machine=Boot and Boot.state_machine
        return machine and machine.current_state_name=="game" and machine.state or nil
    end
    local function own(game)
        local unit,count=nil,0
        for _,player in ipairs(game.players or {}) do
            local go=player.player_go
            if go and go:exists() and go:owned() then unit=go:get("avatar_unit");count=count+1 end
        end
        return count==1 and unit or nil
    end
    local function alive(unit)
        if not unit or not Unit.alive(unit) then return false end
        local health=EntityAux.state(unit,"health")
        return health and not health.is_dead
    end
    local function group(game,name)
        local groups=game.entity_manager and game.entity_manager.component_name_to_contexts
        return groups and groups[name] or {}
    end
    local function context(game,name,unit)
        local contexts=group(game,name)
        return (contexts.master or {})[unit] or (contexts.slave or {})[unit]
    end
    local function contains(list,unit)
        if type(list)~="table" then return false end
        if list[unit] then return true end
        for _,value in pairs(list) do
            if value==unit then return true end
        end
        return false
    end
    local function objective_name(unit)
        return Unit.has_data(unit,"objective_name") and Unit.get_data(unit,"objective_name") or nil
    end
    local function close(unit,player)
        local delta=Unit.world_position(unit,0)-Unit.world_position(player,0)
        if delta.x*delta.x+delta.y*delta.y+delta.z*delta.z>400 then return false end
        local manager=CameraManager
        if not manager or manager.state~="follow" or not manager.viewport or not manager.ground_position then return false end
        local translated=delta+Vector3Aux.unbox(manager.ground_position)
        return manager.viewport:world_to_viewport(translated).y>0
            and manager:is_position_inside_frustum(translated,0,0,0,0)
    end
    local function cleanup()
        if not record then return end
        if record.class.update_masters==record.wrapper then rawset(record.class,"update_masters",record.prior) end
        host:release("camera",resource)
        record=nil
    end
    local function collect(current,player,target,state)
        local name=objective_name(target)
        if not name then return nil,"escort_missing_objective_name" end
        -- Native registration scopes objective_name to the owning level instance.
        -- Separate escort sites can reuse the same name on one mission map.
        local level=Unit.level(target)
        local objective
        local objectives=group(current.game,"objective_escort")
        for _,side in ipairs({"master","slave"}) do
            for unit,entry in pairs(objectives[side] or {}) do
                if Unit.alive(unit) and Unit.level(unit)==level and objective_name(unit)==name and entry.state.mission_state=="pending" then
                    if objective and objective~=unit then return nil,"escort_ambiguous_objective" end
                    objective=unit
                end
            end
        end
        if not objective then return nil,"escort_objective_unavailable" end
        local members,remote={},false
        local contexts=group(current.game,"npc_escort")
        for _,side in ipairs({"master","slave"}) do
            for unit,entry in pairs(contexts[side] or {}) do
                if alive(unit) and Unit.level(unit)==level and objective_name(unit)==name and not entry.state.in_goal then
                    local owner=EntityAux.owner(unit)
                    if owner~=Network.peer_id() then
                        if entry.state.following_unit then return nil,"escort_already_following" end
                        remote=true
                    end
                    members[unit]={owner=owner,attempts=0,time=-math.huge}
                end
            end
        end
        if not members[target] then return nil,"escort_target_unavailable" end
        if not remote and (group(current.game,"objective_escort").master or {})[objective] then return nil end
        -- Distance guards protect migration; already-local groups use native interaction.
        for unit in pairs(members) do
            if not close(unit,player) then return nil,"escort_group_too_far" end
        end
        local now=Application.time_since_launch()
        return {player=player,target=target,interactor=state,objective=objective,members=members,
            objective_request={owner=EntityAux.owner(objective),attempts=0,time=-math.huge},
            expires=now+10,protect_until=now+12}
    end
    local function ready(current,pending)
        local controller=current.game.entity_manager.components.npc_escort
        assert(controller and type(controller.migrate_unit_to_me)=="function","escort_missing_migration_method")
        local objective_controller=current.game.entity_manager.components.objective_escort
        assert(objective_controller and type(objective_controller.migrate_unit_to_me)=="function","escort_missing_objective_migration")
        local objective_owner=EntityAux.owner(pending.objective)
        local request=pending.objective_request
        if objective_owner~=Network.peer_id() and objective_owner~=request.owner then return false,"escort_objective_owner_changed" end
        local objective=(group(current.game,"objective_escort").master or {})[pending.objective]
        if objective_owner~=Network.peer_id() or not objective then
            local now=Application.time_since_launch()
            if objective_owner~=Network.peer_id() and request.attempts<3 and now-request.time>=2 then
                request.time=now;request.attempts=request.attempts+1
                objective_controller:migrate_unit_to_me(pending.objective)
            end
            return false
        end
        if objective.state.mission_state~="pending" then return false,"escort_objective_unavailable" end
        if type(objective.state.npc_units)~="table" then return false end
        local complete=true
        for unit,item in pairs(pending.members) do
            if not alive(unit) or not close(unit,pending.player) then return false,"escort_member_unavailable" end
            local owner=EntityAux.owner(unit)
            if owner~=Network.peer_id() and owner~=item.owner then return false,"escort_owner_changed" end
        end
        for unit,item in pairs(pending.members) do
            local owner=EntityAux.owner(unit)
            local entry=(group(current.game,"npc_escort").master or {})[unit]
            if owner~=Network.peer_id() or not entry
                or not EntityAux.has_component_master(unit,"health") or not entry.state.registered_at_objective
                or entry.state.master~=pending.objective or not contains(objective.state.npc_units,unit) then
                complete=false
                local now=Application.time_since_launch()
                if owner~=Network.peer_id() and item.attempts<3 and now-item.time>=2 then
                    item.time=now;item.attempts=item.attempts+1
                    controller:migrate_unit_to_me(unit)
                end
            end
        end
        return complete
    end
    local function update(current,contexts)
        local player=own(current.game)
        local entry=player and contexts[player]
        local state=entry and entry.state
        if not state then return end
        local pending=current.pending
        local now=Application.time_since_launch()
        if current.retired and now>=current.retired.protect_until then current.retired=nil end
        local target_health=state.interactable_component=="npc_escort" and alive(state.interactable_unit)
            and EntityAux.state(state.interactable_unit,"health")
        if state.enabled and alive(player) and target_health and target_health.is_downed==true then
            if pending then
                pending.protect_until=math.min(pending.protect_until,now+2)
                current.retired=pending
                current.pending=nil
            end
            problem=nil
            return
        end
        if pending and not pending.sent then
            state.do_interact=false
            local objective=context(current.game,"objective_escort",pending.objective)
            if not alive(player) or player~=pending.player or state~=pending.interactor
                or not state.enabled or state.interactable_unit~=pending.target
                or state.interactable_component~="npc_escort"
                or not objective or objective.state.mission_state~="pending"
                or Application.time_since_launch()>=pending.expires then
                current.pending=nil;problem="escort_transfer_cancelled_or_timeout";return
            end
            local complete,reason=ready(current,pending)
            if reason then current.pending=nil;problem=reason;return end
            if complete then
                pending.sent=true
                pending.protect_until=Application.time_since_launch()+2
                state.do_interact=true
                problem=nil
            end
            return
        end
        if pending and Application.time_since_launch()>=pending.protect_until then current.pending=nil end
        if not state.do_interact or not state.enabled or not alive(player)
            or state.interactable_component~="npc_escort" or not alive(state.interactable_unit) then return end
        if pending and pending.sent then state.do_interact=false;return end
        local target=state.interactable_unit
        local candidates=group(current.game,"npc_escort")
        state.do_interact=false
        local request,reason=collect(current,player,target,state)
        if reason then problem=reason;return end
        if not request then state.do_interact=true;problem=nil;return end
        current.pending=request
        problem=nil
        ready(current,request)
    end
    return {
        tick=function(enabled)
            local game=game_now()
            if record and (not enabled or record.game~=game or record.class~=InteractorComponent) then cleanup() end
            if not enabled or not game then problem=nil;return end
            if record then return problem end
            local class=InteractorComponent
            if type(class)~="table" or type(class.update_masters)~="function" then return "escort_missing_interactor" end
            if not host:claim("camera",resource) then return "hook_busy:"..resource end
            local current={game=game,class=class,prior=rawget(class,"update_masters"),native=class.update_masters}
            current.wrapper=function(controller,contexts,...)
                if game_now()==current.game then
                    local ok,message=pcall(update,current,contexts)
                    if not ok then
                        current.pending=nil;problem=tostring(message)
                        local player=own(current.game)
                        local entry=player and contexts[player]
                        if entry and entry.state.interactable_component=="npc_escort" then entry.state.do_interact=false end
                    end
                end
                return current.native(controller,contexts,...)
            end
            record=current;class.update_masters=current.wrapper
        end,
        status=function()
            local pending=record and record.pending
            if not pending then return nil end
            if pending.sent then return "dispatched" end
            local count,total=0,0
            local npc_masters=group(record.game,"npc_escort").master or {}
            for unit in pairs(pending.members) do
                total=total+1
                if npc_masters[unit] then count=count+1 end
            end
            local objective=(group(record.game,"objective_escort").master or {})[pending.objective] and "ready" or "waiting"
            return "waiting:"..count.."/"..total..",objective:"..objective
        end,
        prepare=function(unit,context)
            local current=record
            local pending=current and current.pending
            if current and (not pending or not pending.members[unit]) then pending=current.retired end
            if not pending or game_now()~=current.game or not pending.members[unit]
                or Application.time_since_launch()>=pending.protect_until or not alive(pending.player)
                or own(current.game)~=pending.player or not alive(unit) or not close(unit,pending.player)
                or not EntityAux.has_component_master(unit,"npc_escort") then return end
            if not context or not context.state or not Unit.alive(pending.objective) then return end
            return pending.player
        end
    }
end
