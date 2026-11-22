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
