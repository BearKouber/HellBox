-- [ai mech] 机制实测探针（HD1-012，2026-10-13）：录用户实机操作，分析雷鸣连发、Q 转、近战后撤、趴下、倒地。
-- 只读游戏状态（唯一例外是测试用的锁血开关，默认关，见 LOCK 那段）。外部程序 ai\mech_feed.py 读这张表。
-- 单独一张表、自己的魔数：陪玩用的 ai_bridge 一格不动，这张表出问题也不影响她。
-- 由 build.py 追加到 character_state_machine 末尾（排在 ai_menu 后面）。
--
-- 表布局（下标从 1 开始；改布局要同步改 mech_feed.py 并把 VERSION 加 1）：
--   1-4 魔数；5 VERSION；6 已写完的帧号；7 正在写的帧号（和 6 相等说明这一帧完整）；8 本帧 dt；9 游戏时间（dt 累加）；
--   10 写了几个玩家；11 每帧采集出错次数（到 50 次停采，不影响游戏）；12 事件钩子出错次数；13 字符串条数；
--   14 最新事件序号；15 钩子装上了哪些（按位：1 出膛 do_fire，2 爆炸 do_explosion，4 近战 do_damage，
--   8 挨打 HealthComponent.command_master，16 炮弹登记 ExplosiveComponent.setup_master，
--   32 击杀 HealthComponent.update_stats）；
--   16 锁血（1 开 0 关）；17 锁血键找到没有（1/0，-1 = 还没找）；18 锁血键名字（字符串号）；19 镜头转角（弧度，-99 读不到）；
--   20 键盘的手柄编号（KEYBOARD_MOUSE_PAD_NUMBER）；21 ai_bridge 的帧号（对表用）；22-32 保留
--   玩家区 P0 = 33，4 个 × PF 格（按 ai_bridge 的编号从小到大，和它的玩家区同序），格子含义见 write_player 上面；
--   事件区 EV0：MAX_EV 条 × EVF 格的环，第 n 个事件放第 (n-1) % MAX_EV 条，格子含义见 push 上面；
--   字符串区 S0：MAX_STRINGS 条 × SL 格（第 0 格长度，后面每格一个字节）；错误信息区 ERR0：200 格。
do
	local VERSION = 1
	local H = 32
	local MAX_PLAYERS, PF = 4, 64
	local MAX_EV, EVF = 256, 16
	local MAX_STRINGS, SL = 128, 40
	local ERR_LEN = 200
	local P0 = H + 1
	local EV0 = P0 + MAX_PLAYERS * PF
	local S0 = EV0 + MAX_EV * EVF
	local ERR0 = S0 + MAX_STRINGS * SL
	local N = ERR0 + ERR_LEN
	local MAX_ERRORS = 50
	local MISS = -999
	local EMPTY = {}
	-- 锁血键：小键盘 0（小键盘 1~9 留给电脑那边打标签，F8 是陪玩的兜底键）。引擎的键名不确定，几个都试
	local LOCK_KEY_NAMES = { "numpad 0", "num 0", "numpad0", "kp 0" }
	local LOCK_ALLOWED = true

	local B = AIMech or {}

	AIMech = B

	if not B.t or B.t[5] ~= VERSION then
		local t = {}

		for i = 1, N do
			t[i] = 0
		end

		t[1] = tonumber("17320508.5")
		t[2] = tonumber("-244948.625")
		t[3] = tonumber("1732.0625")
		t[4] = tonumber("137438953472.375")
		t[5] = VERSION
		t[17] = -1
		t[18] = -1
		B.t = t
		B.strings = {}
		B.nstrings = 0
		B.frame = 0
		B.time = 0
		B.errors = 0
		B.hook_errors = 0
		B.ev_seq = 0
		B.next_shot = 1
		B.proj = {}
		B.nproj = 0
		B.since = {}
		B.wrapped = {}
		B.lock = false
		B.own_ids = {}
		B.next_own_id = 1000000
	end

	B.killed = B.killed or {}
	B.nkilled = B.nkilled or 0

	local t = B.t
	local call = pcall or function(f, ...)
		return true, f(...)
	end
	local plist = {}
	local seen = {}

	local function num(v, d)
		if type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then
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
		t[13] = B.nstrings

		return id
	end

	-- 单位编号和 ai_bridge 共用（同一个单位两张表里编号一样）；没有 ai_bridge 时自己编（从 100 万起，免得撞）
	local function uid(u)
		if u == nil then
			return -1
		end

		local ab = rawget(_G, "AIBridge")

		if ab and ab.unit_ids and ab.next_unit_id then
			local id = ab.unit_ids[u]

			if not id then
				id = ab.next_unit_id
				ab.next_unit_id = id + 1
				ab.unit_ids[u] = id
				ab.n_unit_ids = (ab.n_unit_ids or 0) + 1
			end

			return id
		end

		local id = B.own_ids[u]

		if not id then
			id = B.next_own_id
			B.next_own_id = id + 1
			B.own_ids[u] = id
		end

		return id
	end

	local function write_text(s)
		s = tostring(s)

		local n = math.min(#s, ERR_LEN - 1)

		for i = 1, n do
			t[ERR0 + i] = string.byte(s, i)
		end

		t[ERR0] = n
	end

	local function hook_error(where, err)
		B.hook_errors = B.hook_errors + 1
		t[12] = B.hook_errors

		if B.errors == 0 then
			write_text(where .. ": " .. tostring(err))
		end
	end

	-- 是谁：1 = 玩家角色，2 = 敌人，0 = 别的 / 读不到
	local function kind_of(u)
		if u == nil or not Unit.alive(u) then
			return 0
		end

		if EntityAux.has_component(u, "character") then
			return 1
		end

		if EntityAux.has_component(u, "enemy") then
			return 2
		end

		return 0
	end

	local function enemy_type(u)
		local ok, s = call(LuaSettingsManager.get_settings_by_unit, LuaSettingsManager, u)
		local info = ok and type(s) == "table" and s.enemy_info

		return info and info.enemy_type
	end

	local function xyz(v)
		if v == nil then
			return MISS, MISS, MISS
		end

		return num(v.x, MISS), num(v.y, MISS), num(v.z, MISS)
	end

	-- ---------- 事件 ----------
	-- 每条：+0 序号 +1 游戏时间 +2 种类，+3~+15 看种类：
	--   1 出膛：+3 谁开的（编号）+4 连发第几发（1 起）+5~7 出膛点 xyz +8~10 枪口朝向 xyz（attach_node 的前方，
	--     散布前）+11 威力 +12 炮弹号 +13 这一发时的蓄力秒数（第 1 发 = 抬炮蓄了多久）+14 身体朝向（度）+15 武器名
	--   2 爆炸：+3 来源编号（-1 = 没有）+4 来源是谁（1 玩家 2 敌人 0 别的）+5~7 xyz +8 对应炮弹号（-1 = 对不上）
	--     +9 炮弹单位编号 +10 外圈半径 +11 内圈半径 +12 外圈威力 +13 内圈威力 +14 来源的种类名（敌人）+15 保留
	--   3 近战命中：+3 出手的人编号 +4 打到谁（编号）+5 打到的是谁（1/2/0）+6 种类名 +7 威力 +8 打之前对方血量
	--     +9 对方最大血量 +10 出手人 x +11 y +12 对方 x +13 y +14 破甲（1/0）
	--   4 玩家挨打：+3 挨打的人编号 +4 打人的编号 +5 打人的是谁（1/2/0）+6 打人的种类名 +7 威力（护甲前）
	--     +8 挨打前血量 +9 伤害类型 +10 锁血补回了（1/0）+11 打人的 x +12 y +13 挨打前已倒地（1/0）+14 打人的单位（attacker，编号）
	--   5 锁血开关：+3 现在开没开
	--   6 击杀（HD1-040，游戏自己算的谁杀的；只有结算这个单位的那台机器看得到，敌人一般在房主那）：
	--     +3 死的单位编号 +4 死的是谁（1/2/0）+5 死的种类名（敌人）+6 凶手编号（owner_unit，-1 = 没有）
	--     +7 凶手是谁（1/2/0）+8 动手的单位编号（attacker_unit：子弹 / 炮弹 / 战备）+9 伤害类型 +10 死的 x +11 y
	--     +12 凶手的种类名（敌人）+13 摔死（1/0）
	local function push(kind, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15)
		B.ev_seq = B.ev_seq + 1

		local base = EV0 + ((B.ev_seq - 1) % MAX_EV) * EVF

		t[base + 1] = B.time
		t[base + 2] = kind
		t[base + 3] = num(a3, MISS)
		t[base + 4] = num(a4, MISS)
		t[base + 5] = num(a5, MISS)
		t[base + 6] = num(a6, MISS)
		t[base + 7] = num(a7, MISS)
		t[base + 8] = num(a8, MISS)
		t[base + 9] = num(a9, MISS)
		t[base + 10] = num(a10, MISS)
		t[base + 11] = num(a11, MISS)
		t[base + 12] = num(a12, MISS)
		t[base + 13] = num(a13, MISS)
		t[base + 14] = num(a14, MISS)
		t[base + 15] = num(a15, MISS)
		t[base] = B.ev_seq
		t[14] = B.ev_seq
	end

	local function weapon_name(w)
		local ok, up = call(LoadoutSettings.get_upgraded_settings, w)

		return ok and type(up) == "table" and (up.hud_info or EMPTY).weapon_icon or nil
	end

	-- 出膛：照 LauncherComponent.do_fire 自己的算法算出膛点和朝向（同一帧、同样的引擎调用）。
	-- 在原函数之前算（之后 burst_round 等不会变，但 firing_single 会被清掉），威力在原函数之后读 burst_start_power。
	local function before_fire(unit, st)
		local wielder = EntityAux.has_component(unit, "equipment") and EntityAux.state(unit, "equipment").wielder or unit
		local rot = Unit.world_rotation(wielder, st.attach_node or 0)
		local fwd = Quaternion.forward(rot)
		local p = Unit.world_position(unit, 0)

		if st.ray_source_offset then
			p = p + Quaternion.rotate(rot, Vector3Aux.unbox(st.ray_source_offset))
		end

		local face = Quaternion.forward(Unit.world_rotation(wielder, 0))
		local px, py, pz = xyz(p)
		local fx, fy, fz = xyz(fwd)
		local id = B.next_shot

		B.next_shot = id + 1

		return {
			id = id,
			who = uid(wielder),
			round = st.fire_on_release and num(st.burst_round, 1) or 1,
			x = px, y = py, z = pz, dx = fx, dy = fy, dz = fz,
			charge = num(st.shot_charge_timer, MISS),
			face = math.deg(math.atan2(num(face.y, 0), num(face.x, 0))),
			name = sid(weapon_name(unit)),
		}
	end

	local function after_fire(info, unit, st)
		local power = st.fire_on_release and st.burst_start_power or st.power

		push(1, info.who, info.round, info.x, info.y, info.z, info.dx, info.dy, info.dz, num(power, MISS), info.id,
			info.charge, info.face, info.name)
	end

	local function remember_proj(u, shot)
		if B.nproj > 512 then
			B.proj = {}
			B.nproj = 0
		end

		B.proj[u] = shot
		B.nproj = B.nproj + 1
	end

	local function on_explosion(unit, boxed, info, proj, owner)
		local p = Vector3Aux.unbox(boxed)
		local x, y, z = xyz(p)
		local src = proj or unit
		local shot = src and B.proj[src]
		local k = kind_of(owner)

		info = info or EMPTY

		push(2, owner and uid(owner) or -1, k, x, y, z, shot or -1, src and uid(src) or -1, num(info.blast_radius, MISS),
			num(info.center_radius, MISS), num(info.blast_power, MISS), num(info.center_power, MISS),
			k == 2 and sid(enemy_type(owner)) or -1)

		if shot then
			B.proj[src] = nil
			B.nproj = math.max(B.nproj - 1, 0)
		end
	end

	local function unit_xy(u)
		if u and Unit.alive(u) then
			local p = Unit.world_position(u, 0)

			return num(p.x, MISS), num(p.y, MISS)
		end

		return MISS, MISS
	end

	local function on_melee(info, hit_unit)
		local hs = EntityAux.has_component(hit_unit, "health") and EntityAux.state(hit_unit, "health") or EMPTY
		local k = kind_of(hit_unit)
		local ax, ay = unit_xy(info.owner_unit)
		local tx, ty = unit_xy(hit_unit)

		push(3, uid(info.owner_unit), uid(hit_unit), k, k == 2 and sid(enemy_type(hit_unit)) or -1, num(info.power, MISS),
			num(hs.hitpoints, MISS), num(hs.max_hitpoints, MISS), ax, ay, tx, ty, flag(info.armorpiercing))
	end

	local function on_hurt(unit, ent, arg, healed)
		local s = (ent or EMPTY).state or EMPTY
		local owner = arg.owner_unit
		local k = kind_of(owner)
		local ox, oy = unit_xy(owner)

		push(4, uid(unit), owner and uid(owner) or -1, k, k == 2 and sid(enemy_type(owner)) or -1, num(arg.power, MISS),
			num(s.hitpoints, MISS), sid(arg.damage_type), flag(healed), ox, oy, flag(s.is_downed),
			arg.attacker_unit and uid(arg.attacker_unit) or -1)
	end

	-- 击杀：HealthComponent.update_stats 是游戏给"谁杀的"记账的地方（血掉到 constitution 以下才算死），
	-- 同一个单位只记一次（B.killed 弱表）
	local function on_kill(unit, ent, arg)
		local s = (ent or EMPTY).state or EMPTY

		local last = B.killed[unit]

		if not (num(s.hitpoints_real, 1) <= num(s.constitution, 0)) or (last and B.time - last < 2) then
			return
		end

		-- 单位指针会被新单位重用，所以只挡 2 秒内的重复；攒多了清空
		if B.nkilled > 4000 then
			B.killed, B.nkilled = {}, 0
		end

		B.killed[unit] = B.time
		B.nkilled = B.nkilled + 1

		local k = kind_of(unit)
		local owner = arg and arg.owner_unit
		local ok_ = kind_of(owner)
		local x, y = unit_xy(unit)

		push(6, uid(unit), k, k == 2 and sid(enemy_type(unit)) or -1, owner and uid(owner) or -1, ok_,
			arg and arg.attacker_unit and uid(arg.attacker_unit) or -1, arg and sid(arg.damage_type) or -1, x, y,
			ok_ == 2 and sid(enemy_type(owner)) or -1, arg == nil and 1 or 0)
	end

	-- ---------- 钩子（第一次采集时装，类都已经建好了） ----------
	local function install_hooks()
		local bits = 0
		local lc = rawget(_G, "LauncherComponent")

		if lc and lc.do_fire and lc.do_fire ~= B.wrapped.fire then
			local orig = lc.do_fire
			local function pass(info, unit, st, ...)
				B.cur_shot = nil

				if info then
					local ok, err = call(after_fire, info, unit, st)

					if not ok then
						hook_error("fire2", err)
					end
				end

				return ...
			end

			B.wrapped.fire = function(self, unit, st, ...)
				local info

				if B.errors < MAX_ERRORS then
					local ok, r = call(before_fire, unit, st)

					if ok then
						info = r
					else
						hook_error("fire", r)
					end
				end

				B.cur_shot = info and info.id

				return pass(info, unit, st, orig(self, unit, st, ...))
			end
			lc.do_fire = B.wrapped.fire
		end

		if lc and lc.do_fire == B.wrapped.fire then
			bits = bits + 1
		end

		local xm = rawget(_G, "ExplosionManager")

		if xm and xm.do_explosion and xm.do_explosion ~= B.wrapped.explosion then
			local orig = xm.do_explosion

			B.wrapped.explosion = function(self, unit, boxed, info, proj, owner, ...)
				if B.errors < MAX_ERRORS then
					local ok, err = call(on_explosion, unit, boxed, info, proj, owner)

					if not ok then
						hook_error("explosion", err)
					end
				end

				return orig(self, unit, boxed, info, proj, owner, ...)
			end
			xm.do_explosion = B.wrapped.explosion
		end

		if xm and xm.do_explosion == B.wrapped.explosion then
			bits = bits + 2
		end

		local mc = rawget(_G, "MeleeComponent")

		if mc and mc.do_damage and mc.do_damage ~= B.wrapped.melee then
			local orig = mc.do_damage

			B.wrapped.melee = function(self, info, pos, hit_unit, hit_pos, ...)
				if B.errors < MAX_ERRORS then
					local ok, err = call(on_melee, info, hit_unit)

					if not ok then
						hook_error("melee", err)
					end
				end

				return orig(self, info, pos, hit_unit, hit_pos, ...)
			end
			mc.do_damage = B.wrapped.melee
		end

		if mc and mc.do_damage == B.wrapped.melee then
			bits = bits + 4
		end

		-- 挨打：只看打在玩家角色身上的 do_damage。锁血开着时，原函数之前打开游戏自带的"玩家无敌"
		-- （HealthComponent.player_invincibility，调试命令用的那个，扣血那一步会跳过），原函数之后再用 set_hitpoints 补满。
		-- 只靠事后补满不够：一下把血打到死透线以下（雷鸣炸自己 1800）当场就死，补不回来（2026-10-13 实测）。
		local hc = rawget(_G, "HealthComponent")

		if hc and hc.command_master and hc.command_master ~= B.wrapped.health then
			local orig = hc.command_master
			local function pass(unit, ent, arg, is_player, ...)
				if is_player then
					local ok, err = call(function()
						local healed = false

						if B.lock then
							local s = (ent or EMPTY).state or EMPTY

							if num(s.max_hitpoints, 0) > 0 then
								EntityAux.queue_command_master(unit, "health", "set_hitpoints", s.max_hitpoints)

								healed = true
							end
						end

						if healed then
							-- 补满的事记在挨打事件里（事件是原函数之前推的，这里改它的 +10 格）
							local base = EV0 + ((B.ev_seq - 1) % MAX_EV) * EVF

							if t[base] == B.ev_seq and t[base + 2] == 4 then
								t[base + 10] = 1
							end
						end
					end)

					if not ok then
						hook_error("lock", err)
					end
				end

				return ...
			end

			B.wrapped.health = function(self, unit, ent, cmd, arg, ...)
				local is_player = false

				if cmd == "do_damage" and B.errors < MAX_ERRORS and type(arg) == "table" then
					local ok, err = call(function()
						if EntityAux.has_component(unit, "character") then
							is_player = true

							on_hurt(unit, ent, arg, false)
						end
					end)

					if not ok then
						hook_error("hurt", err)
					end
				end

				if is_player and (B.lock or B.god_set) then
					self.player_invincibility = B.lock
					B.god_set = B.lock
				end

				return pass(unit, ent, arg, is_player, orig(self, unit, ent, cmd, arg, ...))
			end
			hc.command_master = B.wrapped.health
		end

		if hc and hc.command_master == B.wrapped.health then
			bits = bits + 8
		end

		-- 击杀（HD1-040）：update_stats 只读不改，原函数照常跑
		if hc and hc.update_stats and hc.update_stats ~= B.wrapped.stats then
			local orig = hc.update_stats

			B.wrapped.stats = function(self, unit, ent, arg, ...)
				if B.errors < MAX_ERRORS then
					local ok, err = call(on_kill, unit, ent, arg)

					if not ok then
						hook_error("kill", err)
					end
				end

				return orig(self, unit, ent, arg, ...)
			end
			hc.update_stats = B.wrapped.stats
		end

		if hc and hc.update_stats == B.wrapped.stats then
			bits = bits + 32
		end

		-- 炮弹登记：出膛时（do_fire 里面）生出来的炸药，记下是第几号炮弹，爆炸时就能对上
		local ec = rawget(_G, "ExplosiveComponent")

		if ec and ec.setup_master and ec.setup_master ~= B.wrapped.setup then
			local orig = ec.setup_master
			local function pass(unit, ...)
				if B.cur_shot then
					local ok, err = call(remember_proj, unit, B.cur_shot)

					if not ok then
						hook_error("setup", err)
					end
				end

				return ...
			end

			B.wrapped.setup = function(self, unit, ...)
				return pass(unit, orig(self, unit, ...))
			end
			ec.setup_master = B.wrapped.setup
		end

		if ec and ec.setup_master == B.wrapped.setup then
			bits = bits + 16
		end

		t[15] = bits
	end

	-- ---------- 锁血开关 ----------
	local function check_lock_key()
		if not LOCK_ALLOWED then
			t[17] = 0

			return
		end

		local kb = rawget(_G, "Keyboard")

		if not kb then
			t[17] = 0

			return
		end

		if B.lock_key == nil then
			B.lock_key = false

			for _, name in ipairs(LOCK_KEY_NAMES) do
				local ok, idx = call(kb.button_index, name)

				if ok and type(idx) == "number" then
					B.lock_key = idx
					t[18] = sid(name)

					break
				end
			end

			t[17] = B.lock_key and 1 or 0
		end

		if B.lock_key then
			local ok, down = call(kb.pressed, B.lock_key)

			if ok and down then
				B.lock = not B.lock

				push(5, flag(B.lock))
			end
		end

		t[16] = flag(B.lock)
	end

	-- ---------- 玩家区 ----------
	-- 每人 PF 格：+0 有人 +1 编号（和 ai_bridge 一样）+2 手柄编号 +3~5 位置 +6~7 身体朝向 +8~10 速度
	--   +11 血量 +12 最大血量 +13 死透线（血量到这就死，倒地时血往这掉）+14 倒地 +15 死了 +16 闪避中（趴着）
	--   +17 状态名 +18 进这个状态的游戏时间 +19 子状态名 +20 进子状态的游戏时间
	--   输入（游戏读到的，角色的 input 表）：+21~22 移动方向（地图方向）+23~24 瞄准方向（键鼠是朝鼠标的地图方向，
	--     没按瞄准 / 开火时是 0）+25 按着的动作（按位：1 冲刺 2 近战 4 开火 8 连发 16 趴下 32 换弹 64 扔雷
	--     128 互动 256 战略配备 512 地图）+26 开火键按多深 +27 互动键（按住 1）+28 换枪（字符串号，-1 没换）+29 冲刺键按多深
	--   +30 想要的移动速度 +31 趴下计时（dive_timer）+32 起身中（dive_get_up）
	--   +33 自救按了多少 +34 要按多少 +35 自救清零倒计时 +36 举枪中
	--   +37 近战冷却剩余（melee_time，-99 没有）+38 近战时长
	--   武器：+39 有武器 +40 名字 +41 编号 +42 弹匣剩几发 +43 弹匣容量 +44 换弹中 +45 换弹剩几秒
	--   发射器（雷鸣这类松开发射的）：+46 是（1/0）+47 蓄力中（charging_shot）+48 蓄了几秒（shot_charge_timer）
	--     +49 连发第几发（burst_round，0 = 不在连发）+50 下一发还要几秒（burst_timer，-1 = 没有）+51 本发威力（burst_start_power）
	--     +52 上一帧在蓄力 +53 等松手（waiting_for_charge_release）+54 最少蓄几秒 +55 最多蓄几秒 +56 连发间隔
	--     +57 连发几发 +58 基础威力 +59 蓄满加多少 +60 每发减多少
	--   +61~63 枪口朝向 xyz（武器 attach_node 的前方；没有就是 -999）
	local BUTTONS = { { "sprint", 1 }, { "melee", 2 }, { "fire", 4 }, { "fire_auto", 8 }, { "dodge", 16 }, { "reload", 32 },
		{ "throw", 64 }, { "interact", 128 }, { "stratagems", 256 }, { "map", 512 } }

	local function since(u, key, name)
		local rec = B.since[u]

		if not rec then
			rec = {}
			B.since[u] = rec
		end

		if rec[key] ~= name then
			rec[key] = name
			rec[key .. "_t"] = B.time
		end

		return rec[key .. "_t"]
	end

	local function boxed_xy(b)
		if type(b) ~= "table" and type(b) ~= "userdata" then
			return 0, 0
		end

		local ok, x, y = call(function()
			return b.x, b.y
		end)

		if not ok then
			return 0, 0
		end

		return num(x, 0), num(y, 0)
	end

	local function write_weapon(base, u, s)
		local w = s.current_weapon or (s.inventory_state or EMPTY).current_weapon

		for i = 39, 63 do
			t[base + i] = MISS
		end

		t[base + 39] = 0
		t[base + 46] = 0

		if not w or not Unit.alive(w) then
			return
		end

		local ms = EMPTY

		if EntityAux.owned(w) then
			local ok, st = call(EntityAux.state_master_interface, w, "weapon")

			ms = ok and type(st) == "table" and st or EMPTY
		end

		t[base + 39] = 1
		t[base + 40] = sid(weapon_name(w))
		t[base + 41] = uid(w)
		t[base + 42] = num(ms.rounds, MISS)
		t[base + 43] = num(ms.magazine_capacity, MISS)
		t[base + 44] = flag(ms.is_reloading)
		t[base + 45] = num(ms.reload_time, MISS)

		if ms.fire_on_release then
			t[base + 46] = 1
			t[base + 47] = flag(ms.charging_shot)
			t[base + 48] = num(ms.shot_charge_timer, MISS)
			t[base + 49] = num(ms.burst_round, 0)
			t[base + 50] = num(ms.burst_timer, -1)
			t[base + 51] = num(ms.burst_start_power, MISS)
			t[base + 52] = flag(ms.was_charging_shot)
			t[base + 53] = flag(ms.waiting_for_charge_release)
			t[base + 54] = num(ms.min_charge_time, MISS)
			t[base + 55] = num(ms.max_charge_time, MISS)
			t[base + 56] = num(ms.burst_round_delay, MISS)
			t[base + 57] = num(ms.burst_rounds, MISS)
			t[base + 58] = num(ms.power, MISS)
			t[base + 59] = num(ms.charge_max_extra_power, MISS)
			t[base + 60] = num(ms.burst_round_power_decrease, MISS)
		end

		if type(ms.attach_node) == "number" then
			local ok, x, y, z = call(function()
				return xyz(Quaternion.forward(Unit.world_rotation(u, ms.attach_node)))
			end)

			if ok then
				t[base + 61], t[base + 62], t[base + 63] = x, y, z
			end
		end
	end

	local function write_player(base, u, e)
		local s = e.state or EMPTY
		local p = Unit.world_position(u, 0)
		local f = Quaternion.forward(Unit.world_rotation(u, 0))
		local hs = s.health_state or EMPTY
		local vel = (s.mover_state or EMPTY).velocity or EMPTY
		local inp = s.input or EMPTY
		local info = (e.settings or EMPTY).character_info or EMPTY

		t[base + 1] = uid(u)
		t[base + 2] = num((s.input_state or EMPTY).pad_number, -1)
		t[base + 3], t[base + 4], t[base + 5] = xyz(p)
		t[base + 6], t[base + 7] = num(f.x, 0), num(f.y, 0)
		t[base + 8], t[base + 9], t[base + 10] = num(vel.x, 0), num(vel.y, 0), num(vel.z, 0)
		t[base + 11] = num(hs.hitpoints, MISS)
		t[base + 12] = num(hs.max_hitpoints, MISS)
		t[base + 13] = num(hs.constitution, MISS)
		t[base + 14] = flag(hs.is_downed)
		t[base + 15] = flag(hs.is_dead)
		t[base + 16] = flag(hs.is_dodging)

		local sname = s.current_state and s.current_state.name
		local subname = s.current_substate and s.current_substate.name

		t[base + 17] = sid(sname)
		t[base + 18] = since(u, "s", sname)
		t[base + 19] = sid(subname)
		t[base + 20] = since(u, "sub", subname)
		t[base + 21], t[base + 22] = boxed_xy(inp.movement)
		t[base + 23], t[base + 24] = boxed_xy(inp.aim)

		local bits = 0

		for _, b in ipairs(BUTTONS) do
			if inp[b[1]] then
				bits = bits + b[2]
			end
		end

		t[base + 25] = bits
		t[base + 26] = num(inp.fire_amount, 0)
		t[base + 27] = num(inp.interact_button, 0)
		t[base + 28] = inp.switch_weapon and sid(inp.switch_weapon) or -1
		t[base + 29] = num(inp.sprint_amount, 0)
		t[base + 30] = num(s.wanted_move_speed, MISS)
		t[base + 31] = num(s.dive_timer, MISS)
		t[base + 32] = flag(s.dive_get_up)
		t[base + 33] = num(s.get_up_presses, MISS)
		t[base + 34] = num(s.get_up_presses_needed, num(info.get_up_presses_needed, MISS))
		t[base + 35] = num(s.get_up_reset_timer, MISS)
		t[base + 36] = flag(s.is_aiming)

		local w = s.current_weapon or (s.inventory_state or EMPTY).current_weapon
		local mel = w and Unit.alive(w) and EntityAux.has_component(w, "melee") and EntityAux.state(w, "melee") or EMPTY

		t[base + 37] = num(mel.melee_time, -99)
		t[base + 38] = num((mel.melee_info or EMPTY).duration, MISS)

		local ok, err = call(write_weapon, base, u, s)

		if not ok then
			t[base + 39] = 0
			hook_error("weapon", err)
		end

		t[base] = 1
	end

	local function by_uid(a, b)
		return uid(a) < uid(b)
	end

	local function entities(em, name)
		if em.has_entities and not em:has_entities(name) then
			return EMPTY
		end

		return em:get_master_entities(name) or EMPTY
	end

	local function snapshot(comp, dt)
		local em = comp.entity_manager

		if not em then
			return
		end

		B.frame = B.frame + 1
		B.time = B.time + num(dt, 0)
		t[7] = B.frame
		B.cur_shot = nil

		install_hooks()
		check_lock_key()

		for i = #plist, 1, -1 do
			plist[i] = nil
		end

		local chars = entities(em, "character")
		local np = 0

		for u in pairs(chars) do
			if Unit.alive(u) then
				np = np + 1
				plist[np] = u
			end
		end

		table.sort(plist, by_uid)

		for i = 1, MAX_PLAYERS do
			local base = P0 + (i - 1) * PF
			local u = plist[i]

			if u then
				write_player(base, u, chars[u])
			else
				t[base] = 0
			end
		end

		-- 隔一阵清掉已经不在的单位的状态计时
		if B.frame % 600 == 0 then
			for u in pairs(B.since) do
				if not Unit.alive(u) then
					B.since[u] = nil
				end
			end
		end

		local cam = rawget(_G, "CameraManager")
		local ab = rawget(_G, "AIBridge")

		t[8] = num(dt, 0)
		t[9] = B.time
		t[10] = math.min(np, MAX_PLAYERS)
		t[19] = num(cam and cam.follow_spin, -99)
		t[20] = num(rawget(_G, "KEYBOARD_MOUSE_PAD_NUMBER"), -1)
		t[21] = num(ab and ab.frame, -1)
		t[6] = B.frame
	end

	local function record_error(err)
		B.errors = B.errors + 1
		t[11] = B.errors
		write_text(err)
	end

	local orig_update = CharacterStateMachine.update

	-- 和 ai_bridge 一样：同一个角色第二次出现 = 新的一帧开始，这时采集一次
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
