-- [host loadout] 房主定配装（2026-11-18 V0.96，HD1-033）。由 build.py 追加到 character_state_machine 末尾。
--
-- 用户定：房主在 HellBox「玩法」页定一套配装，每一格（天赋、主武器、战备 5～8）可以「指定某样」或「自由」；
--   开着 HellBox 的队友进房主的房间，锁住的格子只能用房主定的；没装 HellBox 的人不受影响（他们读不到、也没人改他们）。
--
-- 规则从哪来：
--   房主：HellBox 写 %APPDATA%/Arrowhead/Helldivers/hellbox/host-loadout.txt（HBLO1，一行一个 键=值：on=1、perk=、primary=、
--     s5=～s8=，空 = 自由；name.* 行是 HellBox 自己存的显示名，这里不看），每秒看一次。当房主时把规则写进 Steam 房间数据
--     hellbox_lo（不碰游戏自己的 data 串），关掉时写一个空格。
--   队友（客机）：每 2 秒读当前房间的 hellbox_lo（SteamLobby.data / LanLobby.data，pcall 包着；读不到 = 没有规则）。
--   规则串：1|天赋|主武器|s5|s6|s7|s8（空 = 自由，? = 随机，2026-11-18 V0.97 加）。名字不在 LoadoutSettings 里的格子当自由
--   （V0.96 的队友读到 ? 也当自由，不会坏）。
--
-- V0.97（2026-11-18 用户定）：每一格「固定 / 自由 / 随机」。随机 = 游戏自己的随机配装办法：离开选装备界面时（原版抽随机配装
--   的同一时刻，MenuScreenLoadout.on_exit）按这个玩家已解锁的东西抽一个（天赋 / 主武器先随机挑一组再挑一样；战备从全部已解锁的
--   里不重复地抽，避开固定格的）；每个人各抽各的，存在 G.draws[手柄号]，出生时换进去。界面上随机格照游戏随机配装显示 ???，
--   固定格照训练场显示锁（host_loadout_menu.lua 里一份照抄原版 draw_menu、只把「整套随机 / 训练场」的判断改成按格子判断）；
--   这两种格子按确定键打不开挑选列表。
--
-- V0.97 第 ⑥ 步：客机「跟随房主的玩法」（play.txt 的 follow=，hellbox_play.lua 读；默认开）。关着时在别人房间里不用房主的配装块
--   （G.rule = nil，照自己的配装，选装备界面不锁）；房主的规则还是读出来放在 G.host_rule 给 HellBox 显示「房主开了什么」。
--   自己当房主 / 单机 / 本机分屏不受这个开关管，永远用自己的。
--
-- 怎么生效：
--   1) 出生时（InventoryComponent.set_loadout，读存档里那套配装的地方）：原版调用期间临时包一层 SaveManager:get / user_get，
--      读到 loadout* / random_loadout* 这些配装表时返回「锁住的格子换成房主的」的副本；存档本身不动。训练场配装
--      （use_proving_grounds_loadout）和直接传进来的配装（loadout_override）不管。
--   2) 选装备界面（MenuScreenLoadout）：锁住的格子显示房主的东西，玩家换了会弹回去；切预设、离开界面前先把玩家原来的
--      放回去（原版会把界面上的格子写回预设 / 存档），切完再锁上——玩家自己的预设不会被改掉。训练场界面不管。
--   状态写 hellbox/host-loadout-status.txt（role=host|guest|none、rule=…、api=… 读不读得到房间数据）给 HellBox 显示。
do
	local G = HellBoxHostLoadout or {}

	HellBoxHostLoadout = G

	local KEY = "hellbox_lo"
	local SLOTS = { "perk", "primary", "s5", "s6", "s7", "s8" }

	local function hb_dir()
		local appdata = os.getenv and os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/")
	end

	local function log(msg)
		if rawget(_G, "HellBoxLog") then
			HellBoxLog("host_loadout", msg)
		end
	end

	-- 规则：{ perk=, primary=, s = {[5]=,…} }，没有任何锁的格子 = nil
	local RANDOM = "?"

	local function valid(kind, name)
		if type(name) ~= "string" or name == "" then
			return nil
		elseif name == RANDOM then
			return RANDOM
		end

		local ok, item = pcall(LoadoutSettings.get_item, kind, name)

		return ok and type(item) == "table" and name or nil
	end

	local function from_parts(perk, primary, s5, s6, s7, s8)
		local r = { perk = valid("perks", perk), primary = valid("primary_weapon", primary), s = {} }
		local any = r.perk ~= nil or r.primary ~= nil

		local ss = { s5, s6, s7, s8 }

		for i = 1, 4 do
			r.s[i + 4] = valid("stratagems", ss[i])
			any = any or r.s[i + 4] ~= nil
		end

		return any and r or nil
	end

	local function to_string(r)
		if not r then
			return " "
		end

		return table.concat({ "1", r.perk or "", r.primary or "", r.s[5] or "", r.s[6] or "", r.s[7] or "", r.s[8] or "" }, "|")
	end

	local function from_string(text)
		if type(text) ~= "string" or text:sub(1, 2) ~= "1|" then
			return nil
		end

		local p = {}

		for part in (text .. "|"):gmatch("([^|]*)|") do
			p[#p + 1] = part
		end

		return from_parts(p[2], p[3], p[4], p[5], p[6], p[7])
	end

	-- 房主自己的规则文件（内容变了才重读）
	local function read_file()
		local dir = hb_dir()
		local f = dir and io.open(dir .. "host-loadout.txt", "rb")

		if not f then
			G.file_text, G.file_rule = nil, nil

			return
		end

		local text = f:read("*a") or ""

		f:close()

		if text == G.file_text then
			return
		end

		G.file_text = text

		local kv = {}

		for line in text:gmatch("[^\r\n]+") do
			local k, v = line:match("^([%w_]+)=(.*)$")

			if k then
				kv[k] = v
			end
		end

		local rule = text:match("^HBLO1") and kv.on == "1" and from_parts(kv.perk, kv.primary, kv.s5, kv.s6, kv.s7, kv.s8) or nil

		-- 2026-11-19 发行抢先版 用户定：固定格只能定房主自己解锁了的（HellBox 下拉框里没解锁的选不了）；以前存下的没解锁的那格
		--   当「自由」（profile_tool.lua 的 item_on）。只管房主自己的文件，客机收到房主的规则照用（那是房主解锁了的）。
		--   拿不到存档（item_on 返回 nil）：这格先当自由，不记 file_text，下一秒重读再核对。
		local pt = rawget(_G, "ProfileToolMod")
		local item_on = type(pt) == "table" and type(pt.item_on) == "function" and pt.item_on or nil

		if rule and item_on then
			local unsure = false

			local function keep(kind, v)
				if v == nil or v == RANDOM then
					return v
				end

				local ok, yes = pcall(item_on, kind, v)

				if not ok or yes == nil then
					unsure = true

					return nil
				end

				if not yes then
					log("fixed item not unlocked, freed: " .. v)
				end

				return yes and v or nil
			end

			rule.perk = keep("perks", rule.perk)
			rule.primary = keep("primary_weapon", rule.primary)

			local any = rule.perk ~= nil or rule.primary ~= nil

			for i = 5, 8 do
				rule.s[i] = keep("stratagems", rule.s[i])
				any = any or rule.s[i] ~= nil
			end

			if not any then
				rule = nil
			end

			if unsure then
				G.file_text = nil
			end
		end

		G.file_rule = rule
	end

	local function lobby_now()
		local ng = rawget(_G, "NetworkGlobal")
		local lobby = type(ng) == "table" and ng.lobby

		if type(lobby) == "table" and lobby.lobby and lobby.is_valid and lobby:is_valid() then
			return lobby
		end

		return nil
	end

	local function read_lobby(lobby)
		local api = (lobby.backend_type == "STEAM" and rawget(_G, "SteamLobby"))
			or (lobby.backend_type == "LAN" and rawget(_G, "LanLobby")) or nil

		if type(api) ~= "table" or type(api.data) ~= "function" then
			G.api = "missing"

			return nil
		end

		local ok, v = pcall(api.data, lobby.lobby, KEY)

		G.api = ok and "ok" or ("err:" .. tostring(v))

		return ok and v or nil
	end

	local function write_lobby(lobby, text)
		local api = (lobby.backend_type == "STEAM" and rawget(_G, "SteamLobby"))
			or (lobby.backend_type == "LAN" and rawget(_G, "LanLobby")) or nil

		if type(api) == "table" and type(api.set_data) == "function" then
			pcall(api.set_data, lobby.lobby, KEY, text)
		end
	end

	-- 客机跟不跟房主（hellbox_play.lua 读 play.txt 的 follow=；那个脚本没装 / 没读到 = 跟）
	local function follow_on()
		local p = rawget(_G, "HellBoxPlay")

		return not (type(p) == "table" and type(p.cfg) == "table" and p.cfg.follow == false)
	end

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

	local function write_status()
		local dir = hb_dir()

		if not dir then
			return
		end

		local text = string.format("role=%s\nrule=%s\napi=%s\nfollow=%s\nhost_rule=%s\n", G.role or "none", to_string(G.rule),
			G.api or "", follow_on() and "1" or "0", G.host_rule and to_string(G.host_rule) or "")

		if text == G.status_text then
			return
		end

		local f = io.open(dir .. "host-loadout-status.tmp", "wb")

		if f then
			local okw = f:write(text)
			local okc = f:close()

			-- 写、关、改名全成功才记「已写」；失败下次再试
			if okw and okc and swap_in(dir .. "host-loadout-status.tmp", dir .. "host-loadout-status.txt") then
				G.status_text = text
			else
				os.remove(dir .. "host-loadout-status.tmp")
			end
		end
	end

	-- 这一关用的配装规则（V0.97 用户定：HellBox 版一律「下一关生效」）：进关（Boot 当前 state 是 game）的第一次，把当时的规则和每个
	-- 手柄已抽好的随机结果定下来（G.frozen），整关出生 / 增援复活、给客机的广播都用这份；中途改配装块 / 客机切跟随都等回飞船、
	-- 下一次选装备 / 下一关。选装备界面（在飞船上）照旧实时用 G.rule / G.draws。没有 Boot（离线测试）= 不定，都实时。
	local timer, pub_timer = 0, 0
	local refresh  -- 下面定义；sync_frozen 第一次定下前要先同步读一次

	local function level_state()
		-- 首选 hellbox_play 在生成地图（GeneratedLevel.spawn_levels，StateGame 里调用）时定下的这一关：人一定在地图生成之后才出生，
		-- 不用管 Boot 切到 game 和第一次出生谁先（StateMachine 源码没解出来，查不到先后）。没有 hellbox_play 才退回看 Boot 的 state。
		local play = rawget(_G, "HellBoxPlay")
		local pf = type(play) == "table" and rawget(play, "frozen")

		if type(pf) == "table" and pf.gl ~= nil then
			return pf.gl
		end

		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if type(sm) ~= "table" then
			return nil
		end

		local ok, name = pcall(sm.get_current_state_name, sm)

		if not ok or name ~= "game" then
			return nil
		end

		local ok2, st = pcall(sm.get_current_state, sm)

		return ok2 and type(st) == "table" and st or nil
	end

	local function sync_frozen()
		local st = level_state()

		if not st then
			G.frozen = nil

			return nil
		end

		if not G.frozen or G.frozen.state ~= st then
			-- 第一次定下之前先同步读一次房间数据 / 文件（客机中途加入、refresh 还没跑过时，不能按「无规则」定下整关）；读失败 = 照现在的
			G.frozen = nil
			timer = 0
			pcall(refresh, 0)

			local d = {}

			for k, v in pairs(G.draws or {}) do
				d[k] = v
			end

			G.frozen = { state = st, rule = G.rule, draws = d }
		end

		return G.frozen
	end

	refresh = function(dt)
		timer = timer - (dt or 0)
		pub_timer = pub_timer - (dt or 0)

		if timer > 0 then
			return
		end

		timer = 1
		read_file()

		-- 2026-11-25 用户定：HellBox 关了（hellbox_alive.lua）= 不锁格子，马上生效：这一关定下的规则也清掉（之后复活照自己的配装），
		--   当房主时广播「没有规则」；HellBox 再打开，选装备界面马上照规则，这一关定下的等下一关
		local alive = rawget(_G, "HellBoxAlive")
		local off = type(alive) == "table" and type(alive.off) == "function" and alive.off() or false

		if off and G.frozen and (G.frozen.rule or next(G.frozen.draws or {})) then
			G.frozen.rule, G.frozen.draws = nil, {}
		end

		local lobby = lobby_now()

		if lobby and lobby:is_host() then
			G.role = "host"
			G.host_rule = nil
			G.rule = not off and G.file_rule or nil

			-- 在一关里广播这一关用的（迟加入的客机和房主一致），回飞船才按最新的
			local text = to_string(G.frozen and G.frozen.rule or (not G.frozen and G.rule) or nil)

			if text ~= G.published or pub_timer <= 0 then
				write_lobby(lobby, text)
				G.published = text
				pub_timer = 30
			end
		elseif lobby then
			G.role = "guest"
			G.published = nil
			G.host_rule = from_string(read_lobby(lobby))
			G.rule = not off and follow_on() and G.host_rule or nil
		else
			-- 没有房间（主菜单）：按自己的文件（之后开房就是房主）
			G.role = "none"
			G.published = nil
			G.host_rule = nil
			G.rule = not off and G.file_rule or nil
		end

		write_status()
	end

	-- 规则里这一格的原始值：nil = 自由、"?" = 随机、名字 = 固定
	local function slot_value(kind, id)
		local r = G.rule

		if not r then
			return nil
		elseif kind == "perks" then
			return r.perk
		elseif kind == "primary_weapon" then
			return r.primary
		elseif kind == "stratagems" then
			return r.s[id]
		end

		return nil
	end

	-- 固定格的东西（随机、自由 = nil）
	local function locked(kind, id)
		local v = slot_value(kind, id)

		return v ~= RANDOM and v or nil
	end

	local function is_random(kind, id)
		return slot_value(kind, id) == RANDOM
	end

	-- 选装备界面的一格（loadout_menu 里的 {type=, id=}）：nil / "fixed" / "random"
	function G.slot_mode(e)
		if type(e) ~= "table" then
			return nil
		end

		local v = slot_value(e.type, e.id)

		return v == RANDOM and "random" or v and "fixed" or nil
	end

	G.draws = G.draws or {}

	-- 配装表副本：固定格换成房主的，随机格换成这个人离开选装备界面时抽到的（没抽过就照他自己的）
	local function merged(lo)
		if not G.rule or type(lo) ~= "table" then
			return lo
		end

		local out = table.clone(lo)
		local d = G.cur_pad ~= nil and G.draws[G.cur_pad] or nil

		out.stratagems = table.clone(lo.stratagems or {})
		out.perk = locked("perks") or (is_random("perks") and d and d.perk) or out.perk
		out.primary_weapon = locked("primary_weapon") or (is_random("primary_weapon") and d and d.primary) or out.primary_weapon

		for i = 5, 8 do
			out.stratagems[i] = locked("stratagems", i) or (is_random("stratagems", i) and d and d.s[i]) or out.stratagems[i]
		end

		G.merged = (G.merged or 0) + 1

		return out
	end

	local function is_loadout_key(key)
		return type(key) == "string" and (key:find("^loadout") ~= nil or key:find("^random_loadout") ~= nil)
	end

	--------------------------------------------------------------------------
	-- 出生：InventoryComponent.set_loadout
	--------------------------------------------------------------------------
	local function hook_inventory()
		local cls = rawget(_G, "InventoryComponent")

		if type(cls) ~= "table" or type(cls.set_loadout) ~= "function" or rawget(cls, "_hb_host_loadout") then
			return
		end

		local orig = cls.set_loadout

		cls.set_loadout = function(self, unit, data, params, explicit, ...)
			local sm = rawget(_G, "SaveManager")

			local fz = sync_frozen()
			local rule = fz and fz.rule or (not fz and G.rule) or nil

			if not rule or explicit ~= nil or type(params) ~= "table" or params.pad_number == nil or type(sm) ~= "table" then
				return orig(self, unit, data, params, explicit, ...)
			end

			local ok_pg, pg = pcall(sm.get, sm, "use_proving_grounds_loadout")

			if ok_pg and pg then
				return orig(self, unit, data, params, explicit, ...)
			end

			G.cur_pad = params.pad_number

			-- merged / locked 读 G.rule、G.draws：调用期间换成这一关定下的（放回在下面，出错也放回）
			local live_rule, live_draws = G.rule, G.draws

			if fz then
				G.rule, G.draws = fz.rule, fz.draws
			end

			local own_get, own_uget = rawget(sm, "get"), rawget(sm, "user_get")
			local base_get, base_uget = sm.get, sm.user_get

			sm.get = function(s, key, ...)
				local v = base_get(s, key, ...)

				return is_loadout_key(key) and merged(v) or v
			end
			sm.user_get = function(s, key, ...)
				local v = base_uget(s, key, ...)

				return is_loadout_key(key) and merged(v) or v
			end

			local res = { pcall(orig, self, unit, data, params, explicit, ...) }

			rawset(sm, "get", own_get)
			rawset(sm, "user_get", own_uget)
			G.cur_pad = nil
			G.rule, G.draws = live_rule, live_draws

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end
		cls._hb_host_loadout = true
	end

	--------------------------------------------------------------------------
	-- 选装备界面
	--------------------------------------------------------------------------
	local function lock_menu(m)
		if type(m) ~= "table" or type(m.loadout_menu) ~= "table" then
			return
		end

		for _, e in ipairs(m.loadout_menu) do
			local want = type(e) == "table" and locked(e.type, e.id)

			if want then
				if not e.hb_saved then
					e.hb_saved, e.hb_orig = true, e.item
				end

				if type(e.item) ~= "table" or e.item.name ~= want then
					local ok, item = pcall(LoadoutSettings.get_item, e.type, want)

					if ok and type(item) == "table" then
						e.item = table.clone(item)
					end
				end
			elseif type(e) == "table" and e.hb_saved then
				-- 规则变了、这一格不锁了：还给玩家
				e.item, e.hb_saved, e.hb_orig = e.hb_orig, nil, nil
			end
		end
	end

	local function unlock_menu(m)
		if type(m) ~= "table" or type(m.loadout_menu) ~= "table" then
			return
		end

		for _, e in ipairs(m.loadout_menu) do
			if type(e) == "table" and e.hb_saved then
				e.item, e.hb_saved, e.hb_orig = e.hb_orig, nil, nil
			end
		end
	end

	-- 2026-11-19 发行抢先版修（用户实测：客机关了「跟随房主」自己换了被锁的武器，房主的选装备界面上那个客机还显示房主定的）：
	--   以前房主把界面上所有人的格子都按自己的规则锁 / 画锁和 ???，连队友的那一栏也盖掉了。
	--   现在只管这台电脑自己的玩家（player_go:owned()，含本机分屏）；队友那一栏照原版显示他们真实的配装
	--   （跟随房主的队友在他们自己电脑上已经锁好了，传过来的就是锁好的东西）。
	local function owned_slot(self, i)
		local players = type(self.parent) == "table" and self.parent.players
		local pl = type(players) == "table" and players[i]
		local go = type(pl) == "table" and pl.player_go

		if type(go) ~= "table" or type(go.owned) ~= "function" then
			return true -- 认不出来：照以前的做法
		end

		local ok, yes = pcall(go.owned, go)

		return not ok or yes == true
	end

	local function menu_owned(self, m)
		for i, x in pairs(type(self.option_menus) == "table" and self.option_menus or {}) do
			if x == m then
				return owned_slot(self, i)
			end
		end

		return true
	end

	local function each_menu(self, fn)
		if type(self) == "table" and not self.is_proving_ground_trial and type(self.option_menus) == "table" then
			for i, m in pairs(self.option_menus) do
				if fn == lock_menu and not owned_slot(self, i) then
					unlock_menu(m)
				else
					fn(m)
				end
			end
		end
	end

	-- 照原版 on_exit 抽随机配装的办法，给随机格抽一个（available_items = 这个玩家已解锁的）
	local function pick_group(groups)
		if type(groups) ~= "table" or #groups == 0 then
			return nil
		end

		local g = groups[math.random(#groups)]
		local items = type(g) == "table" and g.items

		if type(items) ~= "table" or #items == 0 then
			return nil
		end

		local it = items[math.random(#items)]

		return type(it) == "table" and it.name or nil
	end

	local function draw_for(m)
		local av = type(m) == "table" and m.available_items

		if type(av) ~= "table" then
			return nil
		end

		local d = { s = {} }

		if is_random("perks") then
			d.perk = pick_group(av.perks and av.perks.groups)
		end

		if is_random("primary_weapon") then
			d.primary = pick_group(av.primary_weapon and av.primary_weapon.groups)
		end

		local pool, taken = {}, {}

		for i = 5, 8 do
			local v = locked("stratagems", i)

			if v then
				taken[v] = true
			end
		end

		for _, g in ipairs(av.stratagems and av.stratagems.groups or {}) do
			for _, it in ipairs(type(g) == "table" and g.items or {}) do
				if type(it) == "table" and it.name and not taken[it.name] then
					pool[#pool + 1] = it.name
				end
			end
		end

		for i = 5, 8 do
			if is_random("stratagems", i) and #pool > 0 then
				local k = math.random(#pool)

				d.s[i] = pool[k]
				table.remove(pool, k)
			end
		end

		return d
	end

	local function draw_all(self)
		if not G.rule or self.is_proving_ground_trial or type(self.option_menus) ~= "table" then
			return
		end

		local players = self.parent and self.parent.players

		for i, m in ipairs(self.option_menus) do
			local pl = type(players) == "table" and players[i]

			if type(pl) == "table" and pl.pad_number ~= nil and pl.player_go and pl.player_go:owned() then
				G.draws[pl.pad_number] = draw_for(m)
				G.drawn = (G.drawn or 0) + 1
			end
		end
	end

	-- 固定 / 随机格按确定键不打开挑选列表：原版在「整套随机」时不开（handle_input 里 not random_loadout），
	-- 这里在选中了这种格子的那一下临时把 random_loadout 设上，handle_input 一结束马上放回（update 里会把它同步给网络，不能留着）。
	local blocked = {}

	local function hook_input(cls)
		local o_sel, o_input = cls.was_option_selected, cls.handle_input

		if type(o_sel) ~= "function" or type(o_input) ~= "function" then
			return
		end

		cls.was_option_selected = function(self, input, m, ...)
			local yes = o_sel(self, input, m, ...)

			if yes and G.rule and not self.is_proving_ground_trial and type(m) == "table" and not m.submenu and m.enabled
					and not m.random_loadout and type(m.loadout_menu) == "table" then
				local idx = m.current_selection_index

				if m.current_selection_index_cursor ~= nil and input and input.select_mouse then
					idx = m.current_selection_index_cursor
				end

				-- 鼠标点的是上面的预设按钮（原版 handle_input 里 select 为 false 且 loadout_hover_index_cursor 有值那一支，
				-- 直接 update_loadout_view 换预设，不开挑选列表）：不拦，让原版自己设 random_loadout
				local on_preset = input and input.select_mouse and not input.select and m.loadout_hover_index_cursor ~= nil

				if not on_preset and G.slot_mode(m.loadout_menu[idx]) then
					blocked[m] = { index = m.loadout_index }
					m.random_loadout = true
				end
			end

			return yes
		end

		cls.handle_input = function(self, ...)
			local res = { pcall(o_input, self, ...) }

			-- 只在预设没变时放回 false（我们临时设的）；预设被原版换了的话 update_loadout_view 已经设了对的值，不能盖掉
			for m, mark in pairs(blocked) do
				if m.loadout_index == mark.index then
					m.random_loadout = false
				end

				blocked[m] = nil
			end

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end
	end

	local function hook_draw(cls)
		local o_draw = cls.draw_menu

		if type(o_draw) ~= "function" then
			return
		end

		cls.draw_menu = function(self, ...)
			-- 第 10 个参数是这一栏玩家的 player_go（原版 draw 里 self:draw_menu(…, var_5_10)）；队友那一栏照原版画
			local go = select(10, ...)
			local mine = true

			if type(go) == "table" and type(go.owned) == "function" then
				local ok, yes = pcall(go.owned, go)

				mine = not ok or yes == true
			end

			if mine and G.rule and not self.is_proving_ground_trial and type(G.draw_menu) == "function" then
				return G.draw_menu(self, ...)
			end

			return o_draw(self, ...)
		end
	end

	local function hook_menu()
		local cls = rawget(_G, "MenuScreenLoadout")

		if type(cls) ~= "table" or rawget(cls, "_hb_host_loadout") or type(cls.update) ~= "function"
				or type(cls.on_exit) ~= "function" or type(cls.update_loadout_view) ~= "function" then
			return
		end

		local o_update, o_exit, o_view = cls.update, cls.on_exit, cls.update_loadout_view

		cls.update = function(self, ...)
			local res = { o_update(self, ...) }

			pcall(each_menu, self, G.rule and lock_menu or unlock_menu)

			return unpack(res)
		end

		cls.update_loadout_view = function(self, m, ...)
			pcall(unlock_menu, m)

			local res = { pcall(o_view, self, m, ...) }

			if G.rule and not self.is_proving_ground_trial and menu_owned(self, m) then
				pcall(lock_menu, m)
			end

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end

		cls.on_exit = function(self, ...)
			pcall(each_menu, self, unlock_menu)

			local ok, err = pcall(draw_all, self)

			if not ok then
				log("draw: " .. tostring(err))
			end

			return o_exit(self, ...)
		end
		hook_input(cls)
		hook_draw(cls)
		cls._hb_host_loadout = true
	end

	local function tick(dt)
		sync_frozen()
		refresh(dt)
		hook_inventory()
		hook_menu()
	end

	G.parse = from_string  -- 离线测试用
	G.merge_fn = merged
	G.draw_for = draw_for
	G.dump = to_string

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_hb_host_loadout") then
		local orig = wm.update

		wm.update = function(self, dt, ...)
			local ok, err = pcall(tick, dt)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				log(G.last_error)
			end

			return orig(self, dt, ...)
		end
		wm._hb_host_loadout = true
	end
end
