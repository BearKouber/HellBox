-- [player params] HellBox「数据」页「潜兵」的游戏这边（2026-11-15，用户要：数据里加上潜兵自己的数据、两种无敌）。
-- 由 build.py 追加到 character_state_machine 末尾，要在 data_live.lua 前面（data_live 调 PlayerParamsMod.apply）。
--
-- 改两样，只管这台电脑自己控制的潜兵（你和本机 2P）：
--   倍数 common：潜兵设置表里的数按原值乘（health_info.health*2 = 血量翻倍；character_info.move_speed_jog*1.5 …）。
--     潜兵的设置表 = 有 character_info、health_info、没有 enemy_info 的那种（游戏里两份：unknown_4d81… 和 unknown_581b…，
--     原版血量 100、跑步 4、冲刺 5～7、冲刺体力 5 秒、装甲 35）。游戏生成角色时用 LoadoutSettings.get_upgraded_settings
--     读设置表，这里包一层套上；跑步速度这类每次换动作都重新读设置表，改了马上生效；已经在场的角色把血量上限、回血、
--     装甲、倒地能撑多久同步过去。
--   无敌 god：
--     off  原版
--     heal 加血无敌：血一掉就补满（挨打、被打飞照常；倒地马上站起来；一下打掉的血超过 血量 + 倒地那一截 还是会死）。
--          只靠打完再补救不了一下打死（2026-10-13 陪玩那边实测：雷鸣炸自己 1800），所以叫「加血」，和真无敌分开。
--     true 真无敌：挨打那一下不扣血（游戏自带的 health 状态 invincible，撤离时原版就这么用；只在这一下里打开，打完还原，
--          不碰撤离自己设的）。掉出地图下面还是会死（那是直接改血，不走挨打）。
--   挨打的挂点：HealthComponent.command_master 的 do_damage（只看本机控制的潜兵：EntityAux.owned）。
--
-- 命令（data_live.lua 每秒读 data-live.txt 的 player= 那一行，变了才调）：
--   reset
--   god=heal;common=health_info.health*2,character_info.move_speed_jog*1.5
do
	local G = PlayerParamsMod or {}

	PlayerParamsMod = G
	G.common = G.common or {}
	G.god = G.god or "off"
	G.base = G.base or setmetatable({}, { __mode = "k" })

	local function split_path(path)
		local parts = {}

		for p in tostring(path):gmatch("[^%.]+") do
			parts[#parts + 1] = p
		end

		return parts
	end

	local function get_path(tbl, path)
		local cur = tbl

		for _, p in ipairs(split_path(path)) do
			if type(cur) ~= "table" then
				return nil
			end

			cur = cur[p]
		end

		return cur
	end

	local function set_path(tbl, path, val)
		local parts = split_path(path)
		local cur = tbl

		for i = 1, #parts - 1 do
			cur = cur[parts[i]]

			if type(cur) ~= "table" then
				return
			end
		end

		cur[parts[#parts]] = val
	end

	local function is_player(tbl)
		return type(tbl) == "table" and type(tbl.character_info) == "table" and type(tbl.health_info) == "table"
			and tbl.enemy_info == nil
	end

	-- 先把记下的原值写回去，再按现在的倍数重新乘（重复调不会越乘越大）
	local function apply_table(tbl)
		if not is_player(tbl) then
			return
		end

		local saved = G.base[tbl]

		if not saved then
			saved = {}
			G.base[tbl] = saved
		end

		for path, v in pairs(saved) do
			set_path(tbl, path, v)
		end

		for path, mult in pairs(G.common) do
			local orig = saved[path]

			if orig == nil then
				orig = get_path(tbl, path)

				if type(orig) == "number" then
					saved[path] = orig
				end
			end

			if type(orig) == "number" then
				local v = orig * mult

				if path == "health_info.health" then
					v = math.max(1, v)
				end

				set_path(tbl, path, v)
			end
		end
	end

	local function game_state()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if not sm or sm:get_current_state_name() ~= "game" then
			return nil
		end

		return sm:get_current_state()
	end

	-- 本机控制的、活着的潜兵
	local function own_units()
		local out = {}
		local st = game_state()

		if type(st) ~= "table" or type(st.players) ~= "table" then
			return out
		end

		for _, p in pairs(st.players) do
			local go = type(p) == "table" and p.player_go

			if go and go:exists() and go:owned() then
				local u = go:get("avatar_unit")

				if u and Unit.alive(u) then
					out[#out + 1] = u
				end
			end
		end

		return out, st
	end

	local function master_ctx(st, name, unit)
		local em = st.entity_manager
		local groups = type(em) == "table" and em.component_name_to_contexts
		local group = type(groups) == "table" and groups[name]

		return type(group) == "table" and type(group.master) == "table" and group.master[unit] or nil
	end

	-- 已经在场的潜兵：设置表套上新倍数，血量上限 / 回血 / 装甲 / 倒地那一截同步过去（血条比例不变）
	local function patch_live()
		local units, st = own_units()

		for _, u in ipairs(units) do
			local ok, err = pcall(function()
				local cctx = master_ctx(st, "character", u)

				if cctx then
					apply_table(cctx.settings)
				end

				local hctx = master_ctx(st, "health", u)
				local hs = hctx and hctx.state
				local info = hs and hs.health_info

				if type(info) ~= "table" then
					return
				end

				apply_table(cctx and cctx.settings)

				local want = tonumber(info.health)

				if want and want > 0 and want ~= hs.max_hitpoints then
					local old = tonumber(hs.max_hitpoints) or want
					local real = tonumber(hs.hitpoints_real) or old

					hs.max_hitpoints = want

					if real > 0 then
						EntityAux.queue_command_master(u, "health", "set_hitpoints", math.max(1, math.floor(real / old * want + 0.5)))
					end
				end

				hs.constitution = -(tonumber(info.constitution) or 0)
				hs.constitution_decay = tonumber(info.constitution_decay) or 0
				EntityAux.queue_command_master(u, "health", "set_health_decay", nil)
				EntityAux.queue_command_master(u, "health", "armor", { armor_min = info.armor_min or 0, armor_max = info.armor_max or 0 })
			end)

			if not ok and rawget(_G, "HellBoxLog") then
				HellBoxLog("player_params", tostring(err))
			end
		end
	end

	local function apply_command(text)
		text = tostring(text or "reset")

		local common, god = {}, "off"

		if text ~= "reset" then
			for part in text:gmatch("[^;]+") do
				local k, v = part:match("^(%w+)=(.*)$")

				if k == "god" then
					god = (v == "heal" or v == "true") and v or "off"
				elseif k == "common" then
					for item in v:gmatch("[^,]+") do
						local path, m = item:match("^([%w_%.]+)%*([%d%.]+)$")

						m = tonumber(m)

						if path and m and m >= 0 and m <= 100 then
							common[path] = m
						end
					end
				end
			end
		end

		G.common = common
		G.god = god

		for tbl in pairs(G.base) do
			apply_table(tbl)
		end

		patch_live()

		local n = 0

		for _ in pairs(common) do
			n = n + 1
		end

		return string.format("ok:god=%s,n=%d", god, n)
	end

	G.apply = apply_command

	-- 挂点 1：设置表（生成角色时）
	local cls = rawget(_G, "LoadoutSettings")

	if type(cls) == "table" and type(cls.get_upgraded_settings) == "function" and not rawget(cls, "_player_params_hooked") then
		local orig = cls.get_upgraded_settings

		cls.get_upgraded_settings = function(unit, upgrade, ...)
			local res = orig(unit, upgrade, ...)

			if next(G.common) and is_player(res) then
				pcall(apply_table, res)
			end

			return res
		end
		cls._player_params_hooked = true
	end

	-- 挂点 2：挨打（do_damage）
	local function own_character(unit)
		return EntityAux.has_component(unit, "character") and EntityAux.owned(unit)
	end

	local hc = rawget(_G, "HealthComponent")

	if type(hc) == "table" and type(hc.command_master) == "function" and hc.command_master ~= G.wrapped_health then
		local orig = hc.command_master

		local function after(ctx, ...)
			if ctx then
				pcall(function()
					local s = ctx.state

					if s.hitpoints_real > s.constitution and s.hitpoints_real < s.max_hitpoints then
						EntityAux.queue_command_master(ctx.unit, "health", "set_hitpoints", s.max_hitpoints)
					end
				end)
			end

			return ...
		end

		G.wrapped_health = function(self, unit, ent, cmd, arg, ...)
			if cmd ~= "do_damage" or G.god == "off" or type(ent) ~= "table" or type(ent.state) ~= "table" then
				return orig(self, unit, ent, cmd, arg, ...)
			end

			local ok, mine = pcall(own_character, unit)

			if not ok or not mine then
				return orig(self, unit, ent, cmd, arg, ...)
			end

			if G.god == "true" then
				local s = ent.state
				local prev = s.invincible

				s.invincible = true

				local res = { pcall(orig, self, unit, ent, cmd, arg, ...) }

				s.invincible = prev

				if not res[1] then
					error(res[2], 0)
				end

				return unpack(res, 2)
			end

			return after({ state = ent.state, unit = unit }, orig(self, unit, ent, cmd, arg, ...))
		end
		hc.command_master = G.wrapped_health
	end

	-- 挂点 3：加血无敌时每帧补满（中毒、着火这类持续掉血也补；倒地还没死的补满 = 原地站起来，和队友救起一样走 hitpoints > 0）
	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped_update then
		local orig = wm.update

		G.wrapped_update = function(self, dt, ...)
			if G.god == "heal" then
				local ok, err = pcall(function()
					local units, st = own_units()

					for _, u in ipairs(units) do
						local hctx = master_ctx(st, "health", u)
						local s = hctx and hctx.state

						if s and s.hitpoints_real > s.constitution and s.hitpoints_real < s.max_hitpoints then
							EntityAux.queue_command_master(u, "health", "set_hitpoints", s.max_hitpoints)
						end
					end
				end)

				if not ok and rawget(_G, "HellBoxLog") then
					HellBoxLog("player_params", tostring(err))
				end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped_update
	end
end
