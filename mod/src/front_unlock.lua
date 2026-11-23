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
--   2026-11-23 用户：「攻打到对应的母城了,会只有五个关卡选项,这时候报复关数量好像对这个就没影响了」。
--     母星 / 防守事件那颗星不走 generate_planet，是 MenuScreenCampaignPlanet.setup_event_planets 生成的 5 关
--     （难度 3、6、9、12、15，event_mission_difficulties），也调 get_planet_mission_types，但：
--     - 落在难度 3 那一关的报复关会被原版改回普通任务（难度 < 4 没有报复关），固定 1 个时有 1/5 机会一个都没有；
--     - 装了 QoL Mod 时它的 setup_event_planets 每一关都重新调一次 get_planet_mission_types、只取第 i 个，
--       我们每次都重新洗牌，个数就成了随机的。
--     所以在 setup_event_planets 里面：报复关只放在难度 >= 4 的关上，个数按设置；这一次生成里同样的调用给同一份结果。
--     只在母星这几关重新生成时生效（原版按事件编号缓存：新的进攻 / 防守事件，或者重开游戏）。
--
-- 2026-11-23 用户定（V1.06）：解锁战线三选一：普通星区（上面那套）/ 进攻母星 / 保卫超级地球（选一个种族）。
--   母星、保卫超级地球原版都是服务器发「事件」才有（CampaignManager.cache.attack_events / defend_event）。这里在本机
--   假装有这个事件：get_active_* / get_latest_* 多返回一个我们造的事件（编号 >= FAKE_BASE，服务器上没有）。
--   战役地图（update_campaign_status）看到进攻事件就把这条战线放到第 11 星区（母星），防守事件放到事件的星区（0 = 超级地球），
--   setup_event_planets 照原版生成那颗星的 5 关（难度 3/6/9/12/15，报复关数量照样管）。
--   - 打完不报服务器：complete_*_event_mission 遇到我们的编号直接跳过（只算自己玩，不算进银河战争）。
--   - 结算时把任务统计里的事件编号改回 0（StateMissionEnd.on_enter 之后）：结算照普通任务走，房主和队友（不管装没装 HellBox）
--     的存档都不会记下这个假事件，不会算进事件相关的成就。
--   - 已经有真事件的种族不加假的（母星）；保卫超级地球时盖掉真的防守事件（只在本机显示上）。
--   - 刷新：planet_refresh.lua 在这颗星里按刷新键 = G.reroll_event 重抽这 5 关。
--   - 开机值：build.py 填 FRONT_EVENT 占位（"" / "home" / "se1"～"se3"，1～3 = 虫族 / 生化人 / 光能者）；热切换信箱 e=。
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

	if not G.event_init then
		G.event_init = true
		G.event = "@FRONT_EVENT@" -- "" / "home" / "se1"～"se3"
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
			local e = s:match("e=([^;]*)")

			if f then
				G.on = f == "1"
			end

			if g then
				G.gen = count(g)
			end

			if e and (e == "" or e == "home" or e:match("^se[123]$")) then
				G.event = e
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
				local events = ds.event_mission_difficulties
				if G.event_types and type(events) == "table" and slots == #events then
					-- 母星 / 防守事件那 5 关（setup_event_planets 里面）：报复关只放在难度够的关上，同一次生成结果不变
					if G.event_types[slots] then
						return G.event_types[slots]
					end
					local ok_slots = {}
					for i = 1, slots do
						types[i] = normal
						if (events[i] or 0) >= ds.genocide_mission_available_difficulty then
							ok_slots[#ok_slots + 1] = i
						end
					end
					math.shuffle(ok_slots)
					for n = 1, math.min(G.gen, #ok_slots) do
						types[ok_slots[n]] = retaliation
					end
					G.event_types[slots] = types
					return types
				end
				for i = 1, slots do
					types[i] = i <= G.gen and retaliation or normal
				end
				math.shuffle(types)
				return types
			end
			ds.get_planet_mission_types = G.mission_types
		end
		local planet_screen = rawget(_G, "MenuScreenCampaignPlanet")
		if type(planet_screen) == "table" and type(planet_screen.setup_event_planets) == "function"
				and planet_screen.setup_event_planets ~= G.setup_event then
			local original = planet_screen.setup_event_planets
			G.setup_event = function(self, ...)
				G.planet_screen = self -- 刷新假事件那颗星时要用它的任务表
				if G.gen == nil then
					return original(self, ...)
				end
				G.event_types = {}
				local ok, err = pcall(original, self, ...)
				G.event_types = nil
				if not ok then
					error(err, 0)
				end
			end
			planet_screen.setup_event_planets = G.setup_event
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

	-- ------------------------------------------------------------ 假事件（V1.06）
	local FAKE_BASE = 2000000000 -- 服务器的事件编号到不了这么大；网络对象里是 uint31，放得下

	local function is_fake(id)
		return type(id) == "number" and id >= FAKE_BASE
	end

	G.is_fake = is_fake

	local function live(cm)
		return G.on and G.raw == 0 and type(cm) == "table" and cm.status == "online"
	end

	local function fake_event(cm, kind, enemy)
		G.fakes = G.fakes or {}

		local key = kind .. enemy
		local e = G.fakes[key]

		if not e then
			local ok, now = pcall(cm.get_server_time, cm)

			now = math.floor(ok and tonumber(now) or os.time())
			e = {
				event_id = FAKE_BASE + (kind == "defend" and 10 or 20) + enemy,
				event_type = kind,
				enemy = enemy,
				region = kind == "defend" and 0 or 11,
				status = "active",
				start_time = now - 3600,
				end_time = now + 7 * 86400,
				points = 0,
				points_max = 100,
				hellbox = true,
			}
			G.fakes[key] = e
		end

		return e
	end

	local function se_enemy()
		local n = type(G.event) == "string" and G.event:match("^se([123])$")

		return n and tonumber(n) - 1
	end

	local function with_fake_attacks(cm, real)
		if not live(cm) or G.event ~= "home" then
			return real
		end

		local out, have = {}, {}

		for _, e in ipairs(real or {}) do
			out[#out + 1] = e
			have[e.enemy] = true
		end

		for enemy = 0, 2 do
			if not have[enemy] then
				out[#out + 1] = fake_event(cm, "attack", enemy)
			end
		end

		return out
	end

	local function hook_events()
		local cm = rawget(_G, "CampaignManager")

		if type(cm) == "table" then
			local function wrapf(name, fn)
				if type(cm[name]) == "function" and cm[name] ~= G["ev_" .. name] then
					local orig = cm[name]

					G["ev_" .. name] = function(...)
						return fn(orig, ...)
					end
					cm[name] = G["ev_" .. name]
				end
			end

			for _, name in ipairs({ "get_active_defend_event", "get_latest_defend_event" }) do
				wrapf(name, function(orig, self, ...)
					local enemy = se_enemy()

					if enemy and live(self) then
						return fake_event(self, "defend", enemy)
					end

					return orig(self, ...)
				end)
			end

			for _, name in ipairs({ "get_active_attack_events", "get_latest_attack_events" }) do
				wrapf(name, function(orig, self, ...)
					return with_fake_attacks(self, orig(self, ...))
				end)
			end

			for _, name in ipairs({ "complete_defend_event_mission", "complete_attack_event_mission" }) do
				wrapf(name, function(orig, self, id, ...)
					if is_fake(id) then
						G.not_reported = (G.not_reported or 0) + 1 -- 我们造的事件：不报服务器

						return
					end

					return orig(self, id, ...)
				end)
			end
		end

		local sme = rawget(_G, "StateMissionEnd")

		if type(sme) == "table" and type(sme.on_enter) == "function" and sme.on_enter ~= G.ev_mission_end then
			local orig = sme.on_enter

			G.ev_mission_end = function(self, ...)
				local result = orig(self, ...)
				local p = self.current_planet
				local stats = self.mission_stats_go

				if type(p) == "table" and (is_fake(p.defend_event) or is_fake(p.attack_event)) and stats then
					pcall(stats.set, stats, "defend_event_id", 0)
					pcall(stats.set, stats, "attack_event_id", 0)
				end

				return result
			end
			sme.on_enter = G.ev_mission_end
		end
	end

	-- 刷新键（planet_refresh.lua）：重抽假事件那颗星的 5 关，原地改任务表（星球、选任务界面、发给客机的是同一份）
	function G.reroll_event(planet)
		local ds = rawget(_G, "DifficultySettings")

		if type(planet) ~= "table" or type(planet.missions) ~= "table" or not ds then
			return false
		end

		local diffs = ds.event_mission_difficulties
		local n = #diffs

		G.event_types = {}

		local ok, types = pcall(ds.get_planet_mission_types, diffs[n], n)

		G.event_types = nil

		if not ok then
			error(types, 0)
		end

		local genocide_type = ds.get_mission_type_value("genocide")
		local mission_type = ds.get_mission_type_value("mission")

		for i = 1, n do
			local diff = diffs[i]
			local ty = types[i]

			if ty == genocide_type and diff < ds.genocide_mission_available_difficulty then
				ty = mission_type
			end

			local seed

			if planet.attack_event then
				seed = ds.modulate_seed_for_planet(planet.shading_environment, planet.environment, planet.environment_variant,
					planet.enemy, ty, diff, math.random(0, 2147483646), 0)
			else
				seed = ds.modulate_seed_for_planet(planet.shading_environment, planet.environment, planet.environment_variant,
					planet.enemy, ty, diff, math.random(0, 2147483646))
			end

			planet.missions[i] = planet.missions[i] or {}
			planet.missions[i].seed = seed
			planet.missions[i].completed = false
		end

		for i = #planet.missions, n + 1, -1 do
			planet.missions[i] = nil
		end

		planet.selected_mission_index = nil

		local ps = G.planet_screen
		local camp = type(ps) == "table" and ps.parent

		if type(camp) == "table" and type(camp.send_planet_info) == "function" then
			pcall(camp.send_planet_info, camp, ps.defend_event_missions, ps.attack_events_missions)
		end

		G.event_rerolls = (G.event_rerolls or 0) + 1

		return true
	end

	local function tick()
		poll_mailbox()
		genocide()
		hook_events()

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
