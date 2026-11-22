-- [weapon params] HellBox「数据修改」页武器属性块的游戏这边（2026-11-14，HD1-033）。由 build.py 追加到
-- character_state_machine 末尾，要在 data_live.lua 前面（data_live 调这里放出来的 WeaponParamsMod.apply）。
--
-- 改玩家武器（主武器 / 副武器 / 支援武器，以及它们打出去的榴弹、导弹、炸药包）的设置表：
--   游戏在武器生成 / 重算时用 LoadoutSettings.get_upgraded_settings(单位, 升级值) 取设置表
--   （loadout_settings.lua:4255；firearm_component.lua:31/71/110/156，beamweapon :24/70，arcweapon :24/95，
--     flameweapon :33/60/115，launcher :141/181/201，healbeam :154，melee_component :107/113，explosive_component :14/37）。
--   这里包一层：认出是哪把武器的表（按单位路径），把改动直接写进表里，第一次改之前记下原值，恢复 = 写回原值。
--   升级：每种升级组合是一张单独的表（create_upgrade_settings_permutations :4413 预先算好），倍率按那张表里
--   （装了升级后的）数值乘；直接写数 = 每张表都写这个数。
--
-- 命令（WeaponParamsMod.apply(文字)，返回结果文字；data_live.lua 每秒读 data-live.txt 的 weapon= 行交给这里）：
--   reset                                  全部恢复原版
--   set=武器.路径*倍数,武器.路径=值,...     武器 = 单位短名（wep_assaultrifle_01、equipment_impact_grenade_02 …，见 KEYS）
--                                          值：数字 / true / false；default = 这一项按原版（等于不写）
--   common=路径*倍数,...                    所有认得的武器里有这个数值字段的都按自己的原值乘（HellBox 现在不发这一段，
--                                          「全部武器」在 HellBox 那边展开成 set；留着手动调试用）
--   common=...;set=...                      两段一起换；只发一段 = 另一段不动
--   同一项 common 和 set 都有时以 set 为准。
--
-- 热生效：
--   - 伤害、暴击、穿甲 / 穿透、爆炸参数、近战、修理量：游戏每次命中时直接读设置表，下一发就变。
--   - 射速、散布、弹匣、射程、换弹、散热、蓄能这类组件在生成时抄进自己状态里的，这里包了各武器组件的
--     update_masters / update_slaves：命令变了以后下一帧对手上已有的枪重跑一次组件自己的 reload_master /
--     reload_slave（喷火器只补抄几个字段，不重跑，免得丢掉已经生成的燃烧区），弹匣变小时多出来的子弹去掉。
--   - 维修工具：修理量、距离下一次判定就变；同时修理数、移动转向下一帧补抄。
--   - 炸药包携带数：下次拿到 / 生成时生效（throwable_weapon_component 只在 setup 时抄）。
-- 安全：所有改动 pcall 包着；不会让射速 / 弹匣 / 射程等变成 0（除以零），开火方式不会被改成「单发、全自动都不行」
--   （游戏里有 assert，会崩）。
-- 联机：只改本机的设置表。本机玩家（和本机 2P / AI 队友）的枪按改过的算；别人的枪在他们电脑上按他们的设置。
--   子弹伤害由开枪那台电脑算（weapon_utility.lua shoot_ray_callback），所以别人看到你的伤害也是改过的，但别人自己的枪不变。
do
	local G = WeaponParamsMod or {}

	WeaponParamsMod = G

	if not G.ready then
		G.ready = true
		G.ov = {}
		G.common = {}
		G.base = setmetatable({}, { __mode = "k" })     -- 设置表 -> {路径 = {has, v}}（原值）
		G.touched = setmetatable({}, { __mode = "k" })  -- 设置表 -> 武器短名（改过 / 认出来的表）
		G.ident = setmetatable({}, { __mode = "k" })    -- 设置表 -> 武器短名 / false
		G.setup_arg = setmetatable({}, { __mode = "k" }) -- 组件数据 -> setup 时的参数（重跑 reload 用同一个升级值）
		G.done = setmetatable({}, { __mode = "k" })     -- 组件实例 -> {m = 已同步的代数, s = …}
		G.gen = 0
		G.errors = 0
		G.result = ""
	end

	-- 认得的单位（武器 + 它们的弹头 / 炸药包）；和 ai/weapon_fields.json 对应
	local KEYS = {
		"wep_assaultrifle_01", "wep_assaultrifle_02", "wep_assaultrifle_03", "wep_nailgun_01", "wep_machinegun_light",
		"wep_shotgun_01", "wep_shotgun_02", "wep_shotgun_03", "wep_submachinegun_01", "wep_submachinegun_02",
		"wep_submachinegun_03", "wep_marksmanrifle_01", "wep_bolt_action_01", "wep_railgun_01", "wep_canisterrifle_01",
		"wep_plasma_01", "wep_laserrifle_01", "wep_laserrifle_02", "wep_lasersmg_01", "wep_lasershotgun_01",
		"wep_arcrifle_01", "wep_arcshotgun_01", "wep_pistol_01", "wep_revolver_01", "wep_flamepistol_01",
		"wep_plasmapistol_01", "wep_mg_01", "wep_mg_02", "wep_lasercannon_01", "wep_20mm_cannon",
		"wep_grenadelauncher_01", "wep_mortar_01", "wep_flamethrower_01", "wep_chemthrower_01", "wep_rpg_01",
		"wep_law_01", "wep_missile_launcher_01", "wep_satchelcharge_01", "wep_repairtool_01",
		"equipment_impact_grenade_02", "equipment_impact_grenade_incendiary", "equipment_impact_grenade_03",
		"equipment_impact_grenade_toxic", "gameobject_homing_missile_01", "gameobject_homing_missile_02",
		"equipment_satchelcharge_01", "equipment_satchelcharge_02",
	}
	local IS_KEY = {}

	for _, k in ipairs(KEYS) do
		IS_KEY[k] = true
	end

	local function full_path(key)
		if string.sub(key, 1, 11) == "gameobject_" then
			return "gameobjects/" .. key
		end

		return "equipment/" .. key
	end

	-- 取整的字段、下限（防除零 / 防不开火）
	local INT = {
		["weapon_info.magazine_capacity"] = true, ["weapon_info.magazines"] = true, ["weapon_info.magazines_max"] = true,
		["weapon_info.shots_per_round"] = true, ["weapon_info.burst_rounds"] = true,
		["weapon_info.min_number_of_jumps"] = true, ["weapon_info.max_number_of_jumps"] = true,
		["weapon_info.max_num_targets"] = true,
	}
	local MIN = {
		["weapon_info.firerate"] = 1, ["weapon_info.magazine_capacity"] = 1, ["weapon_info.range"] = 1,
		["weapon_info.spread_shots_max"] = 1, ["weapon_info.heat_capacity"] = 0.05, ["weapon_info.max_charge_time"] = 0.05,
		["weapon_info.max_range"] = 0.5, ["weapon_info.max_range_from_owner"] = 1, ["weapon_info.shots_per_round"] = 1,
		["weapon_info.burst_rounds"] = 1, ["weapon_info.max_num_targets"] = 1, ["explosive_info.blast_radius"] = 0.1,
	}

	local function note_error(err)
		G.errors = (G.errors or 0) + 1
		G.last_error = tostring(err)

		if rawget(_G, "HellBoxLog") then
			HellBoxLog("weapon_params", G.last_error)
		end
	end

	--------------------------------------------------------------------------
	-- 表路径
	--------------------------------------------------------------------------
	local function split_path(path)
		local parts = {}

		for p in string.gmatch(path or "", "[^.]+") do
			parts[#parts + 1] = p
		end

		return parts
	end

	local function get_path(tbl, path)
		local cur = tbl

		for _, part in ipairs(split_path(path)) do
			if type(cur) ~= "table" then
				return nil
			end

			cur = cur[part]
		end

		return cur
	end

	-- 只改已经存在的子表（weapon_info / attributes），不凭空造 explosive_info 之类
	local function set_path(tbl, path, val)
		local parts = split_path(path)

		if #parts == 0 then
			return false
		end

		local cur = tbl

		for i = 1, #parts - 1 do
			cur = cur[parts[i]]

			if type(cur) ~= "table" then
				return false
			end
		end

		cur[parts[#parts]] = val

		return true
	end

	local function fix_number(path, v)
		if INT[path] then
			v = math.floor(v + 0.5)
		end

		local lo = MIN[path]

		if lo and v < lo then
			v = lo
		end

		return v
	end

	local function parse_value(s)
		if s == "true" then
			return true
		elseif s == "false" then
			return false
		end

		return tonumber(s)
	end

	--------------------------------------------------------------------------
	-- 认表：这张设置表是哪把武器的
	--------------------------------------------------------------------------
	local function build_rev()
		local lsm = rawget(_G, "LuaSettingsManager")

		G.rev = setmetatable({}, { __mode = "k" })

		if type(lsm) ~= "table" and type(lsm) ~= "userdata" then
			return
		end

		for _, key in ipairs(KEYS) do
			local ok, base = pcall(lsm.get_settings_by_unit_path, lsm, full_path(key))

			if ok and type(base) == "table" then
				G.rev[base] = key
			end
		end
	end

	local function identify(unit, tbl)
		local known = G.ident[tbl]

		if known ~= nil then
			return known or nil
		end

		local key = false

		-- 怪物的表（有 enemy_info）不是武器
		if type(tbl.enemy_info) ~= "table" and (type(tbl.weapon_info) == "table" or type(tbl.explosive_info) == "table") then
			if not G.rev then
				build_rev()
			end

			local lsm = rawget(_G, "LuaSettingsManager")

			if lsm and unit then
				local ok, base = pcall(lsm.get_settings_by_unit, lsm, unit)

				if ok and type(base) == "table" then
					key = G.rev[base] or false
				end
			end

			if not key and G.rev[tbl] then
				key = G.rev[tbl]
			end

			-- 兜底：按单位类型比（firearm_component.lua:206 同样用 Unit.is_a 比路径）
			if not key and unit and rawget(_G, "Unit") and Unit.is_a then
				for _, k in ipairs(KEYS) do
					local ok, yes = pcall(Unit.is_a, unit, full_path(k))

					if ok and yes then
						key = k

						break
					end
				end
			end
		end

		G.ident[tbl] = key

		return key or nil
	end

	--------------------------------------------------------------------------
	-- 套改动 / 恢复
	--------------------------------------------------------------------------
	local function remember(tbl, saved, path)
		if saved[path] == nil then
			local cur = get_path(tbl, path)

			saved[path] = { has = cur ~= nil, v = cur }
		end

		return saved[path]
	end

	local function apply_table(tbl, key)
		local saved = G.base[tbl]

		if not saved then
			saved = {}
			G.base[tbl] = saved
		end

		G.touched[tbl] = key

		local ov = G.ov[key] or {}

		-- 1) 全体倍率（单只设了的跳过，以单只为准）
		for path, mult in pairs(G.common) do
			if ov[path] == nil then
				local orig = get_path(tbl, path)

				if saved[path] then
					orig = saved[path].v
				end

				if type(orig) == "number" then
					remember(tbl, saved, path)
					set_path(tbl, path, fix_number(path, orig * mult))
				end
			end
		end

		-- 2) 单把覆盖
		for path, val in pairs(ov) do
			local s = remember(tbl, saved, path)

			if type(val) == "table" then
				if type(s.v) == "number" then
					set_path(tbl, path, fix_number(path, s.v * val.mult))
				end
			elseif type(val) == "number" then
				if s.has or string.find(path, "^weapon_info%.") then
					set_path(tbl, path, fix_number(path, val))
				end
			elseif type(val) == "boolean" then
				set_path(tbl, path, val)
			end
		end

		-- 3) 开火方式不能全关（firearm_component.lua:37 等有 assert）
		local wi = tbl.weapon_info
		local attrs = type(wi) == "table" and wi.attributes

		if type(attrs) == "table" and (ov["weapon_info.attributes.fully_automatic"] ~= nil or ov["weapon_info.attributes.semi_automatic"] ~= nil) then
			if not attrs.semi_automatic and not attrs.fully_automatic and not attrs.fire_on_release then
				remember(tbl, saved, "weapon_info.attributes.semi_automatic")
				attrs.semi_automatic = true
			end
		end
	end

	local function restore_all()
		for tbl, saved in pairs(G.base) do
			for path, s in pairs(saved) do
				if s.has then
					set_path(tbl, path, s.v)
				else
					set_path(tbl, path, nil)
				end
			end
		end

		G.base = setmetatable({}, { __mode = "k" })
	end

	--------------------------------------------------------------------------
	-- 手上已有的枪：组件抄进状态里的字段重算
	--------------------------------------------------------------------------
	local function clamp_rounds(comp, st, protected)
		local cap = tonumber(st.magazine_capacity)
		local rounds = tonumber(st.rounds)

		if cap and rounds then
			local limit = cap + ((type(st.attributes) == "table" and st.attributes.chambered) and 1 or 0)

			if rounds > limit then
				if protected then
					comp:set_protected(st, "rounds", limit)
				else
					st.rounds = limit
				end
			end
		end

		local mx = tonumber(st.magazines_max)
		local mags = tonumber(st.num_mags)

		if mx and mags and mags > mx then
			if protected then
				comp:set_protected(st, "num_mags", mx)
			else
				st.num_mags = mx
			end
		end
	end

	local MASTER = {
		FirearmComponent = function(comp, unit, ctx)
			comp:reload_master(unit, ctx, G.setup_arg[ctx])

			local st = ctx.state
			local wi = st.weapon_info

			st.magazines_max = wi.magazines_max or 0
			st.magazines = wi.magazines or 0
			clamp_rounds(comp, st, true)
		end,
		BeamweaponComponent = function(comp, unit, ctx)
			comp:reload_master(unit, ctx, G.setup_arg[ctx])
			clamp_rounds(comp, ctx.state, false)
		end,
		ArcweaponComponent = function(comp, unit, ctx)
			comp:reload_master(unit, ctx, G.setup_arg[ctx])
			ctx.state.magazines_max = ctx.state.weapon_info.magazines_max or 0
		end,
		LauncherComponent = function(comp, unit, ctx)
			comp:reload_master(unit, ctx, G.setup_arg[ctx])
			clamp_rounds(comp, ctx.state, false)
		end,
		-- 喷火器的 reload_master 会把已生成的燃烧区清单清空，这里只补抄会变的字段（flameweapon_component.lua:31-104）
		FlameweaponComponent = function(comp, unit, ctx)
			local st = ctx.state
			local wi = st.weapon_info

			if type(wi) ~= "table" then
				return
			end

			st.spread = math.rad(wi.spread or 0)
			st.shots_per_round = wi.shots_per_round or 1
			st.move_speed_reload = wi.move_speed_reload or 1
			st.move_speed_aim = wi.move_speed_aim or 1
			st.turn_speed_reload = wi.turn_speed_reload or 1
			st.turn_speed_aim = wi.turn_speed_aim or 1
			st.magazines_max = wi.magazines_max

			local cap = wi.magazine_capacity or 0

			if comp.get_ammo_from_hits_half_magazine then
				cap = math.ceil(cap / 2)
			end

			comp:set_protected(st, "magazine_capacity", cap)
			clamp_rounds(comp, st, true)
		end,
		-- 维修工具的 reload_master 会把弹药重置（healbeam_component.lua:12-30），只补抄
		HealbeamComponent = function(comp, unit, ctx)
			local st = ctx.state
			local wi = LoadoutSettings.get_upgraded_settings(unit, G.setup_arg[ctx] and G.setup_arg[ctx].upgrade_value).weapon_info

			if type(wi) ~= "table" then
				return
			end

			st.weapon_info = wi
			st.max_num_targets = wi.max_num_targets or 1
			st.move_speed_reload = wi.move_speed_reload or 1
			st.move_speed_aim = wi.move_speed_aim or 1
			st.turn_speed_reload = wi.turn_speed_reload or 1
			st.turn_speed_aim = wi.turn_speed_aim or 1
			st.turn_speed_fire = wi.turn_speed_fire or nil
		end,
	}

	local SLAVE = {
		FirearmComponent = function(comp, unit, ctx)
			comp:reload_slave(unit, ctx, G.setup_arg[ctx])
		end,
		BeamweaponComponent = function(comp, unit, ctx)
			comp:reload_slave(unit, ctx, G.setup_arg[ctx])
		end,
		ArcweaponComponent = function(comp, unit, ctx)
			comp:reload_slave(unit, ctx, G.setup_arg[ctx])
		end,
		LauncherComponent = function(comp, unit, ctx)
			comp:reload_slave(unit, ctx, G.setup_arg[ctx])
		end,
		FlameweaponComponent = function(comp, unit, ctx)
			comp:reload_slave(unit, ctx, G.setup_arg[ctx])

			local st = ctx.state
			local wi = st.weapon_info
			local cap = wi.magazine_capacity or 0

			if comp.get_ammo_from_hits_half_magazine then
				cap = math.ceil(cap / 2)
			end

			st.magazine_capacity = cap
			st.magazines_max = wi.magazines_max
		end,
		HealbeamComponent = function(comp, unit, ctx)
			comp:reload_slave(unit, ctx)
		end,
	}

	local function resync(comp, which, fn, units)
		local d = G.done[comp]

		if not d then
			d = {}
			G.done[comp] = d
		end

		if G.gen == 0 or d[which] == G.gen then
			return
		end

		d[which] = G.gen

		if type(units) ~= "table" then
			return
		end

		for unit, ctx in pairs(units) do
			if type(ctx) == "table" and type(ctx.state) == "table" then
				local ok, err = pcall(fn, comp, unit, ctx)

				if not ok then
					note_error(err)
				end
			end
		end
	end

	local function hook_component(name)
		local cls = rawget(_G, name)

		if type(cls) ~= "table" or rawget(cls, "_weapon_params_hooked") then
			return
		end

		local mfn, sfn = MASTER[name], SLAVE[name]

		for _, which in ipairs({ "setup_master", "setup_slave" }) do
			local orig = rawget(cls, which) or cls[which]

			if type(orig) == "function" then
				cls[which] = function(self, unit, ctx, arg, ...)
					if type(ctx) == "table" then
						G.setup_arg[ctx] = arg
					end

					return orig(self, unit, ctx, arg, ...)
				end
			end
		end

		if mfn and type(cls.update_masters) == "function" then
			local orig = cls.update_masters

			cls.update_masters = function(self, units, ...)
				resync(self, "m", mfn, units)

				return orig(self, units, ...)
			end
		end

		if sfn and type(cls.update_slaves) == "function" then
			local orig = cls.update_slaves

			cls.update_slaves = function(self, units, ...)
				resync(self, "s", sfn, units)

				return orig(self, units, ...)
			end
		end

		cls._weapon_params_hooked = true
	end

	--------------------------------------------------------------------------
	-- 命令
	--------------------------------------------------------------------------
	local function count(t)
		local n = 0

		for _, v in pairs(t) do
			if type(v) == "table" then
				for _ in pairs(v) do
					n = n + 1
				end
			else
				n = n + 1
			end
		end

		return n
	end

	local function reapply()
		for tbl, key in pairs(G.touched) do
			local ok, err = pcall(apply_table, tbl, key)

			if not ok then
				note_error(err)
			end
		end

		G.gen = G.gen + 1
	end

	local function apply_command(text)
		text = (text or ""):gsub("^%s+", ""):gsub("%s+$", "")

		if text == "reset" or text == "" then
			restore_all()
			G.ov = {}
			G.common = {}
			G.gen = G.gen + 1

			return "ok:reset"
		end

		local common, ov = {}, {}
		local bad = 0
		local has_common, has_set = false, false

		for part in string.gmatch(text, "[^;]+") do
			local k, body = string.match(part, "^%s*([%w_]+)%s*=%s*(.-)%s*$")

			if k == "common" then
				has_common = true

				for entry in string.gmatch(body .. ",", "([^,]*),") do
					local path, mult = string.match(entry, "^%s*([%w_%.]+)%s*%*%s*([%d%.]+)%s*$")
					local n = tonumber(mult)

					if path and n and n >= 0 and n <= 100 then
						common[path] = n
					elseif string.gsub(entry, "%s", "") ~= "" then
						bad = bad + 1
					end
				end
			elseif k == "set" then
				has_set = true

				for entry in string.gmatch(body .. ",", "([^,]*),") do
					local key, path, rest = string.match(entry, "^%s*([%w_]+)%.([%w_%.]+)%s*([=%*].-)%s*$")
					local ok = false

					if key and IS_KEY[key] then
						local op, val = string.sub(rest, 1, 1), string.match(string.sub(rest, 2), "^%s*(.-)%s*$")

						if op == "*" then
							local n = tonumber(val)

							if n and n >= 0 and n <= 100 then
								ov[key] = ov[key] or {}
								ov[key][path] = { mult = n }
								ok = true
							end
						elseif val == "default" then
							ok = true
						else
							local v = parse_value(val)

							if v ~= nil then
								ov[key] = ov[key] or {}
								ov[key][path] = v
								ok = true
							end
						end
					end

					if not ok and string.gsub(entry, "%s", "") ~= "" then
						bad = bad + 1
					end
				end
			elseif k then
				return "err:不认识的键：" .. k
			end
		end

		if not has_common and not has_set then
			return "err:看不懂的命令"
		end

		restore_all()

		if has_common then
			G.common = common
		end

		if has_set then
			G.ov = ov
		end

		reapply()

		return string.format("ok:n=%d;c=%d;bad=%d", count(G.ov), count(G.common), bad)
	end

	G.apply = function(text)
		local ok, res = pcall(apply_command, text)

		if not ok then
			note_error(res)
			res = "err:" .. tostring(res)
		end

		G.result = res

		return res
	end

	--------------------------------------------------------------------------
	-- 挂点
	--------------------------------------------------------------------------
	local function hook_loadout()
		local cls = rawget(_G, "LoadoutSettings")

		if type(cls) ~= "table" or type(cls.get_upgraded_settings) ~= "function" or rawget(cls, "_weapon_params_hooked") then
			return
		end

		local orig = cls.get_upgraded_settings

		cls.get_upgraded_settings = function(unit, upgrade, ...)
			local res = orig(unit, upgrade, ...)

			if type(res) == "table" and (next(G.ov) or next(G.common)) then
				local ok, err = pcall(function()
					local key = identify(unit, res)

					if key then
						apply_table(res, key)
					end
				end)

				if not ok then
					note_error(err)
				end
			end

			return res
		end
		cls._weapon_params_hooked = true
	end

	local COMPONENTS = { "FirearmComponent", "BeamweaponComponent", "ArcweaponComponent", "FlameweaponComponent",
		"LauncherComponent", "HealbeamComponent" }

	local function hook_all()
		hook_loadout()

		for _, name in ipairs(COMPONENTS) do
			hook_component(name)
		end
	end

	G.hook_all = hook_all  -- 测试 / 调试用

	local ok0, err0 = pcall(hook_all)

	if not ok0 then
		note_error(err0)
	end

	-- 有的类加载得晚：每帧补挂一次（都是 rawget 判断，挂过的直接跳过）
	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_weapon_params_hooked") then
		local orig = wm.update

		wm.update = function(self, dt, ...)
			local ok, err = pcall(hook_all)

			if not ok then
				note_error(err)
			end

			return orig(self, dt, ...)
		end
		wm._weapon_params_hooked = true
	end
end
