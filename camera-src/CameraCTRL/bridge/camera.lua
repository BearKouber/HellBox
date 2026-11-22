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
            if record.seat and not seat and want then record.seat_exit_until=Application.time_since_launch()+0.25 end
            record.seat=seat
            if record.original_active or seat or not want then record.seat_exit_until=nil end
            exiting=record.seat_exit_until and Application.time_since_launch()<record.seat_exit_until
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
