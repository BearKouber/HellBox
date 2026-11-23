-- [planet refresh] 刷新星球（2026-10-22）。由 build.py 追加到 character_state_machine 末尾（在 front_unlock 后面）。
--
-- 原版：MenuScreenCampaign.on_enter（每次打开战役地图）调 generate_planets；它从存档读 "available_planets"，
--   读不到（nil）就给三个种族全部重新生成一批星球（当前前线星区、按等级的难度、随机任务，报复打击概率见 front_unlock.lua）。
-- 这里：窗口发来刷新请求后，下一次 MenuScreenCampaign.on_enter 前把存档的 "available_planets" 和 "current_planet" 清掉，
--   原版就当成第一次进来重新生成。首领星球（boss_planets）不动。房主刷新后 generate_planets 会把新星球发给客机。
-- 热刷新（2026-11-08）：战役地图开着、自己是房主、停在选战线 / 选星区 / 选星球 / 选任务界面时，不用等下次打开：
--   包 MenuScreenCampaign.update，在它前面清存档、generate_planets，再 show_state("planet") 把当前种族的星球列表重进一次
--   （原版 setup_planets 认出没扫描过的新星球，会放扫描动画）。在选战线 / 选星区界面只换数据，不切界面。
--   其他界面（开场回顾、联机房间列表、客机）不动，请求留着，等回到上面这些界面或下次打开地图再刷。
--
-- 星球里面（选任务界面）按刷新键 = 只重抽这颗星的任务（2026-11-14 V0.91，见 reroll_planet）。
--
-- 信箱表 G.t，布局和 room_name.lua 一样（只是魔数不同），窗口用 mod\room_name_live.py 写；内容不看，请求号变了就算一次刷新。
--   1-4 魔数；5 VERSION；6 请求号；7 已收到的请求号。
do
	local VERSION = 3
	local MAX_BYTES = 256
	local B0 = 9
	local OUT0 = B0 + MAX_BYTES
	local N = OUT0 + 130
	local G = PlanetRefreshMod or {}

	PlanetRefreshMod = G

	if not G.t or G.t[5] ~= VERSION or #G.t < N then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("44721359.5")
		t[2] = -tonumber("301029.875")
		t[3] = tonumber("2645.75")
		t[4] = tonumber("34359738368.125")
		t[5] = VERSION
		G.t = t
		G.seq = 0
		G.pending = false
	end

	local t = G.t

	local function poll_mailbox()
		local seq = t[6]

		if seq == G.seq then
			return
		end

		G.seq = seq
		G.pending = true
		t[7] = seq
	end

	-- 只重新生成一个阵营（race 从 1 数）的普通星球：把这个阵营的星球清空、current_region 设成战线当前星区，
	--   再调原版 generate_planets。原版看到「星区没变、星球不够 15 颗」就按难度 1、2、3… 补齐（和第一次生成一样），
	--   环境、名字（不和另外两个阵营重名）、奖励、任务都照原版生成，存档、发给客机、首领星球也照原版走。
	--   另外两个阵营走的是原版每次打开地图都会走的那段（换掉打完的星球），和平时一样。
	local function regen_race(screen, race)
		local all = SaveManager:get("available_planets")
		local group = type(all) == "table" and all[race]
		local enemy = DifficultySettings.enemy_lookup[race]
		local prog = type(screen.campaign_progress) == "table" and screen.campaign_progress[enemy]

		if type(group) ~= "table" or type(prog) ~= "table" or type(prog.active_region) ~= "number" then
			return false
		end

		-- 选中的星球是这个阵营的才清（另外两个阵营的选择不动）
		local cur = SaveManager:get("current_planet")
		local mine = type(cur) ~= "table"

		for _, p in ipairs(group.planets or {}) do
			if type(cur) == "table" and p.name == cur.name then
				mine = true
			end
		end

		group.planets = {}
		group.current_region = prog.active_region

		if mine then
			SaveManager:set("current_planet", nil)
			screen.current_planet = nil
			screen.selected_planet = nil
		end

		SaveManager:set("available_planets", all)
		screen:generate_planets()

		return true
	end

	-- 地图开着时当场刷新；当前界面不适合就返回 false，请求留着
	local function refresh_now(screen)
		local from_key = G.pending == "key"
		local st = screen.active_state
		local name = type(st) == "table" and st.name
		local race

		if name == "planet" or name == "region" or name == "start" then
			race = st.selected_race
		elseif name == "mission" then
			race = type(st.selected_planet) == "table" and type(st.selected_planet.enemy) == "number" and st.selected_planet.enemy + 1
		else
			return false
		end

		if not (type(screen.parent) == "table" and screen.parent.is_server) or not rawget(_G, "SaveManager") then
			return false
		end

		G.pending = false

		-- 2026-11-19 发行抢先版 用户定：选星球界面按刷新键只刷新当前这个阵营，另外两个阵营的星球和进度不动。
		--   （以前这里三个阵营全刷再退回选星区。）HellBox 窗口里的「现在刷新」还是三个阵营全刷。
		if from_key then
			if name == "planet" and type(race) == "number" and race >= 1 and regen_race(screen, race) then
				screen:show_state("planet", {selected_race = race})
				G.refreshes = (G.refreshes or 0) + 1
				G.live_refreshes = (G.live_refreshes or 0) + 1
				return true
			end

			if rawget(_G, "HellBoxLog") then HellBoxLog("planet_refresh", "race refresh skipped: " .. tostring(name) .. " " .. tostring(race)) end
			return true
		end

		SaveManager:set("available_planets", nil)
		SaveManager:set("current_planet", nil)
		screen.current_planet = nil
		screen.selected_planet = nil
		screen:generate_planets()

		if (name == "planet" or name == "mission") and type(race) == "number" and race >= 1 then
			screen:show_state("planet", {
				selected_race = race
			})
		end

		G.refreshes = (G.refreshes or 0) + 1
		G.live_refreshes = (G.live_refreshes or 0) + 1

		return true
	end

	local actions = {
		reload = {"reload_pressed", "reload_button"}, switch_weapon = {"switch_weapon_down"},
	}

	local function publish_choices()
		local cfg = rawget(_G, "HellBoxOptions")
		if not cfg or not InputRebinder or not InputRebinder.keybindings then
			return
		end
		local choices = cfg.refresh_choices()
		local valid = {}
		for _, action in ipairs({"reload", "switch_weapon"}) do
			if choices[action] then
				valid[#valid + 1] = action
			end
		end
		local text = table.concat(valid, ",")
		if G.choices ~= text then
			G.choices = text
			for i = 1, #text do
				t[OUT0 + 1 + i] = text:byte(i)
			end
			t[OUT0 + 1] = #text
			t[OUT0] = t[OUT0] + 1
		end
	end

	local function open_refresh(screen, input)
		local cfg = rawget(_G, "HellBoxOptions")
		local action = cfg and cfg.action
		if not cfg or not cfg.refresh or not actions[action] or not screen.parent.parent.is_server
				or not screen.done or screen.planet_scanning_state or screen.enter_planet_timer
				or screen.leave_to_region_timer or screen.update_region_timer or screen.event_timer
				or screen.tutorial_states or screen.show_leaderboard or screen.confirmation_dialog:is_active()
				or Window and not Window.has_focus() then
			return false
		end
		-- 2026-11-16：只认不冲突的那个设备上的按键（hellbox_qol.refresh_pressed），不再看合并后的 input
		if not (cfg.refresh_pressed and cfg.refresh_pressed(action)) then
			return false
		end
		screen.confirmation_dialog:on_enter({
			background_alpha = 0.9,
			selected_option = 2,
			confirmation_text = "刷新这个阵营的普通星球？这个阵营未完成的星球进度会清除，另外两个阵营不变。",
			callback_object = {on_dialog_confirmation = function(_, yes)
				if yes then
					G.pending = "key"
				end
			end},
		})
		return true
	end

	-- 2026-11-14 V0.91 用户定：在星球里面（选任务界面）按刷新键 = 只重抽这颗星的任务（打过的也行），弹同样的确认框。
	-- 照原版 MenuScreenCampaign.generate_planet 的任务部分重新生成：任务数按难度随机、任务类型 / 样本数照原版算，
	-- 星球本身（名字、环境、难度、奖励）不变；存回存档的 available_planets，房主发给客机，再把选任务界面重进一次。
	-- 2026-11-23 用户（V1.06）：「希望刷新同样使用于这个特殊事件」——解锁战线造出来的母星 / 超级地球（front_unlock.lua 的假事件）也能刷。
	--   真的事件星（服务器发的）照旧不刷。
	local function fake_event_planet(planet)
		local fu = rawget(_G, "FrontUnlockMod")

		return type(planet) == "table" and type(fu) == "table" and type(fu.is_fake) == "function"
			and (fu.is_fake(planet.defend_event) or fu.is_fake(planet.attack_event)), fu
	end

	local function reroll_planet(camp, ms)
		local planet = ms.selected_planet
		local fake, fu = fake_event_planet(planet)

		if fake then
			if not fu.reroll_event(planet) then
				return false
			end

			camp:show_state("mission", { selected_planet = planet, selected_planet_index = ms.selected_planet_index })
			G.rerolls = (G.rerolls or 0) + 1

			return true
		end

		if type(planet) ~= "table" or planet.boss or planet.defend_event or planet.attack_event then
			return false
		end

		local all = SaveManager:get("available_planets")
		local target, race

		for r, group in ipairs(all or {}) do
			for _, p in ipairs(group.planets or {}) do
				if p.name == planet.name then
					target, race = p, r
				end
			end
		end

		if not target then
			return false
		end

		local diff = target.difficulty
		local range = DifficultySettings.planet_missions_by_difficulty[diff]
		local n = math.random(range[1], range[2])
		local samples = GameSettings.get_num_research_samples_for_planet(diff, n)
		local per = math.ceil(samples / n)
		local types = DifficultySettings.get_planet_mission_types(diff, n)
		local old = {}

		for _, m in ipairs(target.missions or {}) do
			old[m.seed] = true
		end

		local missions = {}

		for i = 1, n do
			local seed
			local dup = true
			local tries = 0

			while dup and tries < 50 do
				tries = tries + 1
				seed = DifficultySettings.modulate_seed_for_planet(target.shading_environment, target.environment,
					target.environment_variant, race - 1, types[i], diff, math.random(0, 2147483646))
				dup = old[seed] or false

				for _, m in ipairs(missions) do
					if m.seed == seed then
						dup = true
					end
				end
			end

			missions[i] = { seed = seed, completed = false, num_research_samples = math.min(samples, per) }
			samples = samples - per
		end

		target.missions = missions
		target.completed = false
		target.selected_mission_index = nil

		if planet ~= target then
			planet.missions = table.clone and table.clone(missions) or missions
			planet.completed = false
			planet.selected_mission_index = nil
		end

		SaveManager:set("available_planets", all)

		if type(camp.send_planet_info) == "function" then
			camp:send_planet_info()
		end

		camp:show_state("mission", { selected_planet = planet, selected_planet_index = ms.selected_planet_index })
		G.rerolls = (G.rerolls or 0) + 1

		return true
	end

	local function open_reroll(ms, input)
		local cfg = rawget(_G, "HellBoxOptions")
		local action = cfg and cfg.action
		local camp = ms.parent

		if not cfg or not cfg.refresh or not actions[action] or type(camp) ~= "table"
				or not (type(camp.parent) == "table" and camp.parent.is_server)
				or ms.tutorial_states or not ms.done or not ms.mission_level or ms.retreat_timer
				or ms.confirmation_dialog:is_active() or Window and not Window.has_focus() then
			return false
		end

		local planet = ms.selected_planet

		if type(planet) ~= "table" or planet.boss or (planet.defend_event or planet.attack_event) and not fake_event_planet(planet) then
			return false
		end

		-- 2026-11-16：只认不冲突的那个设备上的按键（hellbox_qol.refresh_pressed），不再看合并后的 input
		if not (cfg.refresh_pressed and cfg.refresh_pressed(action)) then
			return false
		end

		ms.confirmation_dialog:on_enter({
			background_alpha = 0.9,
			selected_option = 2,
			confirmation_text = "重新生成这颗星球的任务？这颗星球的任务进度会清除。",
			callback_object = {on_dialog_confirmation = function(_, yes)
				if yes then
					G.reroll = ms
				end
			end},
		})

		return true
	end

	local function hook_mission()
		local cls = rawget(_G, "MenuScreenCampaignMission")

		if not cls or type(cls.handle_input) ~= "function" or cls.handle_input == G.mission_input then
			return
		end

		local original = cls.handle_input

		G.mission_input = function(self, input)
			local ok, handled = pcall(open_reroll, self, input)

			if not ok or not handled then
				return original(self, input)
			end
		end
		cls.handle_input = G.mission_input
	end

	local function hook_planet()
		local planet = rawget(_G, "MenuScreenCampaignPlanet")
		if not planet or type(planet.handle_input) ~= "function" then
			return
		end
		if planet.handle_input ~= G.handle_input then
			local original = planet.handle_input
			G.handle_input = function(self, input)
				local ok, handled = pcall(open_refresh, self, input)
				if not ok or not handled then
					return original(self, input)
				end
			end
			planet.handle_input = G.handle_input
		end
	end

	local function hook()
		local cls = rawget(_G, "MenuScreenCampaign")

		if type(cls) ~= "table" or type(cls.on_enter) ~= "function" then
			return false
		end

		if type(cls.update) == "function" and cls.update ~= G.update then
			local orig_update = cls.update

			G.update = function(self, ...)
				if G.reroll and not self.do_exit then
					local ms = G.reroll

					G.reroll = nil

					if self.active_state == ms then
						local ok, err = pcall(reroll_planet, self, ms)

						if not ok then
							G.errors = (G.errors or 0) + 1
							G.last_error = err
							if rawget(_G, "HellBoxLog") then HellBoxLog("planet_refresh", tostring(err)) end
						end
					end
				end

				if G.pending and not self.do_exit then
					local ok, err = pcall(refresh_now, self)

					if not ok then
						G.pending = false
						G.errors = (G.errors or 0) + 1
						G.last_error = err
					end
				end

				return orig_update(self, ...)
			end
			cls.update = G.update
		end

		if cls.on_enter ~= G.on_enter then
			local orig = cls.on_enter

			G.on_enter = function(...)
				local self = (...)
				if G.pending and rawget(_G, "SaveManager") and (not self.parent or self.parent.is_server) then
					G.pending = false
					SaveManager:set("available_planets", nil)
					SaveManager:set("current_planet", nil)
					G.refreshes = (G.refreshes or 0) + 1
				end

				return orig(...)
			end
			cls.on_enter = G.on_enter
		end

		return true
	end

	local function tick()
		poll_mailbox()
		local now = Application and Application.time_since_launch and Application.time_since_launch() or os.clock()
		if not G.next_choices or now >= G.next_choices then
			publish_choices()
			hook_planet()
			hook_mission()
			G.next_choices = now + 1
		end

		if not G.hooked then
			G.hooked = hook()
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
