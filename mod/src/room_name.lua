-- [room name] 自定义房间名（2026-10-21）。由 build.py 追加到 character_state_machine 末尾（在 recap_guard 后面）。
--
-- 原版：别人房间列表里显示的名字 = 大厅数据 "name"（menu_screen_campaign_multiplayer 里 room_browser:lobby(i).name），
--   开房时由引擎填成房主的 Steam 昵称；Lua 只在房主迁移时用 NetworkRoom.set_name(UserManager:get_name()) 再写一次。
-- 这里：挂 WorldManager.update，自己是房主时把 "name" 改成 NAME；之后只在和房间里的不一样时再写（引擎 / 迁移写回昵称也算），
--   而且只在飞船上、进舱门之前写（2026-11-19 用户定，以前每 REFRESH=5 秒重写一次，见 ship_ok）。
--   NAME 开机时是 build.py 从 mod\room_name.txt 填进来的；空 = 用"我的名字"（self_name.lua），那个也空就用 Steam 昵称。
--   只有当房主时有效，别人不用装 mod。长度上限是 Steam 房间数据的 8192 字节，游戏本身不限。
--   2026-11-18 V0.97：真房间名一律写成「[HellBox · 描述] 名字」（描述由 HellBox 桌面写 room-desc.txt，见下面「真房间名」一节和
--   pages/room_desc.py），名字就是上面说的那个（不再有「不改」的情况）；去掉了 V0.94 给别人房名加本地前缀的做法。
--
-- 热改名：信箱表 G.t（每格一个 double），开关窗口（mod\room_name_live.py）在游戏内存里找魔数后往里写新名字。
--   1-4 魔数；5 VERSION；6 请求号（窗口写，每次加 1，最后写）；7 已应用的请求号（这里写回）；8 名字字节数；
--   9 起 MAX_BYTES 格：名字的 UTF-8 字节（0-255）。改布局要同步改 room_name_live.py 并把 VERSION 加 1。
--   房间名和"我的名字"都变成空 = 名字部分用 Steam 昵称。（2026-11-08 VERSION 3：MAX_BYTES 256 -> 8192）
do
	local NAME = "@ROOM_NAME@"
	local VERSION = 3
	local MAX_BYTES = 8192
	local B0 = 9
	local N = B0 + MAX_BYTES - 1
	local G = RoomNameMod or {}

	RoomNameMod = G

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("27182818.5")
		t[2] = tonumber("-577215.75")
		t[3] = tonumber("1618.03125")
		t[4] = tonumber("549755813888.375")
		t[5] = VERSION
		G.t = t
		G.name = NAME
		G.seq = 0
	end

	local t = G.t
	local timer = 0

	-- 窗口写了新请求就换名字（字节不合法就不换，只回请求号）
	local function poll_mailbox()
		local seq = t[6]

		if seq == G.seq then
			return
		end

		G.seq = seq

		local len = t[8]

		if type(len) == "number" and len >= 0 and len <= MAX_BYTES and len % 1 == 0 then
			local bytes = {}

			for i = 1, len do
				local b = t[B0 + i - 1]

				if type(b) ~= "number" or b < 0 or b > 255 or b % 1 ~= 0 then
					bytes = nil

					break
				end

				bytes[i] = string.char(b)
			end

			if bytes then
				G.name = table.concat(bytes)
				timer = 0
				G.changes = (G.changes or 0) + 1
			end
		end

		t[7] = seq
	end

	local function write_name(lobby, name)
		if lobby.backend_type == "STEAM" then
			SteamLobby.set_data(lobby.lobby, "name", name)
		elseif lobby.backend_type == "LAN" then
			LanLobby.set_data(lobby.lobby, "name", name)
		else
			return
		end

		lobby.name = name
		G.writes = (G.writes or 0) + 1
	end

	-- 现在该用的房间名：自己填的房间名，空就用"我的名字"，再空 = ""（原版）
	local function wanted()
		if G.name ~= "" then
			return G.name
		end

		local s = rawget(_G, "SelfNameMod")

		if type(s) == "table" and type(s.name) == "string" then
			return s.name
		end

		return ""
	end

	--------------------------------------------------------------------------
	-- hellbox=1 记号（2026-11-16）：房主在 Steam 房间数据多写一个键，给 HellBox 认房间用（不碰游戏自己的 data 串）。
	--   V0.94 那套「选房时在装了 HellBox 的人屏幕上给房名加前缀」2026-11-18 V0.97 去掉了：房间名本身就写成「[HellBox……] 名字」，
	--   所有人都看得到，再加本地前缀会显示两次。键还留着。
	--------------------------------------------------------------------------
	-- 2026-11-19 用户定：每个房间只写一次（以前每 30 秒重写一次）
	local function tag_host(lobby)
		if lobby.backend_type ~= "STEAM" or not SteamLobby or G.tagged == lobby.lobby then
			return
		end

		SteamLobby.set_data(lobby.lobby, "hellbox", "1")
		G.tagged = lobby.lobby
	end

	-- 2026-11-19 用户定（多人时房主卡、看别人闪现，用户怀疑和房间名每 5 秒重写有关）：房间名只在「该用的名字和房间里的
	--   不一样」时写，不再定时重写；而且只在飞船上、进舱门之前写（Boot 当前 state 是 menu，出发流程 menu_state 是自由走动
	--   或房主在星图）。倒计时、简报、选装备、出发、关卡里一律不写，改了的设置回到飞船再写。拿不到状态（离线测试）当可以写。
	local function ship_ok()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if type(sm) ~= "table" then
			return true
		end

		local ok, name = pcall(sm.get_current_state_name, sm)

		if not ok or name ~= "menu" then
			return false
		end

		local ok2, st = pcall(sm.get_current_state, sm)

		if not ok2 or type(st) ~= "table" then
			return false
		end

		local ms = st.menu_state

		return ms == nil or ms == st.MENU_STATE_INVALID or ms == st.MENU_STATE_HOST_IN_CAMPAIGN
	end

	--------------------------------------------------------------------------
	-- 真房间名「[HellBox · 描述] 名字」（2026-11-18 V0.97 第 ⑤ 步，用户定，HD1-033）
	--   描述由 HellBox 桌面拼好写在 hellbox/room-desc.txt（HBROOM1：full / short / tfull / tshort 四行，见 pages/room_desc.py），
	--   这里每 2 秒读一次。训练场（HellBoxPlay.armed / used，即真训练场设好了或正在打）用 tfull / tshort，别的时候用 full / short。
	--   没有这个文件（HellBox 桌面没开过）= 「[HellBox] 名字」。名字 = 自定义房间名 → 我的名字 → Steam 昵称。
	--   长度：整个房间名最多 MAX_NAME 字节（选房列表里一眼看全；游戏不限长度，Steam 房间数据值最多 8192 字节）。
	--   装得下用全描述；装不下换简写；还装不下截名字（按整个字，末尾「…」），描述和 [HellBox ... ] 的括号永远在。
	--   关掉 HellBox 核心 = 游戏文件还原成原版，这个脚本不在了，房间名就是游戏自己的（Steam 昵称）。
	--------------------------------------------------------------------------
	local MAX_NAME = 200
	local SEP = " \194\183 " -- 空格 + 中点 U+00B7 + 空格
	local ELLIPSIS = "\226\128\166" -- 省略号 U+2026
	local EMPTY_DESC = { full = "", short = "", tfull = "", tshort = "", order = "" }

	-- 切到最多 n 字节，不把一个字切成两半
	local function cut(str, n)
		if #str <= n then
			return str
		end

		local i = n

		while i > 0 do
			local b = str:byte(i + 1)

			if not b or b < 128 or b >= 192 then
				break
			end

			i = i - 1
		end

		return str:sub(1, i)
	end

	-- name_first（2026-11-21 HD1-038 用户要求可选）：名字在前、[HellBox …] 在后；截短规矩一样（截的是名字）
	local function compose(base, full, short, name_first)
		local function head(d)
			return d ~= "" and ("[HellBox" .. SEP .. d .. "]") or "[HellBox]"
		end

		local function join(h, b)
			if b == "" then
				return h
			end

			return name_first and (b .. " " .. h) or (h .. " " .. b)
		end

		for _, d in ipairs({ full, short }) do
			local h = head(d)

			if #h + 1 + #base <= MAX_NAME then
				return join(h, base)
			end
		end

		local h = head(short)

		if #h + 1 + #ELLIPSIS >= MAX_NAME then
			return "[HellBox]"
		end

		return join(h, cut(base, MAX_NAME - #h - 1 - #ELLIPSIS) .. ELLIPSIS)
	end

	G.compose = compose

	local function read_desc()
		local appdata = os.getenv and os.getenv("APPDATA")
		local f = appdata and io.open(appdata .. "/Arrowhead/Helldivers/hellbox/room-desc.txt", "rb")

		if not f then
			G.desc = EMPTY_DESC

			return
		end

		local text = f:read("*a") or ""

		f:close()

		if text == G.desc_text then
			return
		end

		G.desc_text = text

		local d = { full = "", short = "", tfull = "", tshort = "", order = "" }

		if text:match("^HBROOM1") then
			for line in text:gmatch("[^\r\n]+") do
				local k, v = line:match("^(%a+)=(.*)$")

				if k and d[k] then
					d[k] = (v:gsub("[%c]", " "):gsub("[%[%]]", ""))
				end
			end
		end

		G.desc = d
		timer = 0
	end

	local function training()
		local p = rawget(_G, "HellBoxPlay")

		return type(p) == "table" and (p.armed ~= nil or p.used ~= nil)
	end

	-- 名字部分：自己填的房间名 → "我的名字"（self_name.lua）→ Steam 昵称
	local function base_name()
		if G.name ~= "" then
			return G.name
		end

		local s = rawget(_G, "SelfNameMod")

		if type(s) == "table" and type(s.name) == "string" and s.name ~= "" then
			return s.name
		end

		local ok, nick = pcall(function() return UserManager:get_name() end)

		return ok and type(nick) == "string" and nick or ""
	end

	-- 现在该用的整个房间名
	local function wanted()
		local d = G.desc or EMPTY_DESC

		local name_first = d.order == "name"

		if training() then
			return compose(base_name(), d.tfull, d.tshort, name_first)
		end

		return compose(base_name(), d.full, d.short, name_first)
	end

	local desc_timer = 0

	--------------------------------------------------------------------------
	-- 回报（2026-11-18 V0.97 整理第 2 批）：把「我现在是房主 / 客机 / 没房间」和房主时实际写进房间的完整名字写给 HellBox 桌面显示
	--   hellbox/room-status.txt：HBROOMST1 / role=host|guest|none / name=整个房间名（只有 host 有，没有换行）/ t=写的时间（os.time）。
	--   内容变了马上写，没变也每 10 秒写一次（先写 .tmp 再改名；写失败下次再试）；HellBox 只在游戏开着时读，
	--   文件的 t 超过 30 秒没刷新就当没有回报（脚本被换回原版 / 游戏崩了），「恢复原版」也会把它删掉。
	--------------------------------------------------------------------------
	local NL = string.char(10)
	local REPORT_EVERY = 10

	-- 写好的临时文件换成正式文件，成功才返回 true。Windows 的 os.rename 不能盖掉已有文件：先直接改名；不行就把旧的挪成 .bak、
	-- 新的改过去，新的改不过去再把旧的挪回来（失败时尽量留着上一份）。
	local function swap_in(tmp, final)
		if os.rename(tmp, final) then
			return true
		end

		local bak = final .. ".bak"

		os.remove(bak)

		local had = os.rename(final, bak)

		if os.rename(tmp, final) then
			os.remove(bak)

			return true
		end

		if had then
			os.rename(bak, final)
		end

		os.remove(tmp)

		return false
	end

	local function report(role, name)
		local appdata = os.getenv and os.getenv("APPDATA")

		if not appdata then
			return
		end

		local clean = ((name or ""):gsub("%c", " "))
		local body = "HBROOMST1" .. NL .. "role=" .. role .. NL .. "name=" .. clean .. NL
		local now = os.time()

		-- 内容没变也每 REPORT_EVERY 秒重写一次（带时间 t=）：HellBox 看到文件太旧就当游戏没在回报（脚本被换回原版 / 游戏崩了）
		if body == G.status_text and now - (G.status_at or 0) < REPORT_EVERY then
			return
		end

		local text = body .. "t=" .. string.format("%d", now) .. NL

		local d = appdata .. "/Arrowhead/Helldivers/hellbox/room-status"
		local f = io.open(d .. ".tmp", "wb")

		if not f then
			return
		end

		local okw = f:write(text)
		local okc = f:close()

		-- 写、关、改名全成功才记「已写」；失败下次再试
		if okw and okc and swap_in(d .. ".tmp", d .. ".txt") then
			G.status_text = body
			G.status_at = now
			G.reports = (G.reports or 0) + 1
		else
			os.remove(d .. ".tmp")
		end
	end

	local function enforce(dt)
		poll_mailbox()

		local lobby = rawget(_G, "NetworkGlobal") and NetworkGlobal.lobby

		if type(lobby) ~= "table" or not lobby.lobby or not lobby.is_valid or not lobby:is_valid() then
			timer = 0
			pcall(report, "none")

			return
		end

		if not lobby:is_host() then
			timer = 0
			pcall(report, "guest")

			return
		end

		pcall(tag_host, lobby)

		-- 进舱门之后（倒计时 / 简报 / 选装备 / 出发 / 关卡里）：不读描述、不改名，只回报现在的名字
		if not ship_ok() then
			pcall(report, "host", lobby.name)

			return
		end

		desc_timer = desc_timer - (dt or 0)

		if desc_timer <= 0 or not G.desc then
			desc_timer = 2
			pcall(read_desc)
		end

		local name = wanted()

		-- 只在不一样时写：自己改了名字 / 描述（玩法设置）变了 / 引擎（房主迁移）把名字写回了昵称
		if lobby.name ~= name then
			write_name(lobby, name)
		end

		pcall(report, "host", lobby.name)
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local ok, err = pcall(enforce, dt)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = err
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
