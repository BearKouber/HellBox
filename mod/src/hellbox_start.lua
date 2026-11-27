-- [hellbox start] 游戏开着、人在飞船上时，HellBox「训练」页点开始直接进训练关，不重开游戏（2026-11-16 V0.95，
-- 用户："训练我记得是开始游戏如果在飞船上也能直接进"；11-15 定过）。由 build.py 追加到 character_state_machine 末尾
-- （要在 training_loadout.lua 后面，它负责出发前弹选战备界面）。
--
-- 做法照游戏自带的开发菜单「手动输入种子」（menu_screen_training_manual_seed.lua 255 行）：飞船状态机直接
--   change_state("transition", {wanted_state = "mission_start", is_training = true, mission_seed = …})。
--   planet_name 写 "Autohost"，和以前「关游戏、-autohost 重开」进的训练关完全一样（training_loadout.lua 认这个名字弹选战备）。
--   这条路不走出发舱、不通知联机队友，所以房间里有别人（不是本机分屏的玩家）时拒掉，让 HellBox 提示。
--
-- 和 HellBox 怎么说话：文件，不走信箱表（不用扫内存，旧版 MOD 读不到就当没装这个功能）。
--   HellBox 写 %APPDATA%/Arrowhead/Helldivers/hellbox/start-training.txt：
--     HBSTART1
--     id=随机串
--     time=写的时刻（秒）
--     seed=地图编号
--   这里每 0.5 秒看一次，读到就删掉；超过 20 秒的请求不认（防止 HellBox 早关了，过很久才进飞船时突然开局）。
--   结果写 start-training-result.txt：id=…、result=ok / not_ship / not_host / teammates / busy / bad / error。
--   2026-11-22 用户定：游戏关着时点「开始」也要在线。以前 HellBox 用 -autohost 开游戏，游戏自己把联机方式设成 LAN
--     （state_main_menu.lua 549 行）= 离线。现在 HellBox 正常开游戏，请求多带 wait=1：没到飞船（主菜单、加载）或飞船正忙
--     就先记着，进飞船站稳 SHIP_SETTLE 秒后照常处理（一个人直接进、有队友设下一局）；WAIT_AGE 秒内没进飞船就作废。
--     没走「直接进关」这条路时，把 training-loadout.txt（进关前弹选战备的标记）删掉，免得留给以后。
--
-- 2026-11-19「选图」设为下一局（用户定：房间里有队友时像试炼场那样把这张图注入下一局，队友不用装 HellBox；
--   房主、队友都照常记经验和银河战争；一个人时照旧直接进关。docs/任务/HD1-033 2026-11-19 那几条）。
--   请求里带 mode=auto（新版 HellBox 都带）时，有联机队友不再回 teammates，而是回 armed：
--   - 原版飞船出发用的种子：有 selected_trial 就用它（state_menu.lua get_mission_seed 3113 行），出发舱也只有在
--     有 current_planet 或 selected_trial 时才打开（2062 行）。所以和「玩法」页真训练场一样写 selected_trial，
--     但它是普通关卡：没有 provinggrounds_seed（不走训练场规则、简报照普通任务），planet 按地图编号拆出来填。
--     飞船把种子广播给队友（rpc_on_mission_selected 1965 行），出发舱 → 简报 → 选装备 → 出发全是原版流程。
--   - current_planet 先拿掉：结算时（state_mission_end.lua 206、260 行）有它就会把这一关算成这颗星的任务完成。
--     拿掉的星球同时存进这个 trial 的 hb_planet（跟着存档走，游戏中途关掉下次开也能放回去）。
--   - is_training 不碰（照常 false）：经验、银河战争照常记。is_last_mission 设成 false（trial 那条路原版不改它）。
--   - 出发时种子对上就算用掉；回到飞船把 trial 去掉、星球放回去。房主在星图上选了别的星球 / 别的训练场 = 这次作废；
--     只是被原版菜单清掉（开了星图又退出来）就再放回去。
--   - trial 带 hellbox 字段：玩法页 hellbox_play.lua 的 ours() 也认，服务器训练场名单那一步不会把它清掉（那边的保护共用）。
do
	local G = HellBoxStart or {}

	HellBoxStart = G

	local MAX_AGE = 20
	local WAIT_AGE = 600 -- 【用户 2026-11-22】游戏关着时点「开始」：开游戏、进飞船最多等 10 分钟（和选战备标记的 10 分钟一样）
	local SHIP_SETTLE = 3 -- 【暂定】进飞船后等几秒再开，飞船和房间先建好

	local function dir()
		local appdata = os.getenv and os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/")
	end

	local function answer(id, result)
		local d = dir()
		local f = d and io.open(d .. "start-training-result.tmp", "wb")

		if not f then
			return
		end

		f:write("id=" .. tostring(id) .. "\nresult=" .. result .. "\n")
		f:close()
		os.remove(d .. "start-training-result.txt")
		os.rename(d .. "start-training-result.tmp", d .. "start-training-result.txt")
	end

	local function take_request()
		local d = dir()
		local path = d and (d .. "start-training.txt")
		local f = path and io.open(path, "rb")

		if not f then
			return nil
		end

		local text = f:read("*a") or ""

		f:close()
		os.remove(path)

		if not text:match("^HBSTART1") then
			return nil
		end

		local req = {}

		for line in text:gmatch("[^\r\n]+") do
			local k, v = line:match("^([%w_]+)=(.*)$")

			if k then
				req[k] = v
			end
		end

		return req
	end

	-- 现在能不能直接进：返回 nil = 能（附带飞船对象），否则返回原因
	local function check()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if not sm or sm:get_current_state_name() ~= "menu" then
			return "not_ship"
		end

		local ship = sm:get_current_state()

		if type(ship) ~= "table" or type(ship.get_active_players) ~= "function" then
			return "not_ship"
		end

		if not ship.is_server then
			return "not_host"
		end

		-- 出发舱倒计时 / 任务简报 / 选装备 / 正在出发：别插队
		local ms = ship.menu_state

		if ms ~= nil and ms ~= ship.MENU_STATE_INVALID and ms ~= ship.MENU_STATE_HOST_IN_CAMPAIGN then
			return "busy"
		end

		local players = ship:get_active_players()

		for _, p in ipairs(players) do
			if not p.owned then
				return "teammates", ship
			end
		end

		return nil, ship, sm, players
	end

	-- ------------------------------------------------------------ 选图：设为下一局（2026-11-19）
	local function mine(t)
		return type(t) == "table" and t.hellbox == "map"
	end

	local function map_trial(seed, planet, id)
		local p = DifficultySettings.get_mission_params(seed)

		return {
			unlocked = true,
			index = 1,
			seed = seed,
			name = "HellBox",
			hellbox = "map",
			hellbox_map = id,
			hb_planet = planet,
			planet = {
				region = 0,
				name = type(planet) == "table" and planet.name or "city_superearth",
				difficulty = p.difficulty,
				enemy = p.enemy,
				environment = p.environment,
				environment_variant = p.environment_variant,
				shading_environment = p.shading_environment,
				seed = seed
			}
		}
	end

	-- 去掉我们的 trial，原来的星球放回去（只在现在没有星球时放，别盖掉房主新选的）
	local function disarm_map()
		local t = SaveManager:get("selected_trial")
		local planet = G.map and G.map.planet

		if mine(t) then
			SaveManager:set("selected_trial", nil)

			if t.hb_planet ~= nil then
				planet = t.hb_planet
			end
		end

		if mine(SaveManager:get("last_trial")) then
			SaveManager:set("last_trial", nil)
		end

		if planet ~= nil and SaveManager:get("selected_trial") == nil and SaveManager:get("current_planet") == nil then
			SaveManager:set("current_planet", planet)
		end
	end

	local function arm_map(ship, seed, id)
		local cur = SaveManager:get("selected_trial")
		local planet = SaveManager:get("current_planet")

		if mine(cur) and planet == nil then
			planet = cur.hb_planet -- 已经设过一张：换图时原来的星球接着带上
		end

		local trial = map_trial(seed, planet, id)

		SaveManager:set("dropzone_position", nil)
		SaveManager:set("selected_trial", trial)
		SaveManager:set("current_planet", nil)
		ship.is_last_mission = false

		G.map = { id = id, seed = seed, planet = planet, trial = trial }
		G.map_used = nil
		G.map_state = "armed"
	end

	local function map_tick()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if not sm then
			return
		end

		local name = sm:get_current_state_name()
		local state = sm:get_current_state()

		if name == "menu" and type(state) == "table" then
			if G.map_used then
				-- 打完回到飞船：恢复原样
				G.map = G.map_used
				disarm_map()
				G.map, G.map_used = nil, nil
				G.map_state = "done"

				return
			end

			local t = SaveManager:get("selected_trial")

			if G.map then
				if not state.is_server then
					disarm_map()
					G.map = nil
					G.map_state = "cancelled"
				elseif mine(t) then
					state.is_last_mission = false

					-- 别的模块（比如玩法页真训练场撤掉时）把星球放回来了：收进 trial 里，别让结算把这一关记到它头上
					local cur = SaveManager:get("current_planet")

					if cur ~= nil then
						G.map.planet = cur
						G.map.trial.hb_planet = cur
						t.hb_planet = cur
						SaveManager:set("selected_trial", t)
						SaveManager:set("current_planet", nil)
					end
				elseif t == nil and SaveManager:get("current_planet") == nil then
					-- 被原版菜单清掉了（开了星图又退出来）：放回去，还是下一局
					SaveManager:set("selected_trial", G.map.trial)
				else
					-- 房主在星图上选了别的星球 / 别的训练场：这次作废，星球交给原版管
					G.map = nil
					G.map_state = "cancelled"
				end
			elseif mine(t) then
				-- 上次设了没打就关了游戏（存档里还留着）：放回原来的星球
				disarm_map()
			end
		elseif (name == "mission_start" or name == "game") and G.map and type(state) == "table" then
			if state.mission_seed == G.map.seed then
				G.map_used = G.map
				G.map = nil
				G.played_seed = G.map_used.seed -- 战绩（hellbox_results.lua）认这一关是「选图」
				G.map_state = "used"
			end
		end
	end

	local function drop_loadout_flag()
		local d = dir()

		if d then
			os.remove(d .. "training-loadout.txt")
		end
	end

	local function serve()
		local req = take_request()

		if req then
			G.pending = nil -- 新请求顶掉还在等的
		else
			req = G.pending

			if not req then
				return
			end
		end

		local id = req.id or "?"
		local stamp = tonumber(req.time)
		local seed = tonumber(req.seed)
		local waiting = req.wait == "1"

		if not stamp or math.abs(os.time() - stamp) > (waiting and WAIT_AGE or MAX_AGE) then
			G.last = "stale"
			G.pending = nil

			if waiting then
				drop_loadout_flag()
			end

			return -- 太旧：HellBox 早就当超时了，不回
		end

		if not seed or seed < 0 or seed ~= math.floor(seed) then
			G.pending = nil
			answer(id, "bad")

			return
		end

		local why, ship, sm, players = check()
		local strong = rawget(_G, "HellBoxStrong")

		if waiting then
			if why == "not_ship" or why == "busy" then
				G.pending = req -- 还没到飞船 / 飞船正忙：记着，下次再看

				if why == "not_ship" then
					G.ship_since = nil
				end

				return
			end

			local now = Application.time_since_launch()

			G.ship_since = G.ship_since or now

			if now - G.ship_since < SHIP_SETTLE then
				G.pending = req

				return
			end

			G.pending = nil
			G.ship_since = nil

			if why ~= nil then
				drop_loadout_flag() -- 不是一个人直接进关（设下一局 / 不是房主…）：选战备标记用不上
			end
		end

		-- 2026-11-25「变强」：新请求先把上一次的设置清掉，下面一个人直接进关成功才按这次的设（hellbox_strong.lua）
		if strong and strong.arm then
			strong.arm(nil)
		end

		if why == "teammates" and req.mode == "auto" then
			-- 2026-11-19 选图：有联机队友 → 设为下一局（房主走出发舱照常出发）
			local ok, err = pcall(arm_map, ship, seed, id)

			if not ok then
				answer(id, "error")
				error(err, 0)
			end

			G.last = "armed"
			answer(id, "armed")

			return
		end

		if why then
			G.last = why
			answer(id, why)

			return
		end

		if G.map then
			-- 一个人直接进关：之前设的下一局作废（星球放回去）
			disarm_map()
			G.map = nil
			G.map_state = "cancelled"
		end

		local ok, err = pcall(function()
			SaveManager:set("dropzone_position", nil)
			sm:change_state("transition", {
				wanted_state = "mission_start",
				is_training = true,
				planet_name = "Autohost",
				mission_seed = seed,
				active_players = players,
				reserved_slots = {},
				game_id = math.create_weak_unique_identifier()
			})
		end)

		if not ok then
			answer(id, "error")
			error(err, 0)
		end

		if strong and strong.arm and (req.wave or req.revive) then
			strong.arm(seed, req.wave, req.revive == "1")
		end

		G.last = "ok"
		G.started = (G.started or 0) + 1

		answer(id, "ok")
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.tick then
		local orig = wm.update
		local next_check = 0

		G.tick = function(self, ...)
			local now = Application.time_since_launch()

			if now >= next_check then
				next_check = now + 0.5

				local ok, err = pcall(serve)

				if not ok then
					G.last = "error"

					if rawget(_G, "HellBoxLog") then
						HellBoxLog("hellbox_start", err)
					end
				end

				ok, err = pcall(map_tick)

				if not ok and rawget(_G, "HellBoxLog") then
					HellBoxLog("hellbox_start map", err)
				end
			end

			return orig(self, ...)
		end
		wm.update = G.tick
	end
end
