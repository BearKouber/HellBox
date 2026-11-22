return function()
    local env = {}
    function env.game()
        local machine = Boot and Boot.state_machine
        return machine and machine.current_state_name == "game" and machine.state or nil
    end
    function env.own_unit()
        local game = env.game()
        if not game or game.abort_mission or game.wants_exit or game.game_state == "game_over"
            or (game.text_chat and game.text_chat.active) then return nil end
        local chosen, count, fallback
        count = 0
        for _, player in ipairs(game.players or {}) do
            local go = player.player_go
            if go and go:exists() and go:owned() then
                count, fallback = count + 1, player
                if player.pad_number == 0 then
                    if chosen then return nil end
                    chosen = player
                end
            end
        end
        chosen = chosen or (count == 1 and fallback)
        if not chosen or chosen.is_respawning or chosen.player_go:get("has_extracted") then return nil end
        local unit = chosen.player_go:get("avatar_unit")
        return unit and Unit.alive(unit) and unit or nil
    end
    function env.state(unit, name)
        return unit and EntityAux.state_master(unit, name)
    end
    function env.weapon(unit, character)
        local inventory = env.state(unit, "inventory")
        local weapon = character and character.current_weapon
        if not weapon or not Unit.alive(weapon) or not inventory or inventory.current_weapon ~= weapon then return nil end
        local equipment = env.state(weapon, "equipment")
        if not equipment or equipment.wielder ~= unit or equipment.wielded ~= true then return nil end
        local weapon_state = EntityAux.state_master_interface(weapon, "weapon")
        return weapon, weapon_state
    end
    function env.alive(unit)
        local health = unit and EntityAux.state(unit, "health")
        return health and health.is_dead == false
    end
    return env
end
