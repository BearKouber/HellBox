-- [spawn rules] HellBox「出怪」页的游戏这边（2026-11-10，HD1-032）。由 build.py 追加到 character_state_machine 末尾。
--
-- 改对局里的出怪：警报增援、巡逻队、报复关波次，三条来源各自可以选：
--   vanilla  原版不动（= 这条来源恢复默认）
--   only     只出选中的怪（数量照原版；选中的怪按当前阵营过滤，不跨阵营）
--   mult     种类照原版，数量乘倍数
--   none     这条路不出怪
-- 警报和巡逻的"选中怪"各记一份（ua / up），互不影响。全部对局内热切换；reset 恢复原版。
-- 另有 v / uv：载具和首领单独放出来的兵（步兵战车屁股放畸形人这类），和三条来源分开设置，
-- 默认原版不动 —— 改警报 / 巡逻不会再把坦克放出来的兵换掉。
--
-- 报复关专用（HellBox「报复关」页）：
--   glogic=race:难度   让这族的报复关都用"这个难度"的波次表（比如 N15 图用 N5 的轮换逻辑）；
--                      实际是改 genocide_settings_<race>.lua 里每条波次的难度区间
--   gmap=组名=怪*只+怪*只,...   直接换掉报复关某一组的出怪（种类和数量都换）
--   glogic=off / gmap=          恢复原样
--   gcap=N   报复关同时在场最多几只（原版 16；0 = 原版）。只在报复关刷波那一步换掉，警报 / 巡逻 / 载具放兵仍按原版。
--            另外：一个套餐加起来比上限还多时，原版会永远降不下来、波数卡死；这里自动把它拆成几小包（每包 ≤ 上限一半）陆续降。
-- 怪怎么刷、刷在哪照原版走，只换"出什么、几只"。
--
-- 信箱表 G.t（每格一个 double），HellBox 用 mod\room_name_live.py 读写（MAGIC_SPAWN）：
--   1-4 魔数；5 VERSION；6 命令请求号（HellBox 写，最后写）；7 已处理的请求号（这里写）；8 命令字节数；9 起 CMD_BYTES 格：命令 UTF-8。
--   OUT0 = 9 + CMD_BYTES 起是状态：OUT0 状态序号（写完内容最后加 1）；OUT0+1 状态字节数；OUT0+2 起 OUT_BYTES 格：状态 UTF-8。
--   状态每秒刷一次，一行一条（k=v）：
--     ok=1 / ok=0
--     where=game|menu|boot   host=1|0   race=bugs|cyborgs|illuminates
--     a=...;p=...;g=...      v=...      mult=2
--     ua=...;up=...;ug=...;uv=...     （各来源选中的怪，和命令里写的一样）
--     glogic=bugs:5    gmap=组名=怪*只+...（报复关的改法）
--     gcap=0|N;gcapnow=实际上限;gwave=当前波数;gq=排队套餐数;gqn=排队只数;galive=场上活着的;gsplit=拆过几包
--     gwl=最近 8 波抽到的套餐（波数:套餐名*只数+... 波数:...，空格分隔，新的在后；只数是改过以后、拆包以前）
--     spawned=N;blocked=N
--     res=上一条命令的结果   err=最近一次内部错误
--
-- 命令（整条重新发一遍，先写的键后写的键都算；分号分隔的 k=v）：
--   reset
--   a=only;p=mult;g=vanilla      警报 / 巡逻 / 报复
--   v=only                       载具 / 首领放兵（只出选中 / none / vanilla）
--   mult=2                       倍数（mult 模式用）
--   ua=bug_tank/bug_tank*1,bug_warrior/bug_warrior*2   警报"只出选中"用的怪
--   up=...;ug=...                同上，巡逻 / 报复关
--   uv=...                       载具放兵"只出选中"用的怪
--   glogic=bugs:5                报复关用哪套难度逻辑（off = 恢复原样）
--   gmap=bug_warrior_x2=bug_tank/bug_tank*2,...   换掉报复关某一组的怪和数量
--   gcap=32                      报复关同时在场上限（0 = 原版 16）
--   units=...                    老写法：三条来源共用一份（同一份同时写进 ua/up/ug）
--
-- 已知限制：出怪是房主电脑决定的。自己是房主时整队按这里的设置；当客机时改不了出怪。
do
	local VERSION = 6
	local CMD_BYTES = 4096
	local OUT_BYTES = 8192
	local B0 = 9
	local OUT0 = B0 + CMD_BYTES
	local N = OUT0 + 2 + OUT_BYTES - 1
	local REFRESH = 1
	local MODE_OK = { vanilla = true, only = true, mult = true, none = true }
	local RACE_PREFIX = { bugs = "bug_", cyborgs = "cyborg_", illuminates = "illuminate_" }
	local UNIT_RE = "^[a-z0-9_]+/[a-z0-9_]+$"
	local G = SpawnRulesMod or {}

	SpawnRulesMod = G

	local function default_cfg()
		return { a = "vanilla", p = "vanilla", g = "vanilla", v = "vanilla", mult = 2, multg = 2, multp = 2, gcap = 0, acap = 0, pcap = 0, cap = 0, vn = 0,
			ua = {}, up = {}, ug = {}, uv = {} }
	end

	if not G.t or G.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("24494897.5")
		t[2] = -tonumber("173205.375")
		t[3] = tonumber("2071.875")
		t[4] = tonumber("137438953472.625")
		t[5] = VERSION
		G.t = t
		G.seq = 0
		G.result = ""
		G.cfg = default_cfg()
		G.glogic = ""
		G.gmap = {}
		G.gdiff = setmetatable({}, { __mode = "k" })
		G.gbase = setmetatable({}, { __mode = "k" })
		G.spawned = 0
		G.blocked = 0
		G.errors = 0
		G.gsplit = 0
		G.gsplit_n = 0
		G.gwl = {}
	end

	G.amap = G.amap or {}
	G.pmap = G.pmap or {}
	G.alogic_want = G.alogic_want or ""
	G.plogic_want = G.plogic_want or ""
	G.awl = G.awl or {}
	G.alias = G.alias or setmetatable({}, { __mode = "k" })

	local t = G.t
	local timer = 0

	--------------------------------------------------------------------------
	-- 命令解析
	--------------------------------------------------------------------------
	local function clean_path(p)
		p = (p or ""):gsub("^%s+", ""):gsub("%s+$", "")

		if string.sub(p, 1, 11) == "characters/" then
			p = string.sub(p, 12)
		end

		if not string.match(p, UNIT_RE) then
			return nil
		end

		return "characters/" .. p
	end

	-- "a/b*3,c/d" -> {{path="characters/a/b", n=3}, ...}
	local function parse_units(s)
		local list = {}

		for part in string.gmatch(s or "", "[^,]+") do
			local p, n = string.match(part, "^%s*([^%*]+)%*%s*([%d%.]+)%s*$")

			if not p then
				p, n = part, "1"
			end

			local path = clean_path(p)
			local amount = tonumber(n)

			if path and amount and amount >= 1 then
				list[#list + 1] = { path = path, n = math.floor(amount) }
			end
		end

		return list
	end

	-- "a/b*2+a/c*3" -> 报复关一组的怪
	local function parse_group(s)
		local list = {}

		for part in string.gmatch(s or "", "[^+]+") do
			local p, n = string.match(part, "^%s*([^%*]+)%*%s*([%d%.]+)%s*$")

			if not p then
				p, n = part, "1"
			end

			local path = clean_path(p)
			local amount = tonumber(n)

			if path and amount and amount >= 1 then
				list[#list + 1] = { path = path, n = math.floor(amount) }
			end
		end

		return list
	end

	-- 报复关：让这族用某一难度的轮换逻辑（改每条波次的难度区间）
	local function restore_gdiff()
		for wave, name in pairs(G.gdiff) do
			local dr = wave.difficulty_range
			local o = G.gorig[name]

			if type(dr) == "table" and o then
				dr.min = o.min
				dr.max = o.max
			end
		end

		G.gdiff = setmetatable({}, { __mode = "k" })
	end

	-- 运行中的报复关波次表（由 ObjectiveGenocideComponent.update_masters 抓到）
	local function wave_list(race)
		local g = G.gen_groups

		return type(g) == "table" and g[race] or nil
	end

	local function apply_gdiff_now()
		local spec = G.glogic_want or ""

		if spec == "" then
			restore_gdiff()
			G.glogic = ""
			G.gapplied_waves = nil
			G.gapplied_spec = nil

			return 0
		end

		local race, diff = string.match(spec, "^%s*([%a]+)%s*:%s*(%d+)%s*$")

		diff = tonumber(diff)

		if not race or not diff then
			restore_gdiff()
			G.glogic = ""

			return 0
		end

		local waves = wave_list(race)

		if not waves then
			G.glogic = ""

			return 0
		end

		if waves == G.gapplied_waves and spec == G.gapplied_spec then
			G.glogic = race .. ":" .. tostring(diff)

			return 0
		end

		restore_gdiff()

		local n = 0

		G.gorig = G.gorig or {}

		for i, wave in ipairs(waves) do
			local dr = type(wave) == "table" and wave.difficulty_range

			if type(dr) == "table" then
				-- 原版区间按"族#第几条"只记一次：连续换难度不会越改越窄。
				-- 不能按套餐名记：游戏里有同名套餐（赛博格 cyborg_wave_berserker_elites 一条 N8~12、一条 N14~15），
				-- 按名字记会把 N14~15 那条当成 N8~12，在 N10 被打开，一直刷 10 只屠夫。
				local key = race .. "#" .. tostring(i)
				local o = G.gorig[key]

				if not o then
					o = { min = dr.min, max = dr.max }
					G.gorig[key] = o
				end

				G.gdiff[wave] = key

				if (o.min or 0) <= diff and diff <= (o.max or 99) then
					dr.min, dr.max = -1, 100
				else
					dr.min, dr.max = 999, -999
				end

				n = n + 1
			end
		end

		G.glogic = race .. ":" .. tostring(diff)
		G.gapplied_waves = waves
		G.gapplied_spec = spec

		return n
	end

	local function apply_gdiff(spec)
		G.glogic_want = (type(spec) == "string" and spec ~= "off") and spec or ""

		return apply_gdiff_now()
	end

	-- 报复关：直接换掉某一组刷的怪
	local function restore_gmap()
		for g, units in pairs(G.gbase) do
			g.units = units
		end

		G.gbase = setmetatable({}, { __mode = "k" })
	end

	local function apply_gmap(map)
		restore_gmap()
		G.gmap = map or {}

		local groups = rawget(_G, "GenocideGroupSettings")

		G.gmap_table = type(groups) == "table" and groups or nil

		if type(groups) ~= "table" then
			return 0
		end

		local n = 0

		for key, units in pairs(G.gmap) do
			local g = groups[key]

			if type(g) == "table" then
				G.gbase[g] = g.units

				local out = {}

				for _, u in ipairs(units) do
					out[#out + 1] = { unit_path = u.path, amount = u.n }
				end

				g.units = out
				n = n + 1
			end
		end

		return n
	end

	-- "组名=怪*只+怪*只,组名=..." -> {组名 = {{path, n}, ...}}；写法不对返回 nil, 出错的那段
	local function parse_map(v)
		local map = {}

		for entry in string.gmatch(v .. ",", "([^,]+),") do
			local key, expr = string.match(entry, "^%s*([%w_]+)%s*=%s*(.-)%s*$")

			if key then
				map[key] = parse_group(expr)
			elseif string.gsub(entry, "%s", "") ~= "" then
				return nil, entry
			end
		end

		return map
	end

	local function set_logic(src, spec)
		G[src .. "logic_want"] = (type(spec) == "string" and spec ~= "off") and spec or ""
		G.logic_ver = (G.logic_ver or 0) + 1
	end

	local function apply_command(text)
		text = (text or ""):gsub("%s+$", "")

		if text == "reset" then
			G.cfg = default_cfg()
			apply_gdiff("off")
			apply_gmap({})
			G.amap, G.pmap = {}, {}
			set_logic("a", "off")
			set_logic("p", "off")
			G.cfg_ver = (G.cfg_ver or 0) + 1

			return "ok:reset"
		end

		local cfg = G.cfg or default_cfg()
		local any = false
		local glogic, gmap = nil, nil
		local has_glogic, has_gmap = false, false

		for part in string.gmatch(text, "[^;]+") do
			local k, v = string.match(part, "^%s*([%w_]+)%s*=%s*(.-)%s*$")

			if k then
				if k == "a" or k == "p" or k == "g" or k == "v" then
					if MODE_OK[v] then
						cfg[k] = v
						any = true
					else
						return "err:" .. k .. " 模式不认识：" .. tostring(v)
					end
				elseif k == "mult" or k == "multg" or k == "multp" then
					local n = tonumber(v)

					if n and n > 0 and n <= 20 then
						cfg[k] = n
						any = true
					else
						return "err:倍数要 0～20 之间的数"
					end
				elseif k == "ua" or k == "up" or k == "ug" or k == "uv" then
					cfg[k] = parse_units(v)
					any = true
				elseif k == "units" then
					-- 老写法：三条来源共用一份
					local list = parse_units(v)

					cfg.ua, cfg.up, cfg.ug = list, list, list
					any = true
				elseif k == "gcap" or k == "acap" or k == "pcap" then
					local n = tonumber(v)

					if n and (n == 0 or (n >= 1 and n <= 64)) then
						cfg[k] = math.floor(n)
						any = true
					else
						return "err:上限要 0（原版）或 1～64"
					end
				elseif k == "vn" then
					-- 步兵战车每次放几只（2026-11-18 用户要求放回来）：0 = 原版（照它的 spawn_amount）
					local n = tonumber(v)

					if n and n >= 0 and n <= 50 then
						cfg.vn = math.floor(n)
						any = true
					else
						return "err:放兵数量要 0（原版）～50"
					end
				elseif k == "cap" then
					-- 场上上限（2026-11-18 用户定）：0 = 原版 16；17～300 = 固定这么多；-1 = 破限（自动，最多 1000）
					local n = tonumber(v)

					if n and (n == -1 or (n >= 0 and n <= 300)) then
						cfg.cap = math.floor(n)
						any = true
					else
						return "err:场上上限要 -1（破限）或 0～300"
					end
				elseif k == "spread" then
					-- 出生时散开（2026-11-16）：0 原版 / 1 小 / 2 中 / 3 大
					local n = tonumber(v)

					if n and n >= 0 and n <= 3 then
						cfg.spread = math.floor(n)
						any = true
					else
						return "err:散开要 0～3"
					end
				elseif k == "glogic" then
					glogic = v
					has_glogic = true
					any = true
				elseif k == "alogic" or k == "plogic" then
					set_logic(string.sub(k, 1, 1), v)
					any = true
				elseif k == "gmap" or k == "amap" or k == "pmap" then
					local map, bad = parse_map(v)

					if not map then
						return "err:捆的写法不对：" .. tostring(bad)
					end

					if k == "gmap" then
						gmap = map
						has_gmap = true
					else
						G[k] = map
					end

					any = true
				else
					return "err:不认识的键：" .. k
				end
			end
		end

		if not any then
			return "err:空的命令"
		end

		G.cfg = cfg
		G.cfg_ver = (G.cfg_ver or 0) + 1

		if has_glogic then
			apply_gdiff(glogic)
		end

		if has_gmap then
			apply_gmap(gmap)
		end

		return "ok:" .. string.format("a=%s;p=%s;g=%s", cfg.a, cfg.p, cfg.g)
	end

	--------------------------------------------------------------------------
	-- 当前对局
	--------------------------------------------------------------------------
	local function game_state()
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if not sm then
			return nil, nil
		end

		local name = sm:get_current_state_name()

		return name, sm:get_current_state()
	end

	local function race()
		local em = G.em

		if em and type(em.mission_enemy) == "string" and RACE_PREFIX[em.mission_enemy] then
			return em.mission_enemy
		end

		local _, st = game_state()
		local gl = type(st) == "table" and st.generated_level

		if type(gl) == "table" and RACE_PREFIX[gl.enemy] then
			return gl.enemy
		end

		return nil
	end

	-- 2026-11-14：data_live.lua（数据修改页）每秒读文件，按当前阵营挑一份出怪设置调这两个
	G.apply = apply_command
	G.race = race

	local function host()
		local _, st = game_state()

		return type(st) == "table" and st.is_server == true
	end

	local function active()
		local _, st = game_state()

		if type(st) ~= "table" then
			return nil
		end

		-- 2026-11-18 V0.96 用户定：在别人房间（客机）时自己的出怪设置不生效（游戏按 lobby:is_host() 填 is_server）
		if st.is_server == false then
			return nil
		end

		return G.cfg
	end

	--------------------------------------------------------------------------
	-- 自动上限（2026-11-16 用户定，代替手填的 gcap / acap / pcap）
	--   改过的来源：一波 / 一次警报整包下完，不拆、不排队；巡逻按换捆后变大的比例放大原版上限。
	--   全局上限（GameSettings.MAX_NUM_ALLOWED_ENEMIES，坦克放兵、报复关都看它）：出怪改过、或怪物块改了
	--   召唤数量时抬到上限（lim），坦克放兵不再被「场上满 16」吞掉；不限坦克放坦克。没改的来源在自己那一步照原版。
	--   （2026-11-18 起天花板看 cap，见下面 lim）
	--------------------------------------------------------------------------
	-- 2026-11-18 用户定（V0.96）：上限改回能填（数据页滑条 16～300，最右边隔开一格「破限」）。
	--   cap=0（或 ≤16）= 原版：不管改没改都按原版上限（倍数大了会拆包、一点点补）。
	--   cap=N（17～300）= 固定 N：全局上限 N，改过的来源按 N 整包下（比 N 大的拆成小包）。
	--   cap=-1 = 破限：上面 V0.94 那套自动上限，天花板 BREAK = 1000。
	local BREAK = 1000

	local function lim(cfg)
		local c = type(cfg) == "table" and tonumber(cfg.cap) or 0

		if c < 0 then
			return BREAK
		elseif c > 16 then
			return math.min(math.floor(c), 300)
		end

		return nil
	end

	local function src_mod(cfg, s)
		if type(cfg) ~= "table" then
			return false
		end

		local map = (s == "g" and G.gmap) or (s == "a" and G.amap) or (s == "p" and G.pmap) or {}

		return (cfg[s] ~= nil and cfg[s] ~= "vanilla") or next(map) ~= nil
	end

	local function drops_changed()
		local ep = rawget(_G, "EnemyParamsMod")

		if type(ep) ~= "table" then
			return false
		end

		for _, o in pairs(ep.ov or {}) do
			if type(o) == "table" and o["enemy_info.spawn_amount"] ~= nil then
				return true
			end
		end

		return (ep.common or {})["enemy_info.spawn_amount"] ~= nil
	end

	local function any_mod(cfg)
		return type(cfg) == "table" and (src_mod(cfg, "g") or src_mod(cfg, "a") or src_mod(cfg, "p")
			or (cfg.v ~= nil and cfg.v ~= "vanilla") or (tonumber(cfg.vn) or 0) > 0 or drops_changed())
	end

	-- 这个来源改过、上限也放开了：返回放到多少；否则 nil（照原版）
	local function lift(cfg, s)
		local L = lim(cfg)

		return L and src_mod(cfg, s) and L or nil
	end

	-- 每帧（警报 update 里）摆好全局上限的底：固定 N = N；破限 = 改过放到 1000；原版 = 16
	local function set_global(cfg)
		local gs = rawget(_G, "GameSettings")

		if type(gs) ~= "table" or type(gs.MAX_NUM_ALLOWED_ENEMIES) ~= "number" then
			return
		end

		G.cap_orig = G.cap_orig or gs.MAX_NUM_ALLOWED_ENEMIES
		local L = lim(cfg)

		if L and (tonumber(cfg.cap) or 0) > 0 then
			gs.MAX_NUM_ALLOWED_ENEMIES = L
		else
			gs.MAX_NUM_ALLOWED_ENEMIES = L and any_mod(cfg) and L or G.cap_orig
		end
		G.gmax = gs.MAX_NUM_ALLOWED_ENEMIES
	end

	--------------------------------------------------------------------------
	-- 换队 / 换波
	--------------------------------------------------------------------------
	local function sum_amount(group)
		local total = 0

		for _, u in ipairs(group and group.units or {}) do
			total = total + (tonumber(u.amount) or 0)
		end

		return total
	end

	local function race_ok(path, race_prefix)
		if not race_prefix then
			return true
		end

		local name = string.match(path, "/([^/]+)$") or ""

		return string.sub(name, 1, #race_prefix) == race_prefix
	end

	-- 选中的怪里属于这一族的；空 = 这族没有选中的怪
	local function selected(list, r)
		local pre = RACE_PREFIX[r]
		local out = {}

		for _, u in ipairs(list or {}) do
			if race_ok(u.path, pre) then
				out[#out + 1] = u
			end
		end

		return out
	end

	-- 按权重把 total 只摊到选中的怪上
	local function spread(sel, total)
		if #sel == 0 or total < 1 then
			return nil
		end

		local cycle = {}

		for _, u in ipairs(sel) do
			for _ = 1, math.max(1, math.floor(u.n or 1)) do
				cycle[#cycle + 1] = u.path
			end
		end

		local counts, order = {}, {}

		for i = 1, total do
			local p = cycle[(i - 1) % #cycle + 1]

			if not counts[p] then
				order[#order + 1] = p
			end

			counts[p] = (counts[p] or 0) + 1
		end

		local units = {}

		for _, p in ipairs(order) do
			units[#units + 1] = { unit_path = p, amount = counts[p] }
		end

		return { units = units }
	end

	local function scale_group(group, mult)
		local units = {}

		for _, u in ipairs(group and group.units or {}) do
			units[#units + 1] = { unit_path = u.unit_path, amount = math.max(1, math.floor((tonumber(u.amount) or 1) * mult + 0.5)) }
		end

		if #units == 0 then
			return nil
		end

		return { units = units }
	end

	-- 各来源选中的怪（警报 ua / 巡逻 up / 报复 ug 各一份）
	local function unit_list(cfg, source)
		return cfg["u" .. source] or {}
	end

	-- 按模式换掉一组怪；返回 nil = 不刷
	-- only 没勾怪（或勾的全是别的族）时退回原版这一组，不会把整局怪都拦光
	local function transform_group(cfg, source, group, r)
		local mode = cfg[source]

		if mode == "vanilla" then
			return group
		elseif mode == "none" then
			return nil
		elseif mode == "only" then
			return spread(selected(unit_list(cfg, source), r), sum_amount(group)) or group
		elseif mode == "mult" then
			local m = source == "g" and cfg.multg or cfg.mult

			return scale_group(group, m or 2) or group
		end

		return group
	end

	-- EnemyGroupSettings 里这张捆表叫什么（警报 / 巡逻共用这张表，按名字查 amap / pmap）
	local function egs_key(group)
		local egs = rawget(_G, "EnemyGroupSettings")

		if type(egs) ~= "table" or type(group) ~= "table" then
			return nil
		end

		if G.egs_tab ~= egs or not G.egs_rev or G.egs_rev[group] == nil then
			local rev = setmetatable({}, { __mode = "k" })

			for k, v in pairs(egs) do
				if type(v) == "table" then
					rev[v] = k
				end
			end

			G.egs_tab, G.egs_rev = egs, rev
		end

		return G.egs_rev[group]
	end

	-- 按 {{path, n}} 做一张新捆表（其它字段照抄原表）；空 = 这一捆不出（返回 nil）
	local function make_group(base, list)
		if #list == 0 then
			return nil
		end

		local g = {}

		for k, v in pairs(base or {}) do
			g[k] = v
		end

		local units = {}

		for _, u in ipairs(list) do
			units[#units + 1] = { unit_path = u.path, amount = u.n }
		end

		g.units = units

		return g
	end

	-- 警报这一捆实际刷什么：拆出来的小包原样；原版模式下改过的捆按 amap；其它模式照旧
	local function alarm_group(cfg, group)
		if G.alias[group] then
			return group
		end

		if cfg.a == "vanilla" then
			local list = G.amap[egs_key(group) or ""]

			if list then
				return make_group(group, list)
			end

			return group
		end

		return transform_group(cfg, "a", group, race())
	end

	--------------------------------------------------------------------------
	-- 挂点：EncounterManager.spawn_group（警报 + 报复关）
	--------------------------------------------------------------------------
	local function own_call(fn, ...)
		G.own = true
		local res = { pcall(fn, ...) }
		G.own = false

		if not res[1] then
			G.errors = (G.errors or 0) + 1
			G.last_error = tostring(res[2])
			if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end

			return
		end

		return true, unpack(res, 2)
	end

	local function hook_encounter(cls)
		if type(cls) ~= "table" or type(cls.spawn_group) ~= "function" or rawget(cls, "_spawn_rules_hooked") then
			return
		end

		local orig = cls.spawn_group

		G.orig_spawn_group = orig
		cls.spawn_group = function(self, pos, group, wave_id, cost, ...)
			local extra = { ... }

			G.em = self

			if G.own then
				return orig(self, pos, group, wave_id, cost, unpack(extra))
			end

			local cfg = active()

			if not cfg then
				return orig(self, pos, group, wave_id, cost, unpack(extra))
			end

			local source = wave_id and "a" or "g"

			if cfg[source] == "vanilla" and (source == "g" or G.alias[group] or not next(G.amap)) then
				return orig(self, pos, group, wave_id, cost, unpack(extra))
			end

			local ok, err = pcall(function()
				local g

				if source == "a" then
					g = alarm_group(cfg, group)
				else
					g = transform_group(cfg, source, group, race())
				end

				if g == nil then
					G.blocked = (G.blocked or 0) + 1

					return
				end

				G.spawned = (G.spawned or 0) + sum_amount(g)

				-- 顺带告诉 ai_drill 这一组是我们自己刷的（训练关同时开两套设置时不互相抢）
				local drill = rawget(_G, "AIDrillMod")

				if type(drill) == "table" then
					drill.own = true
				end

				own_call(orig, self, pos, g, wave_id, cost, unpack(extra))

				if type(drill) == "table" then
					drill.own = false
				end
			end)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end

				return orig(self, pos, group, wave_id, cost, unpack(extra))
			end
		end
		cls._spawn_rules_hooked = true
	end

	--------------------------------------------------------------------------
	-- 挂点：EncounterManager.spawn_enemy（装甲车放兵这类单只刷）
	--------------------------------------------------------------------------
	local function hook_spawn_enemy(cls)
		if type(cls) ~= "table" or type(cls.spawn_enemy) ~= "function" or rawget(cls, "_spawn_rules_enemy_hooked") then
			return
		end

		local orig = cls.spawn_enemy

		cls.spawn_enemy = function(self, path, ...)
			G.em = self

			if G.own then
				return orig(self, path, ...)
			end

			local cfg = active()

			if not cfg or cfg.v == "vanilla" then
				return orig(self, path, ...)
			end

			local ok, block = pcall(function()
				local mode = cfg.v

				if mode == "none" then
					return true
				elseif mode == "only" then
					local sel = selected(unit_list(cfg, "v"), race())

					if #sel > 0 and type(path) == "string" then
						local i = ((G.single_i or 0) % #sel) + 1

						G.single_i = i
						path = sel[i].path
					end
				end

				return false
			end)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(block)
				if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end

				return orig(self, path, ...)
			end

			if block then
				G.blocked = (G.blocked or 0) + 1

				return
			end

			return orig(self, path, ...)
		end
		cls._spawn_rules_enemy_hooked = true
	end

	--------------------------------------------------------------------------
	-- 挂点：CyborgIfvStateSpawnGroup.on_enter（步兵战车开门放兵，2026-11-18 V0.96 放兵数量放回块里）
	--   原版 on_enter 里 spawns_left = 设置表的 spawn_amount（cyborg_ifv_states.lua:517），之后每隔 spawn_interval
	--   放一只、放完回去打。vn > 0 时把 spawns_left 换成 vn（比怪物块里改的「召唤数量」优先）。
	--------------------------------------------------------------------------
	local function hook_ifv(cls)
		if type(cls) ~= "table" or type(cls.on_enter) ~= "function" or rawget(cls, "_spawn_rules_ifv_hooked") then
			return
		end

		local orig = cls.on_enter

		cls.on_enter = function(unit, data, ...)
			local res = { orig(unit, data, ...) }

			pcall(function()
				local cfg = active()
				local n = cfg and tonumber(cfg.vn) or 0

				if n > 0 and type(data) == "table" and type(data.state) == "table" then
					data.state.spawns_left = n
					G.vn_used = (G.vn_used or 0) + 1
				end
			end)

			return unpack(res)
		end
		cls._spawn_rules_ifv_hooked = true
	end

	--------------------------------------------------------------------------
	-- 挂点：PatrolManager.spawn_patrol（巡逻队；直接调 spawn_manager，不走 spawn_group）
	--------------------------------------------------------------------------
	local function hook_patrol(cls)
		if type(cls) ~= "table" or type(cls.spawn_patrol) ~= "function" or rawget(cls, "_spawn_rules_hooked") then
			return
		end

		local orig = cls.spawn_patrol

		cls.spawn_patrol = function(self, patrol, ...)
			local cfg = active()

			G.pm = self

			if not cfg then
				return orig(self, patrol, ...)
			end

			local info = type(patrol) == "table" and type(patrol.patrol_settings) == "table"
				and patrol.patrol_settings.group_info
			local groups = rawget(_G, "EnemyGroupSettings")
			local old = info and type(groups) == "table" and groups[info]
			local g = nil

			if old then
				if cfg.p == "none" then
					G.blocked = (G.blocked or 0) + 1

					return false
				elseif cfg.p == "only" then
					g = spread(selected(unit_list(cfg, "p"), race()), sum_amount(old))
				elseif cfg.p == "mult" then
					g = scale_group(old, cfg.multp or cfg.mult)
				elseif cfg.p == "vanilla" and G.pmap[info] then
					-- 自己改：只换巡逻刷的这一捆，警报那边用同名捆不受影响
					g = make_group(old, G.pmap[info])

					if not g then
						G.blocked = (G.blocked or 0) + 1

						return false
					end
				end
			end

			local gs = rawget(_G, "GameSettings")

			if type(self.max_num_patrol_units) == "number" then
				G.plimit = self.max_num_patrol_units
			end

			-- 自动上限：巡逻换捆后比原版大几倍，巡逻上限就放大几倍（至少原版），保证这一队刷得出来
			local cap = 0

			if g and old and type(self.max_num_patrol_units) == "number" then
				local n_old, n_new = sum_amount(old), sum_amount(g)

				if n_old > 0 and n_new > n_old and lim(cfg) then
					cap = math.min(lim(cfg), math.max(n_new, math.ceil(self.max_num_patrol_units * n_new / n_old)))
				end
			end

			-- 没换捆也没改上限（或没勾怪）：按原版刷这一队
			if not g and cap <= 0 then
				return orig(self, patrol, ...)
			end

			if g then
				G.spawned = (G.spawned or 0) + sum_amount(g)
				-- 换掉队表这一项再调原版：原版会按队表算人头、走它自己的排队流程
				groups[info] = g
			end

			-- 巡逻上限：只在刷这一队时换（巡逻自己的单位上限；全局上限至少放到同样大）
			local base_max, base_units = nil, nil

			if cap > 0 then
				if type(gs) == "table" and type(gs.MAX_NUM_ALLOWED_ENEMIES) == "number" then
					base_max = gs.MAX_NUM_ALLOWED_ENEMIES
					gs.MAX_NUM_ALLOWED_ENEMIES = math.max(base_max, cap)
				end

				base_units = self.max_num_patrol_units
				self.max_num_patrol_units = cap
			end

			local ok, res = pcall(orig, self, patrol, ...)

			if base_max then
				gs.MAX_NUM_ALLOWED_ENEMIES = base_max
			end

			if cap > 0 then
				self.max_num_patrol_units = base_units
			end

			if g then
				groups[info] = old
			end

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(res)
				if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end

				return false
			end

			return res
		end
		cls._spawn_rules_hooked = true
	end

	--------------------------------------------------------------------------
	-- 挂点：ObjectiveGenocideComponent.update_masters（抓到运行中的报复关波次表）
	--------------------------------------------------------------------------
	-- 报复关：一个套餐一共几只
	local function package_total(pkg)
		local groups = rawget(_G, "GenocideGroupSettings")
		local ev = type(pkg) == "table" and type(pkg.events) == "table" and pkg.events[1]
		local n = 0

		if type(groups) ~= "table" or type(ev) ~= "table" or type(ev.groups) ~= "table" then
			return 0
		end

		for _, ref in ipairs(ev.groups) do
			local g = type(ref) == "table" and groups[ref.group]

			if type(g) == "table" and type(g.units) == "table" then
				for _, u in ipairs(g.units) do
					n = n + (tonumber(u.amount) or 0)
				end
			end
		end

		return n
	end

	local function shallow(src)
		local out = {}

		for k, v in pairs(src) do
			out[k] = v
		end

		return out
	end

	-- 把一个套餐拆成几小包（每包不超过 size 只）；小包的组临时登记进 GenocideGroupSettings
	local function split_package(pkg, size)
		local groups = rawget(_G, "GenocideGroupSettings")
		local ev = pkg.events[1]
		local pieces = {}
		local cur, cur_n = {}, 0

		local function flush()
			if cur_n > 0 then
				G.gsplit_n = (G.gsplit_n or 0) + 1

				local refs = {}

				for i, item in ipairs(cur) do
					local key = "__hellbox_split_" .. tostring(G.gsplit_n) .. "_" .. tostring(i)
					local g = shallow(item.base)

					g.units = item.units
					groups[key] = g
					refs[#refs + 1] = { group = key, delay = item.delay }
				end

				local ev2 = shallow(ev)

				ev2.groups = refs

				local p2 = shallow(pkg)

				p2.events = { ev2 }
				p2.hellbox_piece = true
				pieces[#pieces + 1] = p2
			end

			cur, cur_n = {}, 0
		end

		for _, ref in ipairs(ev.groups) do
			local g = type(ref) == "table" and groups[ref.group]

			if type(g) == "table" and type(g.units) == "table" then
				for _, u in ipairs(g.units) do
					local left = math.floor(tonumber(u.amount) or 0)

					while left > 0 do
						if cur_n >= size then
							flush()
						end

						local take = math.min(left, size - cur_n)
						local item = cur[#cur]

						if not item or item.base ~= g or item.ref ~= ref then
							item = { base = g, ref = ref, units = {}, delay = ref.delay }
							cur[#cur + 1] = item
						end

						item.units[#item.units + 1] = { unit_path = u.unit_path, amount = take }
						cur_n = cur_n + take
						left = left - take
					end
				end
			end
		end

		flush()

		return #pieces > 0 and pieces or nil
	end

	-- 排队里一包比上限还大的（原版会永远降不下来、波数卡死）：拆成几小包，每包不超过上限一半
	local function split_queue(st, cap)
		local q = st.queued_wave_groups

		if type(q) ~= "table" then
			return
		end

		-- 「倍数」模式：刷的时候每捆再乘倍数，按乘完的只数判断、拆的时候按原只数折回去
		local cfg = G.cfg or {}
		local m = (cfg.g == "mult" and tonumber(cfg.multg)) or 1
		local size = math.max(1, math.floor(math.floor(cap / 2) / m))
		local i = 1

		while i <= #q do
			local pkg = q[i]
			local pieces = nil

			if type(pkg) == "table" and not pkg.hellbox_piece and package_total(pkg) * m > cap then
				pieces = split_package(pkg, size)
			end

			if pieces then
				table.remove(q, i)

				for j = #pieces, 1, -1 do
					table.insert(q, i, pieces[j])
				end

				i = i + #pieces
				G.gsplit = (G.gsplit or 0) + 1
			else
				i = i + 1
			end
		end
	end

	-- 记录：现在第几波、排队多少、每一波抽到了哪些套餐
	local function note_wave(st)
		local q = type(st.queued_wave_groups) == "table" and st.queued_wave_groups or {}
		local qn = 0

		for _, pkg in ipairs(q) do
			qn = qn + package_total(pkg)
		end

		G.gq = #q
		G.gqn = qn

		local w = tonumber(st.current_wave) or 0

		if w ~= (G.gwave or 0) then
			-- 波数变小 = 换了一局，旧记录清掉
			if w < (G.gwave or 0) then
				G.gwl = {}
				G.gsplit = 0
			end

			G.gwave = w

			if w > 0 then
				local names = {}

				for _, pkg in ipairs(q) do
					names[#names + 1] = tostring(pkg.name or "?") .. "*" .. tostring(package_total(pkg))
				end

				local log = G.gwl or {}

				log[#log + 1] = tostring(w) .. ":" .. table.concat(names, "+")

				while #log > 8 do
					table.remove(log, 1)
				end

				G.gwl = log
			end
		end
	end

	local function count_alive(comp)
		local em = type(comp) == "table" and comp.entity_manager
		local n = 0

		if type(em) ~= "table" or type(em.all_slaves_iterator) ~= "function" then
			return 0
		end

		local ea = rawget(_G, "EntityAux")

		for unit in em:all_slaves_iterator("enemy") do
			local dead = false

			if type(ea) == "table" and type(ea.state) == "function" then
				local ok, hs = pcall(ea.state, unit, "health")

				dead = ok and type(hs) == "table" and hs.is_dead
			end

			if not dead then
				n = n + 1
			end
		end

		return n
	end

	local function hook_genocide()
		local cls = rawget(_G, "ObjectiveGenocideComponent")

		if type(cls) ~= "table" or type(cls.update_masters) ~= "function" or rawget(cls, "_spawn_rules_hooked") then
			return
		end

		local orig = cls.update_masters

		cls.update_masters = function(self, list, dt, ...)
			if type(list) == "table" then
				for _, inst in pairs(list) do
					local s = type(inst) == "table" and inst.settings
					local oi = type(s) == "table" and s.objective_info
					local g = type(oi) == "table" and oi.groups

					if type(g) == "table" then
						if g ~= G.gen_groups then
							G.gen_groups = g
							apply_gdiff_now()
						end

						break
					end
				end
			end

			local gs = rawget(_G, "GameSettings")
			local base = nil

			if type(gs) == "table" and type(gs.MAX_NUM_ALLOWED_ENEMIES) == "number" then
				base = gs.MAX_NUM_ALLOWED_ENEMIES
				G.cap_orig = G.cap_orig or base
			end

			-- 自动上限：报复关改过且上限放开 = 按上限整波下（lift）；没改 = 原版 16（全局被抬高时这一步也压回原版）
			local use = lift(G.cfg, "g") or G.cap_orig or 16
			local cap = (base and base ~= use) and use or 0

			G.gcapnow = use

			local function each_state(fn)
				if type(list) ~= "table" then
					return
				end

				local ok, err = pcall(function()
					for _, inst in pairs(list) do
						local st = type(inst) == "table" and inst.state

						if type(st) == "table" then
							fn(st)
						end
					end
				end)

				if not ok then
					G.errors = (G.errors or 0) + 1
					G.last_error = tostring(err)
					if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end
				end
			end

			each_state(function(st) split_queue(st, use) end)

			-- 上限只在报复关刷波这一步换掉，调完马上还原（警报 / 巡逻 / 载具放兵照旧）
			if base and cap > 0 then
				gs.MAX_NUM_ALLOWED_ENEMIES = cap
			end

			local res = { pcall(orig, self, list, dt, ...) }

			if base and cap > 0 then
				gs.MAX_NUM_ALLOWED_ENEMIES = base
			end

			-- 这一帧刚抽的新波也马上拆（下一次刷之前），顺便记账
			each_state(function(st)
				note_wave(st)
				split_queue(st, use)
			end)

			local ok_alive, alive = pcall(count_alive, self)

			if ok_alive then
				G.galive = alive
			end

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end
		cls._spawn_rules_hooked = true
	end

	--------------------------------------------------------------------------
	-- 警报 / 巡逻：选难度逻辑、按改后只数算包、拆包、上限
	--------------------------------------------------------------------------
	local function parse_spec(spec)
		local r, d = string.match(spec or "", "^%s*([%a_]+)%s*:%s*(%d+)%s*$")

		return r, tonumber(d)
	end

	local function in_range(entry, diff)
		local dr = type(entry) == "table" and entry.difficulty_range

		return type(dr) == "table" and (dr.min or 0) <= diff and diff <= (dr.max or 99)
	end

	-- 照 EncounterManager.init_host（:65-99）重新选这一难度的警报套餐，分易 / 中 / 难三档
	local function rebuild_alarm(em, diff)
		local es = rawget(_G, "EncounterSettings")
		local list = type(es) == "table" and em.mission_enemy and es[em.mission_enemy]

		if type(list) ~= "table" or type(diff) ~= "number" then
			return false
		end

		local sel = {}

		for _, w in ipairs(list) do
			if in_range(w, diff) then
				sel[#sel + 1] = w
			end
		end

		if #sel == 0 then
			return false
		end

		table.sort(sel, function(x, y) return (x.cost or 0) < (y.cost or 0) end)

		local easy, med, hard = {}, {}, {}
		local n = #sel

		for i, w in ipairs(sel) do
			if i <= n / 3 then
				easy[#easy + 1] = w
			elseif i <= n / 3 * 2 then
				med[#med + 1] = w
			else
				hard[#hard + 1] = w
			end
		end

		em.waves_easy, em.waves_medium, em.waves_hard = easy, med, hard
		em.min_cost, em.max_cost = sel[1].cost, sel[#sel].cost

		return true
	end

	local function rebuild_patrol(pm, diff)
		local ps = rawget(_G, "PatrolSettings")
		local list = type(ps) == "table" and pm.mission_enemy and ps[pm.mission_enemy]

		if type(list) ~= "table" or type(diff) ~= "number" then
			return false
		end

		local out = {}

		for _, p in ipairs(list) do
			if in_range(p, diff) then
				out[#out + 1] = p
			end
		end

		if #out == 0 then
			return false
		end

		pm.applicable_patrol_groups = out

		return true
	end

	-- 这台管理器按 alogic / plogic 换过没有；没设过就别动（原版进关时已经选好了）
	local function sync_logic(mgr, src, rebuild)
		local spec = G[src .. "logic_want"] or ""
		local mark = "_hb_" .. src .. "logic"

		if mgr[mark] == spec then
			return false
		end

		if spec == "" and mgr[mark] == nil then
			mgr[mark] = ""

			return false
		end

		local r, d = parse_spec(spec)
		local diff = mgr.mission_difficulty

		if spec ~= "" and r == mgr.mission_enemy and d then
			diff = d
		end

		rebuild(mgr, diff)
		mgr[mark] = spec

		return true
	end

	local function alarm_wave_size(cfg, wave)
		local egs = rawget(_G, "EnemyGroupSettings")
		local n = 0

		if type(egs) ~= "table" or type(wave) ~= "table" then
			return 0
		end

		for _, ev in ipairs(wave.events or {}) do
			for _, ref in ipairs(ev.groups or {}) do
				local g = egs[ref.group]

				if type(g) == "table" then
					local e = alarm_group(cfg, g)

					if e then
						n = n + sum_amount(e)
					end
				end
			end
		end

		return n
	end

	-- 原版进关时按原捆算好了每包几只（wave_sizes）；改过捆 / 倍数后按实际刷的重算，上限判断才准
	local function resize_alarm(em, cfg)
		em.wave_sizes = em.wave_sizes or {}

		for _, key in ipairs({ "waves_easy", "waves_medium", "waves_hard", "selected_waves" }) do
			for _, w in ipairs(em[key] or {}) do
				em.wave_sizes[w] = alarm_wave_size(cfg, w)
			end
		end
	end

	-- 一包警报比上限还大：原版场上清空也放不下就整次作废。拆成每包不超过上限一半的小包
	local function split_alarm_wave(em, cfg, wave, size)
		local egs = rawget(_G, "EnemyGroupSettings")
		local ev1 = (wave.events or {})[1] or {}
		local pieces = {}
		local cur, cur_n = {}, 0

		local function flush()
			if cur_n > 0 then
				G.gsplit_n = (G.gsplit_n or 0) + 1

				local refs = {}

				for i, item in ipairs(cur) do
					local key = "__hellbox_a_" .. tostring(G.gsplit_n) .. "_" .. tostring(i)
					local g = shallow(item.base)

					g.units = item.units
					egs[key] = g
					G.alias[g] = true
					refs[#refs + 1] = { group = key, delay = 0 }
				end

				local p2 = shallow(wave)

				p2.events = { { delay = ev1.delay or 0, distance = ev1.distance or 0, groups = refs } }
				p2.hellbox_piece = true
				em.wave_sizes[p2] = cur_n
				pieces[#pieces + 1] = p2
			end

			cur, cur_n = {}, 0
		end

		for _, ev in ipairs(wave.events or {}) do
			for _, ref in ipairs(ev.groups or {}) do
				local g = egs[ref.group]
				local e = type(g) == "table" and alarm_group(cfg, g)

				if e then
					for _, u in ipairs(e.units or {}) do
						local left = math.floor(tonumber(u.amount) or 0)

						while left > 0 do
							if cur_n >= size then
								flush()
							end

							local take = math.min(left, size - cur_n)
							local item = cur[#cur]

							if not item or item.src ~= e then
								item = { src = e, base = e, units = {} }
								cur[#cur + 1] = item
							end

							item.units[#item.units + 1] = { unit_path = u.unit_path, amount = take }
							cur_n = cur_n + take
							left = left - take
						end
					end
				end
			end
		end

		flush()

		return #pieces > 0 and pieces or nil
	end

	local function split_alarm(em, cfg, limit)
		local q = em.selected_waves

		if type(q) ~= "table" or type(em.wave_sizes) ~= "table" then
			return
		end

		local size = math.max(1, math.floor(limit / 2))
		local i = 1

		while i <= #q do
			local w = q[i]
			local pieces = nil

			if type(w) == "table" and not w.hellbox_piece and (em.wave_sizes[w] or 0) > limit then
				pieces = split_alarm_wave(em, cfg, w, size)
			end

			if pieces then
				table.remove(q, i)

				for j = #pieces, 1, -1 do
					table.insert(q, i, pieces[j])
				end

				i = i + #pieces
				G.asplit = (G.asplit or 0) + 1
			else
				i = i + 1
			end
		end
	end

	local function prep_alarm(em, cfg)
		G.em = em

		local relogic = sync_logic(em, "a", rebuild_alarm)

		if relogic or em._hb_cfg_ver ~= G.cfg_ver then
			resize_alarm(em, cfg)
			em._hb_cfg_ver = G.cfg_ver
		end

		local gs = rawget(_G, "GameSettings")
		local base = type(gs) == "table" and tonumber(gs.MAX_NUM_ALLOWED_ENEMIES) or 16

		G.alimit = em.max_num_enemies
		G.cap_orig = G.cap_orig or base

		-- 自动上限：警报改过 = 整次警报下完，不拆
		local limit = lift(cfg, "a") or math.min(tonumber(em.max_num_enemies) or base, G.cap_orig or base)

		split_alarm(em, cfg, limit)
	end

	local function hook_alarm_update(cls)
		if type(cls) ~= "table" or type(cls.update) ~= "function" or rawget(cls, "_spawn_rules_upd_hooked") then
			return
		end

		local orig = cls.update

		cls.update = function(self, dt, ...)
			local cfg = active()

			pcall(set_global, cfg)

			if not cfg or type(self) ~= "table" or type(self.waves_easy) ~= "table" then
				return orig(self, dt, ...)
			end

			local ok, err = pcall(prep_alarm, self, cfg)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end
			end

			local alift = lift(cfg, "a")
			local amod = alift ~= nil
			local gs = rawget(_G, "GameSettings")
			local base_max = type(gs) == "table" and gs.MAX_NUM_ALLOWED_ENEMIES

			-- 警报没改、全局也没抬：完全原版
			if not amod and (type(base_max) ~= "number" or base_max == (G.cap_orig or base_max)) then
				return orig(self, dt, ...)
			end

			-- 警报这一步：改过且上限放开 = 自己和全局都放到上限（lift）；没改 = 全局压回原版 16，照原版刷
			local base_em = self.max_num_enemies

			if type(base_max) == "number" then
				gs.MAX_NUM_ALLOWED_ENEMIES = alift or (G.cap_orig or base_max)
			end

			if amod then
				self.max_num_enemies = alift
			end

			local res = { pcall(orig, self, dt, ...) }

			if type(base_max) == "number" then
				gs.MAX_NUM_ALLOWED_ENEMIES = base_max
			end

			if amod then
				self.max_num_enemies = base_em
			end

			if not res[1] then
				error(res[2], 0)
			end

			return unpack(res, 2)
		end

		-- 记录：每次警报抽到了哪些套餐（只数按改后算）
		if type(cls.build_encounter) == "function" then
			local orig_build = cls.build_encounter

			cls.build_encounter = function(self, ...)
				local res = orig_build(self, ...)

				pcall(function()
					local cfg = active() or default_cfg()
					local names = {}

					for _, w in ipairs(type(res) == "table" and res or {}) do
						names[#names + 1] = tostring(w.name or "?") .. "*" .. tostring(alarm_wave_size(cfg, w))
					end

					G.anum = (G.anum or 0) + 1

					local log = G.awl or {}

					log[#log + 1] = tostring(G.anum) .. ":" .. table.concat(names, "+")

					while #log > 6 do
						table.remove(log, 1)
					end

					G.awl = log
				end)

				return res
			end
		end

		cls._spawn_rules_upd_hooked = true
	end

	local function hook_patrol_update(cls)
		if type(cls) ~= "table" or type(cls.update_host) ~= "function" or rawget(cls, "_spawn_rules_upd_hooked") then
			return
		end

		local orig = cls.update_host

		cls.update_host = function(self, dt, ...)
			pcall(function()
				if type(self) == "table" and type(self.applicable_patrol_groups) == "table" then
					G.pm = self

					if type(self.max_num_patrol_units) == "number" then
						G.plimit = self.max_num_patrol_units
					end

					sync_logic(self, "p", rebuild_patrol)
				end
			end)

			return orig(self, dt, ...)
		end
		cls._spawn_rules_upd_hooked = true
	end

	--------------------------------------------------------------------------
	-- 状态区
	--------------------------------------------------------------------------
	local function fmt_units(list)
		local out = {}

		for _, u in ipairs(list or {}) do
			out[#out + 1] = (string.gsub(u.path, "^characters/", "")) .. "*" .. tostring(u.n or 1)
		end

		return table.concat(out, ",")
	end

	local function fmt_map(map)
		local out = {}

		for key, units in pairs(map or {}) do
			-- 一组里的怪用 + 连（和命令写法一样），组和组之间才用逗号；以前用逗号，HellBox 读回会丢掉后面的怪
			out[#out + 1] = key .. "=" .. (string.gsub(fmt_units(units), ",", "+"))
		end

		table.sort(out)

		return table.concat(out, ",")
	end

	local function fmt_gmap()
		return fmt_map(G.gmap)
	end

	local function clean(s)
		return (tostring(s or ""):gsub("[|\r\n]", " "))
	end

	local function build_status()
		local cfg = G.cfg
		local where, st = game_state()
		local lines = {}
		local gl = type(st) == "table" and st.generated_level

		lines[#lines + 1] = "ok=1"
		lines[#lines + 1] = string.format("where=%s;host=%d;race=%s", clean(type(st) == "table" and where or "boot"),
			host() and 1 or 0, tostring(race() or ""))
		lines[#lines + 1] = string.format("mission=%s;diff=%s", clean(type(gl) == "table" and gl.mission_type_name or ""),
			tostring(type(gl) == "table" and gl.difficulty or ""))

		if type(st) == "table" and not st.is_training then
			lines[#lines + 1] = "training=0"
		end

		lines[#lines + 1] = string.format("a=%s;p=%s;g=%s;v=%s", cfg.a, cfg.p, cfg.g, cfg.v)
		lines[#lines + 1] = string.format("mult=%s;multg=%s", tostring(cfg.mult), tostring(cfg.multg))
		lines[#lines + 1] = "ua=" .. clean(fmt_units(cfg.ua))
		lines[#lines + 1] = "up=" .. clean(fmt_units(cfg.up))
		lines[#lines + 1] = "ug=" .. clean(fmt_units(cfg.ug))
		lines[#lines + 1] = "uv=" .. clean(fmt_units(cfg.uv))
		lines[#lines + 1] = "glogic=" .. clean(G.glogic_want or "")
		lines[#lines + 1] = "gready=" .. (type(G.gen_groups) == "table" and "1" or "0")
		lines[#lines + 1] = "gmap=" .. clean(fmt_gmap())
		lines[#lines + 1] = string.format("gcap=%d;gcapnow=%d;gwave=%d;gq=%d;gqn=%d;galive=%d;gsplit=%d",
			cfg.gcap or 0, G.gcapnow or 0, G.gwave or 0, G.gq or 0, G.gqn or 0, G.galive or 0, G.gsplit or 0)
		lines[#lines + 1] = "gwl=" .. clean(table.concat(G.gwl or {}, " "))
		lines[#lines + 1] = "amap=" .. clean(fmt_map(G.amap))
		lines[#lines + 1] = "pmap=" .. clean(fmt_map(G.pmap))
		lines[#lines + 1] = "alogic=" .. clean(G.alogic_want or "")
		lines[#lines + 1] = "plogic=" .. clean(G.plogic_want or "")
		lines[#lines + 1] = string.format("cap=%d;glimit_now=%d;vn=%d;vn_used=%d", tonumber((G.cfg or {}).cap) or 0,
			tonumber(G.gmax) or 0, tonumber((G.cfg or {}).vn) or 0, G.vn_used or 0)
		lines[#lines + 1] = string.format("acap=%d;pcap=%d;multp=%s;alimit=%d;plimit=%d;glimit=%d;anum=%d;asplit=%d",
			cfg.acap or 0, cfg.pcap or 0, tostring(cfg.multp or cfg.mult), tonumber(G.alimit) or 0, tonumber(G.plimit) or 0,
			tonumber(G.cap_orig) or 16, G.anum or 0, G.asplit or 0)
		lines[#lines + 1] = "awl=" .. clean(table.concat(G.awl or {}, " "))
		lines[#lines + 1] = string.format("spawned=%d;blocked=%d", G.spawned or 0, G.blocked or 0)
		lines[#lines + 1] = "seq=" .. tostring(G.seq or 0)
		lines[#lines + 1] = "res=" .. clean(G.result)

		if G.last_error then
			lines[#lines + 1] = "err=" .. clean(G.last_error)
		end

		return table.concat(lines, "\n")
	end

	local function publish()
		local ok, text = pcall(build_status)

		if not ok then
			text = "ok=0\nerr=" .. clean(text)
		end

		local bytes = { text:byte(1, -1) }

		if #bytes > OUT_BYTES then
			bytes = { text:sub(1, OUT_BYTES):byte(1, -1) }
		end

		for i = 1, #bytes do
			t[OUT0 + 1 + i] = bytes[i]
		end

		t[OUT0 + 1] = #bytes

		-- 序号最后写：HellBox 看到序号变了才读
		local seq = (t[OUT0] or 0) + 1

		if seq > 1e9 then
			seq = 1
		end

		t[OUT0] = seq
	end

	local function poll_mailbox()
		local seq = t[6]

		if seq == G.seq then
			return false
		end

		G.seq = seq

		local len = t[8]
		local bytes

		if type(len) == "number" and len >= 0 and len <= CMD_BYTES and len % 1 == 0 then
			bytes = {}

			for i = 1, len do
				local b = t[B0 + i - 1]

				if type(b) ~= "number" or b < 0 or b > 255 or b % 1 ~= 0 then
					bytes = nil

					break
				end

				bytes[i] = string.char(b)
			end
		end

		if bytes then
			local ok, res = pcall(apply_command, table.concat(bytes))

			G.result = ok and res or "err:" .. tostring(res)
		else
			G.result = "err:命令坏了"
		end

		t[7] = seq

		return true
	end

	--------------------------------------------------------------------------
	-- 出生点（2026-11-16）：SpawnManager.get_spawn_points
	-- 原版一捆怪只在中心外 5 米一圈摆 12 个点（spawn_manager.lua:375，前两圈的点被最外圈覆盖掉了），
	-- 同一处刷的几捆都挤在这 12 个点上；一捆超过 12 只就永远凑不够点，重试 10 次后整捆作废（不报错）。
	-- 这里：点数按这一捆的只数给够（多给一半，地面不合格的会被筛掉）；散开 1/2/3 时点距放大、
	-- 每捆的中心再随机挪开一点，几捆不再叠在一起。散开 0 且这捆不超过 12 只时完全走原版。
	--------------------------------------------------------------------------
	local SPREAD_STEP = { [0] = 2.5, 3.5, 5, 7 }

	local function hook_spawn_points(cls)
		if type(cls) ~= "table" or type(cls.get_spawn_points) ~= "function" or rawget(cls, "_spawn_rules_pts_hooked") then
			return
		end

		local orig = cls.get_spawn_points
		local orig_queue = cls.queue_group_spawn

		-- 刷一捆之前先记下这捆几只（原版是先算点、后填成员）
		if type(orig_queue) == "function" then
			cls.queue_group_spawn = function(self, pos, group, ...)
				local n = 0

				for _, u in ipairs(type(group) == "table" and group.units or {}) do
					n = n + (tonumber(u.amount) or 0)
				end

				G.next_group_n = n

				local res = { pcall(orig_queue, self, pos, group, ...) }

				G.next_group_n = nil

				if not res[1] then
					error(res[2], 0)
				end

				return unpack(res, 2)
			end
		end

		cls.get_spawn_points = function(self, center, step, group, ...)
			local cfg = active()
			local spread = (type(cfg) == "table" and tonumber(cfg.spread)) or 0
			local need = (type(group) == "table" and type(group.members) == "table" and #group.members > 0
				and #group.members) or G.next_group_n or 0

			if (spread <= 0 and need <= 12) or type(group) ~= "table" then
				return orig(self, center, step, group, ...)
			end

			local ok, err = pcall(function()
				local s = SPREAD_STEP[spread] or SPREAD_STEP[0]
				local want = math.max(12, math.ceil(need * 1.5) + 2)
				local c = Vector3Aux.unbox(center)

				if spread > 0 then
					local a = math.random() * math.pi * 2
					local r = math.random() * s * 1.5

					c = c + Vector3(math.cos(a) * r, math.sin(a) * r, 0)
				end

				local list = {}
				local ring = 1

				while #list < want and ring <= 40 do
					local count = math.max(6, math.floor(ring * 2 * math.pi))
					local off = math.random() * math.pi * 2

					for i = 1, count do
						local a = off + i * 2 * math.pi / count
						local p = c + Vector3(math.cos(a) * ring * s, math.sin(a) * ring * s, 0)

						if group.force_outside_screen and CameraManager then
							local inside = CameraManager:is_position_inside_frustum(p, 0, 0, 0, 0)

							if inside then
								p = CameraManager:get_closest_position_outside_frustum(p, 0)
							end
						end

						list[#list + 1] = {
							arg_c = 500,
							arg_a = { z = 100, x = p.x, y = p.y },
							arg_b = { z = -1, x = 0, y = 0 },
						}
					end

					ring = ring + 1
				end

				-- 原版从表尾一个个往前射线，最后一个不射（group_raycast_queued），所以多垫一个
				list[#list + 1] = list[#list]
				-- 内圈先射：倒过来放
				local rev = {}

				for i = #list, 1, -1 do
					rev[#rev + 1] = list[i]
				end

				group.queued_raycasts = rev
				G.spread_groups = (G.spread_groups or 0) + 1
			end)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end

				return orig(self, center, step, group, ...)
			end
		end
		cls._spawn_rules_pts_hooked = true
	end

	local function tick(dt)
		local changed = poll_mailbox()

		-- 客机：全局上限是全局变量，当房主时抬过的要放回原版（客机算的步兵战车放兵也看它）
		local _, gst = game_state()

		if type(gst) == "table" and gst.is_server == false and G.cap_orig then
			local gs = rawget(_G, "GameSettings")

			if type(gs) == "table" and gs.MAX_NUM_ALLOWED_ENEMIES ~= G.cap_orig then
				gs.MAX_NUM_ALLOWED_ENEMIES = G.cap_orig
			end
		end

		hook_spawn_points(rawget(_G, "SpawnManager"))

		-- 每帧看看挂点装没装上（换一局、脚本重载后类表可能换了）
		hook_encounter(rawget(_G, "EncounterManager"))
		hook_spawn_enemy(rawget(_G, "EncounterManager"))
		hook_ifv(rawget(_G, "CyborgIfvStateSpawnGroup"))
		hook_patrol(rawget(_G, "PatrolManager"))
		hook_genocide()
		hook_alarm_update(rawget(_G, "EncounterManager"))
		hook_patrol_update(rawget(_G, "PatrolManager"))

		-- 进对局后组表才在：之前存的报复关组改动补套一次
		if next(G.gmap) and rawget(_G, "GenocideGroupSettings") ~= G.gmap_table then
			apply_gmap(G.gmap)
		end

		timer = timer - (dt or 0)

		if changed or timer <= 0 then
			timer = REFRESH

			publish()
		end
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_spawn_rules_hooked") then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local ok, err = pcall(tick, dt)

			if not ok then
				G.errors = (G.errors or 0) + 1
				G.last_error = tostring(err)
				if rawget(_G, "HellBoxLog") then HellBoxLog("spawn_rules", G.last_error) end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
		wm._spawn_rules_hooked = true
	end
end
