-- Protocol 1, carried only by an INACTIVE avatar camera target. Native clients
-- do not consume look_ahead/is_reverse while active=false. No new RPC/schema.
return function()
    local observations={}
    local observed_game
    local function now() return Application.time_since_launch() end
    local function available(current)
        local fields={}
        for _,field in ipairs(current.target.network_fields or {}) do
            if field.write==nil then fields[field.name]=true end
        end
        return fields.active and fields.look_ahead and fields.is_reverse
    end
    local function overlay(current)
        local wire=current.mode_wire
        if not wire or current.target_state.active then return end
        local phase=math.floor(now()/0.5)%4
        current.target_state.look_ahead=8+phase*2+(wire.mode==3 and 1 or 0)
        current.target_state.is_reverse=true
    end
    local function restore(current)
        local wire=current.mode_wire
        if not wire then return end
        current.target_state.look_ahead=wire.look_ahead
        current.target_state.is_reverse=wire.is_reverse
        current.mode_wire=nil
    end
    return {
        restore=restore,
        command=function(current,native,controller,unit,context,command,...)
            -- Preserve the engine's latest intent, never save our own carrier.
            local wire=current.mode_wire
            if wire then
                current.target_state.look_ahead=wire.look_ahead
                current.target_state.is_reverse=wire.is_reverse
            end
            local result=native(controller,unit,context,command,...)
            if wire then
                wire.look_ahead=current.target_state.look_ahead
                wire.is_reverse=current.target_state.is_reverse
                overlay(current)
            end
            return result
        end,
        publish=function(current,mode)
            if not available(current) then return false end
            if mode==0 or current.target_state.active then restore(current);return false end
            if not current.mode_wire then
                current.mode_wire={look_ahead=current.target_state.look_ahead,is_reverse=current.target_state.is_reverse}
            end
            current.mode_wire.mode=mode
            overlay(current)
            -- Native replication handles ownership and local slave copying.
            current.target_controller.replicator:write_fields(current.target)
            return true
        end,
        read=function(game,unit)
            if observed_game~=game then observations={};observed_game=game end
            local groups=game.entity_manager.component_name_to_contexts
            local group=groups.camera_target
            local context=group and group.slave and group.slave[unit]
            local state=context and context.state
            local value=state and state.look_ahead
            local owner=EntityAux.owner(unit)
            local time=now()
            if not state or state.active~=false or state.is_reverse~=true or type(value)~="number"
                or value<8 or value>15 or math.abs(value-math.floor(value+0.5))>0.04 then
                observations[unit]=nil;return 0
            end
            value=math.floor(value+0.5)
            local phase=math.floor((value-8)/2)
            local mode=value%2==1 and 3 or 1
            local previous=observations[unit]
            if not previous or previous.context~=context or previous.state~=state or previous.owner~=owner
                or time-previous.changed>2 then
                observations[unit]={context=context,state=state,owner=owner,phase=phase,changed=time,steps=0,mode=mode}
                return 0
            end
            if phase~=previous.phase then
                local advance=(phase-previous.phase)%4
                if advance==1 or advance==2 then previous.steps=math.min(2,previous.steps+1)
                else previous.steps=0 end
                previous.phase=phase;previous.changed=time
            end
            previous.mode=mode
            -- A frozen marker or one coincidental field value is not consent.
            return previous.steps>=2 and mode or 0
        end,
    }
end
