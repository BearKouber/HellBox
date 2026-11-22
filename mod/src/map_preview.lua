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

	local function generate(seed)
		local level = GeneratedLevel()

		level:initialize(nil, seed, nil)
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

	local function next_request(dir)
		local f = io.open(dir .. "map-requests.txt", "rb")

		if not f then
			return nil
		end

		local text = f:read(4096) or ""

		f:close()

		for line in text:gmatch("[^\r\n]+") do
			local seed = tonumber(line)

			if seed and seed >= 0 and seed <= 2147483647 and not G.failed[seed]
				and not exists(dir .. "maps2/" .. string.format("%d", seed) .. ".txt") then
				return seed
			end
		end
	end

	local function step()
		local machine = rawget(_G, "Boot") and Boot.state_machine

		if not machine or machine.current_state_name == "game" or rawget(_G, "GeneratedLevel") == nil then
			return
		end

		local dir = root()
		local seed = dir and next_request(dir)

		if not seed then
			return
		end

		local ok, result = pcall(function()
			return render(generate(seed))
		end)

		if not ok then
			G.failed[seed] = true
			G.last_error = tostring(result)
			if rawget(_G, "HellBoxLog") then HellBoxLog("map_preview", G.last_error) end

			return
		end

		local name = dir .. "maps2/" .. string.format("%d", seed)
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

			if now - G.last >= 0.5 then
				G.last = now

				local ok, err = pcall(step)

				if not ok then
					G.errors = (G.errors or 0) + 1
					G.last_error = tostring(err)
					if rawget(_G, "HellBoxLog") then HellBoxLog("map_preview", G.last_error) end
				end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
