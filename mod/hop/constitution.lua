return function(env)
    local records = setmetatable({}, {__mode = "k"})
    local normal = {
        CharacterStateSprint=true, CharacterStateCarry=true, CharacterStateIdle=true,
        CharacterStateWalk=true, CharacterStateAim=true, CharacterStateAimWalk=true,
        CharacterStateFire=true, CharacterStateWalkFire=true, CharacterStateAimFire=true,
        CharacterStateAimWalkFire=true, CharacterStateDownedIdle=true, CharacterStateDownedCrawl=true,
        CharacterStateDownedAim=true, CharacterStateDownedAimFire=true,
    }
    local function finite(value)
        return type(value)=="number" and value==value and value > -math.huge and value < math.huge
    end
    return function(native)
        return function(unit, ctx, dt, component)
            local character = ctx.state
            local weapon, state = env.weapon(unit, character)
            local input = character.input
            local current = character.current_state
            local name = current and current.name
            local supported = normal[name] or name=="CharacterStateReload" or name=="CharacterStateDownedReload"
            local eligible = unit==env.own_unit() and env.alive(unit) and not character.seated
                and weapon and state and Unit.get_data(weapon,"unit_path")=="equipment/wep_bolt_action_01"
                and state.attributes and state.attributes.add_single_rounds==true and type(input)=="table"
            if not eligible then
                records[character] = nil
                return native(unit,ctx,dt,component)
            end
            local record = records[character]
            if not finite(state.rounds) or not finite(state.magazine_capacity) or not finite(state.num_mags) then
                records[character]=nil
                return native(unit,ctx,dt,component)
            end
            local game = env.game()
            if not record or record.weapon~=weapon or record.game~=game then
                record={weapon=weapon,game=game}; records[character]=record
            end
            local pressed = input.fire and not record.was_fire
            record.was_fire=input.fire==true
            local blocked = not supported or character.new_state or input.switch_weapon or input.interact
                or input.throw or input.dodge or input.melee or input.stratagems or input.map
                or (name=="CharacterStateCarry" and (character.is_dropping or character.carry_is_switching_weapon or character.carry_is_map))
                or (name and name:find("Downed",1,true) and input.interact_button==1)
            if blocked then record.fill=nil
            elseif input.reload and not input.captain_synthetic_reload then record.fill=true end
            if not finite(state.rounds) or not finite(state.magazine_capacity) or state.rounds>=state.magazine_capacity
                or not finite(state.num_mags) or state.num_mags<=0 then record.fill=nil end
            if pressed and state.rounds>0 and state.fire_timer==0 and not state.is_reloading and not state.reload_abort then record.fill=nil end
            local fire_ready = state.rounds>0 and (input.fire or input.fire_auto)
                and (not finite(state.fire_timer) or state.fire_timer<=0)
            if blocked or not record.fill or not normal[name] or fire_ready or state.reloadable~=true
                or state.is_reloading or state.reload_abort
                or (name=="CharacterStateCarry" and character.carry_is_reloading) then
                return native(unit,ctx,dt,component)
            end
            local fire, auto, reload = input.fire,input.fire_auto,input.reload
            input.fire,input.fire_auto,input.reload=false,false,true
            local ok,result=pcall(native,unit,ctx,dt,component)
            input.fire,input.fire_auto,input.reload=fire,auto,reload
            if not ok then error(result) end
            return result
        end
    end
end
