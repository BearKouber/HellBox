-- [ai bridge] AI 陪玩的"眼睛"：每帧把玩家和敌人的状态写进一张固定大小的数字表，
-- 外部程序（ai\bridge.py）在内存里找到这张表后直接读。
-- 只读游戏状态，不改任何游戏数据。由 build.py 追加到 character_state_machine 末尾。
--
-- 表布局（下标从 1 开始，全部是数字；改布局要同步改 bridge.py 并把 VERSION 加 1）：
--   1-4   魔数（外部程序靠它找表）
--   5     VERSION
--   6     已写完的帧号（写完一帧才更新）
--   7     正在写的帧号（和 6 相等说明这一帧是完整的）
--   8     本帧 dt
--   9     游戏时间（dt 累加）
--   10    玩家数
--   11    写进表的敌人数
--   12    场上敌人总数
--   13    出错次数（到 50 次就停止采集，不影响游戏）
--   14    字符串表里的条数
--   15    镜头水平转角（弧度，CameraManager.follow_spin；关卡 -45 度，飞船 15 度）。
--         手柄的移动和瞄准都按它转成地图方向；-99 = 读不到
--   16    读武器出错的次数（单独记，不算进 13，也不会让采集停下）
--   玩家区：4 个 × 24 格；敌人区：96 个 × 16 格（按离玩家由近到远）；
--   武器区：4 个 × 40 格（和玩家区一一对应，是该玩家手上那把枪，每帧现读，格子含义见 write_weapon）；
--   字符串区：MAX_STRINGS 条 × 40 格（第 0 格长度，后面是字符码；第 7 版起 512 条，之前 128 条）；错误信息区：200 格。
--   第 4 版（2026-10-12）起按"区"加东西：已有的区一格不动，新区接在表尾，区第 0 格是区版本，只往区尾加格子。
--   任务区：140 格（归任务撤离线，格子含义见 write_mission 上面）。
--   飞船区（第 5 版，2026-10-12）：80 格，空投舱座位和每个人"互动"对着什么，格子含义见 write_ship 上面。
--     第 7 版（2026-10-12）：格子不变，座位位置改成舱的位置（第 5、6 版读座位碰撞体位置，飞船上闪退）。
--   表 VERSION 6（2026-10-13，HD1 情况总方案第二阶段，这一轮只加 P0 用的三区，见 docs\游戏陪玩\mod申请清单.md）：
--     玩家输入区（M1）33 格、玩家状态补充区（M2）49 格、视线区（M4）463 格，格子含义见 write_input / write_status /
--     write_sight 上面。
--   表 VERSION 7（2026-10-14，情况总方案 P1 第一批，见 docs\游戏陪玩\mod申请清单.md）：
--     字符串区从 128 条加到 512 条（敌人状态名、真名、武器名、战略配备名一局下来会把 128 条撑满），所以字符串区之后的
--     各区（错误信息、任务、飞船、M1、M2、M4）起点都往后挪了，格子本身不变。
--     M2 补齐 P1 的格子（+5 起身还剩多久、+6 着火、+7 减速倍率、+8 减速来源、+9 中毒、+10 最近一次挨打距今）。
--     新区接在视线区后面，每区 +0 是区版本（1 = 这一帧写好了，0 = 关掉 / 出错 / 没写）：
--       M3 武器补充区 WX0：1 + 4 × 43 格（每个玩家：unit_id + 主武器、副武器、支援武器各 14 格），见 write_weapons_extra
--       M6 虫子补充区 EX0：1 + 96 × 15 格（和敌人区同序），见 write_bugs
--       M8 掉落物区 DR0：1 + 32 × 9 格，见 write_drops
--       M9 队友和增援区 TM0：1 + 4 × 6 + 3 格，见 write_team
--       M10 战略配备区 SG0：1 + 4 × 49 格（每个玩家：unit_id + 8 条 × 6 格）+ 场上信标 8 × 8 格，见 write_strats
--       M12 镜头区 CM0：1 + 8 格，见 write_camera
--     出错只记 t[SI0 + 1]（和第 6 版三区一起数）；M3 里单把枪读出错记 16 号格（和武器区一样）。
--   表 VERSION 8（2026-10-14，情况总方案 P1 第三批 M11 友方伤害源区，见 docs\游戏陪玩\mod申请清单.md）：
--     M11 友方伤害源区 HZ0：1 + 8 × 9 格（炮塔、地雷、电弧塔），见 write_hazards
--     M15 石头/障碍物区 RK0：1 + 4 × 17 格（每个玩家：unit_id + 16 个水平方向的障碍物距离），见 write_rocks
--     M5 弧线区 AR0：1 + 4 × 15 格（每个玩家 unit_id + 14 格，格子含义见 write_arc 上面；清单原来写 1 × 14，mod 分不出谁是 2P，按玩家分块）
--     （三条改 mod 的合成同一个第 8 版，区顺序 M11 → M15 → M5，2026-10-15 合并时排）
--   表 VERSION 14（2026-11-01，HD1-023 冲锋虫节奏模块，见 docs\任务\HD1-023-大虫打法.md）：
--     M18 玩家盾量区 SD0：1 + 4 × 5 格（每个玩家：unit_id + 盾量 + 盾上限 + 盾开着 + 充能计时器），见 write_shield。
--     只读盾组件的 state（shield_component.lua 43-51），全部包在 pcall 里（extra_part），出错只记本区 +1 号格，
--     不影响别的区；读不到 / 没背盾写 -1。新区接在 M17 后面，之前的格子一格没动。
--   表 VERSION 15（2026-11-04，HD1-023 冲锋虫"冲不冲"）：
--     M19 冲锋虫射线区 TR0：2 + 8 × 10 格（每只冲锋虫：它自己冲锋前那几条射线的结果），见 write_tankrays。
--     只读 bug_tank_states.lua 228 行冲锋判断用到的 state 字段，不自己打射线；接在 M18 后面，之前的格子一格没动。
do
	local VERSION = 15
	local MAX_PLAYERS, PF = 4, 24
	local MAX_ENEMIES, EF = 96, 16
	local WF = 40
	local MAX_STRINGS, SL = 512, 40
	local ERR_LEN = 200
	local P0 = 17
	local E0 = P0 + MAX_PLAYERS * PF
	local W0 = E0 + MAX_ENEMIES * EF
	local S0 = W0 + MAX_PLAYERS * WF
	local ERR0 = S0 + MAX_STRINGS * SL
	local M0 = ERR0 + ERR_LEN
	local MF, MAX_OBJ, OF = 140, 8, 9
	local SH0 = M0 + MF
	local SHF, MAX_SEATS, SF = 80, 8, 8
	local SHIP_ENABLED = true  -- 飞船区开关：2026-10-12 查开局闪退时关过，第 7 版不碰座位碰撞体后重新打开
	local IN0 = SH0 + SHF      -- M1 玩家输入区：+0 区版本，之后玩家 4 个 × INF 格
	local INF = 8
	local ST0 = IN0 + 1 + MAX_PLAYERS * INF   -- M2 玩家状态补充区：+0 区版本，之后玩家 4 个 × STF 格
	local STF = 12
	local SI0 = ST0 + 1 + MAX_PLAYERS * STF   -- M4 视线区：+0 区版本 +1 出错次数 +2 留空，之后玩家 4 个 × SIF 格
	local SIF = 115
	local SIGHT_ENABLED = true -- 视线区开关：射线是新调的引擎函数，万一实测闪退，关掉这里重新打包
	-- 第 7 版（P1 第一批）
	local WX0 = SI0 + 3 + MAX_PLAYERS * SIF   -- M3 武器补充区：+0 区版本，之后玩家 4 个 × WXF 格
	local WXW = 14                            -- 每把枪几格
	local WXF = 1 + 3 * WXW                   -- 每个玩家：unit_id + 3 把
	local EX0 = WX0 + 1 + MAX_PLAYERS * WXF   -- M6 虫子补充区：+0 区版本，之后虫 96 只 × EXF 格（和敌人区同序）
	local EXF = 15
	local ONSCREEN_ENABLED = true -- M6"在不在屏幕里"开关：CameraManager:is_position_inside_frustum 要调引擎的 world_to_viewport，
	--                               万一实测闪退，关掉这里重新打包（这一格就写 -99，别的照常）
	local DR0 = EX0 + 1 + MAX_ENEMIES * EXF   -- M8 掉落物区：+0 区版本，之后 MAX_DROPS 个 × DRF 格
	local MAX_DROPS, DRF = 32, 9
	local DROP_RANGE = 40                     -- 离任意活着的玩家多少米以内才写
	local TM0 = DR0 + 1 + MAX_DROPS * DRF     -- M9 队友和增援区：+0 区版本，之后玩家 4 个 × TMF 格 + 全队 3 格
	local TMF = 6
	local SG0 = TM0 + 1 + MAX_PLAYERS * TMF + 3   -- M10 战略配备区：+0 区版本，之后玩家 4 个 × SGF 格 + 信标 MAX_BEACONS × BCF 格
	local MAX_STRATS, STW = 8, 6
	local SGF = 1 + MAX_STRATS * STW
	local MAX_BEACONS, BCF = 8, 8
	local CM0 = SG0 + 1 + MAX_PLAYERS * SGF + MAX_BEACONS * BCF   -- M12 镜头区：+0 区版本，之后 CMF 格
	local CMF = 8
	local CAMERA_ENABLED = true   -- M12 镜头区开关：只读 CameraManager 表里存着的数自己算，不调引擎；万一实测出事，关掉这里
	local HZ0 = CM0 + 1 + CMF     -- M11 友方伤害源区：+0 区版本，之后 MAX_HAZ × HZF 格
	local MAX_HAZ, HZF = 32, 13
	local HAZ_RANGE = 60          -- 离任意活着的玩家多少米以内才写
	local HAZARDS_ENABLED = true  -- M11 友方伤害源区开关
	local RK0 = HZ0 + 1 + MAX_HAZ * HZF   -- M15 石头/障碍物区：+0 区版本，之后玩家 4 个 × RKF 格
	local RK_RAYS = 16            -- 16 个水平方向
	local RKF = 1 + RK_RAYS       -- 每个玩家：unit_id + 16 个方向的距离
	local ROCKS_ENABLED = true    -- M15 开关：射线是引擎物理调用，万一实测闪退，关掉这里重新打包
	local AR0 = RK0 + 1 + MAX_PLAYERS * RKF   -- M5 弧线区：+0 区版本，之后玩家 4 个 × ARF 格（和玩家区同序）
	local ARF = 15
	local ARC_ENABLED = true                  -- M5 开关：射线和视线区一样（damage_ray + "all"）；实测出事就关掉这里重新打包
	local ARC_PERIOD, ARC_DT, ARC_STEPS = 0.3, 0.1, 60   -- 每约 0.3 秒算一个人；弧线 0.1 秒一段，最多看 6 秒
	local ARC_GRAVITY = 18                    -- state_game 里 PhysicsWorld.set_gravity(0, 0, -18)
	local ARC_GROUND_UP, ARC_GROUND_DOWN = 20, 60   -- 找地面：从段末往上 20 米起、往下拉 60 米
	local BL0 = AR0 + 1 + MAX_PLAYERS * ARF
	local BLF = 49 -- uid, radius, large, shield, armor_min/max, forward_x/y
	local LG0 = BL0 + 1 + MAX_ENEMIES * BLF
	local LGF, MVF = 18, 10
	local MV0 = LG0 + 1 + MAX_ENEMIES * LGF
	local N13 = MV0 + 1 + MAX_PLAYERS * MVF   -- 第 13 版到这里为止（bridge.py 的 N13 和这一样）
	local SD0 = N13 + 1                       -- M18 玩家盾量区：+0 区版本 +1 出错次数，之后玩家 4 个 × SDF 格
	local SDF = 5                             -- 每个玩家：unit_id + shieldpoints + max_shieldpoints + shield_activated + shield_regen_timer
	local N14 = SD0 + 1 + MAX_PLAYERS * SDF   -- 第 14 版到这里为止
	local TR0 = N14 + 1                       -- M19 冲锋虫射线区：+0 区版本 +1 出错次数，之后 MAX_TR × TRF 格
	local MAX_TR, TRF = 8, 10
	local N = TR0 + 1 + MAX_TR * TRF
	local MAX_ERRORS = 50
	local EMPTY = {}

	local B = AIBridge or {}

	AIBridge = B

	B.shield_errors = B.shield_errors or 0
	-- M18 盾量区开关：只读组件 state，万一实测出事，改成 false 重新打包（放在 B 上，snapshot 少一个 upvalue：
	-- luaJIT 单个函数最多 60 个 upvalue，snapshot 已经贴着上限了）
	B.shield_enabled = B.shield_enabled ~= false
	B.tankrays_errors = B.tankrays_errors or 0
	B.tankrays_enabled = B.tankrays_enabled ~= false   -- M19 开关（同上，放在 B 上）

	-- 表的版本变了（换了 mod 没重开游戏）也重建，免得按新布局写进旧的小表
	if not B.t or B.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		-- 魔数在运行时从字符串转出来，免得它作为常量出现在字节码里被误找到
		t[1] = tonumber("48151623.5")
		t[2] = tonumber("-271828.125")
		t[3] = tonumber("7340.0078125")
		t[4] = tonumber("1099511627776.25")
		t[5] = VERSION
		B.t = t
		B.strings = {}
		B.nstrings = 0
		B.unit_ids = {}
		B.n_unit_ids = 0
		B.next_unit_id = 1
		B.frame = 0
		B.time = 0
		B.errors = 0
		B.weapon_errors = 0
	end

	B.weapon_errors = B.weapon_errors or 0
	B.mission_errors = B.mission_errors or 0

	local t = B.t
	local call = pcall or function(f, ...)
		return true, f(...)
	end
	local plist, slot_of = {}, {}
	local eu, ed, eidx = {}, {}, {}
	local seen = {}

	local function num(v, d)
		if type(v) == "number" and v == v then
			return v
		end

		return d
	end

	local function flag(v)
		return v and 1 or 0
	end

	local function sid(s)
		if s == nil then
			return -1
		end

		s = tostring(s)

		local id = B.strings[s]

		if id then
			return id
		end

		if B.nstrings >= MAX_STRINGS then
			return -2
		end

		id = B.nstrings

		local base = S0 + id * SL
		local n = math.min(#s, SL - 1)

		for i = 1, n do
			t[base + i] = string.byte(s, i)
		end

		t[base] = n
		B.strings[s] = id
		B.nstrings = id + 1
		t[14] = B.nstrings

		return id
	end

	local function uid(u)
		local id = B.unit_ids[u]

		if not id then
			if B.n_unit_ids > 4096 then
				B.unit_ids = {}
				B.n_unit_ids = 0
			end

			id = B.next_unit_id
			B.next_unit_id = id + 1
			B.unit_ids[u] = id
			B.n_unit_ids = B.n_unit_ids + 1
		end

		return id
	end

	local function by_uid(a, b)
		return uid(a) < uid(b)
	end

	local function by_dist(a, b)
		return ed[a] < ed[b]
	end

	local function entities(em, name)
		if em.has_entities and not em:has_entities(name) then
			return EMPTY
		end

		return em:get_master_entities(name) or EMPTY
	end

	-- 主控 + 副本合在一起（2026-10-18）：联机时别人电脑管的角色、虫子在本机只有副本（slave），只读主控就看不到
	-- 活着的 P3/P4 和归他们管的虫（日志 follow_20261018_223936：整局没见过 P3、穿刺虫）。游戏自己数全队也是读副本
	-- （hud、state_game 的全员阵亡）。同一个单位两份都有时用主控那份（输入、状态机只在主控里）。
	-- 合出来的是自己的表（每帧清空重填），不改引擎的表；副本里没有的字段照旧按"读不到"写。
	local merged, merged_frame, master_set = {}, {}, {}

	local function all_entities(em, name)
		if merged_frame[name] == B.frame then
			return merged[name]
		end

		local m = entities(em, name)
		local masters = master_set[name] or {}

		master_set[name] = masters

		for u in pairs(masters) do
			masters[u] = nil
		end

		if m == EMPTY and em.has_entities and not em:has_entities(name) then
			return EMPTY
		end

		local s = em.get_slave_entities and em:get_slave_entities(name) or EMPTY
		local out = merged[name] or {}

		for u in pairs(out) do
			out[u] = nil
		end

		for u, e in pairs(s) do
			out[u] = e
		end

		for u, e in pairs(m) do
			out[u] = e
			masters[u] = true
		end

		merged[name], merged_frame[name] = out, B.frame

		return out
	end

	local function is_master(name, u)
		local masters = master_set[name]

		return masters ~= nil and masters[u] == true
	end

	local function write_player(base, u, e)
		local s = e.state or EMPTY
		local p = Unit.world_position(u, 0)
		local f = Quaternion.forward(Unit.world_rotation(u, 0))
		local hs = s.health_state or EMPTY
		local vel = (s.mover_state or EMPTY).velocity or EMPTY
		local aim = (s.input or EMPTY).aim or EMPTY
		local w = s.current_weapon or (s.inventory_state or EMPTY).current_weapon
		local mel = w and Unit.alive(w) and EntityAux.has_component(w, "melee") and EntityAux.state(w, "melee") or EMPTY
		local mi = mel.melee_info or EMPTY

		t[base + 1] = num((s.input_state or EMPTY).pad_number, -1)
		t[base + 2] = p.x
		t[base + 3] = p.y
		t[base + 4] = p.z
		t[base + 5] = f.x
		t[base + 6] = f.y
		t[base + 7] = num(vel.x, 0)
		t[base + 8] = num(vel.y, 0)
		t[base + 9] = num(aim.x, 0)
		t[base + 10] = num(aim.y, 0)
		t[base + 11] = num(hs.hitpoints, -1)
		t[base + 12] = num(hs.max_hitpoints, -1)
		t[base + 13] = flag(hs.is_downed)
		t[base + 14] = flag(hs.is_dead)
		t[base + 15] = flag(hs.is_dodging)
		t[base + 16] = sid(s.current_state and s.current_state.name)
		t[base + 17] = num(mel.melee_time, -99)
		t[base + 18] = num(mi.duration, -1)
		t[base + 19] = num(mi.radius, -1)
		t[base + 20] = num(s.sprint_stamina, -1)
		t[base + 21] = num(s.time_outside_screen, -1)
		t[base + 22] = uid(u)
		t[base + 23] = flag(s.is_aiming)
		t[base] = 1
	end

	-- 武器种类：0 = 没拿武器或别的东西，1 = 普通枪（瞬间命中的射线），2 = 激光，3 = 电弧，4 = 火焰，
	-- 5 = 发射会飞的弹（榴弹、导弹、迫击炮），6 = 近战武器，7 = 投掷物
	local KINDS = { { "firearm", 1 }, { "beamweapon", 2 }, { "arcweapon", 3 }, { "flameweapon", 4 }, { "launcher", 5 },
		{ "meleeweapon", 6 }, { "throwable_weapon", 7 } }

	local function deg(v)
		return type(v) == "number" and v == v and math.deg(v) or -1
	end

	-- 布尔配置：true = 1，false = 0，配置里没写 = -1（外部程序把 -1 当"读不到"）
	local function tri(v)
		if v == nil then
			return -1
		end

		return v and 1 or 0
	end

	-- 弹量、换弹、热量这些"现在"的数在主控那份状态里（和游戏 HUD 的读法一样）；
	-- 射程只在显示那份状态里算好（firearm 的 reload_slave 把缺省的 20 填上）。
	local function weapon_states(w)
		local ok_m, ms = false, nil

		if EntityAux.owned(w) then
			ok_m, ms = call(EntityAux.state_master_interface, w, "weapon")
		end

		local ok_s, ss = call(EntityAux.state_interface, w, "weapon")

		return ok_m and ms or EMPTY, ok_s and ss or EMPTY
	end

	-- 格子：0 有武器(1/0) 1 种类 2 名字(字符串号) 3 武器编号(换枪就变) 4 升级值 5 unstoppable 6 piercing
	-- 7 每发弹丸数 8 当前散布(度) 9 最小散布 10 最大散布 11 固定散布 12 散布涨满要几发 13 散布每秒回落几发
	-- 14 当前累计几发 15 射程 16 射速(发/分) 17 半自动 18 全自动 19 自带点射发数 20 弹匣剩几发 21 弹匣容量
	-- 22 备用弹匣 23 正在换弹 24 换弹剩几秒 25 热量 26 举枪转身倍率 27 开火转身倍率 28 举枪移动倍率
	-- 29 电弧第一跳最远 30 电弧扇区内跳多远 31 电弧扇区外跳多远 32 电弧最多跳几次 33 电弧扇区角度(度)
	-- 34 爆炸弹 35 离下一发还要几秒 36 最近射程(火焰/电弧) 37 散布基准角(度，电弧/激光喷子用) 38 弹匣容量是否读到 39 保留
	-- 读不到的格子是 -1。
	local function write_weapon(base, w)
		for i = 0, WF - 1 do
			t[base + i] = -1
		end

		t[base] = 0

		if not w or not Unit.alive(w) then
			t[base + 1] = 0

			return
		end

		local kind = 0

		for _, k in ipairs(KINDS) do
			if EntityAux.has_component(w, k[1]) then
				kind = k[2]

				break
			end
		end

		local up = LoadoutSettings.get_upgraded_settings(w) or EMPTY
		local wi = up.weapon_info or EMPTY
		local at = wi.attributes or EMPTY
		local ms, ss = weapon_states(w)
		local ug = EntityAux.has_component(w, "upgradeable") and EntityAux.state(w, "upgradeable") or EMPTY
		local function now(k)
			local v = ms[k]

			if v == nil then
				v = ss[k]
			end

			return v
		end

		t[base] = 1
		t[base + 1] = kind
		t[base + 2] = sid((up.hud_info or EMPTY).weapon_icon)
		t[base + 3] = uid(w)
		t[base + 4] = num(ug.upgrade_value, -1)
		t[base + 5] = tri(at.unstoppable)
		t[base + 6] = tri(at.piercing)
		t[base + 7] = num(now("shots_per_round"), num(wi.shots_per_round, -1))
		t[base + 8] = deg(now("spread"))
		t[base + 9] = deg(now("spread_min"))
		t[base + 10] = deg(now("spread_max"))
		t[base + 11] = tri(at.fixed_spread)
		t[base + 12] = num(now("spread_shots_max"), -1)
		t[base + 13] = num(now("spread_shots_decay"), -1)
		t[base + 14] = num(now("spread_shots_fired"), -1)

		local range = ss.range or ms.range or wi.range

		if kind == 4 then
			range = wi.max_range
		elseif kind == 3 then
			range = wi.max_range_from_owner
		end

		t[base + 15] = num(range, -1)
		t[base + 16] = num(wi.firerate, -1)
		t[base + 17] = tri(at.semi_automatic)
		t[base + 18] = tri(at.fully_automatic)
		t[base + 19] = num(wi.burst_rounds, -1)
		t[base + 20] = num(ms.rounds, num(ss.rounds, -1))
		t[base + 21] = num(now("magazine_capacity"), num(wi.magazine_capacity, -1))
		t[base + 22] = num(now("num_mags"), -1)
		t[base + 23] = tri(now("is_reloading"))
		t[base + 24] = num(now("reload_time"), -1)
		t[base + 25] = num(now("heat"), -1)
		t[base + 26] = num(wi.turn_speed_aim, -1)
		t[base + 27] = num(wi.turn_speed_fire, -1)
		t[base + 28] = num(wi.move_speed_aim, -1)
		t[base + 29] = num(wi.max_first_jump_distance, -1)
		t[base + 30] = num(wi.max_jump_distance_inside_arc, -1)
		t[base + 31] = num(wi.max_jump_distance_outside_arc, -1)
		t[base + 32] = num(wi.max_number_of_jumps, -1)
		t[base + 33] = deg(wi.arc_size_min)
		t[base + 34] = tri(at.explosive)
		t[base + 35] = num(now("fire_timer"), -1)
		t[base + 36] = num(wi.min_range or wi.min_range_from_owner, -1)
		t[base + 37] = num(wi.spread, -1)
		t[base + 38] = now("magazine_capacity") ~= nil and 1 or 0
	end

	local function record_weapon_error(err)
		local s = "weapon: " .. tostring(err)
		local n = math.min(#s, ERR_LEN - 1)

		for i = 1, n do
			t[ERR0 + i] = string.byte(s, i)
		end

		t[ERR0] = n
	end

    -- health 的 enabled_damage_zones 会同步给远端；敌人的状态机名称不会。
    local function observed_health(u, e, has_master)
        if has_master and EntityAux.has_component_master and EntityAux.has_component_master(u, "health") then
            return EntityAux.state_master(u, "health") or EMPTY
        end
        if EntityAux.has_component(u, "health") then
            return EntityAux.state(u, "health") or EMPTY
        end
        return ((e or EMPTY).state or EMPTY).health_state or EMPTY
    end

    -- 只采集挡弹与朝向；不改变地形/移动区。
    local function write_ballistics(enemies, nw)
        t[BL0] = 0
        for i = 1, MAX_ENEMIES do
            local b = BL0 + 1 + (i - 1) * BLF
            for k = 0, BLF - 1 do t[b + k] = -1 end
            if i <= nw then
                local u = eu[eidx[i]]
                local settings = (enemies[u] or EMPTY).settings or EMPTY
                local hi = settings.health_info
                local hs = observed_health(u, enemies[u], is_master("enemy", u))
                local shield = EntityAux.has_component(u, "shield") and EntityAux.state(u, "shield") or EMPTY
                local f = Quaternion.forward(Unit.world_rotation(u, 0))
                t[b], t[b + 1] = uid(u), num(settings.unit_radius, -1)
                t[b + 2], t[b + 3] = hi and flag(hi.large) or -1, num(shield.shieldpoints, 0)
                t[b + 4], t[b + 5] = num(hs.armor_min, num((hi or EMPTY).armor_min, -1)), num(hs.armor_max, num((hi or EMPTY).armor_max, -1))
                t[b + 6], t[b + 7] = f.x, f.y
                local zones, mask = hs.damage_zones, hs.enabled_damage_zones
                t[b + 8] = -1 -- 未知不能伪装成没有弱点。
                if type(zones) == "table" and type(mask) == "number" and BitAux then
                    t[b + 8] = math.min(#zones, 8)
                    for k = 1, t[b + 8] do
                        local z, c = zones[k], b + 9 + (k - 1) * 5
                        t[c] = flag(BitAux.is_bit_set(mask, k))
                        t[c + 1], t[c + 2] = num(z.min, -99), num(z.max, -99)
                        t[c + 3], t[c + 4] = num(z.armor_min, -1), num(z.armor_max, -1)
                    end
                end
            end
        end
        t[BL0] = 1
    end

	local function write_enemy(base, u, e)
		local s = e.state or EMPTY
		local info = (e.settings or EMPTY).enemy_info or EMPTY
		local p = Unit.world_position(u, 0)
		local hs = s.health_state or EMPTY

		t[base] = uid(u)
		t[base + 1] = sid(info.enemy_type)
		t[base + 2] = p.x
		t[base + 3] = p.y
		t[base + 4] = p.z
		t[base + 5] = num(hs.hitpoints, -1)
		t[base + 6] = num(hs.max_hitpoints, -1)
		t[base + 7] = flag(hs.is_dead)
		t[base + 8] = sid(s.current_state and s.current_state.name)
		t[base + 9] = flag(s.alerted)
		t[base + 10] = num(s.alarm_timer, -99)
		t[base + 11] = flag(s.patroling)
		t[base + 12] = s.target_unit and slot_of[s.target_unit] or -1
		t[base + 13] = flag(s.has_triggered_encounter)
		t[base + 14] = num(s.rotation_angle, 0)
		t[base + 15] = num(info.patrol_range, -1)
	end

	-- ---------- 任务区（第 4 版加，归任务撤离线 HD1-010；格子含义见 docs\任务\HD1-010 的字段清单） ----------
	-- 区内第 k 格 = t[M0 + k]。0 区版本 1 ok 2 is_extracting 3 extraction_done 4 mission_completed
	-- 5 all_objectives_done 6 目标总数 7 完成数 8 失败数 9 种子 10 难度 11 任务类型 12 敌人阵营 13 星球名(字符串号)
	-- 14 区域 15~30 信标 31~42 撤离点和飞机 43~50 名单(手柄编号, 已上机) 51~62 各槽位在碰什么(种类, x, y)
	-- 63 目标个数 64 起每个目标 9 格；136 本区出错次数 137~139 保留。读不到写 -1。
	local OBJ_KIND = { { "objective_interact_object", 1 }, { "objective_hold_object", 2 },
		{ "objective_defend_object", 3 }, { "objective_fortify_object", 4 } }
	local OBJ_STATE = { pending = 0, complete = 1, failed = 2 }
	local mobj, mobj_d = {}, {}

	local function pick(list, good)
		local first

		for u, e in pairs(list) do
			if Unit.alive(u) then
				first = first or u

				if good(u, e.state or EMPTY) then
					return u, e
				end
			end
		end

		return first, first and list[first]
	end

	local function write_beacon(em)
		local list = entities(em, "extract_beacon")
		local u = pick(list, function(_, s)
			return s.activated
		end)

		if not u or not (list[u].state or EMPTY).activated then
			local v = pick(list, function(_, s)
				return s.enabled
			end)

			u = v or u
		end

		if not u then
			return
		end

		local e = list[u]
		local s = e.state or EMPTY
		local info = (e.settings or EMPTY).extract_beacon_info or EMPTY
		local p = Unit.world_position(u, 0)

		t[M0 + 15] = 1
		t[M0 + 16] = p.x
		t[M0 + 17] = p.y
		t[M0 + 18] = p.z
		t[M0 + 19] = flag(s.enabled)
		t[M0 + 20] = flag(s.activated)
		t[M0 + 21] = num(s.extraction_timer, -1)
		t[M0 + 22] = num(s.extraction_time, -1)
		t[M0 + 23] = num(s.progress, -1)
		t[M0 + 24] = num(s.target_interacts, -1)
		t[M0 + 25] = s.interacting_unit and slot_of[s.interacting_unit] or -1
		t[M0 + 26] = flag(s.too_far_away)
		t[M0 + 27] = num(s.too_far_away_timer, -1)
		t[M0 + 29] = num(info.too_far_away_distance, -1)
		t[M0 + 30] = num(info.too_far_away_time, -1)

		-- 中间点：照游戏的算法（活着的角色位置平均，z 当 0，和信标三维位置算距离）
		local cx, cy, n = 0, 0, 0

		for c in pairs(em:get_slave_entities("character") or EMPTY) do
			if Unit.alive(c) and not (EntityAux.state(c, "health") or EMPTY).is_dead then
				local q = Unit.world_position(c, 0)

				cx, cy, n = cx + q.x, cy + q.y, n + 1
			end
		end

		if n > 0 then
			cx, cy = cx / n, cy / n
			t[M0 + 28] = math.sqrt((cx - p.x) ^ 2 + (cy - p.y) ^ 2 + p.z ^ 2)
		end
	end

	local function write_lz(em)
		local list = entities(em, "objective_extract_lz")
		local u = pick(list, function(v, s)
			return s.active_lz == v
		end)

		if u and (list[u].state or EMPTY).active_lz ~= u then
			u = pick(list, function(_, s)
				return num(s.shuttle_state, 0) ~= 0
			end) or u
		end

		if not u then
			return
		end

		local s = list[u].state or EMPTY
		local lp = Unit.world_position(u, 0)
		local sx, sy, sz = lp.x, lp.y, lp.z
		local slave = (em:get_slave_entities("objective_extract_lz") or EMPTY)[u]
		local sh = slave and (slave.state or EMPTY).shuttle

		if sh and Unit.alive(sh) then
			local q = Unit.world_position(sh, 0)

			sx, sy, sz = q.x, q.y, q.z
		elseif s.shuttle_position then
			local q = Vector3Aux.unbox(s.shuttle_position)

			sx, sy, sz = q.x, q.y, q.z
		end

		local fwd = Quaternion.forward(Quaternion(Vector3(0, 0, 1), math.rad(90)))

		t[M0 + 31] = 1
		t[M0 + 32] = num(s.shuttle_state, -1)
		t[M0 + 33] = num(s.abandon_timer, -1)
		t[M0 + 34] = num(s.avatars_in_dropship, -1)
		t[M0 + 35] = sx
		t[M0 + 36] = sy
		t[M0 + 37] = sz
		t[M0 + 38] = sx + fwd.x * 1.5
		t[M0 + 39] = sy + fwd.y * 1.5
		t[M0 + 40] = 1.9
		t[M0 + 41] = lp.x
		t[M0 + 42] = lp.y
	end

	local function write_roster(mm)
		for i = 1, 4 do
			local p = (mm.players or EMPTY)[i]
			local go = p and p.player_go

			if go and go:exists() then
				t[M0 + 41 + 2 * i] = num(p.pad_number, -1)
				t[M0 + 42 + 2 * i] = flag(go:has("has_extracted") and go:get("has_extracted"))
			end
		end
	end

	local function obj_kind(u)
		if EntityAux.has_component(u, "extract_beacon") then
			return 1
		end

		for _, k in ipairs(OBJ_KIND) do
			if EntityAux.has_component(u, k[1]) then
				return k[2] == 1 and 2 or k[2] == 3 and 3 or 9
			end
		end

		return 9
	end

	local function write_touching(chars)
		for i = 1, MAX_PLAYERS do
			local u = plist[i]
			local o = u and (chars[u].state or EMPTY).current_interact_objective_unit
			local b = M0 + 51 + (i - 1) * 3

			if o and Unit.alive(o) then
				local q = Unit.world_position(o, 0)

				t[b] = obj_kind(o)
				t[b + 1] = q.x
				t[b + 2] = q.y
			end
		end
	end

	local function write_objective(b, kind, u, s)
		local p = Unit.world_position(u, 0)
		local st = s.current_stage or EMPTY
		local radius, guarding, progress, left = 0, false, -1, -1

		if kind == 1 then
			guarding = s.interacting_unit ~= nil or num(s.event_duration, 0) > 0 or st.interact_type == "countdown"
			progress = num(s.progress, -1)

			if num(s.event_duration, 0) > 0 then
				left = num(s.event_duration, -1)
			elseif st.interact_type == "countdown" then
				left = num(s.event_countdown, -1)
			end
		elseif kind == 2 then
			radius = num(st.hold_radius, 0)
			guarding = num(s.num_characters_in_radius, 0) > 0 or num(s.percent_done, 0) > 0
			progress = num(s.percent_done, -1)
			left = num(s.timer_fail, -1)
		elseif kind == 3 then
			guarding = s.activated and true or false
			progress = num(s.percent_done, -1)
			left = num(s.defend_timer, -1)
		else
			local ctl, ct = num(s.capture_time_left, 0), num(s.capture_time, 0)

			radius = ctl > 0 and num(s.capture_radius, 0) or num(s.hold_radius, 0)
			guarding = s.player_in_radius and true or ctl <= 0
			progress = ct > 0 and 1 - ctl / ct or -1
		end

		t[b] = kind
		t[b + 1] = p.x
		t[b + 2] = p.y
		t[b + 3] = radius
		t[b + 4] = OBJ_STATE[s.mission_state] or -1
		t[b + 5] = flag(guarding)
		t[b + 6] = progress
		t[b + 7] = kind == 1 and s.interacting_unit and slot_of[s.interacting_unit] or -1
		t[b + 8] = left
	end

	local function by_obj(a, b)
		return mobj_d[a] < mobj_d[b]
	end

	local function write_objectives(em)
		local n = 0

		for i = #mobj, 1, -1 do
			mobj[i] = nil
		end

		for _, k in ipairs(OBJ_KIND) do
			for u, e in pairs(entities(em, k[1])) do
				if Unit.alive(u) then
					local s = e.state or EMPTY
					local p = Unit.world_position(u, 0)
					local best = math.huge

					for i = 1, MAX_PLAYERS do
						local q = P0 + (i - 1) * PF

						if t[q] == 1 then
							best = math.min(best, (p.x - t[q + 2]) ^ 2 + (p.y - t[q + 3]) ^ 2)
						end
					end

					n = n + 1
					mobj[n] = { k[2], u, s }
					-- 进行中的排前面
					mobj_d[mobj[n]] = best + (s.mission_state == "pending" and 0 or 1e12)
				end
			end
		end

		table.sort(mobj, by_obj)

		local w = math.min(n, MAX_OBJ)

		t[M0 + 63] = w

		for i = 1, w do
			local o = mobj[i]

			write_objective(M0 + 64 + (i - 1) * OF, o[1], o[2], o[3])
		end

		for k in pairs(mobj_d) do
			mobj_d[k] = nil
		end
	end

	local function mission_part(f, ...)
		local ok, err = call(f, ...)

		if not ok then
			B.mission_errors = B.mission_errors + 1
			t[M0 + 136] = B.mission_errors

			if B.errors == 0 then
				record_weapon_error("mission: " .. tostring(err))
			end
		end
	end

	local function write_mission(comp, chars)
		t[M0] = 1

		for i = 1, MF - 1 do
			t[M0 + i] = -1
		end

		for i = 1, 4 do
			t[M0 + 41 + 2 * i] = -2
		end

		for i = 51, 62, 3 do
			t[M0 + i] = 0
		end

		t[M0 + 15], t[M0 + 31], t[M0 + 63] = 0, 0, 0
		t[M0 + 136] = B.mission_errors

		local mm = comp.mission_manager
		local em = comp.entity_manager

		if not mm then
			t[M0 + 1] = 0

			return
		end

		local before = B.mission_errors

		mission_part(function()
			t[M0 + 2] = flag(mm.is_extracting)
			t[M0 + 3] = flag(mm.extraction_done)
			t[M0 + 4] = flag(mm.mission_completed)
			t[M0 + 5] = flag(mm.all_objectives_done)
			t[M0 + 6] = num(mm:get_objective_count(), -1)
			t[M0 + 7] = num(mm:get_objectives_complete_count(), -1)

			local failed = 0

			for _, o in ipairs(mm.objectives or EMPTY) do
				if o.name ~= "mission_objective_extract" and o.state == "failed" then
					failed = failed + 1
				end
			end

			t[M0 + 8] = failed
		end)
		mission_part(function()
			local seed = mm.mission_seed

			t[M0 + 9] = num(seed, -1)

			if type(seed) == "number" and rawget(_G, "DifficultySettings") then
				t[M0 + 10] = num(DifficultySettings.get_mission_difficulty(seed), -1)

				local mp = DifficultySettings.get_mission_params(seed) or EMPTY

				t[M0 + 11] = num(mp.mission_type, -1)
				t[M0 + 12] = num(mp.enemy, -1)
			end
		end)
		mission_part(write_beacon, em)
		mission_part(write_lz, em)
		mission_part(write_roster, mm)
		mission_part(write_touching, chars)
		mission_part(write_objectives, em)
		-- 信标、撤离点、名单这几块是她撤离要用的，出错就整区算没写好
		t[M0 + 1] = B.mission_errors == before and 1 or 0
	end

	-- 飞船区（HD1-009 进舱，2026-10-12）：飞船上她要自己走进空投舱、按互动坐进去。
	--   +0 区版本（1 = 这一帧写好了，0 = 出错 / 没写）；+1 写了几个座位；+2 本区出错次数；+3 有几个空投舱
	--   座位 MAX_SEATS 个 × SF 格，从 +4 开始：+0 x、+1 y、+2 z（舱的位置；第 7 版起不读座位碰撞体，见下面）；
	--     +3 舱朝向 fx、+4 fy；+5 有人坐了（1/0）；+6 第几个舱（从 1 数）；+7 舱里第几个座
	--   玩家 4 个 × 2 格，从 +4 + MAX_SEATS * SF 开始，顺序和玩家区一样：
	--     +0 "互动"现在对着的是空投舱（1/0，-1 = 读不到）；+1 对着第几个舱（0 = 不是舱）
	-- 只在有空投舱的地方（飞船）有座位；关卡里座位数是 0。
	local function write_ship(em)
		for i = 1, SHF - 1 do
			t[SH0 + i] = -1
		end

		t[SH0 + 1] = 0
		t[SH0 + 2] = B.ship_errors or 0
		t[SH0 + 3] = 0

		local pods = entities(em, "drop_pod")
		local pod_no = {}
		local n, np = 0, 0

		for u in pairs(pods) do
			if Unit.alive(u) then
				np = np + 1
				pod_no[u] = np

				local p = Unit.world_position(u, 0)
				local f = Quaternion.forward(Unit.world_rotation(u, 0))
				local seat

				if EntityAux.has_component_master(u, "seat") then
					seat = EntityAux.state_master(u, "seat")
				elseif EntityAux.has_component(u, "seat") then
					seat = EntityAux.state(u, "seat")
				end

				-- 座位位置一律写舱的位置，不碰座位碰撞体。
				-- 2026-10-12：第 5、6 版读座位碰撞体的位置（Actor.position），飞船上游戏直接闪退，三份崩溃记录
				-- 都停在 Actor.position 里面（pcall 拦不住引擎里的崩溃）。同时不再调 Unit.find_actor、LoadoutSettings。
				local count = 0

				if seat and type(seat.actor_to_seat) == "table" then
					for _, si in pairs(seat.actor_to_seat) do
						if type(si) == "number" then
							count = math.max(count, si)
						end
					end
				end

				if seat and type(seat.seat_info) == "table" then
					count = math.max(count, #seat.seat_info)
				end

				if count == 0 then
					count = 1
				end

				for si = 1, count do
					if n < MAX_SEATS then
						n = n + 1

						local b = SH0 + 4 + (n - 1) * SF
						local q = p

						local who = seat and type(seat.seated_units) == "table" and seat.seated_units[si]

						t[b] = q.x
						t[b + 1] = q.y
						t[b + 2] = q.z
						t[b + 3] = f.x
						t[b + 4] = f.y
						t[b + 5] = (who and Unit.alive(who)) and 1 or 0
						t[b + 6] = np
						t[b + 7] = si
					end
				end
			end
		end

		t[SH0 + 3] = np

		for i = 1, MAX_PLAYERS do
			local b = SH0 + 4 + MAX_SEATS * SF + (i - 1) * 2
			local u = plist[i]

			if u then
				local ok, st = call(EntityAux.state_master, u, "interactor")

				if ok and type(st) == "table" then
					local target = st.interactable_unit
					local k = target and pod_no[target] or 0

					t[b] = k > 0 and 1 or 0
					t[b + 1] = k
				end
			end
		end

		t[SH0 + 1] = n
	end

	-- ---------- 第 6 版的三区（2026-10-13）。都在 snapshot 末尾、玩家和武器写完以后写，各自包 pcall ----------

	local function xy_of(v)
		if v == nil then
			return 0, 0
		end

		local ok, x, y = call(function()
			return v.x, v.y
		end)

		if not ok then
			return 0, 0
		end

		return num(x, 0), num(y, 0)
	end

	-- 存着的三维点（Vector3Aux.box 过的表）：三个数都读到才返回，否则 nil
	local function xyz_of(v)
		if type(v) ~= "table" and type(v) ~= "userdata" then
			return nil
		end

		local ok, x, y, z = call(function()
			return v.x, v.y, v.z
		end)

		if ok and type(x) == "number" and type(y) == "number" and type(z) == "number" then
			return x, y, z
		end
	end

	-- Vector3Aux.box 过的点的 x、y：先按表里的字段读，读不到再用 Vector3Aux.unbox；都不行返回 nil
	local function boxed_xy(v)
		if type(v) ~= "table" then
			return nil
		end

		local x, y = v.x or v[1], v.y or v[2]

		if type(x) ~= "number" or type(y) ~= "number" then
			local va = rawget(_G, "Vector3Aux")

			if va and va.unbox then
				local ok, w = call(va.unbox, v)

				if ok and w then
					x, y = w.x, w.y
				end
			end
		end

		if type(x) == "number" and type(y) == "number" then
			return x, y
		end
	end

	-- 组件的主控状态（本机是主控时才有：status 的 status_effects、inventory 的冷却都只在主控那份里）；
	-- 没有主控就退到普通状态；都没有返回 nil
	local function comp_state(u, name)
		local ok, st = call(function()
			local hcm = EntityAux.has_component_master

			if hcm and hcm(u, name) then
				return EntityAux.state_master(u, name)
			end

			if EntityAux.has_component(u, name) then
				return EntityAux.state(u, name)
			end
		end)

		return ok and type(st) == "table" and st or nil
	end

	-- 玩家输入区（M1）：区内第 k 格 = t[IN0 + k]。+0 区版本（1 = 这一帧写好了）。
	--   玩家 4 个 × 8 格，从 +1 开始，顺序和玩家区一样：+0 unit_id（-1 = 这一格没人）+1 开火键按着 +2 举枪（瞄准键 / 右摇杆）
	--   +3 +4 移动方向 x、y（游戏读到的输入）+5 +6 瞄准方向 x、y +7 这一帧开出了子弹（弹匣比上一帧少，同一把枪）
	local function write_input(chars)
		B.last_rounds = B.last_rounds or {}

		for i = 1, MAX_PLAYERS do
			local b = IN0 + 1 + (i - 1) * INF
			local u = plist[i]

			for k = 0, INF - 1 do
				t[b + k] = -1
			end

			if u then
				local s = chars[u].state or EMPTY
				local inp = s.input or EMPTY
				local wb = W0 + (i - 1) * WF
				local rounds, wid = t[wb + 20], t[wb + 3]
				local last = B.last_rounds[u]

				t[b] = uid(u)
				t[b + 1] = flag(inp.fire or inp.fire_auto or num(inp.fire_amount, 0) > 0.05)
				t[b + 2] = flag(s.is_aiming)
				t[b + 3], t[b + 4] = xy_of(inp.movement)
				t[b + 5], t[b + 6] = xy_of(inp.aim)
				t[b + 7] = flag(t[wb] == 1 and last ~= nil and last[1] == wid and rounds >= 0 and rounds < last[2])

				if t[wb] == 1 then
					B.last_rounds[u] = { wid, rounds }
				else
					B.last_rounds[u] = nil
				end
			end
		end

		t[IN0] = 1
	end

	-- 玩家状态补充区（M2）：+0 区版本。玩家 4 个 × 12 格，从 +1 开始，顺序和玩家区一样：
	--   +0 unit_id +1 自救已按几下（get_up_presses）+2 要按几下 +3 倒地多久（秒，没倒地 -1）
	--   +4 趴下多久（秒，CharacterStateCrawl；没趴 -1）+5 起身还剩多久 +6 着火 +7 减速倍率 +8 减速来源（字符串号）
	--   +9 中毒 / 持续伤害 +10 最近一次挨打距今 +11 自救清零倒计时（get_up_reset_timer）
	--   第 6 版（P0）只读自救和倒地、趴下计时；第 7 版（P1）补上 +5 ~ +10：
	--   +5 起身还剩多久：趴着（CharacterStateCrawl）且已经开始起身（dive_get_up）时 = dive_duration + dive_recovery_duration
	--      - dive_timer（照 character_state_crawl 的算法），没在起身 -1，读不到 -99
	--   +6 着火 / +7 减速倍率 / +8 减速来源 / +9 中毒：读 status 组件主控状态的 status_effects（没标 remove 的）：
	--      +6 有 burn 就是 1；+7 = 1 - 最强那个 slow 的 amount（不减速 1；水 0.55、雪 0.65）；+8 那个 slow 的模板名
	--      （字符串号，如 difficult_water / difficult_snow / poison_slow / carry_burden，不减速 -1）；
	--      +9 有 damage 类（毒、铁丝网）就是 1。读不到 status 主控状态时 +6、+7、+9 是 -99，+8 是 -1。
	--   +10 最近一次挨打距今（秒）：mod 自己看血量，比上一帧少了就算挨了一下（游戏没存挨打时间）；这个角色还没挨过打 -1
	local function write_status(chars)
		B.since_down = B.since_down or {}
		B.since_prone = B.since_prone or {}
		B.last_hp = B.last_hp or {}
		B.hit_at = B.hit_at or {}

		for i = 1, MAX_PLAYERS do
			local b = ST0 + 1 + (i - 1) * STF
			local u = plist[i]

			for k = 0, STF - 1 do
				t[b + k] = -99
			end

			t[b] = -1
			t[b + 8] = -1

			if u then
				local e = chars[u]
				local s = e.state or EMPTY
				local hs = s.health_state or EMPTY
				local info = (e.settings or EMPTY).character_info or EMPTY
				local sname = s.current_state and s.current_state.name

				t[b] = uid(u)
				t[b + 1] = num(s.get_up_presses, -99)
				t[b + 2] = num(s.get_up_presses_needed, num(info.get_up_presses_needed, -99))

				if hs.is_downed then
					B.since_down[u] = B.since_down[u] or B.time
					t[b + 3] = B.time - B.since_down[u]
				else
					B.since_down[u] = nil
					t[b + 3] = -1
				end

				if sname == "CharacterStateCrawl" then
					B.since_prone[u] = B.since_prone[u] or B.time
					t[b + 4] = B.time - B.since_prone[u]
				else
					B.since_prone[u] = nil
					t[b + 4] = -1
				end

				t[b + 11] = num(s.get_up_reset_timer, -99)

				-- +5 起身还剩多久
				if sname == "CharacterStateCrawl" and s.dive_get_up then
					local dd, dr, dt = info.dive_duration, info.dive_recovery_duration, s.dive_timer

					if type(dd) == "number" and type(dr) == "number" and type(dt) == "number" then
						t[b + 5] = math.max(0, dd + dr - dt)
					end
				else
					t[b + 5] = -1
				end

				-- +6 ~ +9 状态效果
				local sts = comp_state(u, "status")
				local eff = sts and sts.status_effects

				if type(eff) == "table" then
					local burn, dot, slow = 0, 0, nil

					for _, x in ipairs(eff) do
						if type(x) == "table" and not x.remove then
							if x.name == "burn" then
								burn = 1
							elseif x.name == "damage" then
								dot = 1
							elseif x.name == "slow" and (slow == nil or num(x.amount, 0) > num(slow.amount, 0)) then
								slow = x
							end
						end
					end

					t[b + 6] = burn
					t[b + 7] = slow and 1 - num(slow.amount, 0) or 1
					t[b + 8] = slow and sid(slow.template_name) or -1
					t[b + 9] = dot
				end

				-- +10 最近一次挨打距今
				local hp = hs.hitpoints

				if type(hp) == "number" then
					local last = B.last_hp[u]

					if last and hp < last - 1e-6 then
						B.hit_at[u] = B.time
					end

					B.last_hp[u] = hp
				end

				t[b + 10] = B.hit_at[u] and B.time - B.hit_at[u] or -1
			end
		end

		t[ST0] = 1
	end

	-- 视线区（M4）：+0 区版本（1 = 开着）+1 第 6 版三区一共出错几次 +2 留空。玩家 4 个 × 115 格，从 +3 开始，顺序和玩家区一样。
	-- 每个玩家一块（陪玩那边只用 2P 那块；mod 不知道哪个是 2P，就每个人都拉，一帧最多拉一个人的一轮）：
	--   +0 这一块有数（1/0）+1 这一轮拉完的游戏时间 +2 这一轮几只虫
	--   虫 8 只 × 10 格，从 +3 开始（离这个玩家由近到远的活虫）：+0 unit_id +1 结果（中间那条线：0 通 / 1 挡住 /
	--     2 先碰到队友）+2 碰到的队友槽位（-1 = 没有）+3 队友距离 +4 挡住的距离 +5 3 条里通了几条 +6 +7 +8 起点 x、y、z +9 留空
	--   侧移候选点 4 个 × 8 格，从 +83 开始（对最近那只虫，往右挪 -4、-2、2、4 米，负数 = 左）：+0 往右挪几米
	--     +1 +2 候选点 x、y +3 结果 +4 3 条里通了几条 +5 挡住的距离 +6 对的是哪只（unit_id）+7 留空
	-- 射线用游戏子弹那套（"damage_ray"，"all"），和电弧枪的写法一样：碰到自己和目标不算挡；其他单位按大型、护盾、硬甲确认挡弹（普通软目标沿用原行为）；
	-- 碰到玩家算"先碰到队友"；碰到别的（墙、石头）算挡住。起点、终点都在脚下位置往上抬 SIGHT_EYE 米（电弧枪就是 +1 米）。
	local SIGHT_PERIOD, SIGHT_N, SPOT_N = 0.3, 8, 4
	local SIGHT_EYE, SIGHT_EDGE = 1.0, 0.4
	local SPOT_OFFSETS = { -4, -2, 2, 4 }
	local sight_u, sight_d, sight_p = {}, {}, {}

	local function by_sight(a, b)
		return sight_d[a] < sight_d[b]
	end

	local function game_world()
		local wm = rawget(_G, "WorldManager")
		local proxy = wm and wm:get_world_proxy("game_world")

		return proxy and proxy:get_world()
	end

	-- 一条线。返回 结果（0/1/2）、队友槽位、队友距离、挡住的距离
	local function cast(pw, fx, fy, fz, tx, ty, tz, me, target)
		local dx, dy, dz = tx - fx, ty - fy, tz - fz
		local len = math.sqrt(dx * dx + dy * dy + dz * dz)

		if len < 0.05 then
			return 0, -1, -1, -1
		end

		-- 引擎的 Vector3 只在当前帧有效，每次现做（ai_terrain 第 3 版踩过的坑）
		local hits = PhysicsWorld.immediate_raycast(pw, Vector3(fx, fy, fz), Vector3(dx / len, dy / len, dz / len), len,
			"all", "collision_filter", "damage_ray")
		local block, friend, fslot = math.huge, math.huge, -1

		if hits then
			for _, h in ipairs(hits) do
				local dist, actor = h[2], h[4]
				local u = actor and Actor.unit(actor)

				if type(dist) == "number" and u ~= me and u ~= target then
					if u and slot_of[u] then
						if dist < friend then
							friend, fslot = dist, slot_of[u]
						end
                    elseif u and EntityAux.has_component(u, "health") then
                        local ent = (B.sight_entities or EMPTY)[u] or EMPTY
                        local settings = ent.settings or EMPTY
                        local health = settings.health_info or EMPTY
                        local hs = (ent.state or EMPTY).health_state or EMPTY
                        local shield = EntityAux.has_component(u, "shield") and EntityAux.state(u, "shield") or EMPTY
                        local shot = B.sight_shot or EMPTY
                        -- large / 护盾按照游戏弹道直接止弹；小型单位只有确认完全打不穿才新增阻挡。
                        local proof = type(health.armor_min) == "number" and type(shot.power) == "number" and
                            shot.power <= math.max(0, health.armor_min - (shot.ap and 15 or 0))
                        if shot.direct and not hs.is_dead and (health.large or (shield.shieldpoints or 0) > 0 or proof) then
                            if dist < block then block = dist end
                        end
                    else
						if dist < block then
							block = dist
						end
					end
				end
			end
		end

		if friend < block then
			return 2, fslot, friend, -1
		end

		if block < math.huge then
			return 1, -1, -1, block
		end

		return 0, -1, -1, -1
	end

	-- 从 (ox, oy, oz) 对一只虫拉 3 条（中间、左右边缘）。返回 中间那条的四个结果 + 通了几条
	local function cast3(pw, ox, oy, oz, q, me, target)
		local tx, ty, tz = q[1], q[2], q[3] + SIGHT_EYE
		local hx, hy = tx - ox, ty - oy
		local hl = math.sqrt(hx * hx + hy * hy)
		local px, py = 0, 0

		if hl > 1e-3 then
			px, py = -hy / hl * SIGHT_EDGE, hx / hl * SIGHT_EDGE
		end

		local r, fs, fd, bd = cast(pw, ox, oy, oz, tx, ty, tz, me, target)
		local clear = r == 0 and 1 or 0

		for side = -1, 1, 2 do
			local r2, fs2, fd2 = cast(pw, ox, oy, oz, tx + px * side, ty + py * side, tz, me, target)

			if r2 == 0 then
				clear = clear + 1
			elseif r2 == 2 and fs < 0 then
				fs, fd = fs2, fd2
			end
		end

		return r, fs, fd, bd, clear
	end

	local function sight_round(b, pw, me, enemies)
        B.sight_entities = enemies
		local p = Unit.world_position(me, 0)
		local ox, oy, oz = p.x, p.y, p.z + SIGHT_EYE
		local n = 0

		for u, e in pairs(enemies) do
			if Unit.alive(u) and not ((e.state or EMPTY).health_state or EMPTY).is_dead then
				local q = Unit.world_position(u, 0)

				n = n + 1
				sight_u[n] = u
				sight_d[u] = (q.x - ox) ^ 2 + (q.y - oy) ^ 2
				sight_p[u] = { q.x, q.y, q.z }
			end
		end

		for i = #sight_u, n + 1, -1 do
			sight_u[i] = nil
		end

		table.sort(sight_u, by_sight)

		for k = 0, SIF - 1 do
			t[b + k] = -1
		end

		local w = math.min(n, SIGHT_N)

		for i = 1, w do
			local u = sight_u[i]
			local c = b + 3 + (i - 1) * 10
			local r, fs, fd, bd, clear = cast3(pw, ox, oy, oz, sight_p[u], me, u)

			t[c] = uid(u)
			t[c + 1] = r
			t[c + 2] = fs
			t[c + 3] = fd
			t[c + 4] = bd
			t[c + 5] = clear
			t[c + 6], t[c + 7], t[c + 8] = ox, oy, oz
		end

		if w > 0 then
			local u = sight_u[1]
			local q = sight_p[u]
			local hx, hy = q[1] - ox, q[2] - oy
			local hl = math.sqrt(hx * hx + hy * hy)

			if hl > 1e-3 then
				-- 面朝虫子时的右手边
				local rx, ry = hy / hl, -hx / hl

				for i = 1, SPOT_N do
					local off = SPOT_OFFSETS[i]
					local sx, sy = ox + rx * off, oy + ry * off
					local c = b + 3 + SIGHT_N * 10 + (i - 1) * 8
					local r, _, _, bd, clear = cast3(pw, sx, sy, oz, q, me, u)

					t[c] = off
					t[c + 1], t[c + 2] = sx, sy
					t[c + 3] = r
					t[c + 4] = clear
					t[c + 5] = bd
					t[c + 6] = uid(u)
				end
			end
		end

		for k in pairs(sight_d) do
			sight_d[k], sight_p[k] = nil, nil
		end

		t[b + 1] = B.time
		t[b + 2] = w
		t[b] = 1
	end

	-- 每帧最多给一个玩家拉一轮：挑上一轮最早的那个，离上一轮不到 SIGHT_PERIOD 秒就不拉
	local function write_sight(em)
		B.sight_at = B.sight_at or {}
		B.sight_owner = B.sight_owner or {}

		local pw = rawget(_G, "PhysicsWorld") and rawget(_G, "Actor") and game_world()

		pw = pw and World.physics_world(pw)

		local pick_i, pick_at

		for i = 1, MAX_PLAYERS do
			local u = plist[i]
			local b = SI0 + 3 + (i - 1) * SIF

			if B.sight_owner[i] ~= u then
				-- 这个槽位换了人（死了重生、有人进出）：上一个人的结果作废
				B.sight_owner[i] = u
				t[b] = 0
			end

			if not u or not pw then
				t[b] = 0
			else
				local at = B.sight_at[u] or -math.huge

				if B.time - at >= SIGHT_PERIOD and (pick_at == nil or at < pick_at) then
					pick_i, pick_at = i, at
				end
			end
		end

		if pick_i then
			local u = plist[pick_i]

			B.sight_at[u] = B.time
            local cs = (all_entities(em, "character")[u] or EMPTY).state or EMPTY
            local weapon = cs.current_weapon
            local ws = weapon and LoadoutSettings.get_upgraded_settings(weapon) or EMPTY
            local wi = ws.weapon_info or EMPTY
            B.sight_shot = { direct = weapon and (EntityAux.has_component(weapon, "firearm") or EntityAux.has_component(weapon, "beamweapon")),
                             power = wi.power, ap = (wi.attributes or EMPTY).armorpiercing }
			sight_round(SI0 + 3 + (pick_i - 1) * SIF, pw, u, all_entities(em, "enemy"))
		end
	end

	-- ---------- 第 7 版的区（2026-10-14，情况总方案 P1 第一批）。各自包 pcall（extra_part），出错只记 t[SI0 + 1] ----------

	-- M3 武器补充区：+0 区版本。玩家 4 个 × 43 格，从 +1 开始，顺序和玩家区一样（mod 分不出哪个是 2P，每个人都写）：
	--   +0 unit_id（-1 = 这一格没人）
	--   之后主武器、副武器、支援武器各 14 格（inventory 的 primary_weapon / sidearm_weapon / support_weapon），每把：
	--   +0 有没有这把（1/0；读这把出错 -1，错误记 16 号格）+1 武器名（字符串号，hud_info.weapon_icon，和武器区同一个名字）
	--   +2 是不是手上那把（1/0）+3 威力 +4 破甲（attributes.armorpiercing：1 是 / 0 否 / -1 配置没写，游戏里没写等于否）
	--   +5 弹匣剩几发 +6 弹匣容量 +7 备用弹匣 +8 射速（发/分）
	--   +9 换到这把要多久（秒）：手上那把 = 换枪还剩的时间（inventory.switch_weapon_time，换完是 0）；
	--      别的 = 角色的 inventory_info.switch_weapon_duration（现在都是 0.5，不含"按住 Y"这类按键时间）
	--   +10 初速（米/秒）+11 重力（米/秒²）+12 溅射半径（米）：只有会飞的弹（launcher）有，不是会飞的弹填 -1
	--   +13 武器编号（和武器区 +3 同一套号，换了一把就变）
	--   会飞的弹（榴弹、雷鸣、导弹）：+3 威力 = 弹的 explosive_info.center_power（打中中心的伤害；外圈是 blast_power），
	--   +4 破甲读 explosive_info.armorpiercing，+12 = explosive_info.blast_radius；
	--   扔出去的弹（throwable_info）初速照 throwable_component："thrown" 的算法：sqrt(18 × 投掷距离)，
	--   投掷距离 = throw_distance_min + 武器 power × (max - min)（雷鸣蓄力会加 power，这里按没蓄力的 power 算），
	--   重力 18（state_game 里 PhysicsWorld.set_gravity(0, 0, -18)）；追踪导弹（homing_info）初速 = start_velocity，重力 -99。
	--   没拿这把：这一条 +0 = 0，其余 -1；拿着但读不到的格子 -99。
	local GRAVITY = 18
	local WEAPON_SLOTS = { "primary_weapon", "sidearm_weapon", "support_weapon" }

	local function write_weapon_extra(c, w, cur, inv, switch_dur)
		for k = 0, WXW - 1 do
			t[c + k] = -1
		end

		if not w or not Unit.alive(w) then
			t[c] = 0

			return
		end

		for k = 3, 12 do
			t[c + k] = -99
		end

		local up = LoadoutSettings.get_upgraded_settings(w) or EMPTY
		local wi = up.weapon_info or EMPTY
		local at = wi.attributes or EMPTY
		local ms, ss = weapon_states(w)
		local function now(k)
			local v = ms[k]

			if v == nil then
				v = ss[k]
			end

			return v
		end

		t[c] = 1
		t[c + 1] = sid((up.hud_info or EMPTY).weapon_icon)
		t[c + 2] = flag(w == cur)
		t[c + 5] = num(now("rounds"), -99)
		t[c + 6] = num(now("magazine_capacity"), num(wi.magazine_capacity, -99))
		t[c + 7] = num(now("num_mags"), -99)
		t[c + 8] = num(wi.firerate, -99)

		if w == cur then
			t[c + 9] = math.max(0, num(inv.switch_weapon_time, 0))
		else
			t[c + 9] = num(switch_dur, -99)
		end

		t[c + 13] = uid(w)

		if EntityAux.has_component(w, "launcher") then
			local proj = wi.projectile or ms.projectile
			local lsm = rawget(_G, "LuaSettingsManager")
			local ps = proj and lsm and lsm:get_settings_by_unit_path(proj) or EMPTY
			local ex = ps.explosive_info or EMPTY

			t[c + 3] = num(ex.center_power, -99)
			t[c + 4] = tri(ex.armorpiercing)
			t[c + 12] = num(ex.blast_radius, -99)

			local th, hm = ps.throwable_info, ps.homing_info

			if th then
				local p = num(ms.power, num(wi.power, nil))
				local dmin, dmax = num(th.throw_distance_min, nil), num(th.throw_distance_max, nil)

				if p and dmin and dmax then
					t[c + 10] = math.sqrt(math.max(0, dmin + p * (dmax - dmin)) * 18)
				end

				t[c + 11] = GRAVITY
			elseif hm then
				t[c + 10] = num(hm.start_velocity, -99)
			end
		else
			t[c + 3] = num(now("power"), num(wi.power, -99))
			t[c + 4] = tri(at.armorpiercing)
			t[c + 10], t[c + 11], t[c + 12] = -1, -1, -1
		end
	end

	local function write_weapons_extra(chars, em)
		local invs = all_entities(em, "inventory")

		for i = 1, MAX_PLAYERS do
			local b = WX0 + 1 + (i - 1) * WXF
			local u = plist[i]

			for k = 0, WXF - 1 do
				t[b + k] = -1
			end

			if u then
				local s = chars[u].state or EMPTY
				local inv = comp_state(u, "inventory") or s.inventory_state or EMPTY
				local dur = (((invs[u] or EMPTY).settings or EMPTY).inventory_info or EMPTY).switch_weapon_duration
				local cur = s.current_weapon or inv.current_weapon

				t[b] = uid(u)

				for k, slot in ipairs(WEAPON_SLOTS) do
					local c = b + 1 + (k - 1) * WXW
					local ok, err = call(write_weapon_extra, c, inv[slot], cur, inv, dur)

					if not ok then
						t[c] = -1
						B.weapon_errors = B.weapon_errors + 1
						t[16] = B.weapon_errors

						if B.errors == 0 then
							record_weapon_error("weapons: " .. tostring(err))
						end
					end
				end
			end
		end

		t[WX0] = 1
	end

	-- M6 虫子补充区：+0 区版本。虫 96 只 × 15 格，从 +1 开始，和敌人区同序（第 i 条就是敌人区第 i 只；没有的那几条 unit_id 是 -1）：
	--   +0 unit_id（核对用，和敌人区 +0 一样）
	--   +1 在不在屏幕里（1/0；CameraManager:is_position_inside_frustum(位置)，和游戏报警判断同一个函数；
	--      开关 ONSCREEN_ENABLED 关着或读不到 -99）
	--   +2 看不看得到目标（state.can_see_closest_target，1/0）+3 看的是哪个玩家（closest_target_unit 的玩家槽位，-1 = 没有）
	--   +4 真名 enemy_name（字符串号，如 bug_warrior_elite / bug_tank_heavy）
	--   +5 进当前状态多久（秒；游戏不存，mod 自己记状态名变的时刻；这只虫刚进前 96 名时从那一刻算起）
	--   +6 正在出手打谁（玩家槽位；出手了但打的不是玩家 = 9；没在出手 = -1；这只虫没有近战组件 = -99）
	--   +7 出手到判定还剩多久（秒；没在出手 = -1，没有近战组件 = -99）。2026-10-18 补上：读 melee 组件的
	--      melee_delay_timer（游戏 melee_component：收到 "melee" 命令时设成 melee_info.delay，倒数到 0 才判定打没打中，
	--      判定那一刻按"虫 → 目标"方向、center_distance 处半径 radius 的球算；冲锋虫 / 穿刺虫是在那里炸一下）
	--   +8 冲锋冷却 rush_cooldown（冲锋虫；冷却完了会是 0 或负数）、+9 范围攻击冷却 aoe_cooldown（冲锋虫没在冷却 = 0）；
	--      不是冲锋虫两格都是 -1
	--   +10 跳扑蓄力中 +11 蓄力计时 +12 跳向哪个玩家：P2，先填 -99
	--   +13 穿刺虫钻地了没有（1/0，不是穿刺虫 -99）+14 钻地多久（秒，没钻 -1；2026-10-18 补上）
	--   （清单写 12 格，但它列的字段有 15 个，这里按字段给 15 格）
	local function write_bugs(enemies, nw, melees)
		B.est = B.est or {}
		melees = melees or EMPTY

		local cam = rawget(_G, "CameraManager")
		local frust = ONSCREEN_ENABLED and cam and type(cam.is_position_inside_frustum) == "function"

		for i = 1, MAX_ENEMIES do
			local b = EX0 + 1 + (i - 1) * EXF

			if i > nw then
				for k = 0, EXF - 1 do
					t[b + k] = -1
				end
			else
				local u = eu[eidx[i]]
				local e = enemies[u] or EMPTY
				local s = e.state or EMPTY
				local info = (e.settings or EMPTY).enemy_info or EMPTY

				t[b] = uid(u)
				t[b + 1] = -99

				if frust then
					local ok, inside = call(cam.is_position_inside_frustum, cam, Unit.world_position(u, 0))

					if ok then
						t[b + 1] = flag(inside)
					end
				end

				t[b + 2] = flag(s.can_see_closest_target)
				t[b + 3] = s.closest_target_unit and slot_of[s.closest_target_unit] or -1
				t[b + 4] = sid(info.enemy_name)

				local name = s.current_state and s.current_state.name
				local rec = B.est[u]

				if not rec or rec[1] ~= name then
					rec = { name, B.time, 0 }
					B.est[u] = rec
				end

				rec[3] = B.frame
				t[b + 5] = B.time - rec[2]
				t[b + 6], t[b + 7] = -99, -99

				local ms = (melees[u] or EMPTY).state

				if ms then
					local left = ms.melee_delay_timer

					if type(left) == "number" and left >= 0 then
						t[b + 6] = ms.target_unit and slot_of[ms.target_unit] or 9
						t[b + 7] = left
					else
						t[b + 6], t[b + 7] = -1, -1
					end
				end

				t[b + 8] = num(s.rush_cooldown, -1)
				t[b + 9] = num(s.aoe_cooldown, s.rush_cooldown ~= nil and 0 or -1)

				for k = 10, 12 do
					t[b + k] = -99
				end

				-- 穿刺虫钻地（2026-10-18）：状态名是 BugImpalerStateBurrow 就算钻地，钻地多久 = 进这个状态多久（+5 那个数）
				if name == "BugImpalerStateBurrow" then
					t[b + 13], t[b + 14] = 1, t[b + 5]
                elseif info.enemy_name == "bug_impaler" then
                    -- 远端状态机不存在，不把未知写成“没有钻地”。实际弱点由 M16 同步受伤区提供。
                    t[b + 13], t[b + 14] = name and 0 or -99, -1
				else
					t[b + 13], t[b + 14] = -99, -99
				end
			end
		end

		-- 隔一阵清掉不在表里的虫
		if B.frame % 600 == 0 then
			for k, v in pairs(B.est) do
				if v[3] < B.frame - 1 then
					B.est[k] = nil
				end
			end
		end

		t[EX0] = 1
	end

	-- M8 掉落物区：+0 区版本。最多 32 个 × 9 格，从 +1 开始，离任意活着的玩家 DROP_RANGE（40）米以内的，近的在前；
	-- 没有的那几条 unit_id 是 -1（mod 分不出哪个是 2P，按"离任意活着的玩家"挑）：
	--   +0 unit_id +1 种类（0 弹药 ammo_pickup、1 补给箱 supply_crate、2 武器、3 支援武器 weapon_pickup、4 背包 backpack_pickup、
	--      5 样本 research_sample_pickup；游戏里捡起来的枪一律进支援武器槽（rpc_give_weapon → set_support_weapon），
	--      所以地上的枪都报 3，2 现在不会出现）
	--   +2 +3 +4 位置 x、y、z +5 谁叫的（玩家槽位：空投舱的 owner_unit → 舱里的东西 → 补给箱里的东西；-1 = 地图自带 / 不知道）
	--   +6 名字（字符串号，pickup_info.item_name，只有枪和背包写，别的 -1）
	--   +7 还剩多少：补给箱 = 箱里还在的东西几个；弹药 = 1（一个弹药包用一次）；枪 = 备用弹匣（num_mags）；
	--      背包 = num_uses；样本 -99
	--   +8 出现多久了（秒，mod 第一次看到它算起）
	-- 只写看得见的：弹药、枪、背包、样本 enabled 是假（还关在补给箱里没开、已经被捡走）的不写；补给箱空了（is_empty）不写。
	local DROP_KINDS = { { "ammo_pickup", 0 }, { "supply_crate", 1 }, { "weapon_pickup", 3 }, { "backpack_pickup", 4 },
		{ "research_sample_pickup", 5 } }
	local drop_c, drop_px, drop_py = {}, {}, {}

	local function by_drop(a, b)
		return a[7] < b[7]
	end

	local function write_drops(em)
		B.drop_first = B.drop_first or {}

		local np = 0

		for i = 1, MAX_PLAYERS do
			local q = P0 + (i - 1) * PF

			if t[q] == 1 and t[q + 14] ~= 1 then
				np = np + 1
				drop_px[np], drop_py[np] = t[q + 2], t[q + 3]
			end
		end

		-- 谁叫的
		local owner = {}

		for _, e in pairs(all_entities(em, "hellpod")) do
			local s = e.state or EMPTY

			if s.stratagem_unit and s.owner_unit then
				owner[s.stratagem_unit] = slot_of[s.owner_unit] or -1
			end
		end

		local crates = entities(em, "supply_crate")

		for c, e in pairs(crates) do
			local cu = (e.state or EMPTY).content_units

			if owner[c] and type(cu) == "table" then
				for _, x in ipairs(cu) do
					owner[x] = owner[c]
				end
			end
		end

		local n = 0
		local r2 = DROP_RANGE * DROP_RANGE

		for _, k in ipairs(DROP_KINDS) do
			for u, e in pairs(entities(em, k[1])) do
				local s = e.state or EMPTY
				local show

				if k[2] == 1 then
					show = not s.is_empty
				else
					show = s.enabled ~= false
				end

				if show and Unit.alive(u) then
					local p = Unit.world_position(u, 0)
					local best = math.huge

					for j = 1, np do
						local dx, dy = p.x - drop_px[j], p.y - drop_py[j]

						best = math.min(best, dx * dx + dy * dy)
					end

					if best <= r2 then
						n = n + 1

						local r = drop_c[n] or {}

						drop_c[n] = r
						r[1], r[2], r[3], r[4], r[5], r[6], r[7] = u, k[2], p.x, p.y, p.z, e, best
					end
				end
			end
		end

		for i = #drop_c, n + 1, -1 do
			drop_c[i] = nil
		end

		table.sort(drop_c, by_drop)

		for i = 1, MAX_DROPS do
			local c = DR0 + 1 + (i - 1) * DRF
			local r = drop_c[i]

			for k = 0, DRF - 1 do
				t[c + k] = -1
			end

			if r then
				local u, kind, e = r[1], r[2], r[6]
				local s = e.state or EMPTY
				local left = -99

				if kind == 0 then
					left = 1
				elseif kind == 1 then
					left = 0

					for _, x in ipairs(type(s.content_units) == "table" and s.content_units or EMPTY) do
						if Unit.alive(x) then
							left = left + 1
						end
					end
				elseif kind == 3 then
					left = num(s.num_mags, -99)
				elseif kind == 4 then
					left = num(s.num_uses, -99)
				end

				B.drop_first[u] = B.drop_first[u] or B.time
				t[c] = uid(u)
				t[c + 1] = kind
				t[c + 2], t[c + 3], t[c + 4] = r[3], r[4], r[5]
				t[c + 5] = owner[u] or -1
				t[c + 6] = (kind == 3 or kind == 4) and sid(((e.settings or EMPTY).pickup_info or EMPTY).item_name) or -1
				t[c + 7] = left
				t[c + 8] = B.time - B.drop_first[u]
			end
		end

		if B.frame % 600 == 0 then
			for k in pairs(B.drop_first) do
				if not Unit.alive(k) then
					B.drop_first[k] = nil
				end
			end
		end

		t[DR0] = 1
	end

	-- M9 队友和增援区：+0 区版本。玩家 4 个 × 6 格，从 +1 开始，顺序和玩家区一样（死掉的尸体还在玩家区里，占着自己的槽位）：
	--   +0 死了没有（1/0）+1 死了多久（秒，mod 看到 is_dead 起算；活着 -1）+2 +3 尸体位置 x、y（活着 -1）
	--   +4 在等复活（1/0：死了，而且任务管理器的名单里这个人的 avatar_unit 还是这具尸体、没上飞机；
	--      复活出来是新角色，尸体就不再"等"了）
	--   +5 手柄编号（活着时记下的；尸体的手柄编号会变成 -1，这里还是原来的；mod 没见过它活着 -99）
	-- 全队 3 格，从 +1 + 4 × 6 开始：
	--   +0 还剩几次增援：场上只有 1 个人时是 extra_lives（单人的命数）；多人时 -1（不限次数，靠复活战略配备的冷却）；读不到 -99
	--   +1 复活战略配备（stratagem_reinforce）冷却还剩多久：活着的人里最短的那个（秒），没人带 -1
	--   +2 现在有没有复活球在飞（1/0）：场上有扔出去的复活信标还在倒计时，或者任务管理器 num_respawning_players > 0
	local REINFORCE = "stratagem_reinforce"

	local function write_team(comp, chars, em)
		B.pad_alive = B.pad_alive or {}
		B.dead_at = B.dead_at or {}

		local mm = comp.mission_manager
		local waiting = {}
		local active, single = 0, nil

		for _, pe in ipairs(mm and mm.players or EMPTY) do
			local go = type(pe) == "table" and pe.player_go
			local ok, ex = call(function()
				return go and go:exists()
			end)

			if ok and ex then
				active = active + 1
				single = pe

				local ok2, av = call(function()
					return go:get("avatar_unit")
				end)
				local ok3, out = call(function()
					return go:has("has_extracted") and go:get("has_extracted")
				end)

				if ok2 and av then
					waiting[av] = not (ok3 and out)
				end
			end
		end

		local cd

		for i = 1, MAX_PLAYERS do
			local b = TM0 + 1 + (i - 1) * TMF
			local u = plist[i]

			for k = 0, TMF - 1 do
				t[b + k] = -1
			end

			if u then
				local s = chars[u].state or EMPTY
				local hs = s.health_state or EMPTY

				if hs.is_dead then
					local p = Unit.world_position(u, 0)

					B.dead_at[u] = B.dead_at[u] or B.time
					t[b] = 1
					t[b + 1] = B.time - B.dead_at[u]
					t[b + 2], t[b + 3] = p.x, p.y
					t[b + 4] = flag(waiting[u])
				else
					B.dead_at[u] = nil
					B.pad_alive[u] = num((s.input_state or EMPTY).pad_number, -1)
					t[b] = 0
					t[b + 4] = 0

					local inv = comp_state(u, "inventory") or s.inventory_state or EMPTY

					for _, st in ipairs(type(inv.stratagems) == "table" and inv.stratagems or EMPTY) do
						if type(st) == "table" and (st.loadout_info or EMPTY).name == REINFORCE then
							local c = num(st.cooldown_timer, nil)

							if c then
								cd = math.min(cd or c, c)
							end
						end
					end
				end

				t[b + 5] = B.pad_alive[u] or -99
			end
		end

		local T = TM0 + 1 + MAX_PLAYERS * TMF

		if active == 1 then
			t[T] = num(single.extra_lives, -99)
		elseif active > 1 then
			t[T] = -1
		else
			t[T] = -99
		end

		B.lives = t[T]   -- 2026-11-05 HD1-028：给 ai_clock 在画面上显示（不进表布局）

		t[T + 1] = cd and math.max(cd, 0) or -1

		local ball = mm ~= nil and num(mm.num_respawning_players, 0) > 0

		for _, e in pairs(all_entities(em, "stratagem")) do
			local s = e.state or EMPTY

			if s.has_been_thrown and not s.abort and (s.stratagem_info or EMPTY).name == REINFORCE and num(s.activation_time, 0) > 0 then
				ball = true
			end
		end

		t[T + 2] = flag(ball)

		if B.frame % 600 == 0 then
			for k in pairs(B.pad_alive) do
				if not Unit.alive(k) then
					B.pad_alive[k], B.dead_at[k] = nil, nil
				end
			end
		end

		t[TM0] = 1
	end

	-- M10 战略配备区：+0 区版本。
	-- 玩家 4 个 × 49 格，从 +1 开始，顺序和玩家区一样（mod 分不出哪个是 2P，每个人都写）：+0 unit_id（-1 = 没人），
	--   之后 8 条 × 6 格（inventory 主控状态的 stratagems，顺序和游戏里一样；没有的条目 -1）：
	--   +0 名字（字符串号，如 stratagem_mortar）+1 指令（上 1 下 2 左 3 右 4 一位一位拼，雷鸣"下左上左左" = 23133）
	--   +2 冷却还剩多久（秒）+3 还能叫几次（-1 = 不限）
	--   +4 能不能叫：1 能；0 不能（冷却没好 / 次数用完 / blocked / 人站在干扰区里）；-1 不确定（附近有没写半径的干扰区，
	--      或者这条有游戏的 can_use 条件 mod 没法算，比如紧急信标）。复活、地狱炸弹、金属探测器的 can_use 照游戏算
	--   +5 种类：0 补给（stratagem_resupply）、1 装备（其余 supply 类：支援武器、背包、载具）、2 攻击（offensive）、
	--      3 防御（defensive）、4 复活（stratagem_reinforce）、5 其他（地狱炸弹、金属探测器、紧急信标这些任务用的 special 类）、
	--      -99 读不到
	-- 场上信标 8 个 × 8 格，从 +1 + 4 × 49 开始（stratagem 组件里已经扔出去的，近的在前；没有的那几条 unit_id 是 -1）：
	--   +0 unit_id +1 谁扔的（玩家槽位，-1 = 不知道）+2 战略配备名（字符串号）+3 +4 位置 x、y
	--   +5 还有多久落地（秒）= 信标倒计时 activation_time（舱掉下来还要约 1.4 秒，没算进去）；
	--      扔出去还在滚、没停稳（has_been_enabled 还是假，倒计时没开始）-99；被干扰区作废的 -1
	--   +6 危险半径：脚本里没有（落地伤害在 flow 里），-99
	--   +7 已经落地了（1/0）：倒计时走完、舱已经放出来
	local DIRS = { up = 1, down = 2, left = 3, right = 4 }
	local STRAT_KINDS = { supply = 1, offensive = 2, defensive = 3, special = 5 }
	local CAN_USE_OK = { stratagem_reinforce = true, stratagem_hellbomb = true, stratagem_metaldetector = true }
	local beacon_c = {}

	local function combo_code(combo)
		if type(combo) ~= "table" or #combo == 0 then
			return -99
		end

		local v = 0

		for _, d in ipairs(combo) do
			local k = DIRS[d]

			if not k then
				return -99
			end

			v = v * 10 + k
		end

		return v
	end

	local function strat_kind(li)
		if li.name == "stratagem_resupply" then
			return 0
		elseif li.name == REINFORCE then
			return 4
		end

		return STRAT_KINDS[li.stratagem_type] or -99
	end

	-- 打开着的干扰区（照 StratagemsDisabledAreaComponent.is_unit_inside_any_area，但只算写了半径的球；
	-- 没写半径的要调 Unit.box，不碰，记成"有算不了的"）
	local function no_strat_areas(em)
		local list, unknown = {}, false

		if em.has_entities and not em:has_entities("stratagems_disabled_area") or not em.get_slave_entities then
			return list, unknown
		end

		local lsm = rawget(_G, "LuaSettingsManager")

		for a, e in pairs(em:get_slave_entities("stratagems_disabled_area") or EMPTY) do
			if (e.state or EMPTY).enabled and Unit.alive(a) then
				local ok, st = call(function()
					return lsm:get_settings_by_unit(a)
				end)
				local as = ok and type(st) == "table" and st.area_settings or nil

				if as and as.sphere and type(as.radius) == "number" then
					local p = Unit.world_position(a, 0)

					list[#list + 1] = { p.x, p.y, p.z, as.radius }
				else
					unknown = true
				end
			end
		end

		return list, unknown
	end

	local function by_beacon(a, b)
		return a[5] < b[5]
	end

	local function write_strats(comp, chars, em)
		local areas, unknown = no_strat_areas(em)
		local mm = comp.mission_manager
		local nact = 0

		for i = 1, MAX_PLAYERS do
			if plist[i] then
				nact = nact + 1
			end
		end

		local ctx = { player_count = nact, emergency_beacon = false, mission_manager = mm, state_name = "game" }
		local lstrats = rawget(_G, "LoadoutSettings") and LoadoutSettings.stratagems or EMPTY

		for i = 1, MAX_PLAYERS do
			local b = SG0 + 1 + (i - 1) * SGF
			local u = plist[i]

			for k = 0, SGF - 1 do
				t[b + k] = -1
			end

			if u then
				local s = chars[u].state or EMPTY
				local inv = comp_state(u, "inventory") or s.inventory_state or EMPTY
				local strats = type(inv.stratagems) == "table" and inv.stratagems or EMPTY
				local p = Unit.world_position(u, 0)
				local inside = false

				for _, a in ipairs(areas) do
					if (p.x - a[1]) ^ 2 + (p.y - a[2]) ^ 2 + (p.z - a[3]) ^ 2 <= a[4] * a[4] then
						inside = true
					end
				end

				t[b] = uid(u)

				for k = 1, MAX_STRATS do
					local st = strats[k]
					local c = b + 1 + (k - 1) * STW

					if type(st) == "table" then
						local li = st.loadout_info or lstrats[st.id] or EMPTY
						local cdt = num(st.cooldown_timer, -99)
						local uses = st.uses_left
						local can

						if cdt > 0 or (type(uses) == "number" and uses <= 0) or st.blocked or inside then
							can = 0
						elseif cdt == -99 then
							can = -1
						elseif li.can_use then
							if CAN_USE_OK[li.name] and mm then
								local ok, r = call(li.can_use, ctx)

								can = ok and flag(r) or -1
							else
								can = -1
							end
						else
							can = 1
						end

						if can == 1 and unknown then
							can = -1
						end

						t[c] = sid(li.name)
						t[c + 1] = combo_code(li.combo)
						t[c + 2] = cdt == -99 and -99 or math.max(cdt, 0)
						t[c + 3] = uses == nil and -1 or num(uses, -99)
						t[c + 4] = can
						t[c + 5] = strat_kind(li)
					end
				end
			end
		end

		-- 场上信标
		local n = 0

		for su, e in pairs(all_entities(em, "stratagem")) do
			local s = e.state or EMPTY

			if s.has_been_thrown and Unit.alive(su) then
				local p = Unit.world_position(su, 0)
				local best = math.huge

				for i = 1, MAX_PLAYERS do
					local q = P0 + (i - 1) * PF

					if t[q] == 1 then
						best = math.min(best, (p.x - t[q + 2]) ^ 2 + (p.y - t[q + 3]) ^ 2)
					end
				end

				n = n + 1

				local r = beacon_c[n] or {}

				beacon_c[n] = r
				r[1], r[2], r[3], r[4], r[5] = su, s, p.x, p.y, best
			end
		end

		for i = #beacon_c, n + 1, -1 do
			beacon_c[i] = nil
		end

		table.sort(beacon_c, by_beacon)

		for i = 1, MAX_BEACONS do
			local c = SG0 + 1 + MAX_PLAYERS * SGF + (i - 1) * BCF
			local r = beacon_c[i]

			for k = 0, BCF - 1 do
				t[c + k] = -1
			end

			if r then
				local s = r[2]
				local at = num(s.activation_time, -99)

				t[c] = uid(r[1])
				t[c + 1] = s.owner_unit and slot_of[s.owner_unit] or -1
				t[c + 2] = sid((s.stratagem_info or EMPTY).name)
				t[c + 3], t[c + 4] = r[3], r[4]

				if s.abort then
					t[c + 5] = -1
				elseif not s.has_been_enabled then
					-- 还在滚、没停稳：倒计时还没开始
					t[c + 5] = -99
				else
					t[c + 5] = at == -99 and -99 or math.max(at, 0)
				end

				t[c + 6] = -99
				t[c + 7] = flag(not s.abort and s.has_been_enabled and at ~= -99 and at <= 0)
			end
		end

		t[SG0] = 1
	end

	-- M12 镜头区：+0 区版本（CAMERA_ENABLED 关着或没有 CameraManager 是 0）。8 格，从 +1 开始，读不到 -99：
	--   +1 +2 屏幕中心看到的地面点 x、y（CameraManager.ground_position）
	--   +3 半宽（米，过屏幕中心那条横线上，中心到左右边）
	--   +4 半高（米，中心到上下边取近的那边，保守值；地面上屏幕是梯形，远边宽、近边窄，见 +7、+8）
	--   +5 转角（度，CameraManager.follow_spin，和表头 15 号格同一个数：手柄 (0, 1) 转这么多就是屏幕上方在地图上的方向）
	--   +6 缩放：镜头离跟随点的距离（米，follow_distance；PC 上固定 17）
	--   +7 中心到屏幕上边（远边）沿屏幕上方的地面距离（米；上边看到天、没有交点 -99）+8 中心到屏幕下边（近边）的地面距离
	-- 只读 CameraManager 表里存着的数（position、ground_position、fov、follow_angle、follow_spin、follow_distance、
	-- screen_resolution），自己用三角函数算，不调引擎。镜头往下压 follow_angle，竖直视角 fov（Camera.set_vertical_fov）。
	local function write_camera()
		for k = 1, CMF do
			t[CM0 + k] = -99
		end

		local cam = rawget(_G, "CameraManager")

		if not cam then
			return
		end

		local gx, gy, gz = xyz_of(cam.ground_position)
		local _, _, pz = xyz_of(cam.position)

		if gx then
			t[CM0 + 1], t[CM0 + 2] = gx, gy
		end

		local spin = num(cam.follow_spin, nil)

		if spin then
			t[CM0 + 5] = math.deg(spin)
		end

		t[CM0 + 6] = num(cam.follow_distance, -99)

		local fov, a = num(cam.fov, nil), num(cam.follow_angle, nil)
		local res = type(cam.screen_resolution) == "table" and cam.screen_resolution or EMPTY
		local w, h = num(res.width, 0), num(res.height, 0)

		if gz and pz and fov and a and a > 1e-3 and fov > 0 then
			local H = pz - gz

			if H > 0 then
				local tc = H / math.tan(a)
				local up = a - fov / 2
				local far = up > 1e-3 and H / math.tan(up) - tc or nil
				local near = tc - H / math.tan(a + fov / 2)

				if w > 0 and h > 0 then
					t[CM0 + 3] = H / math.sin(a) * math.tan(fov / 2) * w / h
				end

				t[CM0 + 4] = far and math.min(far, near) or near
				t[CM0 + 7] = far or -99
				t[CM0 + 8] = near
			end
		end

		t[CM0] = 1
	end

	-- M11 友方伤害源区（第 8 版，P1 第三批）：+0 区版本。最多 8 个 × 9 格，从 +1 开始，
	-- 离任意活着的玩家 HAZ_RANGE（60）米以内，近的在前；空位整条 -1：
	--   +0 unit_id +1 种类（0 炮塔 turret/launcher_turret、1 地雷 mine、2 电弧塔 tesla、3 其他、
	--      4 穿刺虫触手 melee_turret、5 穿刺虫钻地后触手还没钻出来的出生点）
	--   +2 +3 位置 x、y +4 朝向（度，炮塔有效，地雷/电弧塔/触手写 0；种类 5 写第几根触手 1~3）
	--   +5 正在开火 / 放电 / 触手在打（1/0）
	--   +6 射程或危险半径（米，炮塔 weapon_info.range，地雷 5 米，电弧塔 tesla_info.range 8 米，触手 melee_info.radius 5 米）
	--   +7 扇区半角（度，炮塔用，电弧塔写 -99）；地雷：被踩了还有几秒炸（没被踩 -99）；触手 / 种类 5：还要多少秒才开始打（0 = 已经能打）
	--   +8 谁放的（玩家槽位 0~3，-1 = 地图自带 / 不知道）
	-- 触手（2026-10-18，躲穿刺虫触手）：bug_impaler_tentacle 是 melee_turret，不动，身边 5 米里有人就打（打一下 1.5 秒，
	-- 正在扑出去 is_dodging 的人不挑）。穿刺虫钻地那一刻就在目标身边定好 3 个出生点（burrow_tentacles[i].wanted_spawn_position），
	-- 1.5 秒后钻出来、再 1 秒能打，所以出生点提前约 2.5 秒就写（种类 5），钻出来以后换成真触手（种类 4）。
	local haz_c = {}

	local function by_haz_dist(a, b)
        -- 触手/出生点先保留，避免队友附近的大量炮塔和地雷挤掉致命攻击。
        local ap, bp = a[2] == 4 or a[2] == 5, b[2] == 4 or b[2] == 5
        if ap ~= bp then return ap end
        if a[10] == b[10] then return a[1] < b[1] end
        return a[10] < b[10]
	end

	local function write_hazards(em)
		for k = 0, MAX_HAZ * HZF do
			t[HZ0 + k] = -1
		end
		t[HZ0] = 0

		if not HAZARDS_ENABLED then
			return
		end

		for i = #haz_c, 1, -1 do
			haz_c[i] = nil
		end

		local nh = 0
		B.turret_rounds = B.turret_rounds or {}

		local function dist_to_players(px, py)
			local best = math.huge
			local has_p = false
			for i = 1, MAX_PLAYERS do
				local q = P0 + (i - 1) * PF
				if t[q] == 1 and t[q + 14] ~= 1 then
					has_p = true
					local dx, dy = px - t[q + 2], py - t[q + 3]
					local d2 = dx * dx + dy * dy
					if d2 < best then
						best = d2
					end
				end
			end
			return has_p and best or 0
		end

		local max_d2 = HAZ_RANGE * HAZ_RANGE

		-- 1. 炮塔 (turret & launcher_turret)
		local function add_turrets(comp_name)
			local tlist = entities(em, comp_name)
			for u, e in pairs(tlist) do
				if Unit.alive(u) then
					local s = e.state or comp_state(u, comp_name) or EMPTY
					local hs = s.health_state or EntityAux.state(u, "health") or EMPTY
					if not hs.is_dead and not s.out_of_ammo and not s.time_to_die then
						local p = Unit.world_position(u, 0)
						local d2 = dist_to_players(p.x, p.y)
						if d2 <= max_d2 then
							-- 炮塔朝向：读主控状态里的 turret_rotation_node，不调新引擎函数 Unit.node
							-- 读不到节点就报 -99（Python 那边按小圈算），不退回节点 0：底座朝向不是枪口朝向（评审 rc3-turrets）
							local heading = -99
							local node = s.turret_rotation_node
							if node then
								local f = Quaternion.forward(Unit.world_rotation(u, node))
								heading = math.deg(math.atan2(f.y, f.x))
							end

							-- 在不在开火：开火中、cooldown中、弹量减少、或者锁定了目标
							local cur_r = s.rounds_remaining
							local prev_r = B.turret_rounds[u]
							B.turret_rounds[u] = cur_r
							local rounds_drop = prev_r and cur_r and cur_r < prev_r
							local is_firing = s.is_firing or (type(s.fire_cooldown) == "number" and s.fire_cooldown > 0) or rounds_drop or (s.target_unit ~= nil and not s.out_of_ammo)

							local wi = s.weapon_info or EMPTY
							local ti = s.turret_info or EMPTY
							local reach = num(wi.range, num(ti.check_for_enemies_radius, -99))

							-- 扇区半角（度）：武器散布+余量，抛射炮塔加余量
							local sp = num(wi.spread, nil)
							if sp and sp > 0 and sp < 0.5 then
								sp = math.deg(sp)
							end
							local half = (sp and sp > 0) and sp or 10
							if wi.projectile or wi.z_direction then
								half = half + 25
							end
							half = math.max(15, math.min(60, half))

							local owner = s.owner_unit and slot_of[s.owner_unit] or -1

							nh = nh + 1
							local row = haz_c[nh] or {}
							haz_c[nh] = row
							row[1] = uid(u)
							row[2] = 0
							row[3], row[4] = p.x, p.y
							row[5] = heading
							row[6] = flag(is_firing)
							row[7] = reach
							row[8] = half
							row[9] = owner
							row[10] = d2
						end
					end
				end
			end
		end

		add_turrets("turret")
		add_turrets("launcher_turret")

		-- 2. 地雷 (mine)
		local mlist = entities(em, "mine")
		for u, e in pairs(mlist) do
			if Unit.alive(u) then
				local s = e.state or comp_state(u, "mine") or EMPTY
				if not s.has_exploded and not s.time_to_die then
					local p = Unit.world_position(u, 0)
					local d2 = dist_to_players(p.x, p.y)
					if d2 <= max_d2 then
						-- 地雷半径写死 5 米（脚本 unknown_6e467e424b5e3ccd / unknown_7856ee155f856a82 都是 5，不调引擎防崩溃）
						local owner = s.owner_unit and slot_of[s.owner_unit] or -1
						nh = nh + 1
						local row = haz_c[nh] or {}
						haz_c[nh] = row
						row[1] = uid(u)
						row[2] = 1
						row[3], row[4] = p.x, p.y
						row[5] = 0
						row[6] = flag(s.triggered)
						row[7] = 5.0
						-- 地雷 +7：被踩了还有几秒炸（2026-10-18；脚本 mine_component：踩到后 countdown 0.5 秒到了才 armed，
						-- armed 后 detonation_timer 0.4 秒炸）；没被踩 -99
						if s.triggered then
							local wait = s.armed and 0 or math.max(num(s.countdown, 0), 0)
							row[8] = wait + math.max(num(s.detonation_timer, 0), 0)
						else
							row[8] = -99
						end
						row[9] = owner
						row[10] = d2
					end
				end
			end
		end

		-- 3. 电弧塔 (tesla)
		local tsl_list = entities(em, "tesla")
		for u, e in pairs(tsl_list) do
			if Unit.alive(u) then
				local s = e.state or comp_state(u, "tesla") or EMPTY
				local hs = s.health_state or (s.has_health and EntityAux.state(u, "health")) or EMPTY
				if not s.was_dead and not hs.is_dead then
					local p = Unit.world_position(u, 0)
					local d2 = dist_to_players(p.x, p.y)
					if d2 <= max_d2 then
						local ti = s.tesla_info or EMPTY
						local reach = num(ti.range, 8.0)
						local is_firing = (num(s.charge, 0) > 0) or (num(s.cooldown_timer, 0) > 0) or s.do_shoot
						local owner = s.owner_unit and slot_of[s.owner_unit] or -1
						nh = nh + 1
						local row = haz_c[nh] or {}
						haz_c[nh] = row
						row[1] = uid(u)
						row[2] = 2
						row[3], row[4] = p.x, p.y
						row[5] = 0
						row[6] = flag(is_firing)
						row[7] = reach
						row[8] = -99
						row[9] = owner
						row[10] = d2
					end
				end
			end
		end

		-- 4. 穿刺虫触手 (melee_turret)：V10 用 heading=-2-冷却剩余，保留当前已出手攻击的真实年龄。
		local function add_row(id, kind, x, y, heading, firing, reach, half, d2, attack_left, cooldown, source, target_slot)
			nh = nh + 1
			local row = haz_c[nh] or {}
			haz_c[nh] = row
			row[1], row[2], row[3], row[4], row[5] = id, kind, x, y, heading
            row[6], row[7], row[8], row[9], row[10] = firing, reach, half, -1, d2
            row[11], row[12], row[13], row[14] = attack_left or -99, cooldown or -99, source or 1, target_slot or -1
		end

        local mt_master = entities(em, "melee_turret")
        local mt_list = all_entities(em, "melee_turret")
        local melee_master = entities(em, "melee")
		for u, e in pairs(mt_list) do
			if Unit.alive(u) then
				local s = e.state or comp_state(u, "melee_turret") or EMPTY
				local local_clock = mt_master[u] ~= nil
				local hs = observed_health(u, e, local_clock)
				if not hs.is_dead and not s.time_to_die then
					local p = Unit.world_position(u, 0)
					local d2 = dist_to_players(p.x, p.y)
					if d2 <= max_d2 then
						local mi = (e.settings or EMPTY).melee_info or EMPTY
                        local ms = (melee_master[u] or EMPTY).state or EMPTY
                        add_row(uid(u), 4, p.x, p.y, s.time_since_last_attack and (-2 - s.time_since_last_attack) or -99,
                            local_clock and flag(s.time_since_last_attack ~= nil) or -1,
                            num(mi.radius, 5) + num(mi.center_distance, 0), local_clock and math.max(num(s.spawn_timer, 0), 0) or -99,
                            d2, num(ms.melee_delay_timer, -99), local_clock and num(s.time_since_last_attack, -99) or -99,
                            local_clock and 1 or 2, slot_of[s.target_unit or ms.target_unit] or -1)
					end
				end
			end
		end

		-- 5. 穿刺虫钻地了、触手还没钻出来：预定的出生点（真触手出来了就不写这一根）
		local en_list = all_entities(em, "enemy")
		for u, e in pairs(en_list) do
			local s = e.state
			local bt = s and s.burrow_tentacles
			if type(bt) == "table" and not s.burrow_tentacles_spawned and not s.burrow_exit_timer and Unit.alive(u)
					and not (s.health_state or EMPTY).is_dead then
				local wait = math.max(num(s.burrow_start_timer, 0), 0) + 1
				for i, tt in ipairs(bt) do
					if tt.unit == nil then
						local x, y = boxed_xy(tt.spawn_position or tt.wanted_spawn_position)
						if x then
							local d2 = dist_to_players(x, y)
							if d2 <= max_d2 then
								add_row(uid(u), 5, x, y, i, 0, 5, wait, d2)
							end
						end
					end
				end
			end
		end

		table.sort(haz_c, by_haz_dist)

		local count = math.min(nh, MAX_HAZ)
		for i = 1, count do
			local row = haz_c[i]
			local base = HZ0 + 1 + (i - 1) * HZF
            for k = 1, 9 do t[base + k - 1] = row[k] end
            t[base + 9], t[base + 10], t[base + 11], t[base + 12] = row[2] >= 4 and (row[11] or -99) or -99, row[2] >= 4 and (row[12] or -99) or -99, row[2] >= 4 and (row[13] or 0) or 0, row[2] >= 4 and (row[14] or -1) or -1
		end

		if B.frame % 600 == 0 then
			for k in pairs(B.turret_rounds) do
				if not Unit.alive(k) then
					B.turret_rounds[k] = nil
				end
			end
		end

		t[HZ0] = 1
	end

	-- ---------- M15 石头/障碍物区（P1 第三批 rocks，gm2 那份；2026-10-15 合并时改了起点、节流、区版本） ----------
	-- 从每个玩家身上水平往 16 个方向拉射线：PhysicsWorld.immediate_raycast + "closest" + "default" 过滤器，
	-- 和地形 mod（ai_terrain.lua）已经验证不闪退的写法一样（用户按推荐定，评审 rc3-rocks 五.1）。
	-- 起点：身子外 ROCK_START 米、离地 ROCK_UP 米（hk 那份的做法，拍板清单第 18 条）。从身子中间拉，起点在她自己的
	--   碰撞体里，游戏里没人这么用，可能每条都撞到自己。记的距离 = ROCK_START + 射线撞到的距离（从身子中心算）。
	-- 节流：每帧最多给一个玩家拉一轮（16 条），同一个人两轮至少隔 ROCK_PERIOD 秒；没拉的帧写上一轮的结果。
	-- 每个玩家：+0 unit_id +1~+16 距离（米，碰不到 -1）。没有物理世界（飞船、读不到）时区版本写 0。
	-- "closest" 拿不到撞的是什么：人和虫子也会被当石头，Python 那边按已知的人 / 虫位置把这些点滤掉（rocks.drop_bodies）。
	local ROCK_RANGE = 10.0
	local ROCK_START = 0.7
	local ROCK_UP = 0.9
	local ROCK_PERIOD = 0.2
	local ROCK_ANGLES = {}
	for i = 1, RK_RAYS do
		local a = math.rad((i - 1) * 360 / RK_RAYS)
		ROCK_ANGLES[i] = { math.cos(a), math.sin(a) }
	end

	local function write_rocks(chars)
		B.rock_at = B.rock_at or {}
		B.rock_owner = B.rock_owner or {}
		B.rock_d = B.rock_d or {}

		local pw = rawget(_G, "PhysicsWorld") and game_world()
		pw = pw and World.physics_world(pw)

		local pick_i, pick_at
		for i = 1, MAX_PLAYERS do
			local u = plist[i]
			if B.rock_owner[i] ~= u then
				-- 这个槽位换了人：上一个人的结果作废
				B.rock_owner[i], B.rock_at[i], B.rock_d[i] = u, nil, nil
			end
			if u and chars[u] and pw then
				local at = B.rock_at[i]
				if (not at or B.time - at >= ROCK_PERIOD) and (not pick_i or (at or -1) < (pick_at or -1)) then
					pick_i, pick_at = i, at
				end
			end
		end

		if pick_i then
			local u = plist[pick_i]
			local p = Unit.world_position(u, 0)
			local d = B.rock_d[pick_i] or {}
			B.rock_d[pick_i] = d
			for a = 1, RK_RAYS do
				local dir = ROCK_ANGLES[a]
				local from = Vector3(p.x + dir[1] * ROCK_START, p.y + dir[2] * ROCK_START, p.z + ROCK_UP)
				local hit, pos = PhysicsWorld.immediate_raycast(pw, from, Vector3(dir[1], dir[2], 0), ROCK_RANGE - ROCK_START,
					"closest", "collision_filter", "default")
				if hit and pos then
					local dx, dy = pos.x - p.x, pos.y - p.y
					local dist = math.sqrt(dx * dx + dy * dy)
					d[a] = dist <= ROCK_RANGE and dist or -1
				else
					d[a] = -1
				end
			end
			B.rock_at[pick_i] = B.time
		end

		for i = 1, MAX_PLAYERS do
			local b = RK0 + 1 + (i - 1) * RKF
			local u = plist[i]
			local d = B.rock_d[i]
			t[b] = (u and chars[u]) and uid(u) or -1
			for a = 1, RK_RAYS do
				t[b + a] = (u and chars[u] and d and d[a]) or -1
			end
		end

		if pw then
			t[RK0] = 1
		end
	end

	-- ---------- 第 8 版（2026-10-14，P1 第三批 arc，Haiku 那份；2026-10-15 合并时加了往下找地面的兜底）：M5 弧线区 ----------

	-- M5 弧线区：+0 区版本。每个玩家 15 格，从 +1 开始，顺序和玩家区一样（分不出哪个是 2P，每个人都写，陪玩那边按 unit_id 挑）：
	--   +0 unit_id（-1 = 没这个人）
	--   +1 算好的游戏时间（-1 = 手上不是会飞的弹 / 还没算过；-99 = 算的时候出错）
	--   +2 +3 +4 出膛点 x、y、z（和游戏 launcher_component 一样：枪口位置 + 枪口偏移，再往前 1 米、往上 1 米）
	--   +5 +6 +7 出膛方向（单位向量：枪的朝向水平分量 + 配置里的 z_direction，和 throwable 的初速方向一样）
	--   +8 +9 +10 落点 x、y、z（撞到的那一点；没撞到 -99）
	--   +11 飞多久（秒，到撞到为止；没撞到 -99）
	--   +12 中途有没有撞东西（1 = 飞途中碰到东西，地面也算；0 = 最长 6 秒内什么也没碰到）
	--   +13 撞到的是什么（0 = 地面、1 = 墙或石头、2 = 人、3 = 虫（有血的东西都算虫）；-1 = 没撞到或认不出来）
	--   +14 溅射半径（米，弹的 explosive_info.blast_radius；读不到 -99）
	-- 算法：初速 = sqrt(18 × 投掷距离)，投掷距离 = throw_distance_min + 威力 × (max - min)（和 throwable_component 一样）；
	-- 重力 18。雷鸣蓄力中按 calculate_charge_power 的写法算"现在"的威力，连发第 2、3 发按 burst_round 减。
	-- 每 0.1 秒切一段，每段用 damage_ray 拉一条射线，第一个碰到的（不算自己和这把枪）就是落点。
	-- 兜底（从 ds 那份搬，评审 rc3-arc D1）：damage_ray 是子弹的过滤器，打不打得到地形没验证过。所以这一段什么都没撞到时，
	-- 再在段末往下拉一条 "closest" + "default"（地形 mod 验证过的写法）找地面高度，段末已经低于地面就算落地（0 = 地面）。
	-- 撞到东西按命中法线分地面 / 墙（arc_kind），两个都留，不赌 damage_ray 是哪一边。
	-- 只有能"抛"的弹（throwable_info：榴弹、雷鸣）才算；导弹等填 -1，陪玩那边不开火。
	local function arc_ground(pw, x, y, z0)
		-- 引擎的 Vector3 只在当前帧有效，每次现做（ai_terrain 第 3 版踩过的坑）
		local hit, pos = PhysicsWorld.immediate_raycast(pw, Vector3(x, y, z0), Vector3(0, 0, -1), ARC_GROUND_DOWN, "closest",
			"collision_filter", "default")

		return hit and pos and pos.z or nil
	end

	local function arc_clear(b, v)
		for k = 1, ARF - 1 do
			t[b + k] = v
		end
	end

	-- 命中的东西是什么：0 地面、1 墙石头、2 人、3 虫；认不出来 -1（法线不是数，不敢猜地面还是墙）
	local function arc_kind(hu, n)
		if hu then
			if slot_of[hu] then
				return 2
			end

			if EntityAux.has_component(hu, "health") then
				return 3
			end
			-- 没血的东西也看法线（2026-10-22 实测：地面本身也有 unit，以前一律算墙，雷鸣落地全被当成撞墙）
		end

		local nz = n and n.z

		if type(nz) ~= "number" then
			return -1
		end

		return nz > 0.5 and 0 or 1
	end

	-- 算一次弧线，写进 b 起的 14 格（b 是 +0 那格 unit_id 的下标，+1 在 b + 1）。u 是玩家，w 是他手上这把
	local function arc_round(b, u, w, pw)
		-- 2026-10-22：以前读 EntityAux.state(w, "launcher")，那是同步给别人的那份（reload_slave 只抄了散布、射速这些），
		-- 没有 projectile / power / z_direction / ray_source_offset，弹一直找不到，雷鸣整局都是 -1。
		-- 改成和 write_weapon 一样读主份（state_master_interface "weapon"），主份没有再退回同步份；弹和威力再拿配置兜底
		local ms = weapon_states(w)
		local ls = ms ~= EMPTY and ms or EntityAux.state(w, "launcher") or EMPTY
		local wi = ls.weapon_info or (LoadoutSettings.get_upgraded_settings(w) or EMPTY).weapon_info or EMPTY
		local proj = ls.projectile or wi.projectile
		local ps = proj and LuaSettingsManager:get_settings_by_unit_path(proj) or EMPTY
		local th = ps.throwable_info
		local ex = ps.explosive_info or EMPTY

		if not th then
			arc_clear(b, -1)

			return
		end

		-- 出膛：枪口（武器位置 + 枪口偏移，偏移在手的朝向上转过去），弹生成在它前面 1 米、上面 1 米
		local rot = Unit.world_rotation(u, ls.attach_node)
		local fwd = Quaternion.forward(rot)
		local mp = Unit.world_position(w, 0)
		local off = ls.ray_source_offset and Quaternion.rotate(rot, Vector3Aux.unbox(ls.ray_source_offset)) or Vector3(0, 0, 0)
		local sx, sy, sz = mp.x + off.x + fwd.x, mp.y + off.y + fwd.y, mp.z + off.z + 1

		-- 威力：和 LauncherComponent.do_fire 一样，蓄力的（fire_on_release）按 calculate_charge_power 算
		local p = ls.power or wi.power or 0

		if ls.fire_on_release then
			if ls.burst_round and ls.burst_start_power then
				p = ls.burst_start_power - (ls.burst_round - 1) * ls.burst_round_power_decrease
			elseif ls.charge_max_extra_power and ls.shot_charge_timer and ls.max_charge_time then
				p = p + ls.charge_max_extra_power * (ls.shot_charge_timer / ls.max_charge_time)
			end
		end

		local dmin, dmax = th.throw_distance_min or 0, th.throw_distance_max or 0
		local v = math.sqrt(math.max(0, dmin + p * (dmax - dmin)) * ARC_GRAVITY)
		local dx, dy, dz = fwd.x, fwd.y, ls.z_direction or wi.z_direction or 0
		local dl = math.sqrt(dx * dx + dy * dy + dz * dz)

		if dl < 1e-6 then
			error("arc: 出膛方向是零")
		end

		dx, dy, dz = dx / dl, dy / dl, dz / dl

		t[b + 1] = B.time
		t[b + 2], t[b + 3], t[b + 4] = sx, sy, sz
		t[b + 5], t[b + 6], t[b + 7] = dx, dy, dz
		t[b + 14] = num(ex.blast_radius, -99)

		-- 逐段拉射线。引擎的 Vector3 只在当前帧有效，所以段端点用普通数存，每次拉线现做 Vector3
		local px, py, pz, tp = sx, sy, sz, 0

		for k = 1, ARC_STEPS do
			local tk = k * ARC_DT
			local nx, ny = sx + dx * v * tk, sy + dy * v * tk
			local nz = sz + dz * v * tk - 0.5 * ARC_GRAVITY * tk * tk
			local ax, ay, az = nx - px, ny - py, nz - pz
			local len = math.sqrt(ax * ax + ay * ay + az * az)

			if len > 1e-4 then
				local hits = PhysicsWorld.immediate_raycast(pw, Vector3(px, py, pz), Vector3(ax / len, ay / len, az / len), len,
					"all", "collision_filter", "damage_ray")
				local best, bu, bn = math.huge, nil, nil

				if hits then
					for _, h in ipairs(hits) do
						local hd, actor = h[2], h[4]
						local hu = actor and Actor.unit(actor)

						if type(hd) == "number" and hu ~= u and hu ~= w and hd < best then
							best, bu, bn = hd, hu, h[3]
						end
					end
				end

				if best < math.huge then
					local f = best / len

					t[b + 8], t[b + 9], t[b + 10] = px + ax * f, py + ay * f, pz + az * f
					t[b + 11] = tp + ARC_DT * f
					t[b + 12] = 1
					t[b + 13] = arc_kind(bu, bn)

					return
				end

				local gz = arc_ground(pw, nx, ny, math.max(pz, nz) + ARC_GROUND_UP)

				if gz and nz <= gz then
					-- 这一段穿到地面以下了：按段里线性插值找过地面的那一点，算落地
					local f = (pz > gz and pz ~= nz) and (pz - gz) / (pz - nz) or 1

					t[b + 8], t[b + 9], t[b + 10] = px + ax * f, py + ay * f, gz
					t[b + 11] = tp + ARC_DT * f
					t[b + 12] = 1
					t[b + 13] = 0

					return
				end
			end

			px, py, pz, tp = nx, ny, nz, tk
		end

		t[b + 8], t[b + 9], t[b + 10], t[b + 11] = -99, -99, -99, -99
		t[b + 12] = 0
		t[b + 13] = -1
	end

	local function arc_weapon(c)
		local s = c and c.state or EMPTY

		return s.current_weapon or (s.inventory_state or EMPTY).current_weapon
	end

	-- 每帧先把各人的格子理一遍（换了人清掉；手上不是发射器的写 -1），再挑一个最早算的人算一次（一帧最多一个）
	local function write_arc(chars)
		B.arc_at = B.arc_at or {}
		B.arc_owner = B.arc_owner or {}

		local pw = rawget(_G, "PhysicsWorld") and rawget(_G, "Actor") and game_world()

		pw = pw and World.physics_world(pw)

		local pick_i, pick_at

		for i = 1, MAX_PLAYERS do
			local u = plist[i]
			local b = AR0 + 1 + (i - 1) * ARF
			local w = u and arc_weapon(chars[u])

			if B.arc_owner[i] ~= u then
				B.arc_owner[i] = u
				arc_clear(b, -1)
			end

			t[b] = u and uid(u) or -1

			if not (w and Unit.alive(w) and pw and EntityAux.has_component(w, "launcher")) then
				arc_clear(b, -1)
			else
				local at = B.arc_at[u] or -math.huge

				if B.time - at >= ARC_PERIOD and (pick_at == nil or at < pick_at) then
					pick_i, pick_at = i, at
				end
			end
		end

		if pick_i then
			local u = plist[pick_i]
			local b = AR0 + 1 + (pick_i - 1) * ARF

			B.arc_at[u] = B.time

			local ok, err = call(arc_round, b, u, arc_weapon(chars[u]), pw)

			if not ok then
				arc_clear(b, -99)
				B.extra_errors = (B.extra_errors or 0) + 1
				t[SI0 + 1] = B.extra_errors

				if B.errors == 0 then
					record_weapon_error("arc: " .. tostring(err))
				end
			end
		end

		t[AR0] = 1
	end

	local function extra_part(f, ...)
		local ok, err = call(f, ...)

		if not ok then
			B.extra_errors = (B.extra_errors or 0) + 1
			t[SI0 + 1] = B.extra_errors

			if B.errors == 0 then
				record_weapon_error("extra: " .. tostring(err))
			end
		end

		return ok
	end

    -- M17: original state clocks and exact mother-child handles. Append only.
    -- Remote timers stay unknown; nil on a local master means no active timer.
    function B.write_logic(enemies, nw, chars)
        t[LG0], t[MV0] = 0, 0
        for i = 1, MAX_ENEMIES do
            local b = LG0 + 1 + (i - 1) * LGF
            for k = 0, LGF - 1 do t[b+k] = -99 end
            if i <= nw then
                local u = eu[eidx[i]]
                local e = enemies[u] or EMPTY
                local s, info = e.state or EMPTY, (e.settings or EMPTY).enemy_info or EMPTY
                local own = is_master("enemy", u)
                local children = s.burrow_tentacles or EMPTY
                t[b], t[b+1] = uid(u), own and 1 or 0
                if own then
                    t[b+2] = num(s.spawn_timer,0)
                    local status = comp_state(u,"status")
                    if status and type(status.status_effects)=="table" then
                        t[b+3] = 0
                        for _, effect in ipairs(status.status_effects) do
                            if effect.name=="stun" and effect.active and not effect.remove then
                                t[b+3] = math.max(t[b+3],num(effect.timer,0))
                            end
                        end
                    end
                    t[b+4], t[b+5] = num(s.time_since_last_attack,0), flag(s.has_attacked)
                    t[b+6], t[b+7] = num(s.burrow_cooldown_timer,0), num(s.burrow_start_timer,0)
                    t[b+8], t[b+9] = num(s.burrow_timer,-99), num(s.burrow_exit_timer,0)
                    t[b+10] = num(s.burrow_start_hitpoints,-99)
                    t[b+11] = flag((s.health_state or EMPTY).is_downed)
                    t[b+17] = flag(s.burrow_tentacles_spawned)
                end
                for k=1,3 do
                    local child = children[k] and children[k].unit
                    t[b+11+k] = child and Unit.alive(child) and not (children[k].health_state or EMPTY).is_dead and uid(child) or -1
                end
                t[b+15], t[b+16] = num(info.recovery_flee_distance,-99), num(info.movement_speed_flee,-99)
            end
        end
        for i=1,MAX_PLAYERS do
            local b, u = MV0+1+(i-1)*MVF, plist[i]
            for k=0,MVF-1 do t[b+k] = -99 end
            if u then
                local s = (chars[u] or EMPTY).state or EMPTY
                local m = s.mover_state or comp_state(u,"mover") or EMPTY
                t[b],t[b+1] = uid(u),num(m.wanted_move_speed,-99)
                t[b+2],t[b+3] = num(m.acceleration,-99),num(m.deceleration,-99)
                t[b+4],t[b+5] = flag(m.lock_direction),flag(m.constant_movement)
                t[b+6],t[b+7] = num(s.sprint_time,-99),num(s.initial_move_speed,-99)
                t[b+8],t[b+9] = num(m.slow_multiplier,-99),num(m.deceleration_sideward,-99)
            end
        end
        t[LG0],t[MV0] = 1,1
    end

	-- ---------- M18 玩家盾量区（第 14 版，2026-11-01，HD1-023 冲锋虫节奏模块） ----------

	-- 盾量区：区内第 k 格 = t[SD0 + k]。+0 区版本（1 = 这一帧写好了 / 0 = 出错）、+1 本区出错次数。
	-- 每个玩家 5 格，从 +1 开始，顺序和玩家区一样（分不出哪个是 2P，每个人都写，陪玩那边按 unit_id 挑）：
	--   +0 unit_id（-1 = 这一格没人）
	--   +1 盾量 shieldpoints
	--   +2 盾上限 max_shieldpoints
	--   +3 盾开着 shield_activated（1 / 0；组件没设这个字段 -1）
	--   +4 充能计时器 shield_regen_timer（秒，挨打后重设成 shield_regen_delay；没有 shield 组件 -1）
	-- 全是只读：shield_component.lua 43-51（setup_master 写的那几个字段）+ 274-289（挡伤害时扣盾、重置计时器）。
	-- 没背盾 / 没有 shield 组件写 -1（陪玩那边当“没盾”）；组件在但读出错也写 -1 并记一次错，不影响其他区。
	-- 放在 B 上（不是本地函数）：snapshot 的 upvalue 数已贴 60 的上限（luaJIT 硬限制），多一个都编译不过。
	B.write_shield = function(chars)
		t[SD0] = 0                            -- 出错就留 0，陪玩那边当“这一帧读不到盾”
		for i = 1, MAX_PLAYERS do
			local b, u = SD0 + 2 + (i - 1) * SDF, plist[i]

			for k = 0, SDF - 1 do
				t[b + k] = -1
			end

			if u and chars[u] then
				t[b] = uid(u)

				local has_ok, has = call(EntityAux.has_component, u, "shield")

				if not has_ok then
					B.shield_errors = B.shield_errors + 1
					t[SD0 + 1] = B.shield_errors
				elseif has then
					local st_ok, s = call(EntityAux.state, u, "shield")

					if st_ok and type(s) == "table" then
						t[b + 1] = num(s.shieldpoints, -1)
						t[b + 2] = num(s.max_shieldpoints, -1)
						t[b + 3] = s.shield_activated == nil and -1 or flag(s.shield_activated)
						t[b + 4] = num(s.shield_regen_timer, -1)
					else
						B.shield_errors = B.shield_errors + 1
						t[SD0 + 1] = B.shield_errors
					end
				end
			end
		end

		t[SD0] = 1
	end

	-- ---------- M19 冲锋虫射线区（第 15 版，2026-11-04，HD1-023） ----------

	-- 冲锋虫冲不冲（bug_tank_states.lua 228 行）要同时满足：冷却好了、最近的人在 rush_distance_min（6）外、
	-- 目标在正前 attack_angle（20°）内、前触须 obstacle_distance ≥ 10、左右触须 ≥ 4、看得见最近的人、两个肩膀射线通、
	-- 没被减速。后五条是它自己的射线（异步，结果写回 state），陪玩那边算不出来，这里原样读出来。
	-- 区内第 k 格 = t[TR0 + k]。+0 区版本（1 = 写好了）、+1 出错次数。每只 TRF 格，从 +2 开始，按敌人区顺序取前 MAX_TR 只冲锋虫：
	--   +0 unit_id（-1 = 空位）
	--   +1 前触须 obstacle_distance（没碰到 = 1000；没这个字段 -1）
	--   +2 左触须 obstacle_distance_left  +3 右触须 obstacle_distance_right（同上）
	--   +4 左肩通 left_shoulder_clear  +5 右肩通 right_shoulder_clear（1 / 0；没算过 -1）
	--   +6 离最近的人 distance_to_closest_target（-1 = 没有）
	--   +7 目标在它朝向的哪边 angle_to_target（弧度，带正负；-99 = 没有）
	--   +8 减速中 StatusComponent.is_status_enabled(u, "slow")（1 / 0；读不到 -1）
	--   +9 这只虫是不是本机算的（1 / 0；不是本机算的，上面几格是旧的或没有）
	B.write_tankrays = function(enemies, nw)
		t[TR0] = 0
		for k = TR0 + 2, N do
			t[k] = -1
		end

		local SC = rawget(_G, "StatusComponent")
		local n = 0

		for i = 1, nw do
			if n >= MAX_TR then
				break
			end

			local u = eu[eidx[i]]
			local e = enemies[u] or EMPTY
			local s = e.state or EMPTY

			if s.rush_cooldown ~= nil and s.obstacle_distance_left ~= nil then
				local b = TR0 + 2 + n * TRF

				n = n + 1
				t[b] = uid(u)
				t[b + 1] = num(s.obstacle_distance, -1)
				t[b + 2] = num(s.obstacle_distance_left, -1)
				t[b + 3] = num(s.obstacle_distance_right, -1)
				t[b + 4] = s.left_shoulder_clear == nil and -1 or flag(s.left_shoulder_clear)
				t[b + 5] = s.right_shoulder_clear == nil and -1 or flag(s.right_shoulder_clear)
				t[b + 6] = num(s.distance_to_closest_target, -1)
				t[b + 7] = num(s.angle_to_target, -99)
				t[b + 8] = -1

				if SC and type(SC.is_status_enabled) == "function" then
					local ok, on = call(SC.is_status_enabled, u, "slow")

					if ok then
						t[b + 8] = flag(on)
					else
						B.tankrays_errors = B.tankrays_errors + 1
						t[TR0 + 1] = B.tankrays_errors
					end
				end

				t[b + 9] = flag(is_master("enemy", u))
			end
		end

		t[TR0] = 1
	end

	B.run_tankrays = function(enemies, nw)
		local tr_ok, tr_err = call(B.write_tankrays, enemies, nw)

		if not tr_ok then
			B.tankrays_errors = B.tankrays_errors + 1
			t[TR0 + 1] = B.tankrays_errors

			if B.errors == 0 then
				record_weapon_error("tankrays: " .. tostring(tr_err))
			end
		end
	end

	local function snapshot(comp, dt)
		local em = comp.entity_manager

		if not em then
			return
		end

		B.frame = B.frame + 1
		B.time = B.time + num(dt, 0)
		t[7] = B.frame

		-- 玩家：按出生先后排，外部程序用 pad_number 区分 1P/2P
		for i = #plist, 1, -1 do
			plist[i] = nil
		end

		for k in pairs(slot_of) do
			slot_of[k] = nil
		end

		local chars = all_entities(em, "character")
		local np = 0

		for u in pairs(chars) do
			if Unit.alive(u) then
				np = np + 1
				plist[np] = u
			end
		end

		table.sort(plist, by_uid)

		-- 超过 4 个（多出来的是尸体）：从最老的尸体开始去掉，活人不被挤掉；不超过时顺序照旧按 uid 不变
		-- （2026-10-18：她死过几次以后尸体可能占满 4 格，后进来的 P3 排在最后被挤掉、她看不到 P3）
		local i = 1

		while np > MAX_PLAYERS and i <= np do
			if ((chars[plist[i]].state or EMPTY).health_state or EMPTY).is_dead then
				table.remove(plist, i)
				np = np - 1
			else
				i = i + 1
			end
		end

		for i = 1, MAX_PLAYERS do
			local base = P0 + (i - 1) * PF
			local u = plist[i]

			if u then
				slot_of[u] = i - 1

				write_player(base, u, chars[u])
			else
				t[base] = 0
			end
		end

		-- 武器单独包一层：哪把枪读出错只记 16 号格，不影响玩家和敌人，也不会让采集停下
		for i = 1, MAX_PLAYERS do
			local wb = W0 + (i - 1) * WF
			local u = plist[i]
			local s = u and (chars[u].state or EMPTY)
			local w = s and (s.current_weapon or (s.inventory_state or EMPTY).current_weapon)
			local ok, err = call(write_weapon, wb, w)

			if not ok then
				t[wb] = 0
				B.weapon_errors = B.weapon_errors + 1
				t[16] = B.weapon_errors
				-- 没有别的错误时，把武器的错误写进错误信息区，方便查
				if B.errors == 0 then
					record_weapon_error(err)
				end
			end
		end

		-- 任务区：自己包着 pcall，出错只记本区的数，不影响别的
		write_mission(comp, chars)

		-- 飞船区：一样自己包着，出错只记本区
		t[SH0] = 0

		-- SHIP_ENABLED 关着时本区 +0 保持 0，陪玩那边当"飞船区读不到"。
		local ship_ok, ship_err

		if SHIP_ENABLED then
			ship_ok, ship_err = call(write_ship, em)
		end

		if not SHIP_ENABLED then
			-- 不写
		elseif ship_ok then
			t[SH0] = 1
		else
			B.ship_errors = (B.ship_errors or 0) + 1
			t[SH0 + 2] = B.ship_errors

			if B.errors == 0 then
				record_weapon_error("ship: " .. tostring(ship_err))
			end
		end

		-- 第 6 版的三区：各自包着，出错只记 t[SI0 + 1]，区版本留 0
		t[IN0], t[ST0] = 0, 0
		extra_part(write_input, chars)
		extra_part(write_status, chars)
		t[SI0] = SIGHT_ENABLED and 1 or 0

		if SIGHT_ENABLED then
			extra_part(write_sight, em)
		end

		-- 第 7、8 版的区（P1 第一、三批）：一样各自包着，区版本先清 0，写完才是 1（M6 要等敌人区排好序，在后面写）
		t[BL0] = 0
		t[WX0], t[EX0], t[DR0], t[TM0], t[SG0], t[CM0], t[HZ0], t[RK0], t[AR0] = 0, 0, 0, 0, 0, 0, 0, 0, 0
		extra_part(write_weapons_extra, chars, em)
		extra_part(write_drops, em)
		extra_part(write_team, comp, chars, em)
		extra_part(write_strats, comp, chars, em)

		if CAMERA_ENABLED then
			extra_part(write_camera)
		end
		extra_part(write_hazards, em)

		if ROCKS_ENABLED then
			extra_part(write_rocks, chars)
		end

		if ARC_ENABLED then
			extra_part(write_arc, chars)
		end

		-- M18 玩家盾量区：和飞船区一样自己包着，出错只记本区（区版本留 0、+1 号格加一）
		if B.shield_enabled then
			local shield_ok, shield_err = call(B.write_shield, chars)

			if not shield_ok and B.errors == 0 then
				record_weapon_error("shield: " .. tostring(shield_err))
			end
		end

		-- 敌人：只保留离最近玩家最近的 MAX_ENEMIES 个
		local ne = 0

		for u, e in pairs(all_entities(em, "enemy")) do
			if Unit.alive(u) then
				local p = Unit.world_position(u, 0)
				local best = math.huge

				for i = 1, math.min(np, MAX_PLAYERS) do
					local q = P0 + (i - 1) * PF
					local dx, dy = p.x - t[q + 2], p.y - t[q + 3]
					local d = dx * dx + dy * dy

					if d < best then
						best = d
					end
				end

				ne = ne + 1
				eu[ne] = u
				ed[ne] = best
				eidx[ne] = ne
			end
		end

		for i = #eidx, ne + 1, -1 do
			eu[i], ed[i], eidx[i] = nil, nil, nil
		end

		if ne > MAX_ENEMIES then
			table.sort(eidx, by_dist)
		end

		local enemies = all_entities(em, "enemy")
		local nw = math.min(ne, MAX_ENEMIES)

		for i = 1, nw do
			local u = eu[eidx[i]]

			write_enemy(E0 + (i - 1) * EF, u, enemies[u])
		end

		-- M6 虫子补充区：和敌人区同序，所以在敌人写完以后写
		extra_part(write_bugs, enemies, nw, all_entities(em, "melee"))
        extra_part(write_ballistics, enemies, nw)
        extra_part(B.write_logic, enemies, nw, chars)

		-- M19 冲锋虫射线区：自己包着，出错只记本区（包装函数放在 B 上，snapshot 不多占 upvalue）
		if B.tankrays_enabled then
			B.run_tankrays(enemies, nw)
		end

		local cam = rawget(_G, "CameraManager")

		t[8] = num(dt, 0)
		t[9] = B.time
		t[15] = num(cam and cam.follow_spin, -99)
		t[10] = math.min(np, MAX_PLAYERS)
		t[11] = nw
		t[12] = ne
		t[6] = B.frame
	end

	local function record_error(err)
		B.errors = B.errors + 1
		t[13] = B.errors

		local s = tostring(err)
		local n = math.min(#s, ERR_LEN - 1)

		for i = 1, n do
			t[ERR0 + i] = string.byte(s, i)
		end

		t[ERR0] = n
	end

	local orig_update = CharacterStateMachine.update

	-- 每个本地角色每帧都会经过这里；同一个角色第二次出现 = 新的一帧开始，这时采集一次
	function CharacterStateMachine.update(arg_2_0, arg_2_1, arg_2_2, arg_2_3)
		if B.errors < MAX_ERRORS then
			if seen[arg_2_0] then
				for k in pairs(seen) do
					seen[k] = nil
				end

				local ok, err = call(snapshot, arg_2_3, arg_2_2)

				if not ok then
					record_error(err)
				end
			end

			seen[arg_2_0] = true
		end

		return orig_update(arg_2_0, arg_2_1, arg_2_2, arg_2_3)
	end
end
