-- [front unlock] 没开放的战线照样能打（2026-10-22；2026-11-04 加上 "hidden"、报复打击拆成单独设置）。
--   由 build.py 追加到 character_state_machine 末尾（在 p2_name 后面）。
--
-- 原版：服务器 get_campaign_status 回每个种族一项 {status, points, points_max, season, ...}，存在 CampaignManager.cache.status。
--   能不能选这个种族、星区怎么画，全是客户端 Lua 看 status == "active" 决定的（menu_screen_campaign_region / _campaign / _client），
--   "defeated" 的种族在战役地图上整片涂成已解放，"hidden" 的（新赛季还没出场，points 是 points_max 的一半）整片灰掉，都选不进去。
-- 这里：包 CampaignManager.get_campaign_status，ON 时按每个种族的情况改：
--   "defeated" -> "active"，points 放到 points_max 的 95%（第 10 星区打到一半，也就是攻破前最后一个前线）；
--   "hidden"   -> "active"，points 用服务器给的（新赛季起点）；不在 0~points_max 之间就放一半。
--   本来就是 active 的项原样不动。
--   返回的是拷贝，cache.status（以及存档里的 campaign_cache）保持服务器原样。
--   战役回顾（MenuScreenCampaignRecap 的所有方法）里拿原样的，不然回顾每次都会演一遍"攻破 -> 复活"；
--   存 last_shown_recap_status 时如果拿到的是拷贝，也换回原样再存。
--   ON 开机时是 build.py 从 mod\front_unlock.txt 填进来的（"1" = 开，空 = 原版）。
--   联机：客机选星球时看的是客机自己的状态（menu_screen_campaign_client），所以队友也要装、也要开。
--   报复打击（歼灭任务）概率是单独的设置（和战线开关无关）：原版生成星球时难度 >= 4 且
--   math.random() < genocide_mission_spawn_percent_per_planet（0.33）才把一个任务换成 "genocide"（每颗最多一个）。
--   保留旧档位 0 / 33 / 66 / 100 的存储格式，分别生成固定 0 / 1 / 2 / 3 个报复关。空 = 原版。
--   开机值是 build.py 从 mod\genocide.txt 填进来的。
--
-- 热切换：信箱表 G.t，布局和 room_name.lua 一样（只是魔数不同），窗口用 mod\room_name_live.py 写。
--   1-4 魔数；5 VERSION；6 请求号；7 已应用的请求号；8 字节数；9 起：内容 "f=1;g=100"（f = 战线开关 1/0，g = 报复概率百分比，空 = 原版）。
--   旧格式 "1" / 空 只管战线开关。战线切换后下一次打开战役地图（MenuScreenCampaign.on_enter 会重新读状态）生效。
do
	local ON = "@FRONT_UNLOCK@" == "1"
	local VERSION = 2
	local MAX_BYTES = 256
	local B0 = 9
	local N = B0 + MAX_BYTES - 1
	local POINTS = 0.95
	local G = FrontUnlockMod or {}

	local function count(s)
		return ({["0"] = 0, ["33"] = 1, ["66"] = 2, ["100"] = 3})[s]
	end

	FrontUnlockMod = G

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("16180339.5")
		t[2] = tonumber("-271828.25")
		t[3] = tonumber("1414.0625")
		t[4] = tonumber("137438953472.875")
		t[5] = VERSION
		G.t = t
		G.on = ON
		G.seq = 0
		G.raw = 0 -- > 0：在战役回顾里，拿原样的状态
		G.issued = setmetatable({}, { __mode = "k" }) -- 发出去的拷贝 -> 原样
		G.wrapped_fns = setmetatable({}, { __mode = "k" })
	end

	if not G.gen_init then
		G.gen_init = true
		G.gen = count("@GENOCIDE@") -- nil = 原版
	end

	local t = G.t

	local function poll_mailbox()
		local seq = t[6]

		if seq == G.seq then
			return
		end

		G.seq = seq

		local len = t[8]
		local bytes = {}

		for i = 1, math.min(len, MAX_BYTES) do
			local b = t[B0 + i - 1]

			if type(b) == "number" and b >= 0 and b < 256 then
				bytes[#bytes + 1] = string.char(math.floor(b))
			end
		end

		local s = table.concat(bytes)

		if s == "" then
			G.on = false
		elseif s == "1" then
			G.on = true
		else
			local f = s:match("f=(%d)")
			local g = s:match("g=([^;]*)")

			if f then
				G.on = f == "1"
			end

			if g then
				G.gen = count(g)
			end
		end

		G.changes = (G.changes or 0) + 1
		t[7] = seq
	end

	local function patched(raw)
		if not G.on or G.raw > 0 or type(raw) ~= "table" then
			return raw
		end

		if G.src == raw and G.out then
			return G.out
		end

		local out, any = {}, false

		for i, s in ipairs(raw) do
			local closed = type(s) == "table" and (s.status == "defeated" or s.status == "hidden")

			if closed and type(s.points_max) == "number" and s.points_max > 0 then
				local c = {}

				for k, v in pairs(s) do
					c[k] = v
				end

				c.status = "active"

				if s.status == "defeated" then
					c.points = math.floor(s.points_max * POINTS)
				elseif type(s.points) ~= "number" or s.points <= 0 or s.points >= s.points_max then
					c.points = math.floor(s.points_max * 0.5)
				end

				out[i] = c
				any = true
			else
				out[i] = s
			end
		end

		if not any then
			return raw
		end

		G.src, G.out = raw, out
		G.issued[out] = raw

		return out
	end

	-- 在 f 执行期间拿原样状态；出错照样往外抛
	local function as_raw(f)
		local function finish(ok, ...)
			G.raw = G.raw - 1

			if not ok then
				error((...), 0)
			end

			return ...
		end

		return function(...)
			G.raw = G.raw + 1

			return finish(pcall(f, ...))
		end
	end

	local function hook_campaign()
		local cm = rawget(_G, "CampaignManager")

		if type(cm) ~= "table" or type(cm.get_campaign_status) ~= "function" then
			return false
		end

		if cm.get_campaign_status ~= G.get_status then
			local orig = cm.get_campaign_status

			G.get_status = function(...)
				return patched(orig(...))
			end
			cm.get_campaign_status = G.get_status
		end

		return true
	end

	local function hook_save()
		local sm = rawget(_G, "SaveManager")

		if type(sm) ~= "table" or type(sm.set) ~= "function" then
			return false
		end

		if sm.set ~= G.save_set then
			local orig = sm.set

			G.save_set = function(self, key, value, ...)
				if key == "last_shown_recap_status" and value ~= nil and G.issued[value] then
					value = G.issued[value]
				end

				return orig(self, key, value, ...)
			end
			sm.set = G.save_set
		end

		return true
	end

	local function hook_recap()
		local cls = rawget(_G, "MenuScreenCampaignRecap")

		if type(cls) ~= "table" then
			return false
		end

		local names = {}

		for k, f in pairs(cls) do
			if type(f) == "function" and not G.wrapped_fns[f] then
				names[#names + 1] = k
			end
		end

		for _, k in ipairs(names) do
			local w = as_raw(cls[k])

			G.wrapped_fns[w] = true
			cls[k] = w
		end

		return true
	end

	local function genocide()
		local ds = rawget(_G, "DifficultySettings")
		local campaign = rawget(_G, "MenuScreenCampaign")
		if not ds or not campaign or type(ds.get_planet_mission_types) ~= "function"
				or type(campaign.generate_planet) ~= "function" then
			return
		end
		if ds.get_planet_mission_types ~= G.mission_types then
			local original = ds.get_planet_mission_types
			G.mission_types = function(difficulty, slots)
				if G.gen == nil or difficulty < ds.genocide_mission_available_difficulty then
					return original(difficulty, slots)
				end
				local retaliation, normal
				for i, name in ipairs(ds.mission_type_lookup) do
					if name == "genocide" then
						retaliation = i - 1
					elseif name == "mission" then
						normal = i - 1
					end
				end
				local types = {}
				for i = 1, slots do
					types[i] = i <= G.gen and retaliation or normal
				end
				math.shuffle(types)
				return types
			end
			ds.get_planet_mission_types = G.mission_types
		end
		if campaign.generate_planet ~= G.generate_planet then
			local original = campaign.generate_planet
			G.generate_planet = function(self, planet, enemy_name, sector, environments, difficulties, enemy, index, keep, override)
				local difficulty = override or (keep and planet.difficulty) or (difficulties and difficulties[index])
				if G.gen == 3 and difficulty and difficulty >= ds.genocide_mission_available_difficulty
						and ds.planet_missions_by_difficulty[difficulty][1] < 3 then
					local old = ds.planet_missions_by_difficulty[difficulty]
					ds.planet_missions_by_difficulty[difficulty] = {3, 3}
					local ok, result = pcall(original, self, planet, enemy_name, sector, environments,
						difficulties, enemy, index, keep, override)
					ds.planet_missions_by_difficulty[difficulty] = old
					if not ok then
						error(result, 0)
					end
					return result
				end
				return original(self, planet, enemy_name, sector, environments, difficulties, enemy, index, keep, override)
			end
			campaign.generate_planet = G.generate_planet
		end
	end

	local function tick()
		poll_mailbox()
		genocide()

		if not G.hooked then
			local a = hook_campaign()
			local b = hook_save()
			local c = hook_recap()

			G.hooked = a and b and c
		end
	end

	pcall(tick)

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local ok, err = pcall(tick)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = err
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
