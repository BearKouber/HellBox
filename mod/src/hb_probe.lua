-- [hb probe] 闪退探针（2026-11-19 发行抢先版，用户要求：玩家开着 MOD 进别人房间闪退，游戏没留崩溃报告、我们的日志里也没报错，
--   查不到闪退前停在哪）。由 build.py 追加在 hb_log.lua 后面（后面的脚本可以调 HellBoxProbe 记关键步骤）。
--
-- 游戏这边一直把「现在在干什么」写到 %APPDATA%/Arrowhead/Helldivers/hellbox/logs/game-probe.txt：
--   HBPROBE1
--   session=开游戏那一刻（os.time）
--   started=开游戏的日期时间
--   beat=最后一次心跳的日期时间（每 2 秒一次；加载地图这种卡住的时候不跳，最后几步看下面的 events）
--   now=状态 | 房主 / 客机 / 没房间
--   exit=clean                正常退出时写（全局 shutdown 被调、或者菜单里点了退出 Application.quit）
--   events:
--   时:分:秒<TAB>事件         最近 40 步：状态切换（菜单 / 飞船 / 出发 / 关卡）、房主客机切换、加载地图开始 / 完成、鬼城藏灯……
-- 每次写完就关文件：游戏进程崩了，写进去的内容也已经交给系统，不会丢。
--
-- 闪退了怎么知道：
--   - HellBox 看到游戏没在运行、文件里没有 exit=clean 也没有 reported=1，就把最后几步写进 HellBox 日志，再在文件末尾补 reported=1
--     （hellbox/logbook.py 的 check_probe）。
--   - HellBox 没开着、玩家直接又开了游戏：这里开机时先看上一份，没有 exit=clean 也没报过，就自己写一条 ERROR 进 game.log
--     （HellBox「日志」页能看到），再把上一份另存成 game-probe.last-crash.txt。
-- 全部 pcall 包着，出错只是不记，不影响游戏。
do
	local G = HellBoxProbeState or {}

	HellBoxProbeState = G
	G.events = G.events or {}

	local MAX_EVENTS = 40

	local function dir()
		local appdata = os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/logs/")
	end

	local function one_line(s)
		return (tostring(s or ""):gsub("[\r\n\t]+", " "))
	end

	local function flush()
		local d = dir()

		if not d then
			return
		end

		local lines = {
			"HBPROBE1",
			"session=" .. tostring(G.session),
			"started=" .. tostring(G.started),
			"beat=" .. os.date("%Y-%m-%d %H:%M:%S"),
			"now=" .. one_line(G.now),
		}

		if G.exit then
			lines[#lines + 1] = "exit=" .. G.exit
		end

		lines[#lines + 1] = "events:"

		for _, e in ipairs(G.events) do
			lines[#lines + 1] = e
		end

		local f = io.open(d .. "game-probe.txt", "wb")

		if not f then
			return
		end

		f:write(table.concat(lines, "\n"), "\n")
		f:close()
	end

	function HellBoxProbe(event)
		pcall(function()
			G.events[#G.events + 1] = os.date("%H:%M:%S") .. "\t" .. one_line(event)

			while #G.events > MAX_EVENTS do
				table.remove(G.events, 1)
			end

			flush()
		end)
	end

	-- 开机：上一份没有正常退出、HellBox 也没报过 → 自己记一条进 game.log，上一份另存
	local function check_previous()
		local d = dir()
		local f = d and io.open(d .. "game-probe.txt", "rb")

		if not f then
			return
		end

		local text = f:read("*a") or ""

		f:close()

		if not text:match("^HBPROBE1") or text:find("\nexit=clean", 1, true) or text:find("\nreported=1", 1, true) then
			return
		end

		local started = text:match("\nstarted=([^\n]*)") or "?"
		local beat = text:match("\nbeat=([^\n]*)") or "?"
		local now = text:match("\nnow=([^\n]*)") or "?"
		local tail = {}

		for line in (text:match("\nevents:\n(.*)$") or ""):gmatch("[^\n]+") do
			tail[#tail + 1] = line:gsub("\t", " ")

			if #tail > 6 then
				table.remove(tail, 1)
			end
		end

		if rawget(_G, "HellBoxLog") then
			HellBoxLog("闪退探针", string.format("上次游戏（%s 开的）没有正常退出，可能是闪退。最后心跳 %s，当时：%s；最后几步：%s",
				started, beat, now, table.concat(tail, " → ")), "ERROR")
		end

		os.remove(d .. "game-probe.last-crash.txt")
		os.rename(d .. "game-probe.txt", d .. "game-probe.last-crash.txt")
	end

	local function role()
		local ng = rawget(_G, "NetworkGlobal")
		local lobby = type(ng) == "table" and ng.lobby

		if type(lobby) ~= "table" or not lobby.lobby or type(lobby.is_valid) ~= "function" then
			return "没房间"
		end

		local ok_v, valid = pcall(lobby.is_valid, lobby)

		if not (ok_v and valid) then
			return "没房间"
		end

		local ok, host = pcall(lobby.is_host, lobby)

		return ok and (host and "房主" or "客机") or "房间?"
	end

	local function state_now()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if not sm then
			return "boot"
		end

		local name = tostring(sm:get_current_state_name())

		if name == "game" then
			local st = sm:get_current_state()

			if type(st) == "table" then
				local extra = {}

				if st.planet_name then
					extra[#extra + 1] = "星球 " .. tostring(st.planet_name)
				end

				if st.is_training then
					extra[#extra + 1] = "训练"
				end

				if st.hotjoined_game then
					extra[#extra + 1] = "中途加入"
				end

				if #extra > 0 then
					name = name .. "（" .. table.concat(extra, "，") .. "）"
				end
			end
		end

		return name
	end

	-- 加载地图：卡在这里闪退的话，最后一步就是「开始」。GeneratedLevel 可能比这个脚本晚加载，心跳里一直补挂（挂过就跳过）
	local function hook_levels()
		local gl = rawget(_G, "GeneratedLevel")

		if type(gl) == "table" and type(rawget(gl, "spawn_levels")) == "function" and not rawget(gl, "_hb_probe_spawn") then
			local orig = gl.spawn_levels

			gl.spawn_levels = function(self, ...)
				HellBoxProbe("加载地图开始：" .. one_line(self.time_of_day) .. " " .. one_line(self.shading_environment))

				local r = { orig(self, ...) }

				HellBoxProbe("加载地图完成")

				return unpack(r)
			end
			gl._hb_probe_spawn = true
		end
	end

	local function tick()
		local t = Application.time_since_launch()

		if t - (G.last_check or -10) < 0.5 then
			return
		end

		G.last_check = t
		hook_levels()

		local now = state_now() .. " | " .. role()

		if now ~= G.now then
			G.now = now
			G.last_beat = t
			HellBoxProbe("现在：" .. now)

			return
		end

		if t - (G.last_beat or -10) >= 2 then
			G.last_beat = t
			flush()
		end
	end

	pcall(hook_levels)

	if not G.session then
		pcall(check_previous)

		G.session = os.time()
		G.started = os.date("%Y-%m-%d %H:%M:%S")

		HellBoxProbe("游戏启动，HellBox 脚本已装上")
	end

	-- 心跳 + 状态切换（WorldManager.update 菜单里、飞船上、关卡里每帧都跑）
	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, ...)
			pcall(tick)

			return orig(self, ...)
		end
		wm.update = G.wrapped
	end

	-- 正常退出：游戏关的时候调全局 shutdown；菜单里点退出走 Application.quit
	local function mark_clean(why)
		pcall(function()
			G.exit = "clean"
			HellBoxProbe("正常退出（" .. why .. "）")
		end)
	end

	local sd = rawget(_G, "shutdown")

	if type(sd) == "function" and not G.shutdown_wrapped then
		G.shutdown_wrapped = true
		rawset(_G, "shutdown", function(...)
			mark_clean("shutdown")

			return sd(...)
		end)
	end

	local app = rawget(_G, "Application")

	if type(app) == "table" and type(app.quit) == "function" and not G.quit_wrapped then
		local quit = app.quit

		G.quit_wrapped = pcall(function()
			app.quit = function(...)
				mark_clean("退出菜单")

				return quit(...)
			end
		end)
	end
end
