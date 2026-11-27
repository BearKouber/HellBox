local function install()
-- BEGIN GENERATED HOST FACTORY
local get_host = (function()
-- ABI 1. Embedded in each module; get_host installs exactly one dispatcher.
return function()
    local existing = rawget(_G, "HelldiversBridgeHost")
    if existing then
        assert(existing.abi == 1, "bridge_host_abi_mismatch")
        assert(rawget(_G, "update") == existing.dispatch, "bridge_update_replaced")
        return existing
    end
    local native_update = assert(rawget(_G, "update"), "missing_game_update")
    local host = {abi=1, modules={}, order={}, resources={}, errors={}}
    function host:register(id, callbacks)
        assert(type(id)=="string" and id:match("^[a-z][a-z0-9_]*$"), "invalid_module_id")
        assert(not self.modules[id], "duplicate_bridge_module:"..id)
        assert(type(callbacks)=="table", "invalid_callbacks")
        for _, key in ipairs({"pre","post","on_error"}) do
            assert(callbacks[key]==nil or type(callbacks[key])=="function", "invalid_callback:"..key)
        end
        self.modules[id] = callbacks
        self.order[#self.order+1] = id
        table.sort(self.order)
    end
    -- Future modules must claim shared hook sites before replacing a game method.
    -- A claim is an exclusivity check, not a substitute for restoration.
    function host:claim(id, resource)
        assert(self.modules[id], "module_not_registered")
        local owner = self.resources[resource]
        if owner and owner~=id then return false,owner end
        self.resources[resource]=id
        return true
    end
    function host:release(id, resource)
        if self.resources[resource]==id then self.resources[resource]=nil; return true end
        return false
    end
    local function phase(name, dt, order)
        for _, id in ipairs(order) do
            local module=host.modules[id]
            local callback=module[name]
            if callback then
                local ok,problem=pcall(callback,dt)
                if not ok then
                    host.errors[id]=name..":"..tostring(problem):sub(1,256)
                    if module.on_error then pcall(module.on_error,name,problem) end
                end
            end
        end
    end
    host.dispatch=function(dt)
        local order={unpack(host.order)}
        phase("pre",dt,order)
        -- Do not swallow engine failures or update the native simulation twice.
        native_update(dt)
        phase("post",dt,order)
    end
    rawset(_G,"HelldiversBridgeHost",host)
    rawset(_G,"update",host.dispatch)
    return host
end

end)()
-- END GENERATED HOST FACTORY
-- BEGIN GENERATED PEER MODES FACTORY
local peer_modes_factory = (function()
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

end)()
-- END GENERATED PEER MODES FACTORY
-- BEGIN GENERATED VEHICLES FACTORY
local vehicles_factory = (function()
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

end)()
-- END GENERATED VEHICLES FACTORY
-- BEGIN GENERATED EXTRACTION FACTORY
local extraction_factory = (function()
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

end)()
-- END GENERATED EXTRACTION FACTORY
-- BEGIN GENERATED CAMERA FOCUS FACTORY
local camera_focus_factory = (function()
-- Presentation only: plain-number snapshots survive the engine's temporary-vector arena.
return function()
    local center, source, transition, died_at, selected
    local height_pending,height_direction,height_tracking,height_sample,height_stable_at,last_time
    local height_delay,height_tolerance,height_response=0.5,0.03,0.15
    local held={}
    local SNAP=30
    local last_p
    local function reset_height()
        height_pending,height_direction,height_tracking,height_sample,height_stable_at=nil,nil,nil,nil,nil
    end
    local function follow_height(target,now,elapsed)
        local difference=target-center.z
        if not height_tracking then
            if math.abs(difference)<=height_tolerance then reset_height();return center.z end
            local direction=difference>0 and 1 or -1
            if not height_pending or direction~=height_direction then
                height_pending,height_direction=now,direction
            end
            if now-height_pending<height_delay then return center.z end
            height_tracking=true
            height_sample,height_stable_at=target,now
            elapsed=0
        end
        local height=center.z+difference*(1-math.exp(-elapsed/height_response))
        if math.abs(target-height_sample)>height_tolerance then
            height_sample,height_stable_at=target,now
        end
        if now-height_stable_at>=height_delay and math.abs(target-height)<=0.005 then
            reset_height()
            return target
        end
        return height
    end
    local function copy(p) return {x=p.x,y=p.y,z=p.z} end
    local function blend(a,b,t)
        t=math.max(0,math.min(1,t));t=t*t*(3-2*t)
        return {x=a.x+(b.x-a.x)*t,y=a.y+(b.y-a.y)*t,z=a.z+(b.z-a.z)*t}
    end
    return {
        follow=function(id,p,now,ahead,rate)
            local elapsed=last_time and math.max(0,now-last_time) or 0
            if last_time and now<last_time then reset_height();transition=nil end
            last_time=now
            if center and source~=id then
                transition={from=copy(center),time=now}
                reset_height()
            end
            source=id
            -- HellBox 2026-11-19（用户：分屏时自己的镜头跟自己玩一样）：照原版单人镜头（camera_manager.lua follow）——
            -- 目标 = 位置 + 朝向 x 往前多看 + (-1,-1,0)，镜头每秒按 rate（原版 follow_position_interp 0.6）往目标追。
            -- 换载具 / 复活还是作者的 0.5 秒过渡（过渡的终点也是这个目标）；人一帧瞬移超过 SNAP 米直接对准（开车时镜头落后几十米是正常的，不算）。
            local a=ahead or {x=0,y=0,z=0}
            local goal={x=p.x+a.x-1,y=p.y+a.y-1,z=p.z+a.z}
            if transition then
                center=blend(transition.from,goal,(now-transition.time)/0.5)
                if now-transition.time>=0.5 then transition=nil end
            elseif center then
                local dx,dy,dz=goal.x-center.x,goal.y-center.y,goal.z-center.z
                local jx,jy,jz=last_p and p.x-last_p.x or 0,last_p and p.y-last_p.y or 0,last_p and p.z-last_p.z or 0
                if jx*jx+jy*jy+jz*jz>SNAP*SNAP then -- 人 / 载具一帧挪了 SNAP 米以上 = 瞬移
                    center=copy(goal)
                else
                    local k=1-math.exp(-(rate or 0.6)*elapsed)
                    center={x=center.x+dx*k,y=center.y+dy*k,z=center.z+dz*k}
                end
            else center=copy(goal);reset_height() end
            last_p=copy(p)
            return center
        end,
        die=function(now)
            died_at=now;selected=nil;transition=nil;held={}
            reset_height();last_time=nil
        end,
        watch=function(candidates,keys,blocked,now)
            local previous,next_key=false,false
            for _,key in ipairs({'w','a','s','d'}) do
                local down=keys[key]==true
                if down and not held[key] and not blocked then
                    if key=='w' or key=='a' then previous=true else next_key=true end
                end
                held[key]=down
            end
            if now-died_at<2 then return nil,'spectator_wait' end
            if #candidates==0 then selected=nil;return nil,'spectator_no_teammate' end
            local index
            for i,item in ipairs(candidates) do if item.id==selected then index=i;break end end
            index=index or 1
            if previous~=next_key then index=(index-1+(previous and -1 or 1))%#candidates+1 end
            selected=candidates[index].id
            return candidates[index],'spectator_follow'
        end,
        look=function(p)
            if p then center=copy(p);reset_height();last_time=nil end
            return center
        end
    }
end

end)()
-- END GENERATED CAMERA FOCUS FACTORY
-- BEGIN GENERATED VIEW FACTORY
local view_factory = (function()
-- Private viewport geometry. Never mutate the team viewport's rect or limits.
return function(display,team,permille)
    if not team.rect then return end
    local rect={}
    for key,value in pairs(team.rect) do rect[key]=value end
    display.rect=rect
    display.minimum_aspect,display.maximum_aspect=team.minimum_aspect,team.maximum_aspect
    if not permille or permille==0 then return end
    assert(permille==1250 or permille==1333 or permille==1600 or permille==1778,"invalid_personal_aspect")
    local ratio=({[1250]=5/4,[1333]=4/3,[1600]=16/10,[1778]=16/9})[permille]
    local width,height=Application.back_buffer_size()
    assert(width>0 and height>0,"invalid_back_buffer")
    display.minimum_aspect,display.maximum_aspect=ratio,ratio
    if width/height>ratio then
        rect.width,rect.height=height*ratio/width,1
        rect.x,rect.y=(1-rect.width)/2,0
    else
        rect.width,rect.height=1,width/ratio/height
        rect.x,rect.y=0,(1-rect.height)/2
    end
end

end)()
-- END GENERATED VIEW FACTORY
-- BEGIN GENERATED CAMERA FACTORY
local camera_factory = (function()
return function(host,modes,vehicles,focus_factory,view_factory)
    local selected_ratio=0
    local record
    local fault
    local status={applied=0,owned=0,detail="off"}
    local function game_now()
        local machine=Boot and Boot.state_machine
        return machine and machine.current_state_name=="game" and machine.state or nil
    end
    local function own(game)
        local chosen,count=nil,0
        for _,player in ipairs(game.players or {}) do
            local go=player.player_go
            if go and go:exists() and go:owned() then chosen=go;count=count+1 end
        end
        if count~=1 then return nil,"local_players="..count end
        local unit=chosen:get("avatar_unit")
        if not unit or not Unit.alive(unit) then return nil,"waiting_avatar",chosen end
        return unit,nil,chosen
    end
    local function context(game,unit,name)
        local groups=game.entity_manager and game.entity_manager.component_name_to_contexts
        local group=groups and groups[name]
        return group and group.master and EntityAux.has_component_master(unit,name) and group.master[unit]
    end
    local function valid(current)
        return current and game_now()==current.game and Unit.alive(current.unit)
            and own(current.game)==current.unit
            and select(3,own(current.game))==current.player
            and context(current.game,current.unit,"camera_target")==current.target
            and context(current.game,current.unit,"mover")==current.mover
            and current.target.state==current.target_state and current.mover.state==current.mover_state
            and CameraManager==current.manager and current.manager.viewport==current.viewport
    end
    local function scene_valid(current)
        if not current or game_now()~=current.game or CameraManager~=current.manager
            or current.manager.viewport~=current.viewport then return false end
        local _,_,player=own(current.game)
        return player==current.player
    end
    local function dead(game,unit)
        if not unit or not Unit.alive(unit) then return true end
        local groups=game.entity_manager.component_name_to_contexts
        local character=groups.character or {}
        local ctx=(character.master or {})[unit] or (character.slave or {})[unit]
        local state=ctx and ctx.state
        if state and (state.is_dead or (state.health_state and state.health_state.is_dead)) then return true end
        local health=groups.health or {}
        -- is_dead is derived on the display/slave side in this game build.
        for _,side in ipairs({'slave','master'}) do
            local entry=(health[side] or {})[unit]
            if entry and entry.state and entry.state.is_dead==true then return true end
        end
        return false
    end
    local function seat_for(game,unit)
        local character=context(game,unit,"character")
        local seat=character and character.state.current_seat_unit
        if not seat or not Unit.alive(seat) then return nil,false end
        local groups=game.entity_manager.component_name_to_contexts
        local group=groups.vehicle
        local vehicle=group and ((group.master or {})[seat] or (group.slave or {})[seat])
        return seat,not vehicle
    end
    -- A missing master/ambiguous local player is not necessarily a new avatar.
    -- Retain our baseline while synchronization settles, without writing through
    -- stale contexts. Only an unchanged player object and avatar may reclaim it.
    local function recover(current,game,unit)
        if game~=current.game or not Unit.alive(current.unit)
            or CameraManager~=current.manager or current.manager.viewport~=current.viewport then return false end
        local found=false
        for _,player in ipairs(game.players or {}) do
            if player.player_go==current.player then found=true;break end
        end
        if not found or not current.player:exists()
            or current.player:get('avatar_unit')~=current.unit then return false end
        local _,_,player=own(game)
        if unit~=current.unit or player~=current.player then return nil end
        local target=context(game,unit,'camera_target')
        local mover=context(game,unit,'mover')
        if not target or not mover then return nil end
        if not mover.state or type(mover.state.keep_inside_screen)~='boolean' then return nil end
        local controllers=game.entity_manager.components
        local controller=controllers.camera_target
        local replicator=controller and controller.replicator
        local writable=false
        for _,field in ipairs(target.network_fields or {}) do
            if field.name=='active' and field.write==nil then writable=true end
        end
        if not target.go_id or not writable or not replicator or not replicator.network_session
            or not controllers.mover then return nil end
        if target.state~=current.target_state then
            -- An inactive NEW target may belong to a seat/death/transition. We
            -- cannot attribute its inactivity to our old write.
            if not target.state or target.state.active~=true then return nil end
            current.original_active=target.state.active
            current.mode_wire=nil
        end
        if mover.state~=current.mover_state then
            current.original_limit=mover.state.keep_inside_screen
        end
        current.target,current.target_state=target,target.state
        current.mover,current.mover_state=mover,mover.state
        current.target_controller=controller
        current.mover_controller=controllers.mover
        return true
    end
    local function supported(current)
        if current.spectating or not valid(current) or current.manager.state~="follow" then return false end
        local character=context(current.game,current.unit,"character")
        local state=character and character.state
        local seat,unsupported=seat_for(current.game,current.unit)
        return state and not dead(current.game,current.unit)
            and not unsupported
    end
    local function rendered(current)
        if current and current.spectating then
            return scene_valid(current) and current.manager.state=="follow"
                and current.present and Unit.alive(current.display_unit)
        end
        local exiting=current.seat_exit_until and Application.time_since_launch()<current.seat_exit_until
        return supported(current) and (current.original_active or current.seat or exiting) and current.present and Unit.alive(current.display_unit)
    end
    local function candidates(current)
        local result={}
        for _,player in ipairs(current.game.players or {}) do
            local go=player.player_go
            if go and go~=current.player and go:exists() then
                local unit=go:get('avatar_unit')
                if unit and not dead(current.game,unit) then
                    local groups=current.game.entity_manager.component_name_to_contexts
                    local group=groups.character or {}
                    local ctx=(group.master or {})[unit] or (group.slave or {})[unit]
                    local seat=ctx and ctx.state and ctx.state.current_seat_unit
                    result[#result+1]={id=go,unit=unit,focus=seat and Unit.alive(seat) and seat or unit}
                end
            end
        end
        return result
    end
    local function spectator_input(current)
        local keys={}
        if Keyboard and Keyboard.button_index and Keyboard.button then
            for _,key in ipairs({'w','a','s','d'}) do
                local ok,value=pcall(function() return Keyboard.button(Keyboard.button_index(key)) end)
                keys[key]=ok and (value==true or (type(value)=='number' and value>0.5)) or false
            end
        end
        local game=current.game
        return keys,(game.text_chat and game.text_chat.active) or false
    end
    local function hook(current,object,key,make,resource)
        local prior=rawget(object,key)
        local native=assert(object[key],"missing_method:"..key)
        local wrapper=make(native)
        assert(host:claim("camera",resource),"hook_busy:"..resource)
        current.hooks[#current.hooks+1]={object=object,key=key,prior=prior,wrapper=wrapper,resource=resource}
        object[key]=wrapper
        return native
    end
    local function link_particle(current,particle,unit,aspect)
        if not World.are_particles_playing(current.world,particle) then return end
        local transform=Matrix4x4.identity()
        if aspect then
            local width,height=(unit==current.display_unit and current.display or current.viewport):window()
            Matrix4x4.set_element(transform,1,1,(width/height)/(16/9))
        end
        World.link_particles(current.world,particle,unit,0,transform,"destroy")
    end
    local function adopt_environment_particles(current)
        local level=current.manager.generated_level
        local settings=level and EnvironmentAreaSettings and EnvironmentAreaSettings[level.environment_name]
        settings=settings and settings[level.shading_environment]
        for key,particle in pairs(current.manager.camera_particles or {}) do
            local entry=settings and settings[key]
            if not current.particle_links[particle] and entry and entry.camera_particle then
                link_particle(current,particle,current.display_unit,false)
                current.particle_links[particle]={aspect=false}
            end
        end
    end
    local function cleanup(current)
        current.present=false
        if vehicles then vehicles.restore(current) end
        for index=#current.hooks,1,-1 do
            local item=current.hooks[index]
            if item.object[item.key]==item.wrapper then rawset(item.object,item.key,item.prior) end
            host:release("camera",item.resource)
        end
        current.hooks={}
        if game_now()==current.game and Unit.alive(current.viewport.camera_unit) then
            for particle,info in pairs(current.particle_links or {}) do
                link_particle(current,particle,current.viewport.camera_unit,info.aspect)
            end
        end
        if game_now()==current.game and current.initialized and Unit.alive(current.viewport.camera_unit) then
            local controller=current.game.entity_manager.components.character
            local players=controller and controller.players_in_no_strat_zone
            Unit.flow_event(current.viewport.camera_unit,players and next(players) and "on_enter_no_strat_zone" or "on_exit_no_strat_zone")
        end
        if game_now()==current.game and current.display_unit and Unit.alive(current.display_unit) then
            World.destroy_unit(current.world,current.display_unit)
        end
    end
    local function publish(current,value)
        assert(valid(current),"avatar_changed")
        if value and modes then modes.restore(current) end
        local replicator=current.target_controller.replicator
        if current.target_state.active==value and GameSession.game_object_field(replicator.network_session,current.target.go_id,"active")==value then return end
        current.target_native(current.target_controller,current.unit,current.target,value and "activate" or "deactivate")
        assert(current.target_state.active==value,"camera_command_readback")
        replicator:write_fields(current.target)
        assert(GameSession.game_object_field(replicator.network_session,current.target.go_id,"active")==value,"camera_network_readback")
    end
    local function move_limit(current,value)
        assert(valid(current),"avatar_changed")
        if current.mover_state.keep_inside_screen==value then return end
        current.mover_native(current.mover_controller,current.unit,current.mover,"keep_inside_screen",value)
        assert(current.mover_state.keep_inside_screen==value,"mover_command_readback")
    end
    local function other_targets(current)
        local count=0
        for unit in pairs(current.manager.targets or {}) do
            if unit~=current.unit and unit~=current.seat and Unit.alive(unit) then count=count+1 end
        end
        return count
    end
    local function safe_return(current)
        if other_targets(current)==0 then return true end
        return current.manager:is_position_inside_frustum(Unit.world_position(current.seat or current.unit,0),0.12,0.12,0.12,0.12)
    end
    local function visual(current)
        if not rendered(current) then return end
        local manager=current.manager
        if view_factory then view_factory(current.display,current.viewport,selected_ratio) end
        current.view_ratio=selected_ratio
        local distance=assert(manager.min_follow_distance or manager.follow_distance)
        local rotation=Quaternion.multiply(Quaternion(Vector3(0,0,1),manager.follow_spin),Quaternion(Vector3(-1,0,0),manager.follow_angle))
        local position
        if current.spectating then
            local target=current.watching
            position=current.focus.look(target and not dead(current.game,target.unit)
                and Unit.alive(target.focus) and Unit.world_position(target.focus,0) or nil)
        else
            local anchor=current.seat or current.unit
            -- HellBox：原版往前多看（character / vehicle 组件每帧算的 look_ahead，载具倒车时朝后）
            local ahead
            -- 注意：分屏开着时作者 peer_modes 把自己人物的 look_ahead / is_reverse 拿去给队友发暗号（8～15、is_reverse=true，
            -- 每 0.5 秒变一次），真值存在 current.mode_wire 里；直接读字段会让镜头往身后来回猛冲（2026-11-19 用户实测：摇晃、反方向）。
            local look=current.seat and context(current.game,current.seat,"camera_target") or current.target
            local look_state=look and look.state
            local amount,reverse
            if not current.seat and current.mode_wire then
                amount,reverse=current.mode_wire.look_ahead,current.mode_wire.is_reverse
            elseif look_state then
                amount,reverse=look_state.look_ahead,look_state.is_reverse
            end
            if type(amount)=="number" and amount>0 then
                amount=math.min(amount,15)
                local forward=Quaternion.forward(Unit.world_rotation(anchor,0))
                if reverse then amount=-amount end
                ahead={x=forward.x*amount,y=forward.y*amount,z=forward.z*amount}
            end
            position=current.focus.follow(anchor,Unit.world_position(anchor,0),Application.time_since_launch(),
                ahead,manager.follow_position_interp)
        end
        if not position then return end
        local center=Vector3(position.x,position.y,position.z)
        local destination=center+Quaternion.rotate(rotation,Vector3(0,-distance,0))
        -- HellBox：原版地面点 = 镜头沿视线打到 z=0 的点（震动按它算距离）；震动加在镜头位置上，不进跟随
        local look_dir=Quaternion.forward(rotation)
        if look_dir.z<0 then
            local ground=destination+look_dir*(destination.z/-look_dir.z)
            current.shake_ground={x=ground.x,y=ground.y,z=ground.z}
        end
        if current.shake then
            destination=destination+Quaternion.rotate(rotation,Vector3(current.shake.x,0,current.shake.y))
        end
        current.distance=distance
        local camera=current.display:get_camera()
        Camera.set_local_position(camera,current.display_unit,destination)
        Camera.set_local_rotation(camera,current.display_unit,rotation)
        Camera.set_vertical_fov(camera,manager.fov)
        World.update_unit(current.world,current.display_unit)
        adopt_environment_particles(current)
        local controller=current.game.entity_manager.components.character
        local players=controller and controller.players_in_no_strat_zone
        local effect_unit=current.spectating and current.watching and current.watching.unit or current.unit
        local disabled=players and players[effect_unit]==true or false
        if current.no_strat_zone~=disabled then
            Unit.flow_event(current.display_unit,disabled and "on_enter_no_strat_zone" or "on_exit_no_strat_zone")
            current.no_strat_zone=disabled
        end
        if manager.scatter_system and manager.observer_id then
            ScatterSystem.move_observer(manager.scatter_system,manager.observer_id,center+Vector3(0,0,10))
        end
        if manager.timpani_world then
            TimpaniWorld.set_listener(manager.timpani_world,0,Matrix4x4.from_quaternion_position(rotation,center))
        end
    end
    local function create(game,unit,target,mover)
        local manager=assert(CameraManager,"missing_camera_manager")
        local viewport=assert(manager.viewport,"missing_viewport")
        assert(manager.state=="follow","waiting_follow_camera")
        assert(type(target.state.active)=="boolean" and type(mover.state.keep_inside_screen)=="boolean","invalid_camera_fields")
        local controllers=game.entity_manager.components
        local target_controller=assert(controllers.camera_target,"missing_camera_controller")
        local replicator=target_controller.replicator
        local network=false
        for _,field in ipairs(target.network_fields or {}) do
            if field.name=="active" and field.write==nil then network=true end
        end
        assert(network and target.go_id and replicator and replicator.network_session,"waiting_camera_network")
        local current={game=game,unit=unit,target=target,mover=mover,target_state=target.state,mover_state=mover.state,
            manager=manager,viewport=viewport,target_controller=target_controller,mover_controller=assert(controllers.mover),
            original_active=target.state.active,original_limit=mover.state.keep_inside_screen,hooks={},particle_links={},present=false,unlock=false,
            seat=seat_for(game,unit)}
        local _,_,player=own(game)
        current.player=player
        current.focus=focus_factory()
        record=current
        current.world=viewport:get_world_proxy():get_world()
        current.display_unit=World.spawn_unit(current.world,"gameobjects/camera")
        current.display=setmetatable({camera_unit=current.display_unit},{__index=viewport})
        current.display_owner={viewport=current.display}
        local effect_owner=setmetatable({viewport=current.display},{__index=manager})
        hook(current,manager,"add_camera_particle",function(native)
            return function(owner,key,path,aspect,...)
                if owner~=manager or not rendered(current) then return native(owner,key,path,aspect,...) end
                local existing=manager.camera_particles[key]
                local function finish(...)
                    local particle=manager.camera_particles[key]
                    if particle and (not existing or current.particle_links[particle]) then
                        current.particle_links[particle]={aspect=aspect and true or false}
                    end
                    return ...
                end
                return finish(native(effect_owner,key,path,aspect,...))
            end
        end,"CameraManager.add_camera_particle")
        hook(current,viewport,"render",function(native)
            return function(view,...)
                if rendered(current) then
                    local ok,problem=pcall(visual,current)
                    if not ok then current.present=false;current.error=tostring(problem) end
                end
                return native(rendered(current) and current.display or view,...)
            end
        end,"Viewport.render")
        for _,method in ipairs({"world_to_screen","world_to_viewport","screen_to_world"}) do
            hook(current,viewport,method,function(native)
                return function(owner,...)
                    local recovery=false
                    if not current.spectating and current.in_recovery and method=="world_to_viewport" and rendered(current) then
                        local position=select(1,...)
                        local own_position=Unit.world_position(current.unit,0)
                        recovery=position and position.x==own_position.x and position.y==own_position.y and position.z==own_position.z
                    end
                    if owner==viewport and (current.in_ui or recovery) and rendered(current) and not current.in_team_update then
                        return native(current.display,...)
                    end
                    return native(owner,...)
                end
            end,"Viewport."..method)
        end
        local function ui_scope(native,owner,...)
            if not rendered(current) then return native(owner,...) end
            local previous=current.in_ui
            current.in_ui=true
            local function finish(ok,...)
                current.in_ui=previous
                if not ok then error((...)) end
                return ...
            end
            return finish(pcall(native,owner,...))
        end
        hook(current,Hud,"draw_plugins",function(native)
            return function(owner,...)
                return ui_scope(native,owner,...)
            end
        end,"Hud.draw_plugins")
        hook(current,TextChat,"update",function(native)
            return function(owner,...)
                return ui_scope(native,owner,...)
            end
        end,"TextChat.update")
        hook(current,CharacterComponent,"update_masters",function(native)
            return function(controller,...)
                if current.spectating or not rendered(current) then return native(controller,...) end
                local previous=current.in_recovery
                current.in_recovery=true
                local function finish(ok,...)
                    current.in_recovery=previous
                    if not ok then error((...)) end
                    return ...
                end
                return finish(pcall(native,controller,...))
            end
        end,"CharacterComponent.update_masters")
        local name_view=setmetatable({}, {__index=current.display})
        function name_view:world_to_viewport(position)
            local projected=current.display:world_to_viewport(position)
            if projected.y<=0 then
                local width,height=current.display:window()
                local horizontal=width*0.5-projected.x
                local vertical=height*0.5-projected.z
                local extent=math.max(math.abs(horizontal)/(width*0.5),math.abs(vertical)/(height*0.5))
                if extent<0.000001 then horizontal=0;vertical=-height;extent=2 end
                return Vector3(width*0.5+horizontal*2/extent,projected.y,height*0.5+vertical*2/extent)
            end
            return projected
        end
        hook(current,Hud,"pre_update_and_draw_hud",function(native)
            return function(owner,dt,pads,view,...)
                if rendered(current) then view=name_view end
                return native(owner,dt,pads,view,...)
            end
        end,"Hud.pre_update_and_draw_hud")
        current.target_native=hook(current,CameraTargetComponent,"command_master",function(native)
            return function(controller,candidate,candidate_context,command,...)
                if candidate==current.unit and candidate_context==current.target
                    and candidate_context.state==current.target_state and game_now()==current.game
                    and (command=="activate" or command=="deactivate") then
                    current.original_active=command=="activate"
                    if supported(current) then command="deactivate" end
                end
                if vehicles then command=vehicles.target_command(current,candidate,candidate_context,command) end
                if modes and candidate==current.unit and candidate_context==current.target and valid(current) then
                    return modes.command(current,native,controller,candidate,candidate_context,command,...)
                end
                return native(controller,candidate,candidate_context,command,...)
            end
        end,"CameraTargetComponent.command_master")
        current.mover_native=hook(current,MoverComponent,"command_master",function(native)
            return function(controller,candidate,candidate_context,command,value,...)
                if candidate==current.unit and candidate_context==current.mover
                    and candidate_context.state==current.mover_state and game_now()==current.game and command=="keep_inside_screen" then
                    current.original_limit=value
                    if current.unlock and not current.seat and supported(current) then value=false end
                end
                if vehicles then value=vehicles.mover_command(current,candidate,candidate_context,command,value) end
                return native(controller,candidate,candidate_context,command,value,...)
            end
        end,"MoverComponent.command_master")
        for _,method in ipairs({"camera","camera_unit","get_viewport","world_to_screen","world_to_viewport","screen_to_world"}) do
            hook(current,manager,method,function(native)
                return function(owner,...)
                    if owner==manager and rendered(current) and not current.in_team_update then
                        return native(current.display_owner,...)
                    end
                    return native(owner,...)
                end
            end,"CameraManager."..method)
        end
        hook(current,manager,"update",function(native)
            return function(owner,...)
                if owner~=manager or not rendered(current) then return native(owner,...) end
                local targets=manager.targets
                local filtered={}
                for candidate,properties in pairs(targets) do
                    if current.spectating or candidate~=current.unit then filtered[candidate]=properties end
                end
                if not current.spectating and next(filtered)==nil then filtered[current.unit]={bias=1,look_ahead=0} end
                current.in_team_update=true
                manager.targets=filtered
                -- HellBox 2026-11-19（用户：原版有镜头震动）：原版震动在 CameraManager.update 里每帧算一次
                -- （camera_shaker:update(dt, 地面点)，按爆炸离地面点的距离衰减）。截下这一次：地面点换成自己镜头看的地方，
                -- 结果存起来给 visual 加到自己的镜头上（同一帧不重复推进震动）。
                current.shake=nil
                local shaker=manager.camera_shaker
                local own_update=shaker and rawget(shaker,"update")
                local shaker_update=shaker and shaker.update
                if type(shaker_update)=="function" then
                    shaker.update=function(self,dt,ground,...)
                        local g=current.shake_ground
                        local value=shaker_update(self,dt,g and Vector3(g.x,g.y,g.z) or ground,...)
                        if value then current.shake={x=value.x,y=value.y} end
                        return value
                    end
                end
                local ok,problem=pcall(native,owner,...)
                if shaker then shaker.update=own_update end
                manager.targets=targets
                current.in_team_update=false
                if not ok then error(problem) end
                local drawn,detail=pcall(visual,current,select(1,...))
                if not drawn then current.present=false;current.error=tostring(detail) end
            end
        end,"CameraManager.update")
        hook(current,InputComponent,"update_masters",function(native)
            return function(controller,...)
                if current.spectating or not rendered(current) then return native(controller,...) end
                local distance=manager.follow_distance
                manager.follow_distance=current.distance or manager.min_follow_distance
                local ok,problem=pcall(native,controller,...)
                manager.follow_distance=distance
                if not ok then error(problem) end
            end
        end,"InputComponent.update_masters")
        current.present=true
        visual(current,0)
        current.initialized=true
        return current
    end
    local function tick(mask,dt,ratio)
        selected_ratio=ratio or 0
        status={applied=0,owned=record and 1 or 0,detail="off"}
        local game=game_now()
        local unit,reason
        if game then unit,reason=own(game) end
        -- A dead/destroyed avatar no longer owns mutable gameplay contexts, but the
        -- same local player may retain the local display until a new avatar is ready.
        if record and scene_valid(record) and mask>0 and not record.error
            and record.manager.state=='follow' and dead(game,unit) and not record.spectating then
            if valid(record) then
                record.original_active=false
                if modes then modes.restore(record) end
                publish(record,false)
                record.target_controller.replicator:write_fields(record.target)
                move_limit(record,record.original_limit)
            end
            if vehicles then vehicles.restore(record) end
            record.spectating=true
            record.focus.die(Application.time_since_launch())
        end
        if record and record.spectating then
            local target=unit and context(game,unit,'camera_target')
            local resumed=unit and not dead(game,unit) and target and target.state.active
                and context(game,unit,'mover')
            if not scene_valid(record) or mask==0 or record.error
                or record.manager.state~='follow' or resumed then
                cleanup(record);record=nil;status.owned=0
            else
                local keys,blocked=spectator_input(record)
                record.watching,status.detail=record.focus.watch(candidates(record),keys,blocked,Application.time_since_launch())
                visual(record)
                status.owned=mask;status.applied=mask
                return status
            end
        end
        if record and not valid(record) then
            local recovered=recover(record,game,unit)
            if recovered==nil then
                status.detail=reason or 'waiting_own_master'
                status.owned=record.unlock and 3 or 1
                return status
            elseif not recovered then
                cleanup(record);record=nil;status.owned=0
            end
        end
        if fault and (mask==0 or fault.game~=game or fault.unit~=unit) then fault=nil end
        if fault and not record then status.detail=fault.detail;return status end
        if not game then status.detail="menu";return status end
        if not unit then status.detail=reason or "waiting_avatar";return status end
        local target=context(game,unit,"camera_target")
        local mover=context(game,unit,"mover")
        local character=context(game,unit,"character")
        local seat,unsupported=seat_for(game,unit)
        local is_dead=dead(game,unit)
        local blocked=not character or is_dead or unsupported
        local want=mask>0 and not blocked and CameraManager and CameraManager.state=="follow"
        local exiting=false
        if record then
            local now=Application.time_since_launch()
            if record.seat and not seat and want then record.seat_exit_until=now+0.25;record.seat_exit_cap=now+3 end
            record.seat=seat
            if record.original_active or seat or not want then record.seat_exit_until=nil end
            -- HellBox 2026-11-26（用户：上下车动作期间镜头会被拉到其他队友那边）：原版下车先清 current_seat_unit，
            -- 下车动作（character.seat_info.exit_time，0.67～2.4 秒）播完、离开 CharacterStateSeated 时才把人物镜头 activate。
            -- 作者只等 0.25 秒：动作没播完就收掉自己的镜头，这时自己的镜头目标还关着，原版镜头只框队友 = 拉到队友那边，
            -- 位置限制也被提前还原。改成动作播着就一直算「正在下车」，最多 3 秒。
            if record.seat_exit_until and character and not seat and character.state.seat_info~=nil then
                record.seat_exit_until=math.max(record.seat_exit_until,math.min(now+0.25,record.seat_exit_cap or now))
            end
            exiting=record.seat_exit_until and now<record.seat_exit_until
        end
        if is_dead and record then record.original_active=false end
        if not seat and not exiting and ((record and not record.original_active) or (not record and target and not target.state.active)) then want=false end
        if record then
            if record.error then
                status.detail="camera_error:"..record.error
                if mask>0 then fault={game=game,unit=unit,detail=status.detail} end
                mask=0;want=false
            end
            local unlock=mask==3 and want
            if vehicles then record.vehicle_detail=vehicles.tick(record,not blocked and seat or nil,want and mask or 0) end
            if (not want or (record.unlock and not unlock)) and not blocked
                and (record.original_active or seat) and record.manager.state=="follow" and not safe_return(record) then
                if modes then modes.publish(record,seat and 1 or (record.unlock and 3 or 1)) end
                status.owned=record.unlock and 3 or 1
                if record.error then
                    status.detail="camera_error_pending_return:"..record.error
                else
                    status.detail=seat and "vehicle_return_to_team" or "return_to_team"
                    status.applied=status.owned
                end
                return status
            end
            if not want then
                if modes then modes.restore(record) end
                publish(record,record.original_active)
                -- A seated avatar stays inactive even after personal view ends.
                record.target_controller.replicator:write_fields(record.target)
                move_limit(record,record.original_limit)
                cleanup(record);record=nil
            end
        end
        if not want then
            status.owned=0
            if mask>0 then status.detail=blocked and "suspended_character_or_vehicle" or "waiting_follow_camera" end
            return status
        end
        if not target or not mover then status.detail="waiting_own_master";return status end
        if not record then create(game,unit,target,mover) end
        record.unlock=mask==3
        publish(record,false)
        if modes then modes.publish(record,mask) end
        if vehicles then record.vehicle_detail=vehicles.tick(record,seat,mask) end
        local limit=record.original_limit
        if record.unlock and not seat then limit=false end
        move_limit(record,limit)
        visual(record)
        status.owned=record.unlock and 3 or 1
        local groups=game.entity_manager.component_name_to_contexts.camera_target
        local slave=groups and groups.slave and groups.slave[unit]
        if slave and slave.state.active==false and not record.manager.targets[unit] then
            status.applied=status.owned
            status.detail=record.vehicle_detail or "local_ready_peer_unverified"
        else status.detail="waiting_camera_replication" end
        return status
    end
    return {
        tick=function(mask,dt,ratio)
            local ok,result=pcall(tick,mask,dt,ratio)
            if ok then return result end
            if record then
                record.error=tostring(result)
                record.present=false
                if mask>0 then fault={game=record.game,unit=record.unit,detail="camera_error:"..record.error} end
                if not record.initialized then cleanup(record);record=nil end
            end
            return {applied=0,owned=record and (record.unlock and 3 or 1) or 0,detail="camera_error:"..tostring(result)}
        end,
        status=function() return status end,
        contains=function(game,position)
            if not record or record.spectating or record.game~=game or not rendered(record) then return nil end
            local projected=record.display:world_to_viewport(position)
            local width,height=record.display:window()
            local resolution=record.manager.screen_resolution
            if resolution and (not record.view_ratio or record.view_ratio==0) then width,height=resolution.width,resolution.height end
            return projected.y>0 and projected.x>=0 and projected.x<=width and projected.z>=0 and projected.z<=height
        end
    }
end

end)()
-- END GENERATED CAMERA FACTORY
-- BEGIN GENERATED ENCOUNTER FACTORY
local encounter_factory = (function()
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

end)()
-- END GENERATED ENCOUNTER FACTORY
-- BEGIN GENERATED SUPPLY FACTORY
local supply_factory = (function()
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

end)()
-- END GENERATED SUPPLY FACTORY
-- BEGIN GENERATED SPAWNING FACTORY
local spawning_factory = (function()
return function(host,encounter_factory,supply_factory)
    local record,fault
    local function game_now()
        local machine=Boot and Boot.state_machine
        return machine and machine.current_state_name=="game" and machine.state or nil
    end
    local function valid(current)
        return current and game_now()==current.game and current.game.is_server==true
            and CameraManager==current.manager and current.manager.viewport==current.viewport
            and current.game.patrol_manager==current.patrol and current.game.spawn_manager==current.spawn
            and current.game.encounter_manager==current.encounter
            and not current.patrol.destroyed and not current.encounter.destroyed
    end
    local function active(current)
        return valid(current) and not current.error and current.manager.state=="follow"
    end
    local function hook(current,object,key,make,resource)
        local prior=rawget(object,key)
        local native=assert(object[key],"missing_method:"..resource)
        local wrapper=make(native)
        assert(host:claim("camera",resource),"hook_busy:"..resource)
        current.hooks[#current.hooks+1]={object=object,key=key,prior=prior,wrapper=wrapper,resource=resource}
        object[key]=wrapper
        return native
    end
    local function cleanup(current)
        if current.release_supply then current.release_supply() end
        if current.release_encounters then current.release_encounters() end
        for index=#current.hooks,1,-1 do
            local item=current.hooks[index]
            if item.object[item.key]==item.wrapper then rawset(item.object,item.key,item.prior) end
            host:release("camera",item.resource)
        end
        if game_now()==current.game and current.game.patrol_manager==current.patrol
            and not current.patrol.destroyed then
            for _,zone in pairs(current.zones) do
                if Unit.alive(zone.unit) then World.destroy_unit(current.world,zone.unit) end
            end
        end
    end
    local function scope(current,key,native,owner,...)
        local previous=current[key]
        current[key]=true
        local function finish(ok,...)
            current[key]=previous
            if not ok then error((...)) end
            return ...
        end
        return finish(pcall(native,owner,...))
    end
    local function zone_inside(current,zone,position,...)
        local projected=zone.viewport:world_to_viewport(position)
        if projected.y<=0 then return false end
        return current.frustum(zone,position,...)
    end
    local function extra_inside(current,position,...)
        for _,zone in pairs(current.zones) do
            if zone_inside(current,zone,position,...) then return true end
        end
        return false
    end
    local function guarded_inside(current,position,...)
        local ok,result=pcall(extra_inside,current,position,...)
        if not ok then current.error=tostring(result);return false end
        return result
    end
    local function outside_views(current,position,margin)
        local limit=1
        for _ in pairs(current.zones) do limit=limit+1 end
        for _=1,limit do
            if current.public_occupied and zone_inside(current,current.manager,position,0,0,0,0) then
                position=current.outside(current.manager,position,math.max(margin or 0,0.01))
            end
            local moved=false
            for _,zone in pairs(current.zones) do
                if zone_inside(current,zone,position,0,0,0,0) then
                    position=current.outside(zone,position,math.max(margin or 0,0.01))
                    moved=true
                end
            end
            if not moved then break end
        end
        return position
    end
    local function refresh(current)
        local retained={}
        local players={}
        local public_occupied=false
        for unit in pairs(current.game.entity_manager:get_slave_entities("character")) do
            if Unit.alive(unit) then
                local health=EntityAux.state(unit,"health")
                if health and not health.is_dead then
                    local position=Unit.world_position(unit,0)
                    players[#players+1]={unit=unit,x=position.x,y=position.y,z=position.z}
                    local projected=current.viewport:world_to_viewport(position)
                    if projected.y<=0 or not current.frustum(current.manager,position,0,0,0,0) then
                        local zone=current.zones[unit]
                        if not zone then
                            zone={unit=World.spawn_unit(current.world,"core/units/camera")}
                            current.zones[unit]=zone
                            zone.viewport=setmetatable({camera_unit=zone.unit},{__index=current.viewport})
                        end
                        zone.screen_resolution=current.manager.screen_resolution
                        local rotation=Quaternion.multiply(Quaternion(Vector3(0,0,1),current.manager.follow_spin),
                            Quaternion(Vector3(-1,0,0),current.manager.follow_angle))
                        local destination=position+Quaternion.rotate(rotation,Vector3(0,-current.manager.min_follow_distance,0))
                        zone.position={x=destination.x,y=destination.y,z=destination.z}
                        local camera=zone.viewport:get_camera()
                        Camera.set_local_position(camera,zone.unit,destination)
                        Camera.set_local_rotation(camera,zone.unit,rotation)
                        Camera.set_vertical_fov(camera,current.manager.fov)
                        World.update_unit(current.world,zone.unit)
                        retained[unit]=true
                    else
                        public_occupied=true
                    end
                end
            end
        end
        for unit,zone in pairs(current.zones) do
            if not retained[unit] then
                if Unit.alive(zone.unit) then World.destroy_unit(current.world,zone.unit) end
                current.zones[unit]=nil
            end
        end
        current.players=players
        current.public_occupied=public_occupied or #players==0
    end
    local function refresh_authority(current)
        local now=Application.time_since_launch()
        if current.authority_time and now-current.authority_time<1 then return end
        current.authority_time=now
        local handler=assert(current.game.network_session_handler,"missing_network_handler")
        local router=assert(current.game.network_router,"missing_network_router")
        local peer=Network.peer_id()
        local pending={}
        local count=0
        for unit in pairs(current.game.entity_manager:get_slave_entities("enemy")) do
            if Unit.alive(unit) and EntityAux.owner(unit)~=peer then
                local health=EntityAux.state(unit,"health")
                if health and not health.is_dead then
                    local identifier=assert(EntityAux.go_id(unit),"missing_enemy_go_id")
                    local request=current.authority_pending[identifier] or {attempts=0,time=-math.huge}
                    pending[identifier]=request
                    current.authority_pending[identifier]=request
                    count=count+1
                    if now-request.time>=5 then
                        assert(request.attempts<3,"enemy_authority_timeout:"..tostring(identifier))
                        request.attempts=request.attempts+1;request.time=now
                        handler:migrate_game_object(identifier,peer,router.receiver)
                    end
                end
            end
        end
        current.authority_pending=pending
        current.authority_count=count
    end
    local function create(game,settings)
        local current={game=game,manager=assert(CameraManager),viewport=assert(CameraManager.viewport),
            patrol=assert(game.patrol_manager),spawn=assert(game.spawn_manager),encounter=assert(game.encounter_manager),
            hooks={},zones={},players={},authority_pending={},authority_count=0,settings=settings}
        record=current
        current.world=current.viewport:get_world_proxy():get_world()
        current.frustum=hook(current,current.manager,"is_position_inside_frustum",function(native)
            return function(owner,position,left,right,top,bottom)
                if owner==current.manager and current.in_alert and active(current)
                    and left==nil and right==nil and top==nil and bottom==nil then return true end
                if owner==current.manager and current.in_ifv_update and active(current)
                    and left==nil and right==nil and top==nil and bottom==nil
                    and guarded_inside(current,position) then return true end
                if owner==current.manager and current.in_patrol and active(current)
                    and (left==-0.5 or left==-0.1) and right==left and top==left and bottom==left then
                    if guarded_inside(current,position,left,right,top,bottom) then
                        return true,0,0,Vector3(0,0,0)
                    end
                    if not current.error and current.public_occupied==false then return false end
                end
                return native(owner,position,left,right,top,bottom)
            end
        end,"CameraManager.is_position_inside_frustum")
        current.outside=hook(current,current.manager,"get_closest_position_outside_frustum",function(native)
            return function(owner,position,margin,...)
                if owner~=current.manager or not current.in_patrol or not active(current) or not next(current.zones) then
                    return native(owner,position,margin,...)
                end
                local ok,result=pcall(outside_views,current,position,margin)
                if ok then return result end
                current.error=tostring(result)
                return native(owner,position,margin,...)
            end
        end,"CameraManager.get_closest_position_outside_frustum")
        hook(current,assert(EnemyUtility),"check_alert",function(native)
            return function(state,...)
                if not active(current) then return native(state,...) end
                return scope(current,"in_alert",native,state,...)
            end
        end,"EnemyUtility.check_alert")
        for _,name in ipairs({"CyborgIfvStateWander","CyborgIfvStateAttack","CyborgIfvStateBack",
            "CyborgIfvStateRunOver","CyborgIfvStateSpawnGroup","CyborgIfvStateConstitution"}) do
            local state=rawget(_G,name)
            if type(state)=="table" and type(state.update)=="function" then
                hook(current,state,"update",function(native)
                    return function(unit,...)
                        if not active(current) then return native(unit,...) end
                        return scope(current,"in_ifv_update",native,unit,...)
                    end
                end,name..".update")
            end
        end
        hook(current,current.encounter,"get_spawner_peer",function(native)
            return function(owner,...)
                if owner==current.encounter and active(current) then return Network.peer_id() end
                return native(owner,...)
            end
        end,"EncounterManager.get_spawner_peer")
        hook(current,current.encounter,"add_migrated_enemy",function(native)
            return function(owner,unit,...)
                if owner==current.encounter and active(current)
                    and current.authority_pending[EntityAux.go_id(unit)] then return end
                return native(owner,unit,...)
            end
        end,"EncounterManager.add_migrated_enemy")
        hook(current,current.patrol,"update_host",function(native)
            return function(owner,...)
                if owner~=current.patrol or not active(current) then return native(owner,...) end
                local ok,problem=pcall(refresh,current)
                if not ok then current.error=tostring(problem);return native(owner,...) end
                if current.supply_tick then
                    ok,problem=pcall(current.supply_tick)
                    if not ok then current.error="patrol_supply:"..tostring(problem) end
                end
                return scope(current,"in_patrol",native,owner,...)
            end
        end,"PatrolManager.update_host")
        hook(current,current.spawn,"get_spawn_points",function(native)
            return function(owner,position,radius,group,...)
                local function finish(...)
                    if owner==current.spawn and active(current) and group.force_outside_screen and next(current.zones) then
                        local kept={}
                        for _,raycast in ipairs(group.queued_raycasts or {}) do
                            local point=raycast.arg_a
                            local ok,adjusted=pcall(outside_views,current,Vector3(point.x,point.y,position.z),0)
                            if not ok then current.error=tostring(adjusted);break end
                            if not guarded_inside(current,adjusted,0,0,0,0)
                                and (not current.public_occupied or not current.frustum(current.manager,adjusted,0,0,0,0)) then
                                local replacement={}
                                for key,value in pairs(point) do replacement[key]=value end
                                replacement.x=adjusted.x;replacement.y=adjusted.y
                                raycast.arg_a=replacement
                                kept[#kept+1]=raycast
                            end
                        end
                        if not current.error then group.queued_raycasts=kept end
                    end
                    return ...
                end
                return finish(native(owner,position,radius,group,...))
            end
        end,"SpawnManager.get_spawn_points")
        hook(current,current.encounter,"can_spawn",function(native)
            return function(owner,...)
                if owner~=current.encounter or not active(current) or not next(current.zones) then return native(owner,...) end
                return scope(current,"in_encounter_budget",native,owner,...)
            end
        end,"EncounterManager.can_spawn")
        hook(current,current.encounter,"get_center_of_players",function(native)
            return function(owner,...)
                if owner==current.encounter and current.in_encounter_budget and active(current)
                    and owner.encounter_position and next(current.zones) then
                    local position=Vector3Aux.unbox(owner.encounter_position)
                    local nearest,distance
                    for _,player in ipairs(current.players) do
                        local candidate=Vector3(player.x,player.y,0)
                        local delta=Vector3.distance(candidate,position)
                        if not distance or delta<distance then nearest,distance=candidate,delta end
                    end
                    if nearest then return nearest end
                end
                return native(owner,...)
            end
        end,"EncounterManager.get_center_of_players")
        refresh(current)
        if encounter_factory then current.release_encounters=encounter_factory(current,hook,active) end
        if supply_factory and current.patrol_regions then
            current.patrol_point=function(position) return outside_views(current,position,0.15) end
            current.patrol_visible=function(position,margin)
                return (current.public_occupied and zone_inside(current,current.manager,position,margin,margin,margin,margin))
                    or extra_inside(current,position,margin,margin,margin,margin)
            end
            current.release_supply=supply_factory(current)
        end
        return current
    end
    return {diagnostics=function()
        if not record or not record.encounter_trace then return end
        return tostring(record)..":"..record.encounter_trace_serial,table.concat(record.encounter_trace,"\n").."\n"
    end,tick=function(enabled,settings)
        local game=game_now()
        if record and (not enabled or not valid(record) or record.error) then
            if record.error then fault={game=record.game,detail=record.error} end
            cleanup(record);record=nil
        end
        if not enabled or (fault and fault.game~=game) then fault=nil end
        if not enabled then return {applied=0,owned=0,detail="off"} end
        if fault then return {applied=0,owned=0,detail="error:"..fault.detail} end
        if not game then return {applied=0,owned=0,detail="waiting_task"} end
        if game.is_server~=true then return {applied=0,owned=0,detail="host_only"} end
        if not CameraManager or CameraManager.state~="follow" or not game.patrol_manager or not game.encounter_manager
            or not game.spawn_manager then return {applied=0,owned=0,detail="waiting_managers"} end
        local ok,problem=pcall(function()
            if not record then create(game,settings) else record.settings=settings;refresh(record) end
            refresh_authority(record)
        end)
        if not ok then
            fault={game=game,detail=tostring(problem)}
            if record then cleanup(record);record=nil end
            return {applied=0,owned=0,detail="error:"..fault.detail}
        end
        local count=0
        for _ in pairs(record.zones) do count=count+1 end
        local detail=count==0 and "native_same_screen" or "expanded:"..count
        if record.authority_count>0 then detail=detail..";alarm_pending:"..record.authority_count end
        if record.regional_detail then detail=detail..record.regional_detail() end
        if record.supply_detail then detail=detail..record.supply_detail() end
        return {applied=4,owned=4,detail=detail}
    end}
end

end)()
-- END GENERATED SPAWNING FACTORY
-- BEGIN GENERATED RESPAWN FACTORY
local respawn_factory = (function()
return function(host)
    local record
    local function game_now()
        local machine=Boot and Boot.state_machine
        return machine and machine.current_state_name=="game" and machine.state or nil
    end
    local function own_player(game,index)
        local own,count=nil,0
        for _,player in ipairs(game.players or {}) do
            local go=player.player_go
            if go and go:exists() and go:owned() then own=player;count=count+1 end
        end
        return count==1 and own==game.players[index] and own or nil
    end
    local function cleanup()
        if not record then return end
        if record.game.spawn_local_player==record.wrapper then
            rawset(record.game,"spawn_local_player",record.prior)
        end
        host:release("camera","StateGame.spawn_local_player")
        record=nil
    end
    return {tick=function(enabled)
        local game=game_now()
        if record and (not enabled or game~=record.game) then cleanup() end
        if record then return record.error end
        if not enabled or not game or type(game.spawn_local_player)~="function" then return end
        local current={game=game,prior=rawget(game,"spawn_local_player"),native=game.spawn_local_player}
        local function landing(owner,position,index)
            if not current.error and owner==game and game_now()==game then
                local player=own_player(game,index)
                if player and player.has_sent_respawn_request and game.has_faded_in and game.respawn_position then
                    local anchor=Vector3Aux.unbox(game.respawn_position)
                    local horizontal=position.x-anchor.x
                    local vertical=position.y-anchor.y
                    if horizontal*horizontal+vertical*vertical>(index+1)^2+0.001 or math.abs(position.z-anchor.z)>0.001 then
                        local radius=1+math.random()*index
                        local angle=math.pi/2*index+math.random()*math.pi/4
                        position=Vector3(anchor.x+radius*math.cos(angle),anchor.y+radius*math.sin(angle),anchor.z)
                    end
                end
            end
            return position
        end
        current.wrapper=function(owner,position,index,pad,...)
            local ok,replacement=pcall(landing,owner,position,index)
            if ok then position=replacement else current.error=tostring(replacement) end
            return current.native(owner,position,index,pad,...)
        end
        assert(host:claim("camera","StateGame.spawn_local_player"),"hook_busy:StateGame.spawn_local_player")
        record=current
        game.spawn_local_player=current.wrapper
    end}
end

end)()
-- END GENERATED RESPAWN FACTORY
-- BEGIN GENERATED ESCORT TRANSFER FACTORY
local escort_transfer_factory = (function()
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

end)()
-- END GENERATED ESCORT TRANSFER FACTORY
-- BEGIN GENERATED ESCORT FACTORY
local escort_factory = (function()
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

end)()
-- END GENERATED ESCORT FACTORY
    local host=get_host()
    if host.modules.camera then return end
    local root=assert(os.getenv("APPDATA")).."/Arrowhead/Helldivers/camera_ctrl_v1/"
    local marker={protocol=1,session=(tostring({}):gsub("[^%w]",""))..tostring(os.time()),revision=0}
    rawset(_G,"CameraCTRLBridge",marker)
    local last_poll=-1
    local last_trace
    local modes=peer_modes_factory()
    local vehicles=vehicles_factory(modes)
    local camera=camera_factory(host,modes,vehicles,camera_focus_factory,view_factory)
    local extraction=extraction_factory(host)
    local spawning=spawning_factory(host,encounter_factory,supply_factory)
    local respawn=respawn_factory(host)
    local escort_transfer=escort_transfer_factory(host)
    local escort=escort_factory(host,escort_transfer,modes,camera)
    local client,sequence,desired,last_request="",0,0,-100
    local spawn_settings={encounter=2,patrol=4}
    local view_ratio=0
    local reply_nonce,reply_sequence="",0
    local result={applied=0,owned=0,detail="off"}
    local function control(now)
        local file=io.open(root.."control-request.txt","rb")
        if not file then return end
        local text=file:read(513);file:close()
        if not text or #text>512 then return end
        local view=text:match("\nVIEW\n(%d+)\nEND\n$")
        local ratio=tonumber(view) or 0
        if ratio~=0 and ratio~=1250 and ratio~=1333 and ratio~=1600 and ratio~=1778 then return end
        if view then text=text:gsub("\nVIEW\n%d+\nEND\n$","\nEND\n") end
        local nonce,session,owner,serial,mask=text:match("^CAM2\n([a-zA-Z0-9]+)\n([a-zA-Z0-9%-]+)\n([a-zA-Z0-9]+)\n(%d+)\n(%d+)\nEND\n$")
        local encounter,patrol=2,4
        if not nonce then
            nonce,session,owner,serial,mask,encounter,patrol=text:match("^CAM2\n([a-zA-Z0-9]+)\n([a-zA-Z0-9%-]+)\n([a-zA-Z0-9]+)\n(%d+)\n(%d+)\nSPAWN\n(%d+)\n(%d+)\nEND\n$")
            encounter,patrol=tonumber(encounter),tonumber(patrol)
            if not encounter or not patrol or encounter<1 or encounter>100 or patrol<1 or patrol>100 then return end
        end
        if not nonce or #nonce>80 or #owner>80 then return end
        serial,mask=tonumber(serial),tonumber(mask)
        if serial<1 or serial>2147483647 or (mask~=0 and mask~=1 and mask~=3 and mask~=4 and mask~=5 and mask~=7) then return end
        if session=="-" and mask==0 then reply_nonce,reply_sequence=nonce,serial;return end
        if session~=marker.session then return end
        if owner~=client then
            if now-last_request<5 then return end
            client,sequence=owner,0
        end
        if serial<=sequence then return end
        sequence,desired,last_request=serial,mask,now
        spawn_settings={encounter=encounter,patrol=patrol}
        view_ratio=ratio
        reply_nonce,reply_sequence=nonce,serial
    end
    local function report_control()
        if reply_nonce=="" then return end
        local file=io.open(root.."control-status.tmp","wb")
        if not file then return end
        file:write(table.concat({"CAM2",reply_nonce,marker.session,tostring(reply_sequence),tostring(desired),
            tostring(result.applied),tostring(result.owned),result.detail:gsub("[\r\n]"," "):sub(1,768),"END",""},"\n"))
        file:close()
        os.remove(root.."control-status.txt")
        os.rename(root.."control-status.tmp",root.."control-status.txt")
    end
    local function context(game,unit,name)
        local groups=game.entity_manager and game.entity_manager.component_name_to_contexts
        local component=groups and groups[name]
        if not component or not component.master or not EntityAux.has_component_master(unit,name) then return nil end
        return component.master[unit]
    end
    local function inspect()
        local machine=Boot and Boot.state_machine
        if not machine or machine.current_state_name~="game" then return "menu" end
        local game=machine.state
        if not game or type(game.players)~="table" then return "waiting_players" end
        local own,local_count,total=nil,0,0
        for _,player in ipairs(game.players) do
            local go=player.player_go
            if go and go:exists() then
                total=total+1
                if go:owned() then local_count=local_count+1; own=go end
            end
        end
        if local_count~=1 then return "local_players="..local_count end
        local unit=own:get("avatar_unit")
        if not unit or not Unit.alive(unit) then return "waiting_avatar" end
        local camera=context(game,unit,"camera_target")
        local mover=context(game,unit,"mover")
        if not camera or not mover then return "waiting_own_master" end
        local active_field=false
        for _,field in ipairs(camera.network_fields or {}) do
            if field.name=="active" then active_field=true end
        end
        local targets=CameraManager and CameraManager.targets
        local target_count=0
        for _ in pairs(targets or {}) do target_count=target_count+1 end
        local fields={"observed", "players="..total,"supported_mask=7","is_server="..tostring(game.is_server),
            "camera_active="..tostring(camera.state and camera.state.active),
            "active_network_field="..tostring(active_field),
            "keep_inside_screen="..tostring(mover.state and mover.state.keep_inside_screen),
            "is_inside_screen="..tostring(mover.state and mover.state.is_inside_screen),
            "targets="..target_count,"own_target="..tostring(targets and targets[unit]~=nil or false),
            "camera_state="..tostring(CameraManager and CameraManager.state)}
        return table.concat(fields,";")
    end
    local function tick()
        local now=Application.time_since_launch()
        if now-last_poll<0.2 then return end
        last_poll=now
        report_control()
        local trace_id,trace_text=spawning.diagnostics()
        if trace_id and trace_id~=last_trace then
            local trace_file=io.open(root.."encounter-trace.tmp","wb")
            if trace_file then
                trace_file:write("session="..marker.session.."\n"..trace_text)
                trace_file:close()
                os.remove(root.."encounter-trace.txt")
                os.rename(root.."encounter-trace.tmp",root.."encounter-trace.txt")
                last_trace=trace_id
            end
        end
        local file=io.open(root.."camera-request.txt","rb")
        if not file then return end
        local request=file:read(257); file:close()
        if not request or #request>256 then return end
        local nonce=request:match("^CAM1\n([a-zA-Z0-9]+)\nINSPECT\nEND\n$")
        if not nonce or #nonce>80 then return end
        local ok,result=pcall(inspect)
        marker.revision=marker.revision+1
        marker.detail=ok and result or "inspect_error:"..tostring(result)
        local response=io.open(root.."camera-status.tmp","wb")
        if not response then return end
        response:write(table.concat({"CAM1",nonce,marker.session,tostring(marker.revision),
            marker.detail:gsub("[\r\n]"," "):sub(1,768),"END",""},"\n"))
        response:close()
        os.remove(root.."camera-status.txt")
        os.rename(root.."camera-status.tmp",root.."camera-status.txt")
    end
    local function apply(dt)
        local extraction_ok,extraction_problem=pcall(extraction.tick,desired%4==3)
        local transfer_ok,transfer_problem=pcall(escort_transfer.tick,desired%4==3)
        local escort_ok,escort_problem=pcall(escort.tick)
        local respawn_ok,respawn_problem=pcall(respawn.tick,desired%4==3)
        result=camera.tick(desired%4,dt,view_ratio)
        if not extraction_ok or extraction_problem then
            result.detail=result.detail..";extraction_error="..tostring(extraction_problem)
        end
        if not transfer_ok or transfer_problem then
            result.detail=result.detail..";escort_transfer_error="..tostring(transfer_problem)
        end
        local transfer_status=escort_transfer.status()
        if transfer_status then result.detail=result.detail..";escort_transfer="..transfer_status end
        if not escort_ok or escort_problem then
            result.detail=result.detail..";escort_error="..tostring(escort_problem)
        end
        if not respawn_ok or respawn_problem then
            result.detail=result.detail..";respawn_error="..tostring(respawn_problem)
        end
        local spawn=spawning.tick(desired>=4,spawn_settings)
        result={applied=result.applied+spawn.applied,owned=result.owned+spawn.owned,
            detail=result.detail..";spawn="..spawn.detail..";view_config:1;spawn_config:1;spawn_multipliers:"..spawn_settings.encounter.."/"..spawn_settings.patrol}
    end
    host:register("camera",{pre=function(dt)
        local now=Application.time_since_launch()
        if now-last_poll>=0.2 then control(now) end
        if now-last_request>=5 then desired=0 end
        apply(dt)
    end,post=function(dt)
        apply(dt)
        tick()
    end})
end
local ok,problem=pcall(install)
rawset(_G,"CameraCTRLBridgeLoadOk",ok)
rawset(_G,"CameraCTRLBridgeLoadError",ok and "" or tostring(problem))
