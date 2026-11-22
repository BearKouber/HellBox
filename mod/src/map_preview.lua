-- [map preview] HellBox 训练模式的地图小图（2026-11-14）。由 build.py 追加到 character_state_machine 末尾。
--
-- 游戏选关界面的地图就是用地图编号现场拼的（MapWidget.set_seed：GeneratedLevel 按编号随机拼地块，
-- 再把每个地块的地图贴图按位置、朝向画上去，GeneratedLevel.update_map）。
-- 这里用同样的步骤拼一遍，只拼不画（不建渲染世界），把用了哪些地块、在哪、转了几下写成文本；
-- HellBox 从游戏文件里取同名地块的地图贴图（env_xxx/map 材料），照样拼出和游戏里一样的图。
--   请求：%APPDATA%/Arrowhead/Helldivers/hellbox/map-requests.txt，一行一个地图编号（HellBox 写：8 个存档格 + 当前选的图）
--   结果：同目录 maps2/<编号>.txt：
--     HBMAP2
--     env <环境路径>        如 env_desert/
--     mode <任务类型>       如 genocide；报复关的地块原版画两倍大，边缘不画
--     tile <名字> <朝向 0~3> <x> <y> <宽> <高> <放大倍数> <是否边缘 0/1>
--   已经有结果文件的编号跳过。在飞船、菜单里每 0.5 秒最多拼一张；任务进行中不拼（免得卡）。目录由 HellBox 建好。
do
	local G = HellBoxMapPreview or {}

	HellBoxMapPreview = G
	G.last = G.last or -100
	G.failed = G.failed or {}

	local function root()
		local appdata = os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/")
	end

	local function exists(path)
		local f = io.open(path, "rb")

		if f then
			f:close()

			return true
		end

		return false
	end

	local function generate(seed, pg)
		local level = GeneratedLevel()

		level:initialize(nil, seed, pg)
		level:generate_area()
		level:generate_mission()
		level:generate_children()
		level:generate_unique()
		level:generate_children()
		level:generate_extract()
		level:generate_children()
		level:generate_rare()
		level:generate_children()
		level:generate_special()
		level:generate_edge()
		level:generate_common()

		return level
	end

	local function render(level)
		local lines = {
			"HBMAP2",
			"env " .. tostring(level.environment and level.environment.path or ""),
			"mode " .. tostring(level.mission_type_name or ""),
		}
		local genocide = level.mission_type_name == "genocide" or level.mission_type_name == "provinggrounds_genocide_map"
		local settings = rawget(_G, "GeneratedLevelSettings")
		local gs = settings and settings.genocide

		for _, tile in ipairs(level.spawn_list or {}) do
			local mult = 1

			if genocide and gs then
				mult = gs.tile_size_multiplier_per_level and gs.tile_size_multiplier_per_level[tile.level_name] or gs.tile_size_multiplier or 1
			end

			lines[#lines + 1] = string.format("tile %s %d %d %d %d %d %g %d", tostring(tile.level_name), tile.rot or 0,
				tile.x or 0, tile.y or 0, tile.size_x or 1, tile.size_y or 1, mult, tile.is_edge and 1 or 0)
		end

		return table.concat(lines, "\n") .. "\n"
	end

	-- 2026-11-22 玩法页「试验场」也点地图挑地形：请求行还可以是「t 种族 时间 难度档 目标 地形号」，
	--   结果写 maps2/t_种族_时间_难度档_目标_地形号.txt。地图编号照 hellbox_play.lua 的 build_trial 算；
	--   第二个编号只带目标（条件、修正参数填第一个）：拼图只看目标（GeneratedLevel 按 sub_challenge 筛地块）。
	local function index_of(list, name)
		for i, v in ipairs(list or {}) do
			if v == name then
				return i
			end
		end
	end

	local function trial_seeds(race, tod, diff, chal, terrain)
		local P, D = rawget(_G, "ProvinggroundsSettings"), rawget(_G, "DifficultySettings")

		if not P or not D then
			return nil
		end

		local enemy, t = index_of(D.enemy_lookup, race), index_of(D.time_of_day_lookup, tod)
		local step = P.difficulty_steps and P.difficulty_steps[tonumber(diff) or 0]
		local okc, ci = pcall(P.get_flat_sub_challenge_index_from_name, chal)

		if not enemy or not t or not step or not okc or type(ci) ~= "number" or ci < 1 then
			return nil
		end

		local mtype = P.is_genocide_map(chal) and 4 or 3
		local seed = D.modulate_seed(t - 1, (t - 1) % 3, 5, 1, enemy - 1, mtype, step.value, (tonumber(terrain) or 0) * 10000000)

		return seed, P.modulate_seed_flat_indicies(ci - 1, 0, 0)
	end

	-- 返回 文件名（不带 .txt）, 地图编号, 第二个编号（试验场才有）
	local function next_request(dir)
		local f = io.open(dir .. "map-requests.txt", "rb")

		if not f then
			return nil
		end

		local text = f:read(16384) or "" -- 2026-11-22「挑地形」一次要 215 张，清单变长

		f:close()

		for line in text:gmatch("[^\r\n]+") do
			local seed = tonumber(line)

			if seed then
				local key = string.format("%d", seed)

				if seed >= 0 and seed <= 2147483647 and not G.failed[key] and not exists(dir .. "maps2/" .. key .. ".txt") then
					return key, seed
				end
			else
				local race, tod, diff, chal, terrain = line:match("^t (%S+) (%S+) (%S+) (%S+) (%d+)$")

				if race then
					local key = "t_" .. race .. "_" .. tod .. "_" .. diff .. "_" .. chal .. "_" .. terrain

					if not G.failed[key] and not exists(dir .. "maps2/" .. key .. ".txt") then
						local s, pg = trial_seeds(race, tod, diff, chal, terrain)

						if s then
							return key, s, pg
						end

						G.failed[key] = true
					end
				end
			end
		end
	end

	local function step()
		local machine = rawget(_G, "Boot") and Boot.state_machine

		if not machine or machine.current_state_name == "game" or rawget(_G, "GeneratedLevel") == nil then
			return
		end

		local dir = root()

		if not dir then
			return
		end

		local key, seed, pg = next_request(dir)

		if not key then
			return
		end

		local ok, result = pcall(function()
			return render(generate(seed, pg))
		end)

		if not ok then
			G.failed[key] = true
			G.last_error = tostring(result)
			if rawget(_G, "HellBoxLog") then HellBoxLog("map_preview", G.last_error) end

			return
		end

		local name = dir .. "maps2/" .. key
		local f = io.open(name .. ".tmp", "wb")

		if not f then
			return
		end

		f:write(result)
		f:close()
		os.remove(name .. ".txt")
		os.rename(name .. ".tmp", name .. ".txt")
		G.made = (G.made or 0) + 1
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local now = Application.time_since_launch()

			-- 2026-11-22「挑地形」：每 0.25 秒最多拼 4 张、最多花 20 毫秒（以前 0.5 秒一张，215 张要将近两分钟）
			if now - G.last >= 0.25 then
				G.last = now

				local start = os.clock()

				for _ = 1, 4 do
					local before = G.made or 0
					local ok, err = pcall(step)

					if not ok then
						G.errors = (G.errors or 0) + 1
						G.last_error = tostring(err)
						if rawget(_G, "HellBoxLog") then HellBoxLog("map_preview", G.last_error) end

						break
					end

					if (G.made or 0) == before or os.clock() - start > 0.02 then
						break
					end
				end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
