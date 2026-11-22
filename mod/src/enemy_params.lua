-- [enemy params] HellBox「怪物」页的游戏这边（2026-11-10，HD1-032）。由 build.py 追加到 character_state_machine 末尾。
--
-- 改对局里各种怪的参数，两类：
--   通用倍率 common：所有怪共有的属性按倍数放大 / 缩小（血量、移动速度、发现距离、攻速……），
--                    比如 health_info.health*2 = 所有怪血量翻倍。按每只怪自己的原值乘，不写死数值。
--   单只覆盖 set：按怪名改某只怪的某一栏（独特能力，比如冲锋虫的冲刺转向、班长的子弹），绝对值。
-- 游戏在怪生成时用 LoadoutSettings.get_upgraded_settings 读设置表（血量 health_component.lua:132、
-- 移动 enemy_component.lua:481 等），这里包一层把两类改动都套上；已经生成的怪把血量上限同步过去。
-- 改法和恢复都是对局内热切换；恢复默认 = 把改过的地方写回原值。
--
-- 信箱表 G.t，布局同 spawn_rules.lua（魔数不同）：
--   1-4 魔数；5 VERSION；6 命令请求号；7 已处理请求号；8 命令字节数；9 起 CMD_BYTES 格命令；OUT0 起状态区。
--   状态：
--     ok=1 / ok=0   where=game|menu|boot   race=...
--     common=health_info.health*2,...   通用倍率（×1 的不写）
--     n=几条单只覆盖   p=名字.路径=值,...（太长会截断）
--     res=上一条命令的结果   err=最近一次内部错误
--
-- 命令（发哪一段就只换哪一段，另一段保持不动；reset 两段都清）：
--   reset
--   common=health_info.health*2,enemy_info.aggro_range*1.5
--   set=bug_tank.health_info.health=1600,bug_warrior.enemy_info.movement_speed=2
--       也可以写 怪名.路径*倍数（2026-11-14）：这只怪这一项按自己的原值乘，比如 bug_tank.health_info.health*2
--       逗号分隔的 怪名.字段路径=值；值写数字 / true / false / 字符串；写 default 表示把这一项恢复原值
--   common=...;set=...            两段一起换
--
-- 已知限制：联机时每台电脑算自己那部分怪；自己是房主时最完整。移动、攻速这类参数要等这只怪下一次
-- 用设置表才生效（血量已经在场的会马上按比例改）。
do
	local VERSION = 2
	local CMD_BYTES = 4096
	local OUT_BYTES = 4096
	local B0 = 9
	local OUT0 = B0 + CMD_BYTES
	local N = OUT0 + 2 + OUT_BYTES - 1
	local REFRESH = 1
	local G = EnemyParamsMod or {}

	EnemyParamsMod = G

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("26457513.5")
		t[2] = -tonumber("793700.875")
		t[3] = tonumber("1905.25")
		t[4] = tonumber("274877906944.125")
		t[5] = VERSION
		G.t = t
		G.seq = 0
		G.result = ""
		G.ov = {}
		G.common = {}
		G.base = setmetatable({}, { __mode = "k" })
		G.cbase = setmetatable({}, { __mode = "k" })
		G.touched = setmetatable({}, { __mode = "k" })
		G.hp_base = {}
		G.errors = 0
	end

	local t = G.t
	local timer = 0

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

	local function get_path(tbl, path)
		local cur = tbl

		for _, part in ipairs(split_path(path)) do
			if type(cur) ~= "table" then
				return nil
			end

			cur = cur[key_of(part)]
		end

		return cur
	end

	local function set_path(tbl, path, val)
		local parts = split_path(path)

		if #parts == 0 then
			return false
		end

		local cur = tbl

		for i = 1, #parts - 1 do
			cur = cur and cur[key_of(parts[i])]

			if type(cur) ~= "table" then
				return false
			end
		end

		cur[key_of(parts[#parts])] = val

		return true
	end

	-- 怪名和 characters/ 路径都以种族开头（bug_ / cyborg_ / illuminate_）；两边种族不一样 = 跨种族
	local function cross_race(name, v)
		if type(v) ~= "string" then
			return false
		end

		local want = string.match(name, "^(%a+)_")
		local got = string.match(v, "^characters/(%a+)_")

		return want ~= nil and got ~= nil and want ~= got
	end

	local function parse_value(s)
		if s == "true" then
			return true
		elseif s == "false" then
			return false
		end

		local n = tonumber(s)

		if n ~= nil then
			return n
		end

		return s
	end

	-- 把通用倍率和单只覆盖套到设置表上（第一次改之前记下原值）
	local function apply_table(tbl)
		if type(tbl) ~= "table" then
			return
		end

		local info = tbl.enemy_info
		local name = type(info) == "table" and info.enemy_name

		if type(name) ~= "string" then
			return
		end

		G.touched[tbl] = true

		local saved = G.base[tbl]

		if not saved then
			saved = {}
			G.base[tbl] = saved
		end

		local csaved = G.cbase[tbl]

		if not csaved then
			csaved = {}
			G.cbase[tbl] = csaved
		end

		-- 血量原值（给已经在场的怪按倍数改上限用）
		local hp = get_path(tbl, "health_info.health")

		-- 1) 全体通用：每只怪按自己的原值乘倍数
		for path, mult in pairs(G.common) do
			local cur = get_path(tbl, path)

			if type(cur) == "number" then
				if csaved[path] == nil then
					csaved[path] = { has = true, v = cur }
				end

				local value = csaved[path].v * mult
				if path == "health_info.health" then
					value = math.max(1, value)
				end
				set_path(tbl, path, value)
			end
		end

		-- 2) 单只覆盖：绝对值，压在上面
		local ov = G.ov[name]

		if ov then
			for path, val in pairs(ov) do
				if saved[path] == nil then
					local cur = get_path(tbl, path)

					saved[path] = { has = cur ~= nil, v = cur }
				end

				if type(val) == "table" then
					-- 倍率：按原值乘（通用倍率先套过的话，原值在 csaved 里）
					local orig = csaved[path] and csaved[path].v

					if orig == nil then
						orig = saved[path].v
					end

					if type(orig) == "number" then
						local v = orig * val.mult

						if path == "health_info.health" then
							v = math.max(1, v)
						end

						set_path(tbl, path, v)
					end
				else
					set_path(tbl, path, val)
				end
			end
		end

		-- 血量原值：这次记下的原值优先，别把已经改过的值当成原值
		local seen = csaved["health_info.health"] or saved["health_info.health"]

		if seen and seen.has then
			G.hp_base[name] = seen.v
		elseif type(hp) == "number" then
			G.hp_base[name] = hp
		end
	end

	local function restore_saved(base)
		for tbl, saved in pairs(base) do
			for path, s in pairs(saved) do
				if s.has then
					set_path(tbl, path, s.v)
				else
					local parts = split_path(path)
					local cur = tbl

					for i = 1, #parts - 1 do
						cur = type(cur) == "table" and cur[key_of(parts[i])]
					end

					if type(cur) == "table" then
						cur[key_of(parts[#parts])] = nil
					end
				end
			end
		end
	end

	local function restore_all()
		restore_saved(G.base)
		restore_saved(G.cbase)
		G.base = setmetatable({}, { __mode = "k" })
		G.cbase = setmetatable({}, { __mode = "k" })
	end

	--------------------------------------------------------------------------
	-- 2026-11-18 V0.96 用户定：在别人房间（客机）时自己的怪物属性不生效。
	--   游戏会把一部分怪交给客机算（EnemyComponent.migrated_to_me），这些怪读客机自己的设置表；以前客机开着怪物修改
	--   进别人房间，会改到这些怪。现在：StateGame.is_server == false（游戏按 lobby:is_host() 填，单机 / 本机分屏也是
	--   房主）就算客机——改过的设置表全部还原、不再套、不改在场怪血量；回到自己当房主时再套上。
	--------------------------------------------------------------------------
	-- 2026-11-20 修（和 data_live.lua 同一个毛病）：以前只在关卡里算客机，结算画面就当成「回到自己当房主」把改过的表套回去。
	--   现在关卡里照旧看 is_server；关卡外看房间（房间有效、自己不是房主 = 客机；没房间 = 不算）。
	local function is_guest()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if sm and sm:get_current_state_name() == "game" then
			local st = sm:get_current_state()

			if type(st) == "table" and st.is_server ~= nil then
				return st.is_server == false
			end
		end

		local ng = rawget(_G, "NetworkGlobal")
		local lobby = type(ng) == "table" and ng.lobby

		if type(lobby) ~= "table" or not lobby.lobby or type(lobby.is_valid) ~= "function" or type(lobby.is_host) ~= "function" then
			return false
		end

		local ok_v, valid = pcall(lobby.is_valid, lobby)

		if not (ok_v and valid) then
			return false
		end

		local ok, host = pcall(lobby.is_host, lobby)

		return ok and host == false
	end

	--------------------------------------------------------------------------
	-- 已经在场的怪：按新血量上限调当前血量（保持原来的血条比例）
	--------------------------------------------------------------------------
	local function health_target(name)
		local ov = G.ov[name]
		local hp = ov and ov["health_info.health"]

		if type(hp) == "number" and hp > 0 then
			return hp
		end

		local base = G.hp_base[name]

		if type(base) ~= "number" or base <= 0 then
			return nil
		end

		if type(hp) == "table" and type(hp.mult) == "number" then
			return math.max(1, math.floor(base * hp.mult + 0.5))
		end

		local mult = G.common["health_info.health"] or 1

		return math.max(1, math.floor(base * mult + 0.5))
	end

	local function patch_live_health()
		if G.guest then
			return
		end

		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine
		local st = sm and sm:get_current_state()

		if type(st) ~= "table" or sm:get_current_state_name() ~= "game" then
			return
		end

		local em = st.entity_manager

		if type(em) ~= "table" then
			return
		end

		for unit in em:all_slaves_iterator("enemy") do
			local ok, err = pcall(function()
				local es = EntityAux.state(unit, "enemy")
				local settings = type(es) == "table" and es.settings
				local info = type(settings) == "table" and settings.enemy_info
				local name = type(info) == "table" and info.enemy_name
				local want = name and health_target(name)

				if not want then
					return
				end

				local hs = EntityAux.state(unit, "health")

				if type(hs) ~= "table" then
					return
				end

				local old_max = tonumber(hs.max_hitpoints) or 0
				local cur = tonumber(hs.hitpoints) or old_max
				local ratio = old_max > 0 and cur / old_max or 1

				hs.max_hitpoints = want

				local new_hp = math.max(1, math.min(want, math.floor(ratio * want + 0.5)))

				hs.hitpoints = new_hp
				hs.predicted_hitpoints = new_hp

				if hs.hitpoints_real ~= nil then
					hs.hitpoints_real = new_hp
				end
			end)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("enemy_params", G.last_error) end
			end
		end
	end

	local function count_overrides(ov)
		local n = 0

		for _ in pairs(ov) do
			n = n + 1
		end

		return n
	end

	--------------------------------------------------------------------------
	-- 命令
	--------------------------------------------------------------------------
	local function apply_command(text)
		text = (text or ""):gsub("%s+$", "")

		if text == "reset" then
			restore_all()
			G.ov = {}
			G.common = {}

			local ok, err = pcall(patch_live_health)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("enemy_params", G.last_error) end
			end

			return "ok:reset"
		end

		local common, ov = {}, {}
		local errors = 0
		local has_common, has_set = false, false

		for part in string.gmatch(text, "[^;]+") do
			local k, body = string.match(part, "^%s*([%w_]+)%s*=%s*(.-)%s*$")

			if k == "common" then
				has_common = true

				for entry in string.gmatch(body .. ",", "([^,]+),") do
					local path, mult = string.match(entry, "^%s*([%w_%.]+)%s*%*%s*([%d%.]+)%s*$")
					local n = tonumber(mult)

					if path and n and n >= 0 and n <= 100 then
						common[path] = n
					elseif string.gsub(entry, "%s", "") ~= "" then
						errors = errors + 1
					end
				end
			elseif k == "set" then
				has_set = true

				for entry in string.gmatch(body .. ",", "([^,]+),") do
					local keypath, val = string.match(entry, "^%s*([%w_%.]+)%s*=%s*(.-)%s*$")
					local mkey, mval = string.match(entry, "^%s*([%w_%.]+)%s*%*%s*([%d%.]+)%s*$")

					-- 2026-11-14：「怪名.路径*倍数」= 这只怪这一项按自己的原值乘（数据修改页的倍率）
					if not keypath and mkey and tonumber(mval) and tonumber(mval) <= 100 then
						local name, path = string.match(mkey, "^([%w_]+)%.(.+)$")

						if name then
							ov[name] = ov[name] or {}
							ov[name][path] = { mult = tonumber(mval) }
						else
							errors = errors + 1
						end
					elseif not keypath then
						errors = errors + 1
					else
						local name, path = string.match(keypath, "^([%w_]+)%.(.+)$")

						if not name then
							errors = errors + 1
						elseif val ~= "default" then
							local v = parse_value(val)

							if cross_race(name, v) then
								-- 2026-11-19：别的种族的怪 / 投掷物不认（这张图没加载那个种族的资源，会闪退）。
								-- 新界面只列本种族；这里兜底以前存的块。
								G.cross_skipped = (G.cross_skipped or 0) + 1
								if rawget(_G, "HellBoxLog") then
									HellBoxLog("enemy_params", "跳过跨种族：" .. name .. "." .. path .. "=" .. val)
								end
							else
								ov[name] = ov[name] or {}
								ov[name][path] = v
							end
						end
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

		-- 只替换发来的那一段，另一段保持
		if has_common then
			G.common = common
		end

		if has_set then
			G.ov = ov
		end

		-- 已经读过的设置表马上重套（血量另按比例改在场怪）；客机时只记下，回到当房主再套
		if not G.guest then
			for tbl in pairs(G.touched) do
				pcall(apply_table, tbl)
			end
		end

		local ok, err = pcall(patch_live_health)

		if not ok then
			G.errors = (G.errors or 0) + 1
			G.last_error = tostring(err)
			if rawget(_G, "HellBoxLog") then HellBoxLog("enemy_params", G.last_error) end
		end

		return string.format("ok:n=%d;c=%d;bad=%d", count_overrides(ov), count_overrides(common), errors)
	end

	G.apply = apply_command  -- 2026-11-14：data_live.lua（数据修改页）每秒读文件后调它

	--------------------------------------------------------------------------
	-- 挂点：LoadoutSettings.get_upgraded_settings
	--------------------------------------------------------------------------
	local function hook_loadout()
		local cls = rawget(_G, "LoadoutSettings")

		if type(cls) ~= "table" or type(cls.get_upgraded_settings) ~= "function" or rawget(cls, "_enemy_params_hooked") then
			return
		end

		local orig = cls.get_upgraded_settings

		cls.get_upgraded_settings = function(unit, upgrade, ...)
			local res = orig(unit, upgrade, ...)

			if type(res) == "table" and not G.guest and (next(G.ov) or next(G.common)) then
				pcall(apply_table, res)
			end

			return res
		end
		cls._enemy_params_hooked = true
	end

	--------------------------------------------------------------------------
	-- 状态区
	--------------------------------------------------------------------------
	local function clean(s)
		return (tostring(s or ""):gsub("[%c]", " "))
	end

	local function fmt_overrides()
		local out = {}

		for name, fields in pairs(G.ov) do
			for path, val in pairs(fields) do
				if type(val) == "table" then
					out[#out + 1] = name .. "." .. path .. "*" .. tostring(val.mult)
				else
					out[#out + 1] = name .. "." .. path .. "=" .. tostring(val)
				end
			end
		end

		table.sort(out)

		return table.concat(out, ",")
	end

	local function fmt_common()
		local out = {}

		for path, mult in pairs(G.common) do
			out[#out + 1] = path .. "*" .. tostring(mult)
		end

		table.sort(out)

		return table.concat(out, ",")
	end

	local function build_status()
		local lines = {}
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine
		local where = sm and sm:get_current_state_name() or "boot"
		local st = sm and sm:get_current_state()
		local race = ""

		if type(st) == "table" and type(st.generated_level) == "table" then
			race = tostring(st.generated_level.enemy or "")
		end

		lines[#lines + 1] = "ok=1"
		lines[#lines + 1] = string.format("where=%s;race=%s;guest=%d", clean(where), race, G.guest and 1 or 0)
		lines[#lines + 1] = "n=" .. count_overrides(G.ov)
		lines[#lines + 1] = "c=" .. count_overrides(G.common)
		lines[#lines + 1] = "common=" .. clean(fmt_common())
		lines[#lines + 1] = "seq=" .. tostring(G.seq or 0)
		lines[#lines + 1] = "p=" .. clean(fmt_overrides())
		lines[#lines + 1] = "res=" .. clean(G.result)

		if G.last_error then
			lines[#lines + 1] = "err=" .. clean(G.last_error)
		end

		return table.concat(lines, "\n")
	end

	local function publish()
		local ok, text = pcall(build_status)

		if not ok then
			text = "ok=0\nerr=" .. clean(text)
		end

		local bytes = { text:byte(1, -1) }

		if #bytes > OUT_BYTES then
			bytes = { text:sub(1, OUT_BYTES):byte(1, -1) }
		end

		for i = 1, #bytes do
			t[OUT0 + 1 + i] = bytes[i]
		end

		t[OUT0 + 1] = #bytes

		local seq = (t[OUT0] or 0) + 1

		if seq > 1e9 then
			seq = 1
		end

		t[OUT0] = seq
	end

	local function poll_mailbox()
		local seq = t[6]

		if seq == G.seq then
			return false
		end

		G.seq = seq

		local len = t[8]
		local bytes

		if type(len) == "number" and len >= 0 and len <= CMD_BYTES and len % 1 == 0 then
			bytes = {}

			for i = 1, len do
				local b = t[B0 + i - 1]

				if type(b) ~= "number" or b < 0 or b > 255 or b % 1 ~= 0 then
					bytes = nil

					break
				end

				bytes[i] = string.char(b)
			end
		end

		if bytes then
			local ok, res = pcall(apply_command, table.concat(bytes))

			G.result = ok and res or "err:" .. tostring(res)
		else
			G.result = "err:命令坏了"
		end

		t[7] = seq

		return true
	end

	local function tick(dt)
		local changed = poll_mailbox()

		hook_loadout()

		-- 客机 / 房主切换：进别人房间时全部还原，回到自己当房主时重套
		local guest = is_guest()

		if guest ~= (G.guest or false) then
			G.guest = guest

			if guest then
				restore_all()
			else
				for tbl in pairs(G.touched) do
					pcall(apply_table, tbl)
				end

				pcall(patch_live_health)
			end

			changed = true
		end

		timer = timer - (dt or 0)

		if changed or timer <= 0 then
			timer = REFRESH

			publish()
		end
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_enemy_params_hooked") then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local ok, err = pcall(tick, dt)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("enemy_params", G.last_error) end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
		wm._enemy_params_hooked = true
	end
end
