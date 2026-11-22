-- [profile tool] HellBox「角色」「队友」页的游戏这边（2026-11-08）。由 build.py 追加到 character_state_machine 末尾。
--
-- 做三件事（都只动主手柄 = 自己的存档）：
--   研究点：存档 user "research_samples"（样本数；10 个样本 = 1 研究点，上限 GameSettings.MAX_NUM_RESEARCH_SAMPLES = 3168）。
--     命令 "rp=N" 把研究点改成 N，零头样本保留。军械库开着时别改（它退出时会把自己记的旧数写回去）。
--   披风：存档 user "customization".cape = CustomizationSettings.cape 的序号。原版能穿 = 等级够（ProgressionSettings.can_use）
--     或 DLC 有（DlcSettings.can_use）或在 user "item_unlocks" 里（奖励）。命令 "unlockcape=序号" 只解锁；等级 / 奖励没解锁的
--     将名字加进 item_unlocks，玩家自己在军械库换装。DLC 没拥有的不给解锁。旧版界面命令也只解锁。
--   给好友点赞：原版游戏内菜单（MenuScreenMain）右键队友时，MenuScreenMain.is_friend 为真就不放"点赞""举报"
--     （手柄的快捷键、玩家列表按钮也一样）。开关打开时把 MenuScreenMain.is_friend 包成永远返回 false，好友也能在游戏里
--     右键点赞（举报也会出现）；点赞次数、对方加赞照原版走，对方不用装 mod。
--     is_friend 只有这个菜单用（查过 lua_src），房间隐私那边直接调 UserManager:is_friend，不受影响。
--     开机值是 build.py 从 mod\commend_friends.txt 填进来的 "@COMMEND_FRIENDS@"（"1" = 开）；命令 "cf=1" / "cf=0" 热切换。
--   研究点、披风改完都 SaveDataHelper:user_save 存盘。
--
-- 信箱表 G.t（每格一个 double），HellBox 用 mod\room_name_live.py 读写：
--   1-4 魔数；5 VERSION；6 命令请求号（HellBox 写，最后写）；7 已处理的请求号（这里写）；8 命令字节数；9 起 CMD_BYTES 格：命令 UTF-8。
--   OUT0 = 9 + CMD_BYTES 起是状态：OUT0 状态序号（写完内容最后加 1）；OUT0+1 状态字节数；OUT0+2 起 OUT_BYTES 格：状态 UTF-8。
--   状态每秒刷一次，一行一条：
--     ok=1 / ok=0;why=...   （0 = 现在拿不到存档或玩家）
--     rp=样本数;max=上限;per=10
--     lv=等级;cape=当前披风序号;cl=还能点赞几次
--     res=上一条命令的结果（"ok:..." / "err:..."）;seq=命令请求号;cf=好友点赞开关 1/0
--     C=序号|名字key|显示名|状态|要求   状态：on 已解锁（要求 = lv / dlc / reward / default / free）、lv 等级不够（要求 = 几级）、
--                                    rw 奖励没拿到、free 能直接解锁的「DLC」（要求 = ENT 号）、dlc 付费 DLC 没买（要求 = ENT 号）、
--                                    tut 新兵训练披风（军械库里永远选不了，只能这里直接穿）
--     W=序号|名字key|显示名|状态|要求   主武器（LoadoutSettings.primary_weapon，军械库里藏起来的不列），状态同上
--     S=序号|名字key|显示名|状态|要求|种类   战略配备（LoadoutSettings.stratagems，和军械库一样全列；种类 = stratagem_type）。
--                                    开局就带的四个（static_stratagems）算 on/default（2026-11-15 加）
--     lv 那行还有 xp=经验;maxlv=最高级
--
-- 2026-11-15 用户定（「解锁」页改名「潜兵」）：
--   披风全部列出来。社区（ENT015）、开发者（ENT016）、9 件训练场（ENT017～025）在游戏里按 DLC 发，但从来没卖过
--   （发给社区 / 开发组成员、训练场排行榜第一名；榜首常年被作弊占着，正常玩家拿不到），所以能直接解锁；
--   真正要买的 DLC 按拥有检测（DlcSettings.can_use，正式版 ENT001～012 本来就送），没买的不给解锁。
--   解锁 = 名字加进 item_unlocks：军械库（menu_screen_armory_profile / _unlocks）、出发前选装备（menu_screen_loadout）
--   都认这个表，DLC 物品也认（游戏自己的调试命令 unlock_all 就是这么解锁的）。
--   命令：unlockcape=序号 / unlockcapes=all / wearcape=序号（直接穿上，写 customization.cape，和军械库换装一样发
--   on_customized_character）/ unlockweapon=序号 / unlockweapons=all / level=N（经验改成第 N 级的起点，存档和角色都改）
--   / unlockstrat=序号 / unlockstrats=all（2026-11-15 加：战略配备，同样写 item_unlocks，军械库和出发选装备都认）
do
	local VERSION = 2 -- 2026-11-15：状态区 8192 → 16384 字节（加了战略配备）
	local CMD_BYTES = 256
	local OUT_BYTES = 16384
	local B0 = 9
	local OUT0 = B0 + CMD_BYTES
	local N = OUT0 + 2 + OUT_BYTES - 1
	local REFRESH = 1
	local G = ProfileToolMod or {}

	ProfileToolMod = G

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("27644437.5")
		t[2] = -tonumber("693147.125")
		t[3] = tonumber("2756.0625")
		t[4] = tonumber("8589934592.75")
		t[5] = VERSION
		G.t = t
		G.seq = 0
		G.result = ""
		G.commend_friends = "@COMMEND_FRIENDS@" == "1"
	end

	local t = G.t
	local timer = 0

	local function main_pad()
		return GameSettings.get_main_pad_number()
	end

	local function user_id()
		return UserManager:get_user_id(main_pad())
	end

	local function current_state()
		local boot = rawget(_G, "Boot")
		local machine = type(boot) == "table" and boot.state_machine

		return machine and machine:get_current_state()
	end

	local function my_player(state)
		local players = type(state) == "table" and state.players

		if type(players) ~= "table" then
			return nil
		end

		local mp = main_pad()

		for _, p in pairs(players) do
			if type(p) == "table" and p.pad_number == mp and p.player_go and p.player_go:exists() and p.player_go:owned() then
				return p
			end
		end
	end

	local function xp_now(state)
		local p = my_player(state)
		local xp = p and p.player_go:get("xp")

		return xp or SaveManager:user_get("player_xp", user_id()) or 0
	end

	local function rank_level(xp)
		local lv = 0

		for i, r in ipairs(ProgressionSettings.ranks) do
			if xp >= r.required_xp then
				lv = i
			end
		end

		return lv
	end

	local function item_rank(name, kind)
		for i, r in ipairs(ProgressionSettings.ranks) do
			local list = r.unlocks and r.unlocks[kind]

			if list then
				for _, n in ipairs(list) do
					if n == name then
						return i
					end
				end
			end
		end
	end

	local function in_list(list, name)
		for _, n in ipairs(list) do
			if n == name then
				return true
			end
		end

		return false
	end

	-- 返回 状态, 要求（2026-11-15 改：见文件头）
	local FREE_ENT = {
		ENT015 = true, ENT016 = true, ENT017 = true, ENT018 = true, ENT019 = true,
		ENT020 = true, ENT021 = true, ENT022 = true, ENT023 = true, ENT024 = true, ENT025 = true,
	}
	local TUTORIAL = "cus_cape_tutorial"

	local function item_status(name, kind, xp, ents, unlocks)
		if name == TUTORIAL then
			return "tut", ""
		end

		if DlcSettings.is_item_dlc(name) then
			local ent = DlcSettings.get_entitlement_id_by_item_name(name)

			if DlcSettings.can_use(name, ents) then
				return "on", "dlc"
			end

			if in_list(unlocks, name) then
				return "on", FREE_ENT[ent] and "free" or "reward"
			end

			return FREE_ENT[ent] and "free" or "dlc", ent
		end

		if ProgressionSettings.can_use(name, kind, xp) then
			return "on", item_rank(name, kind) == 1 and "default" or "lv"
		end

		if in_list(unlocks, name) then
			return "on", "reward"
		end

		local r = item_rank(name, kind)

		if r then
			return "lv", tostring(r)
		end

		return "rw", ""
	end

	local function cape_status(name, xp, ents, unlocks)
		return item_status(name, "customization", xp, ents, unlocks)
	end

	local function weapons()
		local out = {}

		for i, w in ipairs(LoadoutSettings.primary_weapon or {}) do
			if not w.hide_in_armory then
				out[#out + 1] = { i, w }
			end
		end

		return out
	end

	local function strats()
		local out = {}

		for i, s in ipairs(LoadoutSettings.stratagems or {}) do
			if not s.hide_in_armory then
				out[#out + 1] = { i, s }
			end
		end

		return out
	end

	local function strat_status(name, xp, ents, unlocks)
		if in_list(LoadoutSettings.static_stratagems or {}, name) then
			return "on", "default"
		end

		return item_status(name, "stratagems", xp, ents, unlocks)
	end

	local function standing()
		local uid = user_id()

		return SaveManager:user_get("standing_info", uid) or GameSettings.get_default_standing_settings(), uid
	end

	local function clean(s)
		return (tostring(s or ""):gsub("[|\n\r;]", " "))
	end

	local function build_status()
		local lines = {}
		local state = current_state()
		local uid = user_id()

		if not rawget(_G, "SaveManager") or not rawget(_G, "CustomizationSettings") or not rawget(_G, "ProgressionSettings") or uid == nil then
			lines[1] = "ok=0;why=save"

			return table.concat(lines, "\n")
		end

		lines[#lines + 1] = "ok=1"

		local samples = SaveManager:user_get("research_samples", uid) or 0

		lines[#lines + 1] = string.format("rp=%d;max=%d;per=%d", samples, GameSettings.MAX_NUM_RESEARCH_SAMPLES, GameSettings.NUM_RESEARCH_SAMPLES_PER_REQUISITION_POINT)

		local xp = xp_now(state)
		local custom = SaveManager:user_get("customization", uid) or {}
		local st = standing()

		lines[#lines + 1] = string.format("lv=%d;cape=%d;cl=%d;xp=%d;maxlv=%d", rank_level(xp), custom.cape or 1,
			st.commends_left or 0, xp, #ProgressionSettings.ranks)
		lines[#lines + 1] = string.format("res=%s;seq=%d;cf=%d", clean(G.result), G.seq, G.commend_friends and 1 or 0)

		local ents = DlcSettings.get_combined_entitlements(uid) or {}
		local unlocks = SaveManager:user_get("item_unlocks", uid) or {}

		for i, c in ipairs(CustomizationSettings.cape) do
			local status, need = cape_status(c.name, xp, ents, unlocks)
			local ok, shown = pcall(LocalizationManager.string, LocalizationManager, c.name)

			lines[#lines + 1] = string.format("C=%d|%s|%s|%s|%s", i, c.name, clean(ok and shown or c.name), status, need)
		end

		for _, item in ipairs(weapons()) do
			local i, w = item[1], item[2]
			local status, need = item_status(w.name, "primary_weapon", xp, ents, unlocks)
			local ok, shown = pcall(LocalizationManager.string, LocalizationManager, w.name)

			lines[#lines + 1] = string.format("W=%d|%s|%s|%s|%s", i, w.name, clean(ok and shown or w.name), status, need)
		end

		for _, item in ipairs(strats()) do
			local i, s = item[1], item[2]
			local status, need = strat_status(s.name, xp, ents, unlocks)
			local ok, shown = pcall(LocalizationManager.string, LocalizationManager, s.name)

			lines[#lines + 1] = string.format("S=%d|%s|%s|%s|%s|%s", i, s.name, clean(ok and shown or s.name), status, need,
				clean(s.stratagem_type))
		end

		-- 2026-11-18 V0.96 房主定配装：天赋名单（K=序号|名字key|显示名|状态|要求）和自己现在这套（L=天赋|主武器|战备5|6|7|8）
		for i, p in ipairs(LoadoutSettings.perks or {}) do
			if not p.hide_in_armory then
				local okst, status, need = pcall(item_status, p.name, "perks", xp, ents, unlocks)
				local ok, shown = pcall(LocalizationManager.string, LocalizationManager, p.name)

				lines[#lines + 1] = string.format("K=%d|%s|%s|%s|%s", i, p.name, clean(ok and shown or p.name),
					okst and status or "on", okst and need or "")
			end
		end

		local lo = SaveManager:user_get("loadout", uid)

		if type(lo) == "table" then
			local s = lo.stratagems or {}

			lines[#lines + 1] = "L=" .. table.concat({ clean(lo.perk or ""), clean(lo.primary_weapon or ""), clean(s[5] or ""),
				clean(s[6] or ""), clean(s[7] or ""), clean(s[8] or "") }, "|")
		end

		return table.concat(lines, "\n")
	end

	local function publish()
		local ok, text = pcall(build_status)

		if not ok then
			text = "ok=0;why=" .. clean(text)
		end

		if #text > OUT_BYTES then
			text = text:sub(1, OUT_BYTES)
		end

		for i = 1, #text do
			t[OUT0 + 1 + i] = text:byte(i)
		end

		t[OUT0 + 1] = #text
		t[OUT0] = t[OUT0] + 1
	end

	local function save_user(uid)
		if rawget(_G, "SaveDataHelper") and SaveDataHelper.user_save then
			SaveDataHelper:user_save(uid)
		end
	end

	local function set_research(points)
		local uid = user_id()
		local per = GameSettings.NUM_RESEARCH_SAMPLES_PER_REQUISITION_POINT
		local old = SaveManager:user_get("research_samples", uid) or 0
		local new = math.max(0, math.min(points * per + old % per, GameSettings.MAX_NUM_RESEARCH_SAMPLES))

		SaveManager:user_set("research_samples", new, uid)
		save_user(uid)

		return string.format("ok:研究点 %d", math.floor(new / per))
	end

	-- 把名字加进 item_unlocks（已经在里面的不重复加）
	local function add_unlocks(names)
		local uid = user_id()
		local unlocks = table.clone(SaveManager:user_get("item_unlocks", uid) or {})
		local n = 0

		for _, name in ipairs(names) do
			if not in_list(unlocks, name) then
				unlocks[#unlocks + 1] = name
				n = n + 1
			end
		end

		if n > 0 then
			SaveManager:user_set("item_unlocks", unlocks, uid)
		end

		save_user(uid)

		return n
	end

	local function unlockable(status)
		return status == "lv" or status == "rw" or status == "free"
	end

	local function statuses_now()
		local uid = user_id()

		return xp_now(current_state()), DlcSettings.get_combined_entitlements(uid) or {}, SaveManager:user_get("item_unlocks", uid) or {}
	end

	-- 2026-11-19 发行抢先版 用户定：随机掉落只掉自己（房主）解锁了的战略配备（等级到了、DLC 买了、奖励拿到、开局就带的），
	--   没解锁的在 HellBox 里灰掉，就算以前勾上了游戏里也不掉（hellbox_play.lua 的 drop_names 调这里）。
	--   返回 true / false；拿不到存档（还没登录等）返回 nil。
	local function save_ready()
		return rawget(_G, "SaveManager") and rawget(_G, "ProgressionSettings") and rawget(_G, "DlcSettings")
			and rawget(_G, "LoadoutSettings") and user_id() ~= nil
	end

	function G.strat_on(name)
		if not save_ready() then
			return nil
		end

		local xp, ents, unlocks = statuses_now()

		return (strat_status(name, xp, ents, unlocks)) == "on"
	end

	-- 同一天 用户定：「武装配置」固定格也只能定自己解锁了的（天赋 / 主武器 / 战备），host_loadout.lua 读房主自己的
	--   host-loadout.txt 时调这里，以前定了没解锁的那格当「自由」。kind = "perks" / "primary_weapon" / "stratagems"。
	function G.item_on(kind, name)
		if kind == "stratagems" then
			return G.strat_on(name)
		end

		if not save_ready() then
			return nil
		end

		local xp, ents, unlocks = statuses_now()

		return (item_status(name, kind, xp, ents, unlocks)) == "on"
	end

	-- 同一份名单写给 HellBox（游戏关着时 HellBox 也能按上次看到的灰掉）：hellbox/strat-unlocks.txt
	--   名字带种类前缀（stratagem_ / weapon_ / perk_），三种放在一个 on= 里。
	--   HBUNLK1 / on=解锁了的战备名逗号串。只在变了时写；写成功才记。
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

	local function write_unlocks()
		if not save_ready() then
			return
		end

		local xp, ents, unlocks = statuses_now()
		local on = {}

		for _, item in ipairs(strats()) do
			local name = item[2].name

			if (strat_status(name, xp, ents, unlocks)) == "on" then
				on[#on + 1] = name
			end
		end

		for _, item in ipairs(weapons()) do
			local name = item[2].name

			if (item_status(name, "primary_weapon", xp, ents, unlocks)) == "on" then
				on[#on + 1] = name
			end
		end

		for _, p in ipairs(LoadoutSettings.perks or {}) do
			if not p.hide_in_armory then
				local ok, status = pcall(item_status, p.name, "perks", xp, ents, unlocks)

				if ok and status == "on" then
					on[#on + 1] = p.name
				end
			end
		end

		local text = "HBUNLK1\non=" .. table.concat(on, ",") .. "\n"

		if text == G.unlocks_text then
			return
		end

		local appdata = os.getenv and os.getenv("APPDATA")

		if not appdata then
			return
		end

		local d = appdata .. "/Arrowhead/Helldivers/hellbox/"
		local f = io.open(d .. "strat-unlocks.tmp", "wb")

		if not f then
			return
		end

		local okw = f:write(text)
		local okc = f:close()

		if okw and okc and swap_in(d .. "strat-unlocks.tmp", d .. "strat-unlocks.txt") then
			G.unlocks_text = text
		end
	end

	local function unlock_cape(index)
		local c = CustomizationSettings.cape[index]

		if not c then
			return "err:没有这个披风"
		end

		local status = cape_status(c.name, statuses_now())

		if status == "dlc" then
			return "err:付费 DLC 披风要先在 Steam 买"
		elseif status == "tut" then
			return "err:新兵训练披风不用解锁，直接点「穿上」"
		elseif status == "on" then
			return "ok:已经解锁了"
		end

		add_unlocks({ c.name })

		return "ok:披风已解锁"
	end

	local function unlock_all_capes()
		local xp, ents, unlocks = statuses_now()
		local names = {}

		for _, c in ipairs(CustomizationSettings.cape) do
			if unlockable((cape_status(c.name, xp, ents, unlocks))) then
				names[#names + 1] = c.name
			end
		end

		return string.format("ok:解锁了 %d 件披风", add_unlocks(names))
	end

	local function wear_cape(index)
		local c = CustomizationSettings.cape[index]

		if not c then
			return "err:没有这个披风"
		end

		local status = cape_status(c.name, statuses_now())

		if status ~= "on" and status ~= "tut" then
			return "err:先解锁这件披风"
		end

		local uid = user_id()
		local custom = table.clone(SaveManager:user_get("customization", uid) or {})

		custom.cape = index

		SaveManager:user_set("customization", custom, uid)
		save_user(uid)

		local state = current_state()
		local delegate = type(state) == "table" and state.event_delegate

		if delegate and delegate.trigger then
			pcall(delegate.trigger, delegate, "on_customized_character", main_pad())
		end

		return "ok:披风已换上"
	end

	local function unlock_weapon(index)
		local w = (LoadoutSettings.primary_weapon or {})[index]

		if not w or w.hide_in_armory then
			return "err:没有这把武器"
		end

		local status = item_status(w.name, "primary_weapon", statuses_now())

		if status == "dlc" then
			return "err:付费 DLC 武器要先在 Steam 买"
		elseif status == "on" then
			return "ok:已经解锁了"
		end

		add_unlocks({ w.name })

		return "ok:武器已解锁"
	end

	local function unlock_all_weapons()
		local xp, ents, unlocks = statuses_now()
		local names = {}

		for _, item in ipairs(weapons()) do
			local w = item[2]

			if unlockable((item_status(w.name, "primary_weapon", xp, ents, unlocks))) then
				names[#names + 1] = w.name
			end
		end

		return string.format("ok:解锁了 %d 把武器", add_unlocks(names))
	end

	local function unlock_strat(index)
		local s = (LoadoutSettings.stratagems or {})[index]

		if not s or s.hide_in_armory then
			return "err:没有这个战略配备"
		end

		local status = strat_status(s.name, statuses_now())

		if status == "dlc" then
			return "err:付费 DLC 战略配备要先在 Steam 买"
		elseif status == "on" then
			return "ok:已经解锁了"
		end

		add_unlocks({ s.name })

		return "ok:战略配备已解锁"
	end

	local function unlock_all_strats()
		local xp, ents, unlocks = statuses_now()
		local names = {}

		for _, item in ipairs(strats()) do
			local s = item[2]

			if unlockable((strat_status(s.name, xp, ents, unlocks))) then
				names[#names + 1] = s.name
			end
		end

		return string.format("ok:解锁了 %d 个战略配备", add_unlocks(names))
	end

	local function set_level(n)
		local ranks = ProgressionSettings.ranks
		local r = ranks[n]

		if not r then
			return string.format("err:等级要在 1 到 %d 之间", #ranks)
		end

		local uid = user_id()
		local xp = r.required_xp

		SaveManager:user_set("player_xp", xp, uid)

		local p = my_player(current_state())

		if p then
			p.player_go:set("xp", xp)
		end

		save_user(uid)

		return string.format("ok:等级改成 %d", n)
	end

	local function run(cmd)
		local key, value = cmd:match("^(%w+)=(.*)$")
		local n = tonumber(value)

		if key == "rp" and n then
			return set_research(math.floor(n))
		elseif (key == "unlockcape" or key == "cape") and n then
			return unlock_cape(math.floor(n))
		elseif key == "unlockcapes" then
			return unlock_all_capes()
		elseif key == "wearcape" and n then
			return wear_cape(math.floor(n))
		elseif key == "unlockweapon" and n then
			return unlock_weapon(math.floor(n))
		elseif key == "unlockweapons" then
			return unlock_all_weapons()
		elseif key == "unlockstrat" and n then
			return unlock_strat(math.floor(n))
		elseif key == "unlockstrats" then
			return unlock_all_strats()
		elseif key == "level" and n then
			return set_level(math.floor(n))
		elseif key == "cf" then
			G.commend_friends = value == "1"

			return G.commend_friends and "ok:好友点赞已打开" or "ok:好友点赞已关闭"
		end

		return "err:看不懂的命令"
	end

	local function poll_mailbox()
		local seq = t[6]

		if seq == G.seq then
			return false
		end

		G.seq = seq

		local len = t[8]
		local bytes = {}

		if type(len) == "number" and len >= 0 and len <= CMD_BYTES and len % 1 == 0 then
			for i = 1, len do
				local b = t[B0 + i - 1]

				if type(b) ~= "number" or b < 0 or b > 255 or b % 1 ~= 0 then
					bytes = nil

					break
				end

				bytes[i] = string.char(b)
			end
		else
			bytes = nil
		end

		if bytes then
			local ok, res = pcall(run, table.concat(bytes))

			G.result = ok and res or "err:" .. tostring(res)
		else
			G.result = "err:命令坏了"
		end

		t[7] = seq

		return true
	end

	-- 游戏内菜单的"是不是好友"：开关打开时一律当不是，右键好友也有点赞
	local function hook_friend()
		local cls = rawget(_G, "MenuScreenMain")

		if type(cls) ~= "table" or type(cls.is_friend) ~= "function" or cls.is_friend == G.is_friend then
			return
		end

		local orig = cls.is_friend

		G.is_friend = function(self, ...)
			if G.commend_friends then
				return false
			end

			return orig(self, ...)
		end
		cls.is_friend = G.is_friend
	end

	-- 2026-11-21 用户定：同一个人每轮只能点一次赞，好友、路人都算。一轮 = 原版两次补点赞次数之间
	--   （MatchmakingUtility.refresh_standing 补次数时改 standing_info.last_refresh，它变了就是新一轮，大约每周四）。
	--   每周 10 次、所有人共用照原版不变，只是不能把几次都点给同一个人。
	--   人 = 玩家 owner（peer id，Steam 上就是 Steam ID，跨局不变）| 名字（同一台机器的 2P 靠名字分开）。
	--   记在 %APPDATA%\Arrowhead\Helldivers\hellbox\commended.txt：第 1 行 HBCMD1，第 2 行轮次，后面一行一个人。
	--   原版确认框点「是」、剩余次数真的少了 1 才记下；本轮点过的人再点，弹一个「这周已经给这名玩家点过赞了」代替原版确认框。
	local CMD_FILE = "commended.txt"

	local function hb_dir()
		local appdata = os.getenv and os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/")
	end

	local function standing()
		return SaveManager:user_get("standing_info", user_id())
	end

	-- 这一轮的标记；存档里还没有点赞记录（从没点过）时返回 nil
	local function round_id()
		local s = standing()

		return s and type(s.last_refresh) == "number" and string.format("%.0f", s.last_refresh) or nil
	end

	local function commend_key(info)
		local go = type(info) == "table" and info.player_go

		if not go or not go:exists() then
			return nil
		end

		local ok, owner = pcall(go.owner, go)
		local key = tostring(ok and owner or "") .. "|" .. tostring(go:get("name") or "")

		return (key:gsub("[\r\n]", " "))
	end

	local function load_commended()
		if G.commended then
			return G.commended
		end

		local list = { round = "", who = {} }
		local d = hb_dir()
		local f = d and io.open(d .. CMD_FILE, "rb")

		if f then
			local text = f:read("*a") or ""

			f:close()

			local lines = {}

			for line in text:gmatch("[^\r\n]+") do
				lines[#lines + 1] = line
			end

			if lines[1] == "HBCMD1" then
				list.round = lines[2] or ""

				for i = 3, #lines do
					list.who[lines[i]] = true
				end
			end
		end

		G.commended = list

		return list
	end

	local function remember_commend(key)
		local list = load_commended()
		local round = round_id() or ""

		if list.round ~= round then
			list.round, list.who = round, {}
		end

		list.who[key] = true

		local d = hb_dir()
		local f = d and io.open(d .. CMD_FILE, "wb")

		if not f then
			return
		end

		local lines = { "HBCMD1", list.round }

		for k in pairs(list.who) do
			lines[#lines + 1] = k
		end

		f:write(table.concat(lines, "\n") .. "\n")
		f:close()
	end

	-- 游戏是中文就用中文提示（看原版点赞确认框那句话里有没有汉字）
	local function game_is_zh()
		local ok, s = pcall(LocalizationManager.string_format, LocalizationManager, "menu_ingame_commend_prompt")

		return ok and type(s) == "string" and s:find("[\228-\233]") ~= nil
	end

	local function show_already_commended(self, info)
		local zh = game_is_zh()

		self:push_menu("are_you_sure_player", {
			simple_confirmation = true,
			player_gos = { info.player_go },
			title = zh and "这周已经给这名玩家点过赞了" or "Already commended this week",
			subtitle = zh and "同一个人每周只能点一次赞，每周次数补满后可以再点。"
				or "You can commend the same player once per week. Try again after your weekly commends refill.",
			callback_params = {},
			callback_object = {
				on_dialog_confirmation = function()
					self:pop_menu()
				end
			}
		})
	end

	local function hook_commend()
		local cls = rawget(_G, "MenuScreenMain")

		if type(cls) ~= "table" or type(cls.trigger_commend_dialog) ~= "function" or cls.trigger_commend_dialog == G.commend_hook then
			return
		end

		local orig = cls.trigger_commend_dialog

		G.commend_hook = function(self, info, ...)
			local okk, key = pcall(commend_key, info)

			if not okk or not key then
				return orig(self, info, ...)
			end

			local list = load_commended()
			local round = round_id()

			if round and list.round == round and list.who[key] then
				show_already_commended(self, info)

				return
			end

			-- 原版在确认框的回调里才扣次数：把这次推出来的确认框的回调包一层，扣了才记下这个人
			local own_push = rawget(self, "push_menu")
			local push = self.push_menu

			self.push_menu = function(me, name, params, ...)
				local cb = type(params) == "table" and params.callback_object

				if name == "are_you_sure_player" and not params.simple_confirmation and type(cb) == "table"
					and type(cb.on_dialog_confirmation) == "function" then
					local inner = cb.on_dialog_confirmation

					cb.on_dialog_confirmation = function(c, yes, ...)
						local s = standing()
						local before = s and s.commends_left or GameSettings.STANDING_STARTING_COMMENDS
						local res = { inner(c, yes, ...) }
						local s2 = standing()
						local after = s2 and s2.commends_left

						if yes and type(after) == "number" and after < before then
							local ok, err = pcall(remember_commend, key)

							if not ok and rawget(_G, "HellBoxLog") then
								HellBoxLog("profile_tool", "commend: " .. tostring(err))
							end
						end

						return unpack(res)
					end
				end

				return push(me, name, params, ...)
			end

			local res = { pcall(orig, self, info, ...) }

			self.push_menu = own_push

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end
		cls.trigger_commend_dialog = G.commend_hook
	end

	local function tick(dt)
		local changed = poll_mailbox()

		hook_friend()
		hook_commend()

		timer = timer - (dt or 0)

		if changed or timer <= 0 then
			timer = REFRESH

			publish()

			local ok, err = pcall(write_unlocks)

			if not ok and rawget(_G, "HellBoxLog") then
				HellBoxLog("profile_tool", "unlocks: " .. tostring(err))
			end
		end
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local ok, err = pcall(tick, dt)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = err
				if rawget(_G, "HellBoxLog") then HellBoxLog("profile_tool", G.last_error) end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
