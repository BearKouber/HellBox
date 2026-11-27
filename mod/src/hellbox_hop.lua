-- [hellbox hop] 自动生成，不要手改：改 mod/hop/ 下的文件后跑 tools/make_hop.py。
-- 来源：HalfSugar（半糖）的 HelldiversOptimization（作者同意收进 HellBox，2026-11-19）；
do
local hop_defaults = "@HELLBOX_HOP@"
local context_factory = (function()
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

end)()
local constitution_factory = (function()
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

end)()
local readability_factory = (function()
return function(config,hooks)
    -- 2026-11-21 HD1-038：来自 QoL 的四项（玩家列表字体、名字字体、潜兵轮廓、HUD 透明度）删了，只留半糖自己的名字深色底和长文字不截断
    -- 2026-11-26 用户：名字深色底删了（「这个删除了」）；长文字截断留着，开关改名「名字不乱码」，同一个开关还管字体缺字（src/hellbox_name_font.lua）
    local function trim(text,width,measure)
        if type(text)~="string" or not Utf8.valid(text) or width<=0 then return "" end
        if measure(text)<=width then return text end
        if measure("...")>width then return "" end
        local ends={0}
        for i=2,#text do
            local byte=string.byte(text,i)
            if byte<128 or byte>=192 then ends[#ends+1]=i-1 end
        end
        ends[#ends+1]=#text
        local low,high,best=1,#ends,0
        while low<=high do
            local middle=math.floor((low+high)/2)
            if measure(text:sub(1,ends[middle]).."...")<=width then best=ends[middle];low=middle+1
            else high=middle-1 end
        end
        return text:sub(1,best).."..."
    end
    return function()
        local ready=true
        if config.long_text=="1" then
            for _,spec in ipairs({{"draw_selection_scroll","get_text_bounds","draw_text"},
                {"draw_selection_scroll_hd_gui","get_text_extents","text"}}) do
                local method,measure,draw=unpack(spec)
                ready=hooks.wrap("MenuScreenBase",method,"long_text",function(native)
                    return function(self,gui,z,pos,text,width,selected,...)
                        if selected or type(text)~="string" or not Utf8.valid(text) then
                            return native(self,gui,z,pos,text,width,selected,...)
                        end
                        local clipped=trim(text,width,function(value) return gui[measure](gui,value) end)
                        return gui[draw](gui,clipped,Vector3(pos.x,pos.y,z))
                    end
                end) and ready
            end
        end
        return ready
    end
end

end)()
-- HellBox 转接层的启动部分（2026-11-20 HD1-035）。tools/make_hop.py 把它和半糖 HelldiversOptimization 的模块
-- 拼成 src/hellbox_hop.lua。上面已经有：hop_defaults（编译时填的初始值）、各模块工厂（*_factory）。
--
-- 和半糖原版 bootstrap 的区别：
--   - 设置不是装 MOD 时写死的：游戏每秒读 HellBox 写的 %APPDATA%/Arrowhead/Helldivers/hellbox/hop.txt
--     （HBHOP1，一行一个 键=值），改了就生效。
--   - 挂钩一直装着，每次被调用时看开关（gate），关着就照原版走；不需要重开游戏。
--   - 2026-11-21 HD1-038（用户定）：来自 QoL Mod 的功能全部删掉（QoL 作者希望各自独立、能一起装；想用就装正版 QoL，HellBox 能和它共存）。
--     只留半糖自己的：建构连续装填、长文字不截断（2026-11-26 名字深色底删了；2026-11-22 用户：军械库显示真实数值、显示身上的状态也是 QoL 的，删了）。
--   - 没有 BridgeCore：host 是这里的一个小替身（claim 永远成功），每帧的驱动挂在 WorldManager.update 上。
do
	local live = {}
	local defaults = hop_defaults or {}
	local config = setmetatable({}, {__index = function(_, key)
		local value = live[key]
		if value == nil then value = defaults[key] end
		return value
	end})

	local function on(key) return config[key] == "1" end

	-- 挂钩名字 -> 什么时候算开着：同名设置是 "1"
	local function gate_of(feature)
		return function() return on(feature) end
	end

	local marker = {version = "hellbox-1", status = "waiting", features = {}, module_errors = {}, config = config}  -- config：蜜蜂灯等别的脚本也读
	rawset(_G, "HellBoxHop", marker)

	local function log(where, problem)
		if rawget(_G, "HellBoxLog") then pcall(HellBoxLog, "hellbox_hop", tostring(where) .. ": " .. tostring(problem)) end
	end

	-- 替身 host：BetterHUD 适配器要 claim / release
	local host = {}
	function host:claim() return true end
	function host:release() end

	-- 和半糖 hooks.lua 一样的注册办法，多一层「每次调用看开关」
	local hooks = {}
	do
		local installed = setmetatable({}, {__mode = "k"})
		function hooks.wrap(class_name, method, feature, factory)
			local class = rawget(_G, class_name)
			if type(class) ~= "table" or type(class[method]) ~= "function" then
				marker.features[feature] = "waiting:" .. class_name .. "." .. method
				return false
			end
			local methods = installed[class]
			if not methods then methods = {}; installed[class] = methods end
			local key = feature .. ":" .. method
			if methods[key] then return true end
			local native = class[method]
			local wrapper = factory(native)
			assert(type(wrapper) == "function", "invalid_optimization_wrapper")
			local gate = gate_of(feature)
			local gated = function(...)
				if gate() then return wrapper(...) end
				return native(...)
			end
			class[method] = gated
			methods[key] = gated
			marker.features[feature] = "installed"
			return true
		end
		function hooks.copy(value)
			local copy = {}
			for k, v in pairs(value or {}) do copy[k] = v end
			return copy
		end
		function hooks.scoped(object, key, value, call)
			local previous = object[key]
			object[key] = value
			local function finish(ok, ...)
				object[key] = previous
				if not ok then error((...), 0) end
				return ...
			end
			return finish(pcall(call))
		end
	end

	-- 读 HellBox 写的设置文件
	local last_text
	local function read_live()
		local appdata = os.getenv and os.getenv("APPDATA")
		local f = appdata and io and io.open and io.open(appdata .. "/Arrowhead/Helldivers/hellbox/hop.txt", "rb")
		if not f then return end
		local text = f:read("*a") or ""
		f:close()
		if text == last_text or not text:match("^HBHOP1") then return end
		last_text = text
		local fresh = {}
		for line in text:gmatch("[^\r\n]+") do
			local k, v = line:match("^([%w_]+)=(.*)$")
			if k then fresh[k] = v end
		end
		live = fresh
	end

	local env = context_factory()
	local extensions = {
		readability = readability_factory(config, hooks),
	}
	local disabled = {}

	local weapons_installed = false
	local function install()
		for name, extension in pairs(extensions) do
			if not disabled[name] then
				local ok, result = pcall(extension)
				if not ok then
					disabled[name] = true
					marker.module_errors[name] = tostring(result):sub(1, 512)
					log(name, result)
				end
			end
		end
		if not weapons_installed and type(CharacterStateMachine) == "table"
				and type(CharacterStateMachine.update) == "function" then
			local native = CharacterStateMachine.update
			local wrapped = constitution_factory(env)(native)
			CharacterStateMachine.update = function(...)
				if on("bolt_reload") then return wrapped(...) end
				return native(...)
			end
			weapons_installed = true
		end
		marker.status = next(disabled) and "partial_error" or "installed"
	end

	pcall(read_live)
	pcall(install)
	if WorldManager and WorldManager.update then
		local original = WorldManager.update
		local next_read, next_install = 0, 0
		WorldManager.update = function(self, ...)
			local now = Application and Application.time_since_launch and Application.time_since_launch() or os.clock()
			if now >= next_read then
				next_read = now + 1
				pcall(read_live)
			end
			if now >= next_install then
				next_install = now + 0.25
				local ok, problem = pcall(install)
				if not ok then log("install", problem) end
			end
			return original(self, ...)
		end
	end
end

end
