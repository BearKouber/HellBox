-- [self name] 自定义自己（主手柄）的名字（2026-11-08）。由 build.py 追加到 character_state_machine 末尾（在 room_name 后面、p2_name 前面）。
--
-- 原版：SteamManager.get_name(pad) 主手柄（或不传 pad）返回 Steam 昵称，其他本地手柄返回 "Steam昵称 #手柄号"（UserManager 就是这张表）。
--   出生 / 进飞船时用它写 player_go 的 "name"（头顶、HUD、结算），进别人房间时也把它发给房主，所以联机的人看到的是这个名字。
-- 这里：包一层 get_name，主手柄返回 NAME；其他手柄原版的 "Steam昵称 #手柄号" 换成 "NAME #手柄号"。
--   p2_name.lua 包在这层外面，设了 2P 名字时 2P 照样用 2P 名字。房间名留空时 room_name.lua 也用 NAME 当房间名。
--   NAME 开机时是 build.py 从 mod\self_name.txt 填进来的；空 = 原版行为。
--   游戏的名字字段只存 51 字节（汉字 3 字节 = 17 个字），这里按整字切到 51 字节以内，别人看到的也是这么长。
--
-- 热改名：信箱表 G.t，布局和 room_name.lua 一样（只是魔数不同），窗口用 mod\room_name_live.py 写。
--   1-4 魔数；5 VERSION；6 请求号；7 已应用的请求号；8 名字字节数；9 起 MAX_BYTES 格：名字的 UTF-8 字节。
--   收到新名字后，当前状态里自己本机的角色（名字是这层发出去过的）改成新名字，再清掉 HUD 缓存的 p.name。
do
	local NAME = "@SELF_NAME@"
	local VERSION = 3
	local MAX_BYTES = 8192
	local B0 = 9
	local N = B0 + MAX_BYTES - 1
	local G = SelfNameMod or {}

	SelfNameMod = G

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("16777216.5")
		t[2] = tonumber("-299792.375")
		t[3] = tonumber("3141.5625")
		t[4] = tonumber("17179869184.25")
		t[5] = VERSION
		G.t = t
		G.name = NAME
		G.seq = 0
		G.issued = {} -- 这层返回过的名字 / 换掉的原名 -> true（热改名时靠它认出自己的角色）
	end

	local t = G.t
	local sm = rawget(_G, "SteamManager")

	-- player_go 的名字字段游戏只存 51 字节（2026-11-08 实测），切到这以内（含后缀），不切半个汉字；
	-- 带后缀的不切的话 "名字 #2" 会被游戏切回 "名字"，和主手柄重名
	local NAME_BYTES = 51

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

	-- 2026-11-13：手柄玩家当 1P。原版谁在标题画面按确认键谁就是主手柄（名字不带 " #手柄号"）；
	--   从 HellBox 直接进训练关会跳过标题画面，游戏默认键鼠是主手柄，用手柄玩的人就成了 "名字 #1"。
	--   这里：标题画面没选过主手柄、本机还没有别的本地玩家时，第一个来要名字的手柄算 1P（G.primary），名字不带编号。
	--   p2_name.lua 用 SelfNameMod.primary 认 1P，AI 的 2P 照样排 2P。
	local function local_players()
		local boot = rawget(_G, "Boot")
		local machine = type(boot) == "table" and boot.state_machine
		local state = machine and machine:get_current_state()
		local players = type(state) == "table" and state.players
		local out = {}

		if type(players) == "table" then
			for _, p in pairs(players) do
				if type(p) == "table" and type(p.pad_number) == "number" then
					local go = p.player_go
					local mine = true

					if go and type(go.owned) == "function" then
						local ok, m = pcall(go.owned, go)
						mine = not ok or m
					end

					if mine then
						out[p.pad_number] = true
					end
				end
			end
		end

		return out
	end

	local function effective_main(pad)
		local gs = rawget(_G, "GameSettings")
		local mp = main_pad()

		if not gs or gs.main_pad_number ~= nil then
			G.primary = nil -- 标题画面选过主手柄：照原版

			return mp
		end

		if G.primary ~= nil or type(pad) ~= "number" or pad == mp then
			return G.primary or mp
		end

		-- 自用版装了 AI 陪玩：AI 的虚拟手柄可能比人先出场（考场里她常常一个人），会被错认成 1P，所以不认
		if rawget(_G, "AIBridge") then
			return mp
		end

		for other in pairs(local_players()) do
			if other ~= pad then
				return mp -- 已经有别的本地玩家（键鼠或先进来的手柄），这个手柄不算 1P
			end
		end

		G.primary = pad

		return pad
	end

	G.effective_main = effective_main

	if type(sm) == "table" and type(sm.get_name) == "function" and sm.get_name ~= G.wrapped_get_name then
		local orig = sm.get_name

		G.orig_get_name = orig
		G.wrapped_get_name = function(self, pad, ...)
			local name = orig(self, pad, ...)
			local ok, mp = pcall(effective_main, pad)

			if not ok then
				return name
			end

			if pad == nil or pad == mp then
				G.issued[name] = true

				if pad ~= nil and pad ~= main_pad() then
					name = orig(self, nil) -- 被当成 1P 的手柄：去掉原版加的 " #手柄号"
					G.issued[name] = true
				end

				if G.name ~= "" then
					name = fit(G.name)
					G.issued[name] = true
				end
			elseif type(pad) == "number" and type(name) == "string" then
				local nick = orig(self, nil)

				if type(nick) == "string" and name == string.format("%s #%d", nick, pad) then
					G.issued[name] = true

					if G.name ~= "" then
						name = fit(G.name, string.format(" #%d", pad))
						G.issued[name] = true
					end
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

	local function owned(go)
		if type(go.owned) ~= "function" then
			return true
		end

		local ok, mine = pcall(go.owned, go)

		return not ok or mine
	end

	-- 把当前状态里自己本机角色的名字换成现在该叫的名字（走完整的 get_name，2P 名字那层也算上）
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

			if go and type(pad) == "number" and go:exists() and owned(go) then
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
				G.name = table.concat(bytes)
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
