-- [hellbox self bright] 本机潜兵调亮（2026-11-26 用户要）。
-- 用户：「在显示里面加一个潜兵自己（本机玩家）的高亮显示……默认显示所有本机的玩家（考虑多手柄），
--   然后这个显示效果可以是增加明亮度（但是不是发光效果）……做一个条，可以拖动改变明亮度，如果可以热修改就最好了」
--
-- 设置在 hop.txt（hellbox_hop.lua 每秒读，这里看 HellBoxHop.config）：self_bright（开关）、self_bright_percent（5～200，2026-11-27 用户把上限从 100 改成 200）。
-- 只在自己电脑上画：别人看到的还是原版，不传任何东西。
--
-- 第一版写 diffuse_rgb，实测没效果（用户：「调亮了看着跟不调一个效果」）。拆了盔甲材质才知道：盔甲用的着色器
--   根本没有 diffuse_rgb（只有一套备用着色器有），能调的只有 fresnel_intensity / fresnel_power（边缘反光）、
--   specular / glossiness（高光）、normal_intensity。用户选「边缘反光加强」（2026-11-26）。
-- 做法：本机每个潜兵的盔甲部件（身体、头盔、披风、重甲、全地形靴，customization 组件的 *_unit）所有材质写
--   fresnel_power = POWER（越小反光铺得越开）、fresnel_intensity = 按百分比（越大越亮）。角色本体不动（没法还原）。
--   原版每块材质的值都不一样（强度 0.5～20、范围 1～10），游戏只能写不能读，所以关掉时不写回，
--   而是让 customization 组件把部件重新生成一遍（清掉 last_*，下一帧原版自己换新部件 = 原版材质）。
-- 换装、死了重生会换新的部件：每 0.25 秒看一次，新部件补上。全部 pcall 包着，哪一步不行就是不亮，不影响游戏。
do
	local G = HellBoxSelfBright or {}

	HellBoxSelfBright = G
	G.done = G.done or setmetatable({}, { __mode = "k" }) -- 部件单位 -> 已经写进去的强度
	G.avatars = G.avatars or setmetatable({}, { __mode = "k" }) -- 调过的潜兵（关掉时让它重建部件）

	local POWER = 1 -- 原版多在 2～10；1 = 反光从边缘铺到大半个面
	local MIN_I, MAX_I = 2, 20 -- 5% ≈ 2.9，30% = 7.4，100% = 20（原版最亮的部件也是 20），200% = 38（照同一条线往上延）
	local PARTS = { "heavy_armor", "all_terrain_boots", "helmet", "cape", "body" }
	local STEP = 0.25
	local logged = {}

	local function log(text)
		if rawget(_G, "HellBoxLog") then
			pcall(HellBoxLog, "self_bright", text)
		end
	end

	local function config()
		local hop = rawget(_G, "HellBoxHop")
		return hop and hop.config or {}
	end

	local function current_state()
		local m = rawget(_G, "Boot") and Boot.state_machine
		local name = m and m.current_state_name

		if name == "game" or name == "menu" then
			return m.state, name
		end
	end

	-- 本机所有潜兵（键盘 + 手柄都算）
	local function my_avatars(state)
		local out = {}

		for _, player in ipairs(state and state.players or {}) do
			local go = player.player_go
			local ok, unit = pcall(function()
				return go and go:exists() and go:owned() and go:has("avatar_unit") and go:get("avatar_unit")
			end)

			if ok and unit and Unit.alive(unit) then
				out[#out + 1] = unit
			end
		end

		return out
	end

	local function custom_state(avatar)
		local ok, cs = pcall(EntityAux.state, avatar, "customization")

		return ok and type(cs) == "table" and cs or nil
	end

	local function parts(avatar)
		local out = {}
		local cs = custom_state(avatar)

		if cs then
			for _, name in ipairs(PARTS) do
				local u = cs[name .. "_unit"]

				if u and Unit.alive(u) then
					out[#out + 1] = u
				end
			end
		end

		return out
	end

	-- 给一个单位的所有材质写边缘反光，返回写成功几块（没有这个参数的材质引擎直接忽略）
	local function paint(unit, intensity)
		local n = 0

		for i = 1, Unit.num_meshes(unit) do
			local mesh = Unit.mesh(unit, i - 1)

			for j = 1, Mesh.num_materials(mesh) do
				local mat = Mesh.material(mesh, j - 1)

				if pcall(Material.set_scalar, mat, "fresnel_power", POWER) and pcall(Material.set_scalar, mat, "fresnel_intensity", intensity) then
					n = n + 1
				end
			end
		end

		return n
	end

	-- 让原版把这个潜兵的盔甲部件重新生成（= 回到原版材质）。可见性也让原版重新套一遍（倒地 / 在运兵舱里时新部件不能露出来）。
	local function rebuild(avatar)
		local cs = Unit.alive(avatar) and custom_state(avatar)

		if not cs then
			return false
		end

		for _, name in ipairs(PARTS) do
			if cs[name .. "_unit"] ~= nil then
				cs["last_" .. name] = -1
			end
		end

		cs.last_visible = nil

		return true
	end

	local function restore_all()
		local n = 0

		for avatar in pairs(G.avatars) do
			local ok, rebuilt = pcall(rebuild, avatar)

			if ok and rebuilt then
				n = n + 1
			end

			G.avatars[avatar] = nil
		end

		for unit in pairs(G.done) do
			G.done[unit] = nil
		end

		if n > 0 then
			log(string.format("self bright off: rebuilt armor of %d helldivers", n))
		end
	end

	local next_t = 0

	local function update()
		local t = Application.time_since_launch()

		if t < next_t then
			return
		end

		next_t = t + STEP

		local state, name = current_state()
		local c = config()
		local on = c.self_bright == "1"
		local pct = math.max(0, math.min(200, tonumber(c.self_bright_percent) or 30))

		if not state or not on or pct <= 0 then
			if next(G.avatars) or next(G.done) then
				restore_all()
			end

			return
		end

		local k = MIN_I + pct / 100 * (MAX_I - MIN_I)
		local units, mats = 0, 0

		for _, avatar in ipairs(my_avatars(state)) do
			for _, u in ipairs(parts(avatar)) do
				if G.done[u] ~= k then
					local ok, n = pcall(paint, u, k)

					G.done[u] = k
					G.avatars[avatar] = true
					units = units + 1
					mats = mats + (ok and n or 0)
				end
			end
		end

		if units > 0 and not logged[name] then
			logged[name] = true
			log(string.format("self bright on in %s: %d parts, %d materials, fresnel %.1f / power %.1f", name, units, mats, k, POWER))
		end
	end

	G.update = update
	G.restore_all = restore_all

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_hb_self_bright") then
		local orig = wm.update

		wm.update = function(self, ...)
			local r = { orig(self, ...) }
			local ok, problem = pcall(G.update)

			if not ok and not G.failed then
				G.failed = true
				log("self bright error: " .. tostring(problem))
			end

			return unpack(r)
		end
		rawset(wm, "_hb_self_bright", true)
	end
end
