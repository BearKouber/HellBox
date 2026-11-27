-- [hellbox strong] 选图「变强」（2026-11-25 用户定）：只在一个人打报复关时生效，场上多一个人（本机 2P、联机队友）就不管。
-- 由 build.py 追加到 character_state_machine 末尾（hellbox_start.lua 后面；那边一个人直接进关成功时调 HellBoxStrong.arm）。
--
-- ① 从第 N 波开始：报复关组件还没开第一波（current_wave = 0）时改成 N - 1，第一波就是第 N 波
--    （和 ai_start_wave.lua 同一个做法；出怪抽法、各组的 wave_start 都照原版）。杀怪数照常从 0 开始（用户定）。
-- ② 复活币：最后一条命也死了时不判任务失败，原地重来 ——
--    - 先补一条命，交给原版单人复活（state_game.lua on_player_death 2416 行：有命就扣一条、在死的地方 8 米外重生，
--      报复关还会在死的地方落一发导弹）；
--    - 清掉场上的怪和排队要出的怪（照原版开发菜单 no_enemies，encounter_manager.lua 785 行）；
--    - 杀怪数归 0（照原版开发菜单 restart_objectives，objective_genocide_component.lua 600 行）、波数拨回 N - 1、
--      开场等待重新设成 15 秒、巡逻和警报先关（等待走完原版自己再打开，objective_genocide_component.lua 325 行）；
--    - 落地后战备全部补满（原版 inventory 命令 receive_stratagem：冷却清零、次数 +1、同步，inventory_component.lua 634 行），
--      命数补回开局的 2 条。
--    原版事件分发器没反编译出来，不确定它是不是每次现查 on_player_death：类上挂一层，update_host 里再兜一层
--    （人死了、没命、也没在复活 = 上面那层没跑到，就补一条命再走一遍原版 on_player_death）。
--    - 还没落地的信标取消（原版 stratagem 命令 abort：不再落舱，几秒后信标自己消失，stratagem_component.lua 303 行）；
--      场上的东西全部收走【用户 2026-11-26 改：全部清；11-25 原来定的是炮塔、地雷、载具不清】：
--      地上的枪、背包、弹药、补给舱、拾取物，放下的炮塔、电塔、地雷、固定机枪、载具、护盾、诱饵、无人机、炸药、着火 / 毒气区，
--      落舱用的空舱（原版自己清这些也是 despawn_entity；正飞去对接背包的无人机一起收，drone_component.lua 326 行）。
--      死的那一下收一遍（这时复活舱还没出来），落地 1 秒后再收一遍死后新冒出来的（不收舱）；座位上有人的车下一遍再收。
-- ③ 只在单人模式下生效【用户 2026-11-25】：这一局里只要出现过第二个人（本机 2P、联机队友），或者扔了救援信标
--    （stratagem_emergency_beacon：生效时 state_game.lua 2542 行把房间改公开、HUD 记 emergency_beacon），这一局就不再管。
do
	local G = HellBoxStrong or {}

	HellBoxStrong = G

	local WAIT = 15 -- 【源码】objective_genocide_component var_0_1 = 15：报复关开场等 15 秒；【用户 2026-11-25】重来后也等 15 秒
	local START_LIVES = 2 -- 【源码】state_game.lua 3348 行：报复关单人开局 2 条命
	local SETTLE = 1 -- 【暂定】复活落地站稳几秒再补战备（免得原版复活时下发的战备状态把补好的盖回去）
	local FALLBACK_GRACE = 0.5 -- 【暂定】兜底层等几秒（要比原版判失败的 3 秒短）
	local ENEMY = { "bug_", "cyborg_", "illuminate_" }

	local function log(msg)
		if rawget(_G, "HellBoxLog") then
			HellBoxLog("hellbox_strong", msg)
		end
	end

	-- 2026-11-25 用户定：HellBox 关了（hellbox_alive.lua）复活币、从第 N 波开始都不管，照原版；再打开接着管
	local function on()
		local a = rawget(_G, "HellBoxAlive")

		return not (type(a) == "table" and type(a.off) == "function" and a.off())
	end

	-- HellBox 带来的设置：seed = 这一关的地图编号，wave = 从第几波开始，revive = 复活币。seed 为空 = 清掉
	function G.arm(seed, wave, revive)
		if not seed then
			G.cfg = nil

			return
		end

		wave = math.floor(tonumber(wave) or 1)

		G.cfg = {
			seed = seed,
			wave = math.max(1, math.min(99, wave)),
			revive = revive and true or false
		}
		G.resets = 0
		G.refill = nil
		G.reset_objective = nil
		G.handled = nil
	end

	local function now()
		return Application.time_since_launch()
	end

	-- 这一局是不是「变强」那一关，并且场上只有一个人
	local function active(s)
		local cfg = G.cfg

		if not cfg or cfg.off or type(s) ~= "table" or not s.is_server or not s.is_training or s.mission_seed ~= cfg.seed then
			return nil
		end

		local lvl = s.generated_level

		if type(lvl) ~= "table" or lvl.mission_type_name ~= "genocide" then
			return nil
		end

		if type(s.get_active_players) ~= "function" or #s:get_active_players() ~= 1 then
			return nil
		end

		return cfg
	end

	local function game_state()
		local b = rawget(_G, "Boot")
		local sm = type(b) == "table" and b.state_machine

		if not sm then
			return nil, nil
		end

		return sm:get_current_state_name(), sm:get_current_state()
	end

	local function is_enemy(path)
		if type(path) ~= "string" or not path:find("^characters/") then
			return false
		end

		for _, pre in ipairs(ENEMY) do
			if path:find(pre, 1, true) then
				return true
			end
		end

		return false
	end

	-- 照原版开发菜单 no_enemies：清警报波次的记账、收走所有敌人、把排队要出的敌人撤掉
	local function clear_enemies(s)
		local enc, spm, em, spawner = s.encounter_manager, s.spawn_manager, s.entity_manager, s.entity_spawner

		if type(enc) == "table" then
			enc.enemies = {}
			enc.num_queued_enemies = 0
			enc.selected_waves = nil
			enc.current_wave = nil
			enc.active_events = {}
			enc.active_groups = {}
			enc.wave_duration = 0
		end

		local n = 0

		if type(em) == "table" and type(spawner) == "table" then
			local units = {}

			for unit in pairs(em:get_master_entities("enemy")) do
				units[#units + 1] = unit
			end

			for _, unit in ipairs(units) do
				if Unit.alive(unit) then
					spawner:despawn_entity(unit)

					n = n + 1
				end
			end
		end

		if type(spm) == "table" and type(spm.unqueue_spawns) == "function" then
			local paths, seen = {}, {}

			for _, q in ipairs(spm.queued_spawns or {}) do
				local p = q.unit_path

				if is_enemy(p) and not seen[p] then
					seen[p] = true
					paths[#paths + 1] = p
				end
			end

			spm:unqueue_spawns(paths) -- 只撤敌人；原版这一步还会清掉排队的整队敌人（queued_groups）
		end

		return n
	end

	local function strat_name(id)
		local info = id and LoadoutSettings.stratagems[id]

		return info and info.name
	end

	-- 单人模式检查：出现第二个人、或者扔了 / 开了救援信标，这一局就关掉（不再恢复）
	local function room_check(s)
		local cfg = G.cfg

		if not cfg or cfg.off or type(s) ~= "table" or s.mission_seed ~= cfg.seed then
			return
		end

		local why

		if type(s.get_active_players) == "function" and #s:get_active_players() > 1 then
			why = "players"
		end

		local hud = s.hud
		local ctx = type(hud) == "table" and hud.stratagem_can_use_context

		if not why and type(ctx) == "table" and ctx.emergency_beacon then
			why = "sos"
		end

		if not why and type(s.entity_manager) == "table" then
			for _, e in pairs(s.entity_manager:get_master_entities("stratagem")) do
				if type(e) == "table" and type(e.state) == "table" and strat_name(e.state.stratagem_id) == "stratagem_emergency_beacon" then
					why = "sos"

					break
				end
			end
		end

		if why then
			cfg.off = why
			G.refill = nil
			G.reset_objective = nil

			log("off for this mission: " .. why)
		end
	end

	-- 还没落地的信标：原版 abort（不落舱，信标自己消失）
	local function abort_beacons(s)
		local n = 0

		for unit, e in pairs(s.entity_manager:get_master_entities("stratagem")) do
			local st = type(e) == "table" and e.state

			if type(st) == "table" and not st.abort and (tonumber(st.activation_time) or 0) > 0 and Unit.alive(unit) then
				EntityAux.queue_command_master(unit, "stratagem", "abort")

				n = n + 1
			end
		end

		return n
	end

	-- 2026-11-26 用户改：复活币重来时场上的东西全部清（推翻 11-25「炮塔、地雷、载具不清」；用户实测弹药没清）。
	-- 地上捡的：枪、背包、弹药、补给舱、其它拾取物
	local LOOT = { "weapon_pickup", "backpack_pickup", "ammo_pickup", "supply_crate", "custom_pickup" }
	-- 放下的：炮塔、电塔、地雷、固定机枪、载具、护盾、诱饵、无人机、炸药、着火 / 毒气区
	local PLACED = { "turret", "launcher_turret", "melee_turret", "tesla", "mine", "minedrop", "stationary_weapon",
		"vehicle", "shield_dome", "distractor", "uav_drone", "explosive", "spawn_area_effect" }

	local function masters(em, comp)
		local ok, t = pcall(em.get_master_entities, em, comp)

		return ok and type(t) == "table" and t or {}
	end

	-- 座位上有人（含尸体）的不收：人挂在车上，直接收车不安全；下一轮（落地后那次）再看
	local function occupied(unit)
		local ok, st = pcall(function()
			return EntityAux.has_component(unit, "seat") and EntityAux.state(unit, "seat")
		end)

		for _, u in pairs(ok and type(st) == "table" and st.seated_units or {}) do
			if u and Unit.alive(u) then
				return true
			end
		end

		return false
	end

	-- 清场。full = 刚死那一下（人已经死了、复活舱还没出来）：连落舱用的空舱（hellpod）一起收；
	-- 落地后那次不收舱（自己的复活舱可能也是），只收死后到落地之间新冒出来的（死时掉的枪、死前扔的信标落下的东西）
	local function clear_pickups(s, full)
		local em, spawner = s.entity_manager, s.entity_spawner
		local units, set = {}, {}
		local lists = { LOOT, PLACED }

		if full then
			lists[3] = { "hellpod" }
		end

		for _, list in ipairs(lists) do
			for _, comp in ipairs(list) do
				for unit in pairs(masters(em, comp)) do
					if not set[unit] and Unit.alive(unit) and EntityAux.owned(unit) and not occupied(unit) then
						set[unit] = true
						units[#units + 1] = unit
					end
				end
			end
		end

		for drone, e in pairs(masters(em, "drone")) do
			local st = type(e) == "table" and e.state

			if type(st) == "table" and st.station_unit and set[st.station_unit] and Unit.alive(drone) and EntityAux.owned(drone) then
				units[#units + 1] = drone
				set[drone] = true
			end
		end

		for _, unit in ipairs(units) do
			if Unit.alive(unit) then
				spawner:despawn_entity(unit)
			end
		end

		return #units
	end

	local function solo_player(s)
		for _, p in ipairs(s.players or {}) do
			if p.player_go and p.player_go:exists() then
				return p
			end
		end
	end

	local function avatar_of(p)
		local go = p and p.player_go

		if go and go:exists() and go:has("avatar_unit") then
			local u = go:get("avatar_unit")

			if u and Unit.alive(u) then
				return u
			end
		end
	end

	-- 命用光的这一下：补一条命（原版接着复活），清场，记下要重置报复关和补战备
	local function spend_coin(s, p, unit)
		s:set_extra_lives(p, 1)

		local n = clear_enemies(s)
		local b = abort_beacons(s)
		local ok, picks = pcall(clear_pickups, s, true)

		G.reset_objective = true
		G.refill = { player = p, dead = unit }
		G.handled = unit
		G.resets = (G.resets or 0) + 1

		log(string.format("revive #%d: cleared %d enemies, aborted %d beacons, removed %s objects", G.resets, n, b,
			ok and tostring(picks) or ("error " .. tostring(picks))))
	end

	local function try_coin(s, unit)
		local cfg = active(s)

		if not cfg or not cfg.revive or G.handled == unit then
			return
		end

		for _, p in ipairs(s.players or {}) do
			local go = p.player_go

			if go and go:exists() and go:has("avatar_unit") and go:get("avatar_unit") == unit then
				if (p.extra_lives or 0) <= 0 then
					spend_coin(s, p, unit)
				end

				return
			end
		end
	end

	-- 兜底：人死了、没命、没在复活，而 on_player_death 那层没跑到
	local function watch(s)
		local cfg = active(s)

		if not cfg or not cfg.revive then
			return
		end

		local p = solo_player(s)
		local unit = avatar_of(p)

		if not unit or G.handled == unit or (p.extra_lives or 0) > 0 or p.is_respawning then
			return
		end

		local h = EntityAux.state(unit, "health")

		if not (h and h.is_dead) then
			return
		end

		-- 先等一会儿，让原版的死亡事件（上面那层）先走；原版判失败要等 3 秒（state_game.lua game_over_timer）
		if G.dead_unit ~= unit then
			G.dead_unit, G.dead_since = unit, now()
		end

		if now() - G.dead_since < FALLBACK_GRACE then
			return
		end

		log("fallback: on_player_death hook did not run")
		spend_coin(s, p, unit)
		s:on_player_death(unit) -- 走一遍原版复活（这时有 1 条命）
	end

	-- 复活落地站稳以后：战备补满、命数补回开局
	local function refill(s)
		local r = G.refill

		if not r then
			return
		end

		if not active(s) then
			G.refill = nil

			return
		end

		local unit = avatar_of(r.player)

		if not unit or unit == r.dead then
			return
		end

		local h = EntityAux.state(unit, "health")

		if not h or h.is_dead then
			return
		end

		r.since = r.since or now()

		if now() - r.since < SETTLE then
			return
		end

		G.refill = nil

		local b = abort_beacons(s) -- 死后到落地之间又扔出来的（死前手里那颗）
		local picks = clear_pickups(s)
		local inv = EntityAux.state_master(unit, "inventory")
		local n = 0

		for _, st in ipairs(inv and inv.stratagems or {}) do
			local info = st.id and LoadoutSettings.stratagems[st.id]

			if info then
				-- receive_stratagem 一次补一次次数、冷却清零；补到原版的最多次数为止（多发的那几次原版自己不理）
				for _ = 1, math.max(1, tonumber(info.num_uses) or 1) do
					EntityAux.queue_command_master(unit, "inventory", "receive_stratagem", st.id)
				end

				n = n + 1
			end
		end

		if (r.player.extra_lives or 0) < START_LIVES then
			s:set_extra_lives(r.player, START_LIVES)
		end

		log(string.format("refilled %d stratagems, removed %d pickups, aborted %d beacons", n, picks, b))
	end

	-- 报复关组件：开第一波前拨到第 N 波；复活币用掉后重置这一关
	local function objective(comp, masters)
		local name, s = game_state()
		local cfg = name == "game" and active(s)

		if not cfg then
			return
		end

		for _, m in pairs(masters) do
			local st = type(m) == "table" and m.state

			if type(st) == "table" then
				if not st._hb_strong then
					st._hb_strong = true

					if cfg.wave >= 2 and st.current_wave == 0 then
						st.current_wave = cfg.wave - 1
						st.dirty = true
					end
				end

				if G.reset_objective then
					comp:set_protected(st, "enemies_killed", 0)

					st.current_wave = cfg.wave - 1
					st.queued_wave_groups = {}
					st.initial_wait_time = WAIT
					st.check_wave_done_timer = 0
					st.dirty = true
				end
			end
		end

		if G.reset_objective then
			G.reset_objective = nil

			local threat = comp.threat_go

			if threat and threat:owned() then
				threat:set("patrols", false)
				threat:set("encounter", false)
			end
		end
	end

	local function hook_classes()
		local sg = rawget(_G, "StateGame")

		if type(sg) == "table" and not rawget(sg, "_hb_strong") and type(sg.on_player_death) == "function" and type(sg.update_host) == "function" then
			local orig_death, orig_host = sg.on_player_death, sg.update_host

			sg.on_player_death = function(self, unit, ...)
				if G.cfg and on() then
					local ok, err = pcall(try_coin, self, unit)

					if not ok then
						log(err)
					end
				end

				return orig_death(self, unit, ...)
			end
			sg.update_host = function(self, ...)
				if G.cfg and on() then
					local ok, err = pcall(room_check, self)

					if not ok then
						log(err)
					end

					ok, err = pcall(watch, self)

					if not ok then
						log(err)
					end

					ok, err = pcall(refill, self)

					if not ok then
						log(err)
					end
				end

				return orig_host(self, ...)
			end
			sg._hb_strong = true
		end

		local oc = rawget(_G, "ObjectiveGenocideComponent")

		if type(oc) == "table" and not rawget(oc, "_hb_strong") and type(oc.update_masters) == "function" then
			local orig = oc.update_masters

			oc.update_masters = function(self, masters, ...)
				if G.cfg and on() and type(masters) == "table" then
					local ok, err = pcall(objective, self, masters)

					if not ok then
						log(err)
					end
				end

				return orig(self, masters, ...)
			end
			oc._hb_strong = true
		end
	end

	-- 回到飞船 = 这一关打完了，设置作废（arm 是在飞船上调的，所以要先进过关卡才算）
	local function lifecycle()
		local cfg = G.cfg

		if not cfg then
			return
		end

		local name, s = game_state()

		if name == "game" and type(s) == "table" and s.mission_seed == cfg.seed then
			cfg.entered = true
		elseif name == "menu" and cfg.entered then
			G.arm(nil)
		end
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.tick then
		local orig = wm.update
		local next_check = 0

		G.tick = function(self, ...)
			local t = now()

			if t >= next_check then
				next_check = t + 0.5

				local ok, err = pcall(hook_classes)

				if not ok then
					log(err)
				end

				ok, err = pcall(lifecycle)

				if not ok then
					log(err)
				end
			end

			return orig(self, ...)
		end
		wm.update = G.tick
	end
end
