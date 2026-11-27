-- [hellbox 8p] 8 人房间（HD1-039，2026-11-26 用户定）。由 build.py 追加到 character_state_machine 末尾。
-- 只有「多人」页开关打开时才生效（编译时填 "@HELLBOX_8P@"）；那时 eight_players.py 也把原版脚本里玩家数的 4 改成了 8。
--
-- 规则（用户定）：
-- ① 房间里有原版玩家（没开 8 人模式的）就按 4 人房：总人数到 4 就满；全是开了 8 人模式的才能进到 8 人。
--    原版游戏只有 4 个位置，房间里一出现第 5 号玩家，原版玩家的游戏就会闪退；所以原版玩家进门还要求 5～8 号位置都空着。
--    怎么认：开了 8 人模式的玩家申请加入时，在 engine_hash（原版房主只写日志、不检查）后面带暗号 |hb8。
--    房主收到申请（rpc_on_join_request）、本地手柄加入（rpc_add_local_player_request，房主自己的手柄也走这个）时按上面规则拦，
--    拦下的照原版回「房间已满」。认不出的玩家一律当原版。
-- ② 救援一次最多复活 4 个人（用户：人多了相当于加一点难度）：救援消息 rpc_on_respawn 的名单只有 4 格，
--    先救死得早的，多出来的人等下一次救援（下一次会重新收集死人）。
-- ③ 第 5～8 人：补 4 种颜色和 4 个默认名字；面板三种摆法（「多人」页选）：原来那排正上方第二排 / 8 栏缩小排一排 / 只看自己（开地图才看别人）。
-- ④ 装备界面只有 4 栏：有人在 5～8 号时，每台电脑先画自己的栏（本机 2P 也算），再按顺序补满 4 栏。
--    原版装备界面只给画出来的栏同步选择，不这么排的话第 5～8 号玩家选的装备发不出去。
-- 这些规则和 HellBox 开没开着无关（不看 hellbox_alive）：原版脚本已经改成 8 人，规则不在就会闪退。
do
	local G = HellBox8P or {}

	HellBox8P = G
	G.on = "@HELLBOX_8P@" == "1"

	if G.on then
		local SIG = "|hb8"
		local OLD_MAX = 4 -- 原版游戏的位置数
		local ROW_GAP = 16 -- 【暂定】两排面板之间的空隙（设计尺寸 1280×720 下的像素），等实机截图再调

		-- 【用户 2026-11-26 认可】第 5～8 人：红、白、青、粉（饱和度照原版 4 色压低）
		local COLORS = {
			{ 255, 196, 72, 60 },
			{ 255, 214, 214, 214 },
			{ 255, 64, 172, 190 },
			{ 255, 212, 112, 156 }
		}
		local NAMES = { "E. Eriksson", "F. Moreau", "G. Tanaka", "H. Novak" }

		G.peers = G.peers or {} -- 房主记：peer_id -> true（开了 8 人模式）/ false（原版）

		local function log(msg)
			if rawget(_G, "HellBoxLog") then
				HellBoxLog("hellbox_8p", msg)
			end
		end

		-- 装备界面画哪几栏（menu_screen_loadout 的 update 里原版写死的 {1, 2, 3, 4} 改成了读这个全局变量）
		if type(rawget(_G, "favorite_loadout_index")) ~= "table" then
			rawset(_G, "favorite_loadout_index", { 1, 2, 3, 4 })
		end

		local function mark_engine_hash()
			local eh = rawget(_G, "BUILD_ENGINE_HASH")

			if type(eh) == "string" and not eh:find(SIG, 1, true) then
				rawset(_G, "BUILD_ENGINE_HASH", eh .. SIG)
			end
		end

		local function my_peer()
			local net = rawget(_G, "Network")
			local ok, p = pcall(net.peer_id)

			return ok and p or nil
		end

		local function is_host()
			local ng = rawget(_G, "NetworkGlobal")
			local lobby = type(ng) == "table" and ng.lobby

			if type(lobby) ~= "table" then
				return false
			end

			local ok, host = pcall(lobby.is_host, lobby)

			return ok and host
		end

		-- 数房间里的位置。skip_peer：这个人自己预留的空位不算（他正要把本地玩家放进去）
		-- 返回：占了几个位置、5～8 号有没有人、有没有原版玩家
		local function scan(self, skip_peer)
			local me = my_peer()
			local used, high, old = 0, false, false

			for i, pl in ipairs(self.players or {}) do
				local go = pl.player_go
				local exists = go ~= nil and go:exists()
				local res = pl.reserved_info
				local peer = exists and go:owner() or (res and res.peer_id) or nil
				local busy = exists or res ~= nil or pl.occupied_time ~= nil

				if busy and not exists and res and skip_peer ~= nil and res.peer_id == skip_peer then
					busy = false
				end

				if busy then
					used = used + 1

					if i > OLD_MAX then
						high = true
					end
				end

				if peer ~= nil and peer ~= me and G.peers[peer] ~= true then
					old = true
				end
			end

			return used, high, old
		end

		local function wrap_join(cls, tag)
			if type(cls) ~= "table" or rawget(cls, "_hb8_join") or type(cls.rpc_on_join_request) ~= "function" then
				return
			end

			local orig = cls.rpc_on_join_request

			cls.rpc_on_join_request = function(self, peer, game_hash, engine_hash, np_id, num_local, ...)
				if is_host() then
					local modded = type(engine_hash) == "string" and engine_hash:find(SIG, 1, true) ~= nil
					local ok, full = pcall(function()
						G.peers[peer] = modded

						local used, high, old = scan(self)
						local n = used + (tonumber(num_local) or 1)

						if not modded then
							return high or n > OLD_MAX
						end

						return old and n > OLD_MAX
					end)

					if not ok then
						log(tag .. " join check error, deny: " .. tostring(full))
					end

					if not ok or full then
						log(string.format("%s deny %s (8p=%s)", tag, tostring(peer), tostring(modded)))
						pcall(self.network_router.transmit_to, self.network_router, peer, "rpc_on_join_denied", "network_join_denied_game_full")

						return
					end
				end

				return orig(self, peer, game_hash, engine_hash, np_id, num_local, ...)
			end
			cls._hb8_join = true
		end

		local function wrap_add_local(cls, tag)
			if type(cls) ~= "table" or rawget(cls, "_hb8_add") or type(cls.rpc_add_local_player_request) ~= "function" then
				return
			end

			local orig = cls.rpc_add_local_player_request

			cls.rpc_add_local_player_request = function(self, peer, pad, index, ...)
				if is_host() then
					local ok, block = pcall(function()
						local used, _high, old = scan(self, peer)

						if peer ~= my_peer() and G.peers[peer] ~= true then
							old = true
						end

						return old and used >= OLD_MAX
					end)

					if not ok then
						log(tag .. " add check error, deny: " .. tostring(block))
					end

					if not ok or block then
						return -- 原版没有空位时也是什么都不回
					end
				end

				return orig(self, peer, pad, index, ...)
			end
			cls._hb8_add = true
		end

		-- 救援名单最多 4 个（消息格子只有 4 个），先救死得早的。
		-- 原版名单按座位号 1→8 排（房主坐 1 号，总排第一），原版人人都救所以无所谓；截成 4 个就得按死的先后排
		-- （用户 2026-11-26：「复活不是按照先死的顺序先复活……每次我作为房主都是优先复活的」）。
		G.died = G.died or {} -- 玩家 index → 第几个死的（越小越早）
		G.death_seq = G.death_seq or 0

		local function record_death(self, unit)
			for _, p in ipairs(self.players or {}) do
				local go = p.player_go

				if go and go:exists() and go:has("avatar_unit") and go:get("avatar_unit") == unit then
					G.death_seq = G.death_seq + 1
					G.died[go:get("index")] = G.death_seq

					return
				end
			end
		end

		-- 死人名单 → 最早死的 4 个；没记到死亡的（比如掉线重进）排最后，同样按座位号
		local function earliest_dead(list)
			local order = {}

			for k, idx in ipairs(list) do
				order[k] = { idx = idx, t = G.died[idx] or math.huge, k = k }
			end

			table.sort(order, function(x, y)
				if x.t ~= y.t then
					return x.t < y.t
				end

				return x.k < y.k
			end)

			local out = {}

			for k = 1, OLD_MAX do
				out[k] = order[k].idx
			end

			return out
		end

		local function wrap_respawn(sg)
			if type(sg) ~= "table" or rawget(sg, "_hb8_respawn") or type(sg.on_stratagem_pre_activated) ~= "function" then
				return
			end

			if type(sg.on_player_death) == "function" then
				local orig_death = sg.on_player_death

				sg.on_player_death = function(self, unit, ...)
					local ok, err = pcall(record_death, self, unit)

					if not ok then
						log("record death failed: " .. tostring(err))
					end

					return orig_death(self, unit, ...)
				end
			end

			local orig = sg.on_stratagem_pre_activated

			sg.on_stratagem_pre_activated = function(self, strat, ...)
				local r = self.network_router

				if type(strat) ~= "table" or strat.name ~= "stratagem_reinforce" or type(r) ~= "table" then
					return orig(self, strat, ...)
				end

				local own = rawget(r, "transmit_to_all")
				local send = r.transmit_to_all

				r.transmit_to_all = function(rr, name, a, b, c, list, ...)
					if name == "rpc_on_respawn" and type(list) == "table" then
						if #list > OLD_MAX then
							local ok, out = pcall(earliest_dead, list)

							if not ok then
								log("sort dead failed: " .. tostring(out))
								out = { list[1], list[2], list[3], list[4] }
							end

							log("reinforce: " .. #list .. " dead, sending " .. table.concat(out, ","))
							list = out
						end

						for _, idx in ipairs(list) do
							G.died[idx] = nil -- 救起来了，下次死重新记
						end
					end

					return send(rr, name, a, b, c, list, ...)
				end

				local res = { pcall(orig, self, strat, ...) }

				rawset(r, "transmit_to_all", own)

				if not res[1] then
					error(res[2], 0)
				end

				return unpack(res, 2)
			end
			sg._hb8_respawn = true
		end

		-- 状态栏（面板）：HellBox「多人」页选（用户 2026-11-26 要的），编译时填 "@HELLBOX_8P_HUD@"，如 "small+solo"
		--   摆法二选一（用户：两排和小一号一排冲突）：
		--     rows  = 两排（默认）：1～4 号照原版，5～8 号在原来那排正上方第二排
		--     small = 小一号一排：8 栏都缩小，在屏幕下方排成一排（居中）
		--   solo  = 只看自己（开关，两种摆法都能配）：任务里只画本机玩家的栏，本机有人打开地图（Tab）时才画其他人的；飞船里都画
		-- 缩小是借原版的界面缩放：HdGui 画东西时位置、大小、字号都乘 ui_scale，画某一栏时临时把它乘上 SMALL。
		local HUD_CFG = "@HELLBOX_8P_HUD@"
		local HUD_MODE = HUD_CFG:find("small", 1, true) and "small" or "rows"
		local SOLO = HUD_CFG:find("solo", 1, true) ~= nil
		local MAX = 8
		local SMALL = 0.58 -- 【暂定】8 × 248 × 0.58 + 7 × 10 ≈ 1221，正好放进 1280 宽，等实机截图再调
		local SMALL_GAP = 10
		local DESIGN_W = 1280 -- 原版界面的设计宽度（hd_gui design_resolution）


		local scaled = false -- 正在缩小画：这时 get_player_hud_pos 给缩放后的坐标（hd_gui:move 会再乘回去）

		local function hud_scale(i)
			return HUD_MODE == "small" and SMALL or 1
		end

		local function panel_width(self, j)
			local info = self.hud_info and self.hud_info[j]

			return info and info.width or 248
		end

		-- 第 i 栏左下角在设计尺寸（1280×720）里的位置
		local function design_pos(self, orig, i)
			local s = HudSettings.settings.player_hud
			local m = Vector3Aux.unbox(self.state_name == "menu" and s.margin_menu or s.margin)

			if HUD_MODE == "small" then
				local total = -SMALL_GAP

				for j = 1, MAX do
					total = total + panel_width(self, j) * SMALL + SMALL_GAP
				end

				local x = (DESIGN_W - total) / 2

				for j = 1, i - 1 do
					x = x + panel_width(self, j) * SMALL + SMALL_GAP
				end

				return Vector3(x, m.y, 0)
			end

			if i <= OLD_MAX then
				return orig(self, i)
			end

			local x = 0

			for j = OLD_MAX + 1, i - 1 do
				x = x + panel_width(self, j) + s.spacing
			end

			local hh = s.hud_heights

			return Vector3(m.x + x, m.y + hh.normal + hh.name_bar + hh.color_bar + ROW_GAP, 0)
		end

		-- 用缩小的比例跑 fn（k = 1 时直接跑）；hd_gui 和这一栏的地图 gui 一起缩，跑完（出错也）还原
		local function with_scale(self, k, map_gui, fn, ...)
			if k == 1 or type(self.hd_gui) ~= "table" then
				return fn(...)
			end

			local guis = { self.hd_gui, type(map_gui) == "table" and map_gui or nil }
			local olds = {}

			for n, g in ipairs(guis) do
				olds[n] = g.ui_scale
				g.ui_scale = g.ui_scale * k
			end

			scaled = true

			local res = { pcall(fn, ...) }

			scaled = false

			for n, g in ipairs(guis) do
				g.ui_scale = olds[n]
			end

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end

		-- 只看自己：这一栏要不要藏
		local function hide_panel(self, p)
			if not SOLO or self.state_name == "menu" then
				return false
			end

			local go = type(p) == "table" and p.player_go

			if not go or go:owned() then
				return false
			end

			for _, open in pairs(self._hb8_map or {}) do
				if open then
					return false
				end
			end

			return true
		end

		local function wrap_hud(h)
			if type(h) ~= "table" or rawget(h, "_hb8_pos") or type(h.get_player_hud_pos) ~= "function" then
				return
			end

			local orig = h.get_player_hud_pos

			h.get_player_hud_pos = function(self, i, ...)
				if type(i) ~= "number" or HUD_MODE ~= "small" and i <= OLD_MAX then
					return orig(self, i, ...)
				end

				local pos = design_pos(self, orig, i)

				if scaled then
					local k = hud_scale(i)

					pos = Vector3(pos.x / k, pos.y / k, 0)
				end

				return pos
			end
			h._hb8_pos = true

			-- 面板本体：缩小画 / 只看自己时藏起来
			if type(h.draw_hud) == "function" then
				local orig_draw = h.draw_hud

				h.draw_hud = function(self, dt, unit, vp, i, pos, health, inv, char, p, ...)
					local info = type(i) == "number" and self.hud_info and self.hud_info[i]

					if not info then
						return orig_draw(self, dt, unit, vp, i, pos, health, inv, char, p, ...)
					end

					if hide_panel(self, p) then
						if not info._hb8_hidden then
							info._hb8_hidden = true
							self:destroy_gui_objects(info)
							info.previous_state = nil -- 再出来时照原版「状态变了」重画
							info.last_state = nil
						end

						return
					end

					info._hb8_hidden = nil

					local maps = self.map_hd_gui and self.map_hd_gui[i]

					with_scale(self, hud_scale(i), maps, orig_draw, self, dt, unit, vp, i, pos, health, inv, char, p, ...)

					if SOLO then
						self._hb8_map = self._hb8_map or {}
						self._hb8_map[i] = (type(p) == "table" and p.player_go and p.player_go:owned() and info.state == "map") or nil
					end
				end
			end

			-- 死了以后骷髅从人身上飞进面板：缩小时目标是缩小的面板，起点（设计坐标）先除回去
			if HUD_MODE == "small" and type(h.draw_kia_transition) == "function" then
				local orig_kia = h.draw_kia_transition

				h.draw_kia_transition = function(self, dt, info, i, at, ...)
					local k = hud_scale(i)

					if at then
						at.x, at.y = at.x / k, at.y / k
					end

					return with_scale(self, k, nil, orig_kia, self, dt, info, i, at, ...)
				end
			end

			-- 空位上的「按 A 加入」：原版不走 get_player_hud_pos，自己按 margin.x + (栏宽 + 间距) × (号 - 1) 算，
			-- 第 5 号起画到屏幕外（用户 2026-11-26 实测）。画这些空位时临时换 margin（缩小时连字一起缩），让字落在这一栏的位置。
			if type(h.pre_update_and_draw_hud) ~= "function" then
				return
			end

			local orig_pre = h.pre_update_and_draw_hud

			h.pre_update_and_draw_hud = function(self, dt, pads, vp, i, p, ...)
				if type(i) ~= "number" or type(p) ~= "table" or not p.player_go or p.player_go:exists() then
					return orig_pre(self, dt, pads, vp, i, p, ...)
				end

				if self._hb8_map then
					self._hb8_map[i] = nil -- 人走了，不再算他开着地图
				end

				if HUD_MODE ~= "small" and i <= OLD_MAX then
					return orig_pre(self, dt, pads, vp, i, p, ...)
				end

				local s = HudSettings.settings.player_hud
				local old_m, old_mm = s.margin, s.margin_menu
				local k = hud_scale(i)
				local ok, err = pcall(function()
					local pos = design_pos(self, orig, i)
					local x = pos.x / k - (panel_width(self, i) + s.spacing) * (i - 1)
					local m = Vector3Aux.box({}, Vector3(x, pos.y / k, 0))

					s.margin, s.margin_menu = m, m
				end)

				if not ok then
					s.margin, s.margin_menu = old_m, old_mm
					log("join text pos failed: " .. tostring(err))
				end

				local res = { pcall(with_scale, self, k, nil, orig_pre, self, dt, pads, vp, i, p, ...) }

				s.margin, s.margin_menu = old_m, old_mm

				if not res[1] then
					error(res[2], 0)
				end

				return unpack(res, 2)
			end
		end

		local function extend_settings(gs)
			if type(gs) ~= "table" or rawget(gs, "_hb8") then
				return
			end

			local cols, names = gs.player_colors, gs.player_names

			if type(cols) ~= "table" or type(names) ~= "table" then
				return
			end

			for k = 1, 4 do
				if cols[OLD_MAX + k] == nil then
					local c = COLORS[k]

					cols[OLD_MAX + k] = QuaternionAux.box_elements({}, c[1], c[2], c[3], c[4])
				end

				if names[OLD_MAX + k] == nil then
					names[OLD_MAX + k] = NAMES[k]
				end
			end

			gs._hb8 = true
		end

		-- 房间列表：开了 8 人房间的房主显示「n/8」，其他房间「n/4」（用户 2026-11-26：原来全显示 n/8，
		-- 原版房间 4 人时进不去、隐藏满员也藏不掉）。
		--   房主在房间数据末尾多写一格 hb8 = 1。房间数据是按位置用 | 隔开的一串，原版只认前 21 格，多的一格原版不看。
		--   列表里每个房间记一个上限 room["#MAX_PLAYERS"]（8 / 4）；房间列表「x/4」那条指令（eight_players.py ROOM_MAX）读它，
		--   进房前「本机几个人 > 4 - 房间人数」的检查、「隐藏满员房间」也按它算。
		local function room_max(room)
			return type(room) == "table" and room["#MAX_PLAYERS"] or OLD_MAX
		end

		local function extend_rooms(gs)
			if type(gs) ~= "table" or rawget(gs, "_hb8_rooms") then
				return
			end

			local rv, filters = gs.room_data_values, gs.multiplayer_filters

			if type(rv) ~= "table" or type(filters) ~= "table" then
				return
			end

			if rv.hb8 == nil then
				local n = #rv

				rv[n + 1] = "hb8"
				rv.hb8 = n + 1
			end

			-- 好友列表里的房间不读房间数据，读的是房里每个人的 Steam 好友状态（friends_data_values 这几格，
			-- 由 rpc_on_lobby_data_changed 从房间数据里抄）。这里也加一格 hb8，房间数据里的 hb8 就会跟着抄进去，
			-- 好友列表才认得出 8 人房间（2026-11-26 实测：好友视角 8 人房间显示 4/4、进不来）。原版只认自己那几格，多的不看。
			local fv = gs.friends_data_values

			if type(fv) == "table" and fv.hb8 == nil then
				local n = #fv

				fv[n + 1] = "hb8"
				fv.hb8 = n + 1
			end

			for _, f in ipairs(filters) do
				if f.name == "filter_hide_full_games" then
					f.filter_func = function(room, on)
						return on and type(room) == "table" and (room.num_players or 0) >= room_max(room)
					end
				end
			end

			gs._hb8_rooms = true
		end

		-- 自己当房主：房间数据写上 hb8 = 1（每 0.5 秒看一次；换房、房主迁移后也会补上）
		local function mark_room()
			local ng = rawget(_G, "NetworkGlobal")
			local lobby = type(ng) == "table" and ng.lobby

			if type(lobby) ~= "table" or type(lobby.data_table) ~= "table" or type(lobby.data) ~= "table" then
				return
			end

			local slot = lobby.data_table.hb8

			if slot == nil or lobby.data[slot] == "1" or not lobby:is_valid() or not lobby:is_host() then
				return
			end

			lobby:set_data("hb8", "1")
			-- 马上通知一次「房间数据变了」：房里每个人据此更新 Steam 好友状态（带上 hb8）。不叫的话要等原版 10 分钟一次的刷新
			pcall(lobby.update_room_values, lobby)
		end

		-- 开游戏进主菜单时原版自动建的房间（state_main_menu），Steam 房间上限写死 4 台电脑，这一处没在 eight_players.py 改成 8
		-- （从多人菜单建房的两处改了）。第 5 台电脑连 Steam 房间都进不来，房主收不到申请（2026-11-26 实测）。
		-- 开了 8 人房间时，建房要 4 台的一律改成 8 台；谁能进还是照上面的规则管（有原版玩家就按 4 人）。
		local function wrap_create(cls)
			if type(cls) ~= "table" or rawget(cls, "_hb8_create") or type(cls.create) ~= "function" then
				return
			end

			local orig = cls.create

			cls.create = function(self, n, ...)
				if n == OLD_MAX then
					n = 8
				end

				return orig(self, n, ...)
			end
			cls._hb8_create = true
		end

		local function wrap_rooms(cls)
			if type(cls) ~= "table" or rawget(cls, "_hb8_rooms") then
				return
			end

			local f_room, f_friend = cls.extract_room_info, cls.extract_friend_room_info
			local f_draw, f_join = cls.draw_rooms_info, cls.trigger_join_dialog

			if type(f_room) ~= "function" or type(f_friend) ~= "function" or type(f_draw) ~= "function" or type(f_join) ~= "function" then
				return
			end

			cls.extract_room_info = function(self, name, data, ...)
				local room = f_room(self, name, data, ...)

				if type(room) == "table" then
					local ok, t = pcall(NetworkGlobal.data_string_to_table, data, GameSettings.room_data_values)

					room["#MAX_PLAYERS"] = ok and type(t) == "table" and t.hb8 == "1" and 8 or OLD_MAX
				end

				return room
			end

			-- 好友列表：第 3 个参数是好友状态解开的表，开了 8 人房间的人状态里带 hb8（见 extend_rooms）；没带的按 4
			cls.extract_friend_room_info = function(self, name, info, ...)
				local room = f_friend(self, name, info, ...)

				if type(room) == "table" then
					room["#MAX_PLAYERS"] = type(info) == "table" and info.hb8 == "1" and 8 or OLD_MAX
				end

				return room
			end

			-- 画之前补齐：每个房间都要有上限（那条指令直接读它，缺了会显示空）
			cls.draw_rooms_info = function(self, ...)
				if type(self.displayable_rooms) == "table" then
					for _, room in ipairs(self.displayable_rooms) do
						if type(room) == "table" and room["#MAX_PLAYERS"] == nil then
							room["#MAX_PLAYERS"] = OLD_MAX
						end
					end
				end

				return f_draw(self, ...)
			end

			-- 原版：本机人数 > 4 - 房间人数 就说满了。8 人房间临时把人数减 4，等于按 8 - 房间人数算
			cls.trigger_join_dialog = function(self, ...)
				local room = type(self.displayable_rooms) == "table" and self.displayable_rooms[self.selected_room]
				local n = type(room) == "table" and room.num_players

				if type(n) ~= "number" or room_max(room) == OLD_MAX then
					return f_join(self, ...)
				end

				room.num_players = n - (room_max(room) - OLD_MAX)

				local res = { pcall(f_join, self, ...) }

				room.num_players = n

				if not res[1] then
					error(res[2], 0)
				end

				return unpack(res, 2)
			end
			cls._hb8_rooms = true
		end

		-- 装备界面画哪 4 栏：大家都在 1～4 号时照原版 {1, 2, 3, 4}；有人在 5～8 号时自己的栏在前，再补别人、空位
		local function loadout_order(self)
			local players = self.parent and self.parent.players

			if type(players) ~= "table" then
				return nil
			end

			local own, other, empty = {}, {}, {}
			local high = false

			for i, pl in ipairs(players) do
				local go = pl.player_go

				if go and go:exists() then
					if i > OLD_MAX then
						high = true
					end

					if go:owned() then
						own[#own + 1] = i
					else
						other[#other + 1] = i
					end
				else
					empty[#empty + 1] = i
				end
			end

			if not high then
				return nil
			end

			-- 自己的栏全部放进去（键盘 + 4 个手柄 = 本机最多 5 人，第 5 栏画在屏幕右边缘外一点，但选的装备照样发出去）。
			-- 2026-11-26 用户定：别人不再占整栏，画成小卡片排在剩下几栏的位置（draw_cards）；本机占满 4 栏时没地方，照以前补满 4 栏
			local order = {}

			for _, i in ipairs(own) do
				order[#order + 1] = i
			end

			if #own > 0 and #own < OLD_MAX then
				return order, other
			end

			for _, list in ipairs({ other, empty }) do
				for _, i in ipairs(list) do
					if #order < OLD_MAX then
						order[#order + 1] = i
					end
				end
			end

			return order
		end

		-- 队友小卡片（2026-11-26 用户：「8 个人……选装备界面……自己的整栏 + 7 张队友小卡片」；
		--   原版画 4 栏，第 5～8 人的装备界面以前只能看到 3 个别人）。只在有人坐 5～8 号时画，大家都在 1～4 号（含所有原版房间）照原版。
		--   位置：原版栏的坐标（x = 96 + 280 × (栏 - 1)，y 从 86 起，向上约 500 高）里，自己占前几栏，剩下的栏从上往下叠卡片。
		--   内容：颜色条、军衔、名字；主武器和 4 个战略配备图标（随机配装显示随机图标）；选好了没有（原版的「已完成 / 选择中」字样）。
		--   数据直接从这个人的 player_go 读（原版画栏时也是这么同步的），用这个人自己那份 hd_gui（原版建了 8 份，没画栏的人闲着）。
		local CARD_TOP = 500
		local CARD_GAP = 8
		local CARD_W = 248
		local CARD_FULL = 106 -- 放得下状态那一行的最小高度
		local CARD_MAX = 132

		local function card_slots(n_cards, n_own)
			local cols = OLD_MAX - n_own
			local per = math.ceil(n_cards / cols)
			local h = math.floor((CARD_TOP - (per - 1) * CARD_GAP) / per)

			return cols, per, math.min(h, CARD_MAX)
		end

		local function draw_card(self, gui, go, x, y, h, layer)
			local old_clip = gui.clip_region

			if old_clip then
				gui:set_clip_region(nil)
			end

			gui:move(Vector3(x, y, 0))

			local done = go:get("loadout_done") and true or false

			self:draw_player_panel(gui, h - 11, CARD_W, Color(done and 200 or 140, 255, 255, 255), layer)

			local rgba = { Quaternion.to_elements(QuaternionAux.unbox(GameSettings.player_colors[go:get("index")])) }
			local bar = HudSettings.settings.player_hud.hud_heights.color_bar

			gui:image("hud_icon_color_gradient_01", Vector3(0, h - bar - 1, layer + 1), Vector2(CARD_W - 2, bar),
				ColorAux.from_table(rgba), Vector2(0, 0), Vector2(0.99, 1))

			-- 军衔 + 名字（太长就缩字号，和原版栏头一样）
			local name = go:get("name") or ""
			local rank = ProgressionSettings.get_rank(go:get("xp") or 0)

			gui:set_current_font("body")

			local size = FontSettings.fonts.body.font_size

			while size > 8 and CARD_W - 40 < gui:get_text_extents(name, nil, size, true) do
				size = size - 1
			end

			local name_y = h - bar - 26
			local full = h >= CARD_FULL
			local name_color = Color(255, 178, 178, 178)

			if not full and done then
				name_color = Color(255, 150, 230, 150) -- 放不下状态行时，选好了的名字变绿
			end

			if rank and rank.icon then
				gui:image(rank.icon, Vector3(4, name_y - 2, layer + 10), Vector2(24, 24))
			end

			gui:text(name, Vector3(32, name_y, layer + 10), name_color, nil, size)

			-- 主武器 + 战略配备图标
			local icon_y = name_y - 46

			if go:get("using_random_loadout") then
				gui:image("loadout_random", Vector3(8, icon_y, layer + 10), Vector2(40, 40))
			else
				local wi = go:get("primary_weapon_index") or 0
				local w = wi > 0 and LoadoutSettings.primary_weapon[wi]

				if w and w.icon then
					gui:image(w.icon, Vector3(6, icon_y + 2, layer + 10), Vector2(82, 36))
				end

				local slot = 0

				for id = #LoadoutSettings.static_stratagems + 1, LoadoutSettings.nr_of_stratagem_slots do
					local si = go:get("stratagem" .. tostring(id) .. "_index") or 0
					local s = si > 0 and LoadoutSettings.stratagems[si]

					if s then
						MenuScreenBase:draw_stratagem_icon(nil, gui, s, go:get("stratagem" .. tostring(id) .. "_upgrade") or 0,
							Vector3(96 + slot * 38, icon_y + 2, layer + 10), Vector2(36, 36))
					end

					slot = slot + 1
				end
			end

			if full then
				local text = LocalizationManager:string(done and "loadout_client_loadout_done" or "loadout_client_loadout_in_progress")

				gui:text(text, Vector3(8, icon_y - 22, layer + 10), done and Color(255, 150, 230, 150) or Color(255, 178, 178, 178), nil,
					FontSettings.fonts.body.font_size - 2)
			end

			gui:move(Vector3.zero())

			if old_clip then
				gui:set_clip_region(old_clip)
			end
		end

		local function draw_cards(self, own, others, layer)
			if type(self.hd_gui) ~= "table" then
				return
			end

			local players = self.parent.players
			local cards = {}

			for _, i in ipairs(others) do
				local go = players[i] and players[i].player_go

				if go and go:exists() and self.hd_gui[i] then
					cards[#cards + 1] = i
				end
			end

			if #cards == 0 then
				return
			end

			local _, per, h = card_slots(#cards, #own)
			local base = 86 + (1 - self.parent.gui_manager.ui_scale_user) * 320

			for k, i in ipairs(cards) do
				local col = #own + 1 + math.floor((k - 1) / per)
				local row = (k - 1) % per
				local x = 96 + 280 * (col - 1)
				local y = base + CARD_TOP - (row + 1) * h - row * CARD_GAP

				draw_card(self, self.hd_gui[i], players[i].player_go, x, y, h, layer or 0)
			end
		end

		G.card_slots = card_slots

		local DEFAULT_ORDER = { 1, 2, 3, 4 }

		local function wrap_loadout(cls)
			if type(cls) ~= "table" or rawget(cls, "_hb8_order") or type(cls.update) ~= "function" then
				return
			end

			local orig = cls.update

			cls.update = function(self, dt, layer, ...)
				local ok, order, others = pcall(loadout_order, self)

				if not ok then
					log("loadout order error: " .. tostring(order))
				end

				rawset(_G, "favorite_loadout_index", ok and order or DEFAULT_ORDER)

				local res = { orig(self, dt, layer, ...) }

				if ok and others then
					local fine, err = pcall(draw_cards, self, order, others, layer)

					if not fine and not G.card_err then
						G.card_err = true -- 只记一次
						log("loadout cards error: " .. tostring(err))
					end
				end

				return unpack(res)
			end
			cls._hb8_order = true
		end

		local function hook_all()
			mark_engine_hash()
			extend_settings(rawget(_G, "GameSettings"))
			extend_rooms(rawget(_G, "GameSettings"))
			wrap_rooms(rawget(_G, "MenuScreenCampaignMultiplayer"))
			wrap_create(rawget(_G, "NetworkRoom"))

			local ok, err = pcall(mark_room)

			if not ok and not G.room_err then
				G.room_err = true -- 只记一次，别每 0.5 秒刷屏
				log("mark room failed: " .. tostring(err))
			end
			wrap_hud(rawget(_G, "Hud"))
			wrap_loadout(rawget(_G, "MenuScreenLoadout"))
			wrap_respawn(rawget(_G, "StateGame"))

			for name, tag in pairs({ StateGame = "game", StateMenu = "menu", StateMissionStart = "mission_start", StateMissionEnd = "mission_end" }) do
				local cls = rawget(_G, name)

				wrap_join(cls, tag)
				wrap_add_local(cls, tag)
			end
		end

		local ok, err = pcall(hook_all)

		if not ok then
			log("hook error: " .. tostring(err))
		end

		local wm = rawget(_G, "WorldManager")

		if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.tick then
			local orig = wm.update
			local next_check = 0

			G.tick = function(self, ...)
				local t = Application.time_since_launch()

				if t >= next_check then
					next_check = t + 0.5

					local ok2, err2 = pcall(hook_all)

					if not ok2 then
						log("hook error: " .. tostring(err2))
					end
				end

				return orig(self, ...)
			end
			wm.update = G.tick
		end

		log("8 players on, hud " .. HUD_MODE .. (SOLO and " + solo" or ""))
	end
end
