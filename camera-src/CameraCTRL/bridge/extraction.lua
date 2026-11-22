-- Correct presence checks only on locally authoritative extraction beacons.
return function(host)
    local record
    local resource="ExtractBeaconComponent.update_masters"
    local function cleanup()
        if record then
            if record.class.update_masters==record.wrapper then rawset(record.class,"update_masters",record.prior) end
            host:release("camera",resource);record=nil
        end
    end
    return {tick=function(enabled)
        local machine=Boot and Boot.state_machine
        local game=machine and machine.current_state_name=="game" and machine.state
        if record and (not enabled or game~=record.game) then cleanup() end
        if not enabled or not game then return end
        if record then return record.error end
        local class=ExtractBeaconComponent
        if not class or type(class.update_masters)~="function" then return end
        local current={game=game,class=class,prior=rawget(class,"update_masters"),native=class.update_masters}
        current.wrapper=function(controller,contexts,dt,...)
            if current.error or Boot.state_machine.state~=game then return current.native(controller,contexts,dt,...) end
            -- Keep native completion, cancellation, networking and timers. Only
            -- this controller instance's no-argument distance helper is scoped.
            for unit,ctx in pairs(contexts) do
                if not EntityAux.has_component_master(unit,controller.name) then
                    current.native(controller,{[unit]=ctx},dt,...)
                else
                    local prior=rawget(controller,"get_center_of_players")
                    local native=controller.get_center_of_players
                    controller.get_center_of_players=function(owner,...)
                        if owner~=controller then return native(owner,...) end
                        local closest,distance
                        local origin=Unit.world_position(unit,0)
                        for character in pairs(controller.entity_manager:get_slave_entities("character")) do
                            local health=Unit.alive(character) and EntityAux.state(character,"health")
                            if health and not health.is_dead then
                                local p=Unit.world_position(character,0)
                                local horizontal=Vector3(p.x,p.y,0)
                                local d=Vector3.distance(horizontal,origin)
                                if not distance or d<distance then closest,distance=horizontal,d end
                            end
                        end
                        -- Preserve the native no-living-character behavior.
                        return closest
                    end
                    local ok,problem=pcall(current.native,controller,{[unit]=ctx},dt,...)
                    rawset(controller,"get_center_of_players",prior)
                    if not ok then current.error=tostring(problem);error(problem) end
                end
            end
        end
        assert(host:claim("camera",resource),"hook_busy:"..resource)
        record=current;class.update_masters=current.wrapper
    end}
end
