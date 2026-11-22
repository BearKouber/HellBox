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
