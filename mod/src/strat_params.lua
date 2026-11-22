-- [strat params] HellBox「数据修改」页战备属性（蓝 / 红 / 绿 / 车辆 / 黄）的游戏这边（2026-11-14，HD1-033）。
-- 由 build.py 追加到 character_state_machine 末尾，要在 data_live.lua 前面（data_live 调这里放出来的 StratParamsMod.apply）。
--
-- 改什么：
--   1) 战备本身：LoadoutSettings.stratagems 里每个战备的表（冷却 cooldown_time、呼叫时间 activation_time、
--      次数 num_uses、惊动巡逻范围 patrol_alert_radius……）。升级表 upgrades[k] 里写了同一项的一起改，
--      所以 get_upgraded_stratagem（loadout_settings.lua:4076，升级 = 克隆后逐级覆盖）出来的值也对。
--   2) 战备投下来的东西：炮台、空袭、地雷、载具……的单位设置表。按单位路径找：
--      LuaSettingsManager:get_settings_by_unit_path(路径) 是原表，get_modified_settings(路径, k) 是升级 k 级的那份
--      （游戏开局时由 create_upgrade_settings_permutations 克隆好，loadout_settings.lua:4413），每一份就地改。
--      组件生成时用 LoadoutSettings.get_upgraded_settings 拿到的就是这几份表。
--   第一次改某个格子前记下原值；每次换命令先全部写回原值，再把五类按各自的设置重新套一遍，所以：
--   各类互不覆盖、reset = 这一类回原版、五类都 reset = 完全回到原版。
--
-- 五类怎么分（和 tools/strat_fields.py 同一条规则）：stratagem_type supply = 蓝、offensive = 红、defensive = 绿、
--   special = 黄（菜单颜色 menu_screen_base.lua:527-534）；subtypes 里有 vehicle 且不是空投补给箱（没有 spawn_hellpod）= 车辆。
--
-- 命令（每类一条，data_live.lua 把 strat.<类>= 后面的内容交给 apply(类, 命令)）：
--   reset                              这一类回原版
--   common=cooldown_time*0.5,activation_time*0.5,num_uses*2
--       本类所有战备按各自的原值乘（只认战备表里的项；次数四舍五入）
--   set=战备名.路径=值,战备名.路径*倍数,...
--       路径写法：cooldown_time            战备表里的项
--                 @单位路径@设置路径        单位设置表里的项，比如
--                 @gameobjects/gameobject_hellpod_minigun_turret@weapon_info.power
--       值：数字 / true / false；*倍数 = 按原值乘（0～100），每个升级等级各按自己的原值乘；
--       直接写数 = 所有升级等级都用这个数。战备名不属于这一类的不认（算 bad）。
--   common=...;set=...                 两段一起换；只发一段时另一段保持
--   返回 ok:n=单项条数;c=倍率条数;bad=看不懂的条数;miss=找不到的单位数 或 err:原因
--
-- 什么时候生效：
--   冷却 / 呼叫时间 / 投下来的东西：下次扔信标起生效（扔的时候才读表）。
--   次数：对局里自己身上的战备马上按差值加减剩余次数（通过 inventory 的 "stratagems" 命令，inventory_component.lua:707）。
--   已经放下的炮台、电塔：每次开火 / 放电时读的项（伤害、射程、散布、索敌半径、电击范围……）马上生效；
--     放下时读的项（射速、弹量、耐久、持续时间）要等下一个。已经在路上的空袭不变。
--   载具：速度、转向每次开始驾驶时读；耐久下一辆生效。
-- 联机限制：每台电脑都用自己的设置表。自己（和本机 2P）的冷却、次数、呼叫时间是自己电脑算的，一定生效；
--   投下来的东西由扔的人的电脑生成；别的电脑上伤害、射程怎么结算没实测，别人没装同样的改动时可能不一致。
--   建议单机或全队用同一份设置。房主才有的：惊动巡逻范围（stratagem_component.lua:423）。
do
	local G = StratParamsMod or {}

	StratParamsMod = G

	local CATS = { "blue", "red", "green", "vehicle", "yellow" }
	local TYPE_CAT = { supply = "blue", offensive = "red", defensive = "green", special = "yellow" }
	-- 这些项是整数（乘完四舍五入）
	local INT_KEYS = {
		num_uses = true, num_mines = true, num_bombs = true, rounds = true, num_bolts = true,
		weapons = true, salvo_rounds = true, magazine_capacity = true,
	}
	local MAX_VALUE = 1000000
	local REFRESH = 2

	G.cats = G.cats or {}

	for _, c in ipairs(CATS) do
		G.cats[c] = G.cats[c] or { common = {}, ov = {} }
	end

	G.saved = G.saved or setmetatable({}, { __mode = "k" })
	G.result = G.result or {}
	G.errors = G.errors or 0
	G.last = G.last or -100

	local function log_err(err)
		G.errors = (G.errors or 0) + 1
		G.last_error = tostring(err)

		if rawget(_G, "HellBoxLog") then
			HellBoxLog("strat_params", G.last_error)
		end
	end

	local function split_path(path)
		local parts = {}

		for p in string.gmatch(path or "", "[^.]+") do
			parts[#parts + 1] = p
		end

		return parts
	end

	local function key_of(part)
		return tonumber(part) or part
	end

	-- 设置表可能套了一层保护（loadout_settings.lua:4420 用 __protected_table 取里面那份），写的时候写里面那份
	local function inner(t)
		if type(t) ~= "table" then
			return t
		end

		local ok, p = pcall(function()
			return t.__protected_table
		end)

		if ok and type(p) == "table" then
			return p
		end

		return t
	end

	-- 路径 -> (装这一项的表, 键)；中间断了返回 nil
	local function resolve(tbl, path)
		local parts = split_path(path)

		if #parts == 0 then
			return nil
		end

		local cur = inner(tbl)

		for i = 1, #parts - 1 do
			cur = type(cur) == "table" and inner(cur[key_of(parts[i])]) or nil

			if type(cur) ~= "table" then
				return nil
			end
		end

		return cur, key_of(parts[#parts])
	end

	local function original(box, key)
		local s = G.saved[box]

		if s and s[key] then
			return s[key].v
		end

		return box[key]
	end

	local function write(box, key, val)
		local s = G.saved[box]

		if not s then
			s = {}
			G.saved[box] = s
		end

		if s[key] == nil then
			s[key] = { has = box[key] ~= nil, v = box[key] }
		end

		box[key] = val
	end

	local function restore_all()
		for box, s in pairs(G.saved) do
			for key, o in pairs(s) do
				if o.has then
					box[key] = o.v
				else
					box[key] = nil
				end
			end
		end

		G.saved = setmetatable({}, { __mode = "k" })
	end

	-- spec：{ mult = n } 或绝对值；返回要写的值（nil = 不写）
	local function value_for(orig, spec, key)
		local v

		if type(spec) == "table" then
			if type(orig) ~= "number" then
				return nil
			end

			v = orig * spec.mult
		else
			v = spec

			if type(orig) == "boolean" and type(v) ~= "boolean" then
				return nil
			end
		end

		if type(v) == "number" then
			if v ~= v then
				return nil
			end

			v = math.max(0, math.min(MAX_VALUE, v))

			if INT_KEYS[key] then
				v = math.floor(v + 0.5)
			end
		end

		return v
	end

	local function has(list, x)
		if type(list) == "table" then
			for _, v in ipairs(list) do
				if v == x then
					return true
				end
			end
		end

		return false
	end

	local function category_of(s)
		if type(s) ~= "table" then
			return nil
		end

		if (has(s.stratagem_subtypes, "vehicle") or has(s.stratagem_subtype, "vehicle")) and not s.spawn_hellpod then
			return "vehicle"
		end

		return TYPE_CAT[s.stratagem_type]
	end

	local function find_strat(name)
		local ls = rawget(_G, "LoadoutSettings")

		if type(ls) ~= "table" or type(ls.stratagems) ~= "table" then
			return nil
		end

		for _, s in ipairs(ls.stratagems) do
			if s.name == name then
				return s
			end
		end

		return nil
	end

	--------------------------------------------------------------------------
	-- 战备表：原表 + 写了同一项的升级表
	--------------------------------------------------------------------------
	local function set_strat(s, path, spec)
		local targets = { s }

		if type(s.upgrades) == "table" then
			for _, u in ipairs(s.upgrades) do
				if type(u) == "table" then
					local box, key = resolve(u, path)

					if box and box[key] ~= nil then
						targets[#targets + 1] = u
					end
				end
			end
		end

		local n = 0

		for _, t in ipairs(targets) do
			local box, key = resolve(t, path)

			if box then
				local v = value_for(original(box, key), spec, key)

				if v ~= nil then
					write(box, key, v)
					n = n + 1
				end
			end
		end

		return n
	end

	--------------------------------------------------------------------------
	-- 单位设置表：原表 + 每个升级等级那份
	--------------------------------------------------------------------------
	-- 返回表的列表；nil = 设置管理器还没准备好（过会儿再试）；false = 没有这个单位
	local function unit_tables(upath)
		local lsm = rawget(_G, "LuaSettingsManager")

		if not lsm then
			return nil
		end

		local list, seen = {}, {}

		local function add(t)
			t = inner(t)

			if type(t) == "table" and not seen[t] then
				seen[t] = true
				list[#list + 1] = t
			end
		end

		local ok, base = pcall(lsm.get_settings_by_unit_path, lsm, upath)

		if not ok or type(base) ~= "table" then
			return false
		end

		add(base)

		local ups = inner(base).upgrade_info
		local n = type(ups) == "table" and #ups or 0

		if type(ups) == "table" and ups.type == "bitmask" then
			n = math.pow(2, n)
		end

		for k = 1, n do
			local ok2, t = pcall(lsm.get_modified_settings, lsm, upath, k)

			if ok2 then
				add(t)
			end
		end

		return list
	end

	local function set_unit(upath, spath, spec, cache)
		local list = cache[upath]

		if list == nil then
			list = unit_tables(upath)
			cache[upath] = list == nil and "wait" or list
		elseif list == "wait" then
			list = nil
		end

		if list == nil then
			return nil
		elseif not list then
			return -1
		end

		local n = 0

		for _, t in ipairs(list) do
			local box, key = resolve(t, spath)

			if box and box[key] ~= nil then
				local v = value_for(original(box, key), spec, key)

				if v ~= nil then
					write(box, key, v)
					n = n + 1
				end
			end
		end

		return n
	end

	--------------------------------------------------------------------------
	-- 对局里自己身上的战备：次数按差值加减、刷新 loadout_info（HUD 冷却条用）
	--------------------------------------------------------------------------
	local function inventories()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine
		local st = sm and sm:get_current_state()

		if type(st) ~= "table" or sm:get_current_state_name() ~= "game" or type(st.entity_manager) ~= "table" then
			return nil
		end

		local ok, ents = pcall(st.entity_manager.get_master_entities, st.entity_manager, "inventory")

		return ok and type(ents) == "table" and ents or nil
	end

	local function uses_of(e)
		local ok, info = pcall(LoadoutSettings.get_upgraded_stratagem, e.id, e.upgrade_value or 0)

		return ok and type(info) == "table" and info.num_uses or nil
	end

	local function snapshot_uses()
		local snap = {}
		local ents = inventories()

		if not ents then
			return snap
		end

		for unit, ext in pairs(ents) do
			local list = type(ext) == "table" and type(ext.state) == "table" and ext.state.stratagems

			if type(list) == "table" then
				local row = {}

				for i, e in ipairs(list) do
					row[i] = uses_of(e)
				end

				snap[unit] = row
			end
		end

		return snap
	end

	local function patch_live(snap)
		local ents = inventories()

		if not ents then
			return
		end

		for unit, ext in pairs(ents) do
			local list = type(ext) == "table" and type(ext.state) == "table" and ext.state.stratagems

			if type(list) == "table" and #list > 0 and Unit.alive(unit) then
				local cmd = {}

				for i, e in ipairs(list) do
					local entry = { id = e.id, upgrade_value = e.upgrade_value or 0 }
					local old = snap[unit] and snap[unit][i]
					local new = uses_of(e)

					if type(e.uses_left) == "number" and type(old) == "number" and type(new) == "number" and old ~= new then
						entry.uses_left = math.max(0, math.min(new, e.uses_left + new - old))
					end

					cmd[i] = entry
				end

				EntityAux.queue_command_master(unit, "inventory", "stratagems", cmd)
			end
		end
	end

	--------------------------------------------------------------------------
	-- 全部写回原值，再按五类的设置重新套
	--------------------------------------------------------------------------
	local function apply_all()
		local ls = rawget(_G, "LoadoutSettings")

		if type(ls) ~= "table" or type(ls.stratagems) ~= "table" then
			G.pending = true

			return 0, 1
		end

		local snap = {}
		local ok, s = pcall(snapshot_uses)

		if ok then
			snap = s
		else
			log_err(s)
		end

		restore_all()

		local cache, written, miss, wait = {}, 0, 0, 0

		for _, c in ipairs(CATS) do
			local cfg = G.cats[c]

			for _, s in ipairs(ls.stratagems) do
				if category_of(s) == c then
					for path, mult in pairs(cfg.common) do
						written = written + set_strat(s, path, { mult = mult })
					end

					local ov = cfg.ov[s.name]

					if ov then
						for path, spec in pairs(ov) do
							local upath, spath = string.match(path, "^@([^@]+)@(.+)$")

							if upath then
								local n = set_unit(upath, spath, spec, cache)

								if n == nil then
									wait = wait + 1
									miss = miss + 1
								elseif n < 0 then
									miss = miss + 1
								else
									written = written + n
								end
							else
								written = written + set_strat(s, path, spec)
							end
						end
					end
				end
			end
		end

		-- 单位设置表还没准备好（游戏刚开）：过一会儿再套一次
		G.pending = wait > 0
		-- 记下这次套在哪几张表上（游戏要是重新加载了设置表，tick 里发现换了就重套）
		G.probe_strats = ls.stratagems
		G.probe_units = {}

		for upath, list in pairs(cache) do
			if type(list) == "table" and list[1] then
				G.probe_units[upath] = list[1]
			end
		end

		local ok2, err = pcall(patch_live, snap)

		if not ok2 then
			log_err(err)
		end

		return written, miss
	end

	--------------------------------------------------------------------------
	-- 命令
	--------------------------------------------------------------------------
	local function parse_value(s)
		if s == "true" then
			return true
		elseif s == "false" then
			return false
		end

		local n = tonumber(s)

		if n ~= nil and n == n then
			return n
		end

		return nil
	end

	local function count(t)
		local n = 0

		for _ in pairs(t) do
			n = n + 1
		end

		return n
	end

	local function apply_command(cat, text)
		local cfg = G.cats[cat]

		if not cfg then
			return "err:不认识的类别：" .. tostring(cat)
		end

		text = tostring(text or ""):gsub("^%s+", ""):gsub("%s+$", "")

		if text == "" or text == "reset" then
			G.cats[cat] = { common = {}, ov = {} }

			local _, miss = apply_all()

			G.result[cat] = "ok:reset"

			return "ok:reset" .. (miss > 0 and (";miss=" .. miss) or "")
		end

		local common, ov = {}, {}
		local bad, n_set = 0, 0
		local has_common, has_set = false, false

		for part in string.gmatch(text, "[^;]+") do
			local k, body = string.match(part, "^%s*([%w_]+)%s*=%s*(.-)%s*$")

			if k == "common" then
				has_common = true

				for entry in string.gmatch(body .. ",", "([^,]*),") do
					local path, mult = string.match(entry, "^%s*([%w_%.]+)%s*%*%s*([%d%.]+)%s*$")
					local m = tonumber(mult)

					if path and m and m >= 0 and m <= 100 then
						common[path] = m
					elseif string.gsub(entry, "%s", "") ~= "" then
						bad = bad + 1
					end
				end
			elseif k == "set" then
				has_set = true

				for entry in string.gmatch(body .. ",", "([^,]*),") do
					local name, rest = string.match(entry, "^%s*([%w_]+)%.(.-)%s*$")
					local path, spec

					if rest then
						local p, v = string.match(rest, "^([^=%*]+)=%s*(.-)$")

						if p then
							path, spec = p, parse_value(v)
						else
							local p2, m = string.match(rest, "^([^=%*]+)%*%s*([%d%.]+)$")
							local mv = tonumber(m)

							if p2 and mv and mv >= 0 and mv <= 100 then
								path, spec = p2, { mult = mv }
							end
						end
					end

					if path then
						path = string.gsub(path, "%s+$", "")
					end

					local s = name and find_strat(name)

					if path and spec ~= nil and s and category_of(s) == cat and string.match(path, "^[%w_%.@/]+$") then
						ov[name] = ov[name] or {}
						ov[name][path] = spec
						n_set = n_set + 1
					elseif string.gsub(entry, "%s", "") ~= "" then
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

		if has_common then
			cfg.common = common
		end

		if has_set then
			cfg.ov = ov
		end

		local _, miss = apply_all()
		local n_ov = 0

		for _, f in pairs(cfg.ov) do
			n_ov = n_ov + count(f)
		end

		local res = string.format("ok:n=%d;c=%d;bad=%d;miss=%d", n_ov, count(cfg.common), bad, miss)

		G.result[cat] = res

		return res
	end

	-- data_live.lua 调：StratParamsMod.apply("blue", "common=...;set=...")；出错不抛，返回 err:...
	G.apply = function(cat, text)
		local ok, res = pcall(apply_command, cat, text)

		if not ok then
			log_err(res)

			return "err:" .. tostring(res)
		end

		return res
	end

	-- 只看当前状态（调试用）：G.status() -> "blue=ok:...;red=..."
	G.status = function()
		local out = {}

		for _, c in ipairs(CATS) do
			out[#out + 1] = c .. "=" .. tostring(G.result[c] or "ok:reset")
		end

		return table.concat(out, ";")
	end

	G.category_of = category_of

	--------------------------------------------------------------------------
	-- 每 2 秒看一眼：游戏刚开时单位设置表还没准备好（pending），或游戏重新加载了设置表（stale），就重套
	--------------------------------------------------------------------------
	-- 套过的表还是不是游戏现在用的那几张（只在有改动时看，便宜）
	local function stale()
		local any = false

		for _, c in ipairs(CATS) do
			if next(G.cats[c].common) or next(G.cats[c].ov) then
				any = true
			end
		end

		if not any then
			return false
		end

		local ls = rawget(_G, "LoadoutSettings")

		if type(ls) == "table" and G.probe_strats and ls.stratagems ~= G.probe_strats then
			return true
		end

		local lsm = rawget(_G, "LuaSettingsManager")

		if lsm and G.probe_units then
			for upath, t in pairs(G.probe_units) do
				local ok, now = pcall(lsm.get_settings_by_unit_path, lsm, upath)

				if ok and type(now) == "table" and inner(now) ~= t then
					return true
				end
			end
		end

		return false
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local now = Application.time_since_launch()

			if now - G.last >= REFRESH then
				G.last = now

				if G.pending or stale() then
					local ok, err = pcall(apply_all)

					if not ok then
						G.pending = false
						log_err(err)
					end
				end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
