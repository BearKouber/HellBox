-- [hellbox drone light] 鬼城里的两盏灯（2026-11-20 HD1-035；同日第四版）。
-- 用户：「鬼城太黑了……给小蜜蜂做成可以发光的，发光多少可以调整……只在鬼城生效灯光就更好了」；
--   第一版不亮后：「加一个更亮的小蜜蜂和更亮的信标两个控件」；第二、三版试过探照灯和「所有地图」选项，
--   用户实测后定：「探照灯删除，保留光圈，默认只在触发鬼城时候亮，这个选项删除」，光圈「也需要是逐渐变暗」。
--
-- 设置在 hop.txt（hellbox_hop.lua 每秒读，这里看 HellBoxHop.config）：
--   drone_light / drone_light_percent、beacon_light / beacon_light_percent
-- 灯光是每台电脑自己画的：只有装了 HellBox、开了开关、这一关是鬼城的电脑上才亮，别人看到原版，不传任何东西。
--
-- 灯源是战备信标 gameobjects/flare_01（游戏脚本不能凭空造灯；信标有 3 盏灯，第一盏 type=0 四面照、intensity=1、照 2 米）。
--   蜜蜂光圈：场上有无人机时在自己电脑上生成一个不联网的信标（World.spawn_unit，不进实体系统），藏起模型、只留一盏灯、白光，
--     放在自己潜兵头顶 2.5 米，半径 6～14 米、亮度 2～7 倍，照出脚边一圈。
--     只在场上有无人机时才生成：叫无人机就得先扔一个信标，信标资源一定已经加载（没加载就生成会直接闪退）。
--     无人机进场灯慢慢亮起来，离场（exit）慢慢暗掉；无人机先没了也照样暗完。几架无人机只点一盏灯。
--   信标更亮：落地亮起来的信标（stratagem 组件 has_been_enabled）灯调亮调远；信标完成 / 取消后
--     不马上恢复，几秒内慢慢暗回原样；游戏这时用 FlowCallbacks.disable_light 关掉的灯先替它开着，暗完再关；
--     信标先被收走了（东西落地）灯就跟着没了，和原版一样。2026-11-21 用户：以前这时原地补一盏灯接着暗，
--     落地时信标周围出现「颜色很奇怪、慢慢缩小」的光圈，要去掉（颜色怪：记下的颜色是引擎当帧的临时值，过几帧就成了乱数）。
-- 第一次的关键数值写进 HellBox 日志，实测后好校准。全部 pcall 包着，哪一步不行就是不亮，不影响游戏。
do
	local G = HellBoxDroneLight or {}

	HellBoxDroneLight = G
	G.beacons = G.beacons or {}   -- 信标 -> rec

	local FLARE = "gameobjects/flare_01"
	local ABOVE_DRONE = 8         -- 找不到自己的潜兵时，灯放在无人机脚下那个点上方几米（无人机本身的位置是地面上的点）
	local ABOVE_PLAYER = 2.5      -- 光圈在自己潜兵头顶几米
	local ENTER_FADE = 2.5        -- 无人机进场时灯亮起来要几秒
	local EXIT_FADE = 6           -- 无人机离场时灯暗下去要几秒
	local BEACON_FADE = 4         -- 信标结束后亮光暗回原样要几秒
	local WARM = { 1, 0.95, 0.85 }
	local logged = {}

	local function log(text)
		if rawget(_G, "HellBoxLog") then
			pcall(HellBoxLog, "drone_light", text)
		end
	end

	local function config()
		local hop = rawget(_G, "HellBoxHop")
		return hop and hop.config or {}
	end

	local function pct(c, key)
		local p = tonumber(c[key]) or 60
		return math.max(5, math.min(100, p))
	end

	local function dt()
		local d = rawget(_G, "REAL_TIME_DT")
		return (type(d) == "number" and d > 0 and d < 1) and d or 1 / 60
	end

	local function game_state()
		local m = rawget(_G, "Boot") and Boot.state_machine
		return m and m.current_state_name == "game" and m.state or nil
	end

	local function ghost(state)
		local gl = state and state.generated_level
		return type(gl) == "table" and (rawget(gl, "_hb_ghost") == true or gl.time_of_day == "ghost_town")
	end

	local function contexts(state, name, side)
		local groups = state and state.entity_manager and state.entity_manager.component_name_to_contexts
		return groups and groups[name] and groups[name][side] or {}
	end

	-- 场上的无人机：还没离场的优先；返回 (单位, 状态序号 1 进场 / 2 工作 / 3 离场)
	local function pick_drone(state)
		local best, best_i
		for _, side in ipairs({ "slave", "master" }) do
			for unit, ctx in pairs(contexts(state, "uav_drone", side)) do
				if Unit.alive(unit) then
					local s = type(ctx) == "table" and ctx.state
					local i = s and tonumber(s.current_state_index) or 2
					if not best or (best_i >= 3 and i < 3) then
						best, best_i = unit, i
					end
				end
			end
		end
		return best, best_i
	end

	-- 这台电脑自己的潜兵里离 pos 最近的（分屏时有两个）
	local function my_player(state, pos)
		local best, best_d
		for _, player in ipairs(state and state.players or {}) do
			local go = player.player_go
			local ok, mine = pcall(function()
				return go and go:exists() and go:owned() and go:get("avatar_unit")
			end)
			if ok and mine and Unit.alive(mine) then
				local d = 0
				if pos then
					local ok_p, p = pcall(Unit.world_position, mine, 0)
					d = ok_p and p and Vector3.distance(p, pos) or 0
				end
				if not best or d < best_d then
					best, best_d = mine, d
				end
			end
		end
		return best
	end

	local function position(unit)
		if not unit then
			return nil
		end
		local ok, p = pcall(Unit.world_position, unit, 0)
		return ok and p or nil
	end

	local function getter(name, light)
		local f = rawget(_G, "Light") and Light[name]
		if type(f) ~= "function" then
			return nil
		end
		local ok, v = pcall(f, light)
		if ok then
			return v
		end
	end

	local function remember(light)
		return {
			type = getter("type", light),
			intensity = getter("intensity", light),
			falloff_start = getter("falloff_start", light),
			falloff_end = getter("falloff_end", light),
			spot_start = getter("spot_angle_start", light),
			spot_end = getter("spot_angle_end", light),
		}
	end

	local function describe(orig)
		return string.format("type=%s intensity=%s falloff=%s..%s spot=%s..%s", tostring(orig.type), tostring(orig.intensity),
			tostring(orig.falloff_start), tostring(orig.falloff_end), tostring(orig.spot_start), tostring(orig.spot_end))
	end

	local function lights_of(unit)
		local out = {}
		local ok, n = pcall(Unit.num_lights, unit)
		for i = 0, (ok and type(n) == "number" and n or 0) - 1 do
			local ok_l, light = pcall(Unit.light, unit, i)
			if ok_l and light then
				out[#out + 1] = light
			end
		end
		return out
	end

	local function base_intensity(orig)
		local b = orig.intensity
		return (type(b) == "number" and b > 0) and b or 1
	end

	local function world()
		local ok, w = pcall(function()
			return WorldManager:get_world_proxy("game_world"):get_world()
		end)
		return ok and w or nil
	end

	local function destroy(unit, w)
		if unit and w and Unit.alive(unit) then
			pcall(World.destroy_unit, w, unit)
		end
	end

	-- 生成一个藏起模型的信标，返回 (单位, 世界, 它的灯列表)；只在场上已经有信标 / 无人机时调用（资源一定在）
	local function spawn_lamp_unit(at)
		local w = world()
		if not w then
			return nil
		end
		local ok, unit = pcall(World.spawn_unit, w, FLARE, at or Vector3(0, 0, -500))
		if not ok or not unit then
			if not logged.spawn then
				logged.spawn = true
				log("drone light: spawn beacon failed: " .. tostring(unit))
			end
			return nil
		end
		local ok_m, n = pcall(Unit.num_meshes, unit)
		for i = 0, (ok_m and type(n) == "number" and n or 0) - 1 do
			pcall(Unit.set_mesh_visibility, unit, i, false)
		end
		return unit, w, lights_of(unit)
	end

	-- ================================================================ 蜜蜂的灯
	local function drop_lamp()
		local lamp = G.lamp
		G.lamp = nil
		if lamp then
			destroy(lamp.unit, lamp.world)
		end
	end

	local function make_lamp()
		local unit, w, lights = spawn_lamp_unit()
		if not unit then
			return { failed = true }
		end
		local infos = {}
		for i, l in ipairs(lights) do
			infos[i] = remember(l)
		end
		if not logged.lamp then
			logged.lamp = true
			local parts = {}
			for i, o in ipairs(infos) do
				parts[#parts + 1] = "#" .. i .. " " .. describe(o)
			end
			log(string.format("drone light: beacon has %d lights: %s", #lights, table.concat(parts, " | ")))
		end
		if #lights == 0 then
			destroy(unit, w)
			return { failed = true }
		end
		for i, l in ipairs(lights) do
			pcall(Light.set_enabled, l, i == 1)
		end
		local light, orig = lights[1], infos[1]
		pcall(Light.set_color, light, Vector3(WARM[1], WARM[2], WARM[3]))
		pcall(Light.set_falloff_start, light, 0)
		return { unit = unit, world = w, light = light, orig = orig, level = 0 }
	end

	local function shine_lamp(state, lamp, drone_pos, p)
		local me = my_player(state, drone_pos)
		local mpos = position(me)
		local light = lamp.light
		local k = lamp.level * lamp.level -- 亮度按平方渐变，看着更顺
		local at = mpos and (mpos + Vector3(0, 0, ABOVE_PLAYER)) or (drone_pos and drone_pos + Vector3(0, 0, ABOVE_DRONE))
		if at then
			pcall(Unit.set_local_position, lamp.unit, 0, at)
		end
		-- 脚边一圈：半径 6～14 米，亮度 2～7 倍
		pcall(Light.set_falloff_end, light, 6 + 0.08 * p)
		pcall(Light.set_intensity, light, base_intensity(lamp.orig) * (1.5 + 5.5 * p / 100) * k)
		if not logged.aim then
			logged.aim = true
			log(string.format("drone light: halo lit, player=%s", tostring(me ~= nil)))
		end
	end

	local function update_lamp(state, c)
		if c.drone_light ~= "1" then
			drop_lamp()
			return
		end
		local drone, phase = pick_drone(state)
		local lamp = G.lamp
		if lamp and lamp.done then
			if drone and phase < 3 then
				G.lamp, lamp = nil, nil -- 新的一架无人机来了
			else
				return
			end
		end
		if lamp and lamp.unit and not Unit.alive(lamp.unit) then
			drop_lamp()
			lamp = nil
		end
		if not lamp then
			if not drone or phase >= 3 then
				return -- 只给还没离场的无人机点新灯
			end
			lamp = make_lamp()
			G.lamp = lamp
		end
		if lamp.failed then
			if not drone then
				G.lamp = nil -- 下一架无人机再试
			end
			return
		end
		local d = dt()
		local leaving = not drone or phase >= 3
		if drone then
			local dp = position(drone)
			if dp then
				lamp.last = Vector3Box(dp)
			end
		end
		if leaving then
			lamp.level = lamp.level - d / EXIT_FADE
			if lamp.level <= 0 then
				drop_lamp()
				G.lamp = { done = true } -- 这架无人机的灯用完了；等它没了再给下一架点
				return
			end
		else
			lamp.level = math.min(1, lamp.level + d / ENTER_FADE)
		end
		shine_lamp(state, lamp, lamp.last and lamp.last:unbox() or nil, pct(c, "drone_light_percent"))
	end

	-- ================================================================ 信标更亮
	local function restore_beacon(rec)
		for _, it in ipairs(rec.lights) do
			local o = it.orig
			if o.intensity then pcall(Light.set_intensity, it.light, o.intensity) end
			if o.falloff_end then pcall(Light.set_falloff_end, it.light, o.falloff_end) end
		end
		for name in pairs(rec.game_off or {}) do
			pcall(function()
				Light.set_enabled(Unit.light(rec.unit, name), false)
			end)
		end
	end

	local function boost(it, p, k)
		local o = it.orig
		local reach = (type(o.falloff_end) == "number" and o.falloff_end > 0) and o.falloff_end or 6
		local far = math.max(reach, 8 + 0.4 * p)
		local base = base_intensity(o)
		pcall(Light.set_intensity, it.light, base + (base * 4 * p / 100) * k)
		pcall(Light.set_falloff_end, it.light, reach + (far - reach) * k)
	end

	local function update_beacons(state, c)
		if c.beacon_light ~= "1" then
			for unit, rec in pairs(G.beacons) do
				if Unit.alive(unit) then
					restore_beacon(rec)
				end
				G.beacons[unit] = nil
			end
			return
		end
		local p = pct(c, "beacon_light_percent")
		local d = dt()
		local seen = {}
		for unit, ctx in pairs(contexts(state, "stratagem", "slave")) do
			local s = type(ctx) == "table" and ctx.state
			if s and s.has_been_enabled and Unit.alive(unit) then
				seen[unit] = true
				local rec = G.beacons[unit]
				local ended = s.is_done or s.abort
				if not rec and not ended then
					rec = { unit = unit, lights = {}, s = s }
					for _, light in ipairs(lights_of(unit)) do
						rec.lights[#rec.lights + 1] = { light = light, orig = remember(light) }
					end
					G.beacons[unit] = rec
					if not logged.beacon then
						logged.beacon = true
						log(string.format("beacon light: %d lights; first %s", #rec.lights, rec.lights[1] and describe(rec.lights[1].orig) or "-"))
					end
				end
				if rec then
					local bp = position(unit)
					if bp then
						rec.last = Vector3Box(bp)
					end
					local k = 1
					if ended then
						rec.fade = (rec.fade or 0) + d
						local left = 1 - rec.fade / BEACON_FADE
						k = math.max(0, left) ^ 2
						-- 游戏这时关掉的灯先替它开着，暗完再关
						for name in pairs(rec.game_off or {}) do
							pcall(function()
								Light.set_enabled(Unit.light(unit, name), left > 0)
							end)
						end
					end
					if ended and rec.fade >= BEACON_FADE then
						if not rec.finished then
							restore_beacon(rec)
							rec.finished = true
						end
					else
						for _, it in ipairs(rec.lights) do
							boost(it, p, k)
						end
					end
				end
			end
		end
		for unit, rec in pairs(G.beacons) do
			if not seen[unit] then
				G.beacons[unit] = nil
				if not rec.finished and Unit.alive(unit) then
					restore_beacon(rec)
				end
			end
		end
	end

	-- 信标结束时游戏用流程关灯（FlowCallbacks.disable_light）：结束那一刻起关掉的记下来，暗完再替它关。
	-- 「结束」按倒计时到 0 / 取消算（游戏先发 set_done 流程、后设 is_done）；还亮着的时候关的灯（比如换光柱）不管。
	local function hook_flow()
		local fc = rawget(_G, "FlowCallbacks")
		if type(fc) ~= "table" or type(fc.disable_light) ~= "function" or rawget(fc, "_hb_beacon_fade") then
			return
		end
		local orig_disable = fc.disable_light
		fc.disable_light = function(params, ...)
			local r = { orig_disable(params, ...) }
			pcall(function()
				local rec = G.beacons[params.unit]
				local s = rec and rec.s
				if s and not rec.finished and (s.abort or s.is_done or (tonumber(s.activation_time) or 1) <= 0) then
					rec.game_off = rec.game_off or {}
					rec.game_off[params.light_name] = true
				end
			end)
			return unpack(r)
		end
		rawset(fc, "_hb_beacon_fade", true)
	end

	-- ================================================================
	local function release_all()
		drop_lamp()
		for unit, rec in pairs(G.beacons) do
			if Unit.alive(unit) then
				restore_beacon(rec)
			end
			G.beacons[unit] = nil
		end
	end

	local function update()
		local state = game_state()
		local c = state and config()
		if not (state and ghost(state)) then
			if G.lamp or next(G.beacons) then
				release_all()
			end
			return
		end
		hook_flow()
		update_lamp(state, c)
		update_beacons(state, c)
	end
	G.update = update
	G.release_all = release_all

	local wm = rawget(_G, "WorldManager")
	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_hb_drone_light") then
		local orig = wm.update
		wm.update = function(self, ...)
			local r = { orig(self, ...) }
			local ok, problem = pcall(update)
			if not ok and not G.failed then
				G.failed = true
				log("drone light error: " .. tostring(problem))
			end
			return unpack(r)
		end
		rawset(wm, "_hb_drone_light", true)
	end
end
