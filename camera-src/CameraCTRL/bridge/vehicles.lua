return function(modes)
    local record
    local function context(current,unit,name)
        local group=current.game.entity_manager.component_name_to_contexts[name]
        return group and group.master and EntityAux.has_component_master(unit,name) and group.master[unit]
    end
    local function valid(current,r)
        local machine=Boot and Boot.state_machine
        return machine and machine.current_state_name=="game" and machine.state==current.game
            and r and r.game==current.game and Unit.alive(r.unit)
            and context(current,r.unit,"camera_target")==r.target
            and context(current,r.unit,"mover")==r.mover
            and r.target.state==r.target_state and r.mover.state==r.mover_state
    end
    local function publish(current,r,active,limit)
        local changed=r.target_state.active~=active or r.mover_state.keep_inside_screen~=limit
        if r.target_state.active~=active then
            current.target_native(current.target_controller,r.unit,r.target,active and "activate" or "deactivate")
        end
        if r.mover_state.keep_inside_screen~=limit then
            current.mover_native(current.mover_controller,r.unit,r.mover,"keep_inside_screen",limit)
        end
        if changed then current.target_controller.replicator:write_fields(r.target) end
        r.active,r.limit=active,limit
    end
    local function occupants(current,unit)
        local group=current.game.entity_manager.component_name_to_contexts.seat
        local seats=group and ((group.master or {})[unit] or (group.slave or {})[unit])
        return seats and seats.state.seated_units
    end
    local function restore(current)
        if valid(current,record) then
            local seated=occupants(current,record.unit)
            local active=record.original_active
            -- Native VehicleComponent deactivates a driverless target. While
            -- our target is inactive its native branch is skipped, so do not
            -- briefly reactivate the abandoned vehicle during restoration.
            if type(seated)=="table" and not Unit.alive(seated[1]) then active=false end
            publish(current,record,active,record.original_limit)
        end
        record=nil
    end
    local function safe(current,unit)
        local other=false
        for target in pairs(current.manager.targets or {}) do
            if target~=unit and target~=current.unit and Unit.alive(target) then other=true;break end
        end
        if not other then return true end
        return current.manager:is_position_inside_frustum(Unit.world_position(unit,0),0.12,0.12,0.12,0.12)
    end
    return {
        restore=restore,
        target_command=function(current,unit,ctx,command)
            if valid(current,record) and unit==record.unit and ctx==record.target
                and (command=="activate" or command=="deactivate") then
                record.original_active=command=="activate"
                if record.active==false and command=="activate" then return "deactivate" end
            end
            return command
        end,
        mover_command=function(current,unit,ctx,command,value)
            if valid(current,record) and unit==record.unit and ctx==record.mover and command=="keep_inside_screen" then
                record.original_limit=value
                return record.limit
            end
            return value
        end,
        tick=function(current,seat,mask)
            if record and not valid(current,record) then record=nil end
            if record and record.unit~=seat then restore(current) end
            if not seat then return nil end
            local seated=occupants(current,seat)
            if type(seated)~="table" then restore(current);return "vehicle_waiting_seats" end
            if seated[1]~=current.unit then restore(current);return "vehicle_passenger" end
            local target=context(current,seat,"camera_target")
            local mover=context(current,seat,"mover")
            if not target or not mover or not context(current,seat,"vehicle") then return "vehicle_waiting_owner" end
            if not record then
                record={unit=seat,game=current.game,target=target,mover=mover,target_state=target.state,mover_state=mover.state,
                    original_active=target.state.active,original_limit=mover.state.keep_inside_screen,
                    active=target.state.active,limit=mover.state.keep_inside_screen}
            end
            local all_view,all_unlock,count=true,true,0
            for _,occupant in pairs(seated) do
                if occupant and Unit.alive(occupant) then
                    count=count+1
                    local mode=occupant==current.unit and mask or modes.read(current.game,occupant)
                    all_view=all_view and mode>0
                    all_unlock=all_unlock and mode==3
                end
            end
            all_view=all_view and count>0
            all_unlock=all_view and all_unlock
            local active=not all_view and record.original_active
            local limit=not all_unlock
            -- Do not reactivate a shared target while far away. Keep the last
            -- private state until the driver returns; never teleport the car.
            if record.active==false and (active or (record.limit==false and limit)) and not safe(current,seat) then
                publish(current,record,false,false)
                return "vehicle_return_to_team"
            end
            publish(current,record,active,limit)
            if not all_view then return "vehicle_public_passenger" end
            return all_unlock and "vehicle_unlocked" or "vehicle_team_boundary"
        end,
    }
end
