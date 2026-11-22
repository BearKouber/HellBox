-- 来自 Dive Harder Patch（Oct0pu5，github.com/Octopus058/Helldivers-Dive-Harder-Patch，0.1.1，提交 001211e）的四项，
-- 2026-11-21 HD1-038 作者同意收进 HellBox。原文件 lua/dive_harder.lua、lua/ping_hud.lua，按 MIT 授权，版权声明照抄在下面。
--   1) HUD 延迟显示：每个队友最近 N 次延迟取平均，任务里队友卡片下面写「PING: xx.xxms」；ESC 玩家列表的 Avg Ping
--      原版是单程（往返的一半），一起改成往返，和 HUD 上的数对得上（ping_hud.lua 方案 B）。
--   2) 显示隐藏任务目标：问号目标一开局就显示（dive_harder.lua hook_level）。
--   3) 好友列表自动刷新：选房切到「好友」那一下马上刷一次，房主信息不用等（ping_hud.lua hook_friends）。
--   4) 配合 QoL 的两处（SomeDoggo 的 QoL Mod 的问题，Oct0pu5 修的）：结算 / 星球奖励界面的聊天字体照 QoL 的设置；
--      QoL 的选项名不再显示成「LOC:xxx」（dive_harder.lua hook_guimanager / hook_loc 里和 QoL 有关的部分）。
-- 和原版 Dive Harder 的区别：开关是 HellBox 的（options.txt 每秒读，HellBoxOptions），每次调用时看开关，关着照原版走；
--   不带它的 MOD SETTINGS 页、战线解锁、敌人血量（HellBox 自己有）。
-- 游戏里已经装了 Dive Harder（它的代码在我们前面跑，全局 DiveHarderPatch 已经有了）就整个不装，免得同一处挂两遍。
--
-- MIT License
--
-- Copyright (c) 2026 Dive Harder Patch contributors
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.
-- 注意：这些脚本拼在一起跑，这里不能用 return（会把后面的脚本一起跳过），所以用 if / else。
if rawget(_G, "DiveHarderPatch") ~= nil then
	HellBoxDH = {yielded = true}
else
	local G = HellBoxDH or {}
	HellBoxDH = G

	local function on(key)
		local cfg = rawget(_G, "HellBoxOptions")
		return type(cfg) == "table" and cfg[key] == true
	end

	local function window_size()
		local cfg = rawget(_G, "HellBoxOptions")
		local value = type(cfg) == "table" and tonumber(cfg.ping_window)
		if value == 3 or value == 5 or value == 10 then
			return value
		end
		return 5
	end

	-- ---------------------------------------------------------------- 1) HUD 延迟显示
	-- 队友 -> 最近 N 次延迟（秒）。只采已经在游戏会话里的人：对大厅里还没连上的人调 Network.ping 会让引擎崩（原作者注）
	local samples = {}

	local function push_sample(peer, value)
		local ring = samples[peer]
		if type(ring) ~= "table" then
			ring = {}
			samples[peer] = ring
		end
		ring[#ring + 1] = value
		local limit = window_size()
		while #ring > limit do
			table.remove(ring, 1)
		end
	end

	local function sample_peers(self)
		local ok, peers = pcall(function()
			return self.session:peers()
		end)
		if not ok or type(peers) ~= "table" then
			return
		end
		local seen = {}
		for _, peer in ipairs(peers) do
			if peer ~= nil and not seen[peer] then
				seen[peer] = true
				local ok2, value = pcall(function()
					return Network.ping(peer)
				end)
				if ok2 and type(value) == "number" then
					push_sample(peer, value)
				end
			end
		end
	end

	local function average_for(peer)
		local ring = samples[peer]
		if type(ring) ~= "table" or #ring == 0 then
			return nil
		end
		local count = math.min(#ring, window_size())
		local sum = 0
		for i = #ring - count + 1, #ring do
			sum = sum + ring[i]
		end
		return sum / count
	end

	local function hook_ping()
		local cls = rawget(_G, "NetworkSessionHandler")
		if type(cls) ~= "table" or type(cls.get_average_ping) ~= "function" then
			return false
		end
		local orig_update = cls.update_pings
		local orig_get = cls.get_average_ping
		local orig_set = cls.set_calculate_ping
		if type(orig_update) == "function" then
			cls.update_pings = function(self, ...)
				local result = orig_update(self, ...)
				if on("dh_ping") then
					pcall(sample_peers, self)
				end
				return result
			end
		end
		cls.get_average_ping = function(self, peer)
			if on("dh_ping") then
				local average = average_for(peer)
				if average then
					return average
				end
			end
			return orig_get(self, peer)
		end
		if type(orig_set) == "function" then
			cls.set_calculate_ping = function(self, ...)
				samples = {}
				return orig_set(self, ...)
			end
		end
		return true
	end

	local function network_handler()
		local ok, state = pcall(function()
			return Boot.state_machine:get_current_state()
		end)
		if ok and type(state) == "table" and type(state.network_session_handler) == "table" then
			return state.network_session_handler
		end
		return nil
	end

	local function draw_ping(self, index, info)
		-- 只在任务里画（飞船上 state_name == "menu" 不画）
		if self.state_name == "menu" then
			return
		end
		if type(self.hud_info) ~= "table" or type(self.hud_info[index]) ~= "table" then
			return
		end
		local player_go = info and info.player_go
		if type(player_go) ~= "table" then
			return
		end
		-- 本机的人（自己、分屏的 2P）不画，网上的队友都画
		local ok_owned, owned = pcall(function()
			return player_go:owned()
		end)
		if ok_owned and owned then
			return
		end
		local handler = network_handler()
		if type(handler) ~= "table" then
			return
		end
		local ok_owner, owner = pcall(function()
			return player_go:owner()
		end)
		if not ok_owner then
			owner = nil
		end
		-- 有的 player_go 查不到主人，退回去查它的角色单位
		if owner == nil then
			local ok, unit = pcall(function()
				return player_go:get("avatar_unit")
			end)
			if ok and unit ~= nil then
				local ok2, unit_owner = pcall(function()
					return EntityAux.owner(unit)
				end)
				if ok2 then
					owner = unit_owner
				end
			end
		end
		if owner == nil then
			return
		end
		local ping = average_for(owner)
		if ping == nil then
			local ok, value = pcall(function()
				return handler:get_average_ping(owner)
			end)
			if ok and type(value) == "number" then
				ping = value
			end
		end
		if type(ping) ~= "number" or ping <= 0 then
			return
		end
		local gui = self.hd_gui
		if type(gui) ~= "table" or type(gui.text) ~= "function" or type(gui.move) ~= "function" then
			return
		end
		local ok_pos, base = pcall(function()
			return self:get_player_hud_pos(index)
		end)
		if not ok_pos or base == nil then
			return
		end
		-- Network.ping 给的是往返秒数，×1000 = 平常说的毫秒数；写在卡片下沿下面、左对齐
		local text = string.format("PING: %.2fms", ping * 1000)
		pcall(function()
			gui:move(Vector3(base.x, base.y, 0))
			gui:set_current_font("body")
			gui:text(text, Vector3(4, -18, 4), Color(255, 240, 210, 160))
			gui:set_current_font("body_large")
		end)
	end

	local function hook_hud()
		local cls = rawget(_G, "Hud")
		if type(cls) ~= "table" or type(cls.draw_hud) ~= "function" then
			return false
		end
		local orig = cls.draw_hud
		-- draw_hud 除了 self 还有 11 个参数，各版本不一样，原样转发
		cls.draw_hud = function(self, ...)
			local count = select("#", ...)
			local args = {...}
			local result = orig(self, unpack(args, 1, count))
			if on("dh_ping") then
				pcall(draw_ping, self, args[4], args[9])
			end
			return result
		end
		return true
	end

	-- ESC 玩家列表的「Avg Ping: xx.xxms」原版是 ×0.5×1000（单程），开着时翻倍成往返，和 HUD 一致
	local ESC_PREFIX = "Avg Ping: "
	local function esc_text(text)
		if on("dh_ping") and type(text) == "string" and text:sub(1, #ESC_PREFIX) == ESC_PREFIX then
			local value = tonumber(text:match("^Avg Ping: (%-?%d+%.?%d*)ms$"))
			if value then
				return string.format("Avg Ping: %.2fms", value * 2)
			end
		end
		return text
	end

	-- ---------------------------------------------------------------- 2) 显示隐藏任务目标
	local function hook_level()
		local lvl = rawget(_G, "Level")
		if type(lvl) ~= "table" or type(lvl.get_data) ~= "function" then
			return false
		end
		local orig = lvl.get_data
		lvl.get_data = function(...)
			if select(2, ...) == "objective_hidden_data" and on("dh_hidden") then
				return nil
			end
			return orig(...)
		end
		return true
	end

	-- ---------------------------------------------------------------- 3) 好友列表自动刷新
	local function hook_friends()
		local cls = rawget(_G, "MenuScreenCampaignMultiplayer")
		if type(cls) ~= "table" or type(cls.update) ~= "function" then
			return false
		end
		local orig = cls.update
		cls.update = function(self, ...)
			local result = orig(self, ...)
			if on("dh_friends") then
				pcall(function()
					local filter = self.filter
					if type(filter) == "table" and filter.name == "friends" then
						if not self.hb_friends_refreshed then
							self.hb_friends_refreshed = true
							if type(self.refresh_timer) == "number" then
								self.refresh_timer = -1
							end
						end
					else
						self.hb_friends_refreshed = nil
					end
				end)
			end
			return result
		end
		return true
	end

	-- ---------------------------------------------------------------- 4) 配合 QoL 的两处
	-- QoL 的选项（它放在画面 / 设置页里）在原版语言表里没有，原版显示「LOC:键名」
	local QOL_LABELS = {
		display_player_text_as_chat = "PLAYER NAMES AS CHAT FONT",
		custom_lobby_name_show = "SHOW CUSTOM LOBBY NAME",
		ps_buttons_show = "PS BUTTONS",
		override_viewport_aspect_ratio = "OVERRIDE VIEWPORT ASPECT RATIO",
		camera_shake_multiplier = "CAMERA SHAKE MULTIPLIER",
		skip_intro_video = "SKIP INTRO VIDEO",
		comm_time = "COMMENT TIME INTERVAL",
		control_interact = "INTERACT HOLD",
		menu_not_sticky = "WEAPON SWAP HOLD",
		press_cross_to_join = "ALLOW LOCAL PLAYER JOIN",
		mission_type_genocide = "RETALIATORY MISSION CHANCE",
	}

	local function hook_loc()
		local lm = rawget(_G, "LocalizationManager")
		if type(lm) ~= "table" or type(lm.string) ~= "function" then
			return false
		end
		local orig = lm.string
		lm.string = function(self, key, ...)
			if not on("dh_qol_fix") then
				return orig(self, key, ...)
			end
			if type(key) == "string" and QOL_LABELS[key] then
				return QOL_LABELS[key]
			end
			local text = orig(self, key, ...)
			-- 语言表里没有的键回来是「LOC:xxx」：改成键名大写、下划线换空格
			if type(text) == "string" and type(key) == "string" and text:sub(1, 4) == "LOC:" then
				return (key:gsub("_", " "):upper())
			end
			return text
		end
		return true
	end

	-- GuiManager：update 里把 QoL 的「名字用聊天字体」设置抄过来（结算 / 星球奖励界面原来不跟）；
	-- draw_text 里改 ESC 列表的延迟数字（1）
	local function hook_guimanager()
		local cls = rawget(_G, "GuiManager")
		if type(cls) ~= "table" or type(cls.update) ~= "function" or type(cls.draw_text) ~= "function" then
			return false
		end
		local orig_update = cls.update
		cls.update = function(self, ...)
			local result = orig_update(self, ...)
			if on("dh_qol_fix") then
				pcall(function()
					local q = Application.user_setting("qol", "display_player_text")
					if q ~= nil then
						self.display_player_text = q
					end
				end)
			end
			return result
		end
		local orig_draw = cls.draw_text
		cls.draw_text = function(self, text, ...)
			return orig_draw(self, esc_text(text), ...)
		end
		return true
	end

	-- ---------------------------------------------------------------- 挂上（类还没加载的下一帧再试，每个只挂一次）
	local HOOKS = {
		{"ping", hook_ping}, {"hud", hook_hud}, {"level", hook_level}, {"friends", hook_friends},
		{"loc", hook_loc}, {"gui", hook_guimanager},
	}
	G.hooked = G.hooked or {}

	local function tick()
		for _, item in ipairs(HOOKS) do
			if not G.hooked[item[1]] then
				local ok, done = pcall(item[2])
				if ok and done then
					G.hooked[item[1]] = true
				end
			end
		end
	end

	pcall(tick)
	local wm = rawget(_G, "WorldManager")
	if not G.wm_hooked and type(wm) == "table" and type(wm.update) == "function" then
		G.wm_hooked = true
		local orig = wm.update
		local next_check = 0
		wm.update = function(self, ...)
			local now = Application and Application.time_since_launch and Application.time_since_launch() or os.clock()
			if now >= next_check then
				next_check = now + 0.5
				pcall(tick)
			end
			return orig(self, ...)
		end
	end
end
