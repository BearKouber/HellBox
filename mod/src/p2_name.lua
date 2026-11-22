-- [p2 name] 自定义本地 2P / 3P / 4P 名字（2026-10-22；2026-11-08 起 3P、4P 也能单独改）。由 build.py 追加到 character_state_machine 末尾
--   （在 self_name 后面：这层包在 self_name 那层外面）。
--
-- 原版：SteamManager.get_name(pad) 对不是主手柄的本地手柄返回 "Steam昵称 #手柄号"（UserManager 就是 SteamManager 这张表）。
--   出生 / 进飞船时游戏用它写 player_go 的 "name"（state_menu / state_mission_start / state_game），头顶、HUD、结算都读这个，
--   而且 player_go 会同步给联机的其他人，所以别人看到的也是这个名字。
--   player_go 的名字字段游戏只存 51 字节（2026-11-08 用户实测；汉字 3 字节 = 17 个字），多的被切掉，别人收到的也是切短的。
-- 这里：包一层 get_name，副手柄按第一次出现的先后排成 2P、3P、4P，各用 NAMES[1..3]；没填的 = 原版（设了"我的名字"就是 "我的名字 #手柄号"）。
--   名字不能重复（原版有几处按名字认人）：和主手柄或排在前面的副手柄重名时，后面加 " #手柄号"。
--   超过 51 字节的按整字切短（不留半个汉字）。NAMES 开机时是 build.py 从 mod\p2_name.txt / p3_name.txt / p4_name.txt 填进来的。
--
-- 热改名：信箱表 G.t，布局和 room_name.lua 一样（只是魔数不同），窗口用 mod\room_name_live.py 写。
--   1-4 魔数；5 VERSION；6 请求号；7 已应用的请求号；8 名字字节数；9 起 MAX_BYTES 格：UTF-8 字节。
--   内容是 "2P名字\n3P名字\n4P名字"；只有一行（旧窗口）= 只改 2P，3P、4P 不变。
--   收到新名字后，当前状态（飞船 / 出发 / 任务）里名字是这层发出去的旧名字的 player_go 改成新名字，
--   再清掉 HUD 缓存的 p.name。只改名字对得上的，别人的角色不会碰。
do
	local NAMES = {
		"@P2_NAME@",
		"@P3_NAME@",
		"@P4_NAME@"
	}
	local VERSION = 3 -- 2026-11-08：MAX_BYTES 256 -> 8192
	local MAX_BYTES = 8192
	local NAME_BYTES = 51
	local B0 = 9
	local N = B0 + MAX_BYTES - 1
	local G = P2NameMod or {}

	P2NameMod = G

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("31415926.5")
		t[2] = tonumber("-141421.25")
		t[3] = tonumber("2236.0625")
		t[4] = tonumber("274877906944.625")
		t[5] = VERSION
		G.t = t
		G.names = NAMES
		G.seq = 0
		G.slots = {} -- 手柄号 -> 第几个副手柄（1 = 2P）
		G.nslots = 0
		G.issued = {} -- 发出去过的名字 -> true（热改名时靠它认出自己的副手柄角色）
	end

	local t = G.t
	local sm = rawget(_G, "SteamManager")

	-- 切到 NAME_BYTES 字节以内（含后缀），不切半个汉字
	local function fit(s, suffix)
		suffix = suffix or ""

		local room = NAME_BYTES - #suffix

		if #s > room then
			local cut = room

			while cut > 0 do
				local b = s:byte(cut + 1)

				if b < 128 or b >= 192 then
					break
				end

				cut = cut - 1
			end

			s = s:sub(1, cut)
		end

		return s .. suffix
	end

	local function main_pad()
		local gs = rawget(_G, "GameSettings")

		return gs and gs.get_main_pad_number and gs.get_main_pad_number()
	end

	local function custom_name(self, pad, mp, orig)
		local slot = G.slots[pad]

		if not slot then
			G.nslots = G.nslots + 1
			slot = G.nslots
			G.slots[pad] = slot
		end

		local name = G.names[slot]

		if type(name) ~= "string" or name == "" then
			return nil
		end

		name = fit(name)

		local dup = name == orig(self, mp)

		for s = 1, slot - 1 do
			if type(G.names[s]) == "string" and G.names[s] ~= "" and fit(G.names[s]) == name then
				dup = true
			end
		end

		if dup then
			name = fit(name, string.format(" #%d", pad))
		end

		return name
	end

	if type(sm) == "table" and type(sm.get_name) == "function" and sm.get_name ~= G.wrapped_get_name then
		local orig = sm.get_name

		G.orig_get_name = orig
		G.wrapped_get_name = function(self, pad, ...)
			local name = orig(self, pad, ...)

			if pad ~= nil and type(pad) == "number" then
				-- 1P 用 self_name.lua 认的（手柄玩家跳过标题画面时，主手柄原版会错当成键鼠）
				local sn = rawget(_G, "SelfNameMod")
				local ok, mp = pcall(function()
					return sn and sn.effective_main and sn.effective_main(pad) or main_pad()
				end)

				if ok and mp ~= nil and pad ~= mp then
					local ok2, custom = pcall(custom_name, self, pad, mp, orig)

					if ok2 and custom then
						name = custom
					end

					G.issued[name] = true
				end
			end

			return name
		end
		sm.get_name = G.wrapped_get_name

		local um = rawget(_G, "UserManager")

		if type(um) == "table" and um ~= sm and um.get_name == orig then
			um.get_name = G.wrapped_get_name
		end
	end

	-- 把当前状态里自己副手柄角色的名字换成现在该叫的名字
	local function rename_live()
		local boot = rawget(_G, "Boot")
		local machine = type(boot) == "table" and boot.state_machine
		local state = machine and machine:get_current_state()
		local players = type(state) == "table" and state.players
		local um = rawget(_G, "UserManager") or sm

		if type(players) ~= "table" or not um then
			return
		end

		for _, p in pairs(players) do
			local go = type(p) == "table" and p.player_go
			local pad = type(p) == "table" and p.pad_number

			if go and type(pad) == "number" and go:exists() then
				local cur = go:get("name")

				if G.issued[cur] then
					local new = um:get_name(pad)

					if new ~= cur then
						go:set("name", new)
						p.name = nil
						G.renames = (G.renames or 0) + 1
					end
				end
			end
		end
	end

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
				local text = table.concat(bytes)
				local names = {}

				for i = 1, 3 do
					names[i] = G.names[i]
				end

				local i = 1

				for line in (text .. "\n"):gmatch("([^\n]*)\n") do
					if i <= 3 then
						names[i] = line
					end

					i = i + 1
				end

				G.names = names
				G.changes = (G.changes or 0) + 1

				local ok, err = pcall(rename_live)

				if not ok then
					G.errors = (G.errors or 0) + 1
					G.last_error = err
				end
			end
		end

		t[7] = seq
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local ok, err = pcall(poll_mailbox)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = err
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
