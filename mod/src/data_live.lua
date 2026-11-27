-- [data live] HellBox「数据修改」页的游戏这边（2026-11-14，V0.91）。由 build.py 追加到 character_state_machine 末尾，
-- 要在 spawn_rules.lua、enemy_params.lua 后面（用它们放出来的 SpawnRulesMod.apply / EnemyParamsMod.apply）。
--
-- HellBox 把右边「当前对局数据」里放的块写成一个文件，这里每秒读一次，内容变了就交给对应的模块：
--   %APPDATA%/Arrowhead/Helldivers/hellbox/data-live.txt，一行一条：
--     HBDATA1
--     seq=数字                     HellBox 每写一次加 1
--     params=common=...;set=...    怪物属性（格式见 enemy_params.lua；reset = 原版）
--     spawn.bugs=...               出怪逻辑，三个阵营各一份（格式见 spawn_rules.lua；reset = 原版）
--     spawn.cyborgs=...
--     spawn.illuminates=...
--     player=god=heal;common=...   潜兵（格式见 player_params.lua；2026-11-15）
--   出怪按当前地图的阵营挑那一份；不知道阵营（菜单里）时先不动，进了地图知道阵营再套。
--   所以 HellBox 开着改 = 下一秒生效；HellBox 关着 = 全部按原版（2026-11-25 用户定，以前是照样套上），再打开就套回去。
-- 处理结果写回 data-live-ack.txt（HellBox 用来显示「游戏已收到」）：
--     seq=收到的数字 \n where=game|menu|boot \n race=... \n params=结果 \n spawn=结果
do
	local G = HellBoxDataLive or {}
	local STRAT_CATS = { "blue", "red", "green", "vehicle", "yellow" }

	HellBoxDataLive = G
	G.last = G.last or -100

	local function dir()
		local appdata = os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/")
	end

	local function read_file(path)
		local f = io.open(path, "rb")

		if not f then
			return nil
		end

		local text = f:read("*a")

		f:close()

		return text
	end

	local function parse(text)
		if type(text) ~= "string" or not text:match("^HBDATA1") then
			return nil
		end

		local out = {}

		for line in text:gmatch("[^\r\n]+") do
			local k, v = line:match("^([%w_%.]+)=(.*)$")

			if k then
				out[k] = v
			end
		end

		return out
	end

	local function where()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		return sm and sm:get_current_state_name() or "boot"
	end

	local function clean(s)
		return (tostring(s or ""):gsub("[%c]", " "))
	end

	local function write_ack(d, data)
		local lines = {
			"seq=" .. clean(data.seq),
			"where=" .. clean(where()),
			"race=" .. clean(G.race_now),
			-- 2026-11-18 V0.96：在别人房间里（客机）出怪和怪物属性不生效，HellBox 拿它提示
			--   2026-11-19：武器 / 战备 / 潜兵也一样（上面 is_guest）
			"guest=" .. ((G.guest or (type(rawget(_G, "EnemyParamsMod")) == "table" and EnemyParamsMod.guest)) and "1" or "0"),
			"off=" .. (G.off and "1" or "0"),
			"params=" .. clean(G.params_res),
			"spawn=" .. clean(G.spawn_res),
			"weapon=" .. clean(G.weapon_res),
			"player=" .. clean(G.player_res),
		}

		for _, cat in ipairs(STRAT_CATS) do
			lines[#lines + 1] = "strat." .. cat .. "=" .. clean((G.strat_res or {})[cat])
		end

		lines[#lines + 1] = ""

		local text = table.concat(lines, "\n")

		if text == G.ack_text then
			return
		end

		local tmp = d .. "data-live-ack.tmp"
		local f = io.open(tmp, "wb")

		if not f then
			return
		end

		f:write(text)
		f:close()
		os.remove(d .. "data-live-ack.txt")
		os.rename(tmp, d .. "data-live-ack.txt")
		G.ack_text = text
	end

	-- 2026-11-19 发行抢先版 用户定：开着 MOD 进别人的房间（客机）不带我们的数据——武器、战备、潜兵也和怪物属性 / 出怪
	--   （V0.96 起客机就不生效）一样：客机时全部按原版（reset），回到自己当房主 / 单机再套上。功能（丢装备、换弹不滑……）照常。
	--   StateGame.is_server 游戏按 lobby:is_host() 填，单机 / 本机分屏也是房主。
	-- 2026-11-20 修：以前只在关卡里（state game）才算客机，结算画面、飞船、出发界面一律当房主 → 客机打完一局在结算画面就把
	--   数据套回去，下次进别人房间的出发界面也是带着我们的数据（QiQi 日志 00:01:02「回到自己当房主」时其实还是客机）。
	--   现在：关卡里照旧看 is_server；关卡外看房间（NetworkGlobal.lobby 有效、自己不是房主 = 客机；没房间 = 不算）。
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

	local function step()
		local d = dir()

		if not d then
			return
		end

		local data = parse(read_file(d .. "data-live.txt"))

		if not data then
			return
		end

		local guest = is_guest()

		if guest ~= (G.guest or false) then
			G.guest = guest

			if rawget(_G, "HellBoxLog") then
				HellBoxLog("data_live", guest and "进了别人的房间：武器 / 战备 / 潜兵数据先按原版" or "回到自己当房主：数据重新套上", "INFO")
			end
		end

		-- 2026-11-25 用户定：HellBox 关了（hellbox_alive.lua 心跳过期）= 这一页全部按原版，下面每一项都走 reset；再打开就套回去
		local alive = rawget(_G, "HellBoxAlive")

		G.off = type(alive) == "table" and type(alive.off) == "function" and alive.off() or false

		if G.off then
			data = { seq = data.seq }
		end

		if guest then
			data.weapon, data.player = "reset", "reset"

			for _, cat in ipairs(STRAT_CATS) do
				data["strat." .. cat] = "reset"
			end
		end

		-- 怪物属性：和上次套的不一样才套
		local params = rawget(_G, "EnemyParamsMod")
		local pcmd = data.params or "reset"

		if params and type(params.apply) == "function" and pcmd ~= G.params_cmd then
			local ok, res = pcall(params.apply, pcmd)

			G.params_cmd = pcmd
			G.params_res = ok and res or ("err:" .. tostring(res))
		end

		-- 武器属性（weapon_params.lua；格式见那边，reset = 原版）
		local weapon = rawget(_G, "WeaponParamsMod")
		local wcmd = data.weapon or "reset"

		if weapon and type(weapon.apply) == "function" and wcmd ~= G.weapon_cmd then
			local ok, res = pcall(weapon.apply, wcmd)

			G.weapon_cmd = wcmd
			G.weapon_res = ok and res or ("err:" .. tostring(res))
		end

		-- 潜兵（player_params.lua；2026-11-15）：血量、速度这些倍数和两种无敌
		local player = rawget(_G, "PlayerParamsMod")
		local pl = data.player or "reset"

		if player and type(player.apply) == "function" and pl ~= G.player_cmd then
			local ok, res = pcall(player.apply, pl)

			G.player_cmd = pl
			G.player_res = ok and res or ("err:" .. tostring(res))
		end

		-- 出怪：按当前阵营挑一份；阵营不知道就先不动
		local spawn = rawget(_G, "SpawnRulesMod")

		if spawn and type(spawn.apply) == "function" and type(spawn.race) == "function" then
			local ok, race = pcall(spawn.race)

			race = ok and race or nil

			if race then
				G.race_now = race

				local scmd = data["spawn." .. race] or "reset"
				local key = race .. "|" .. scmd

				if key ~= G.spawn_key then
					local ok2, res = pcall(spawn.apply, scmd)

					G.spawn_key = key
					G.spawn_res = ok2 and res or ("err:" .. tostring(res))
				end
			end
		end

		-- 战备属性：五类各一条（strat.blue= …），和上次套的不一样才套（StratParamsMod 在 strat_params.lua）
		local strat = rawget(_G, "StratParamsMod")

		if strat and type(strat.apply) == "function" then
			G.strat_cmd = G.strat_cmd or {}
			G.strat_res = G.strat_res or {}

			for _, cat in ipairs(STRAT_CATS) do
				local scmd = data["strat." .. cat] or "reset"

				if scmd ~= G.strat_cmd[cat] then
					local ok, res = pcall(strat.apply, cat, scmd)

					G.strat_cmd[cat] = scmd
					G.strat_res[cat] = ok and res or ("err:" .. tostring(res))
				end
			end
		end

		write_ack(d, data)
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local now = Application.time_since_launch()

			if now - G.last >= 1 then
				G.last = now

				local ok, err = pcall(step)

				if not ok then
					G.errors = (G.errors or 0) + 1
					G.last_error = tostring(err)
					if rawget(_G, "HellBoxLog") then HellBoxLog("data_live", G.last_error) end
				end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
