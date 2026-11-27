-- [hellbox play] HellBox「玩法」页（2026-11-16 V0.95，用户要训练场的特殊玩法：晚上、换弹随机换枪、自动落红色战备……
-- 「两个确实可以都做」）。由 build.py 追加到 character_state_machine 末尾。两样东西：
--
-- 一、真训练场（联机版）：用游戏自己的训练场（proving grounds）那条路。
--   飞船（StateMenu）出发用的种子来自存档里的 selected_trial（原来的训练场选关菜单写它，state_menu.lua 3099～3120 行）；
--   有它时飞船把任务和第二个编号（provinggrounds_seed）广播给队友（rpc_on_mission_selected，1965 行），出发舱 → 简报
--   （写训练场名字和两个模式）→ 选装备（按模式强制发装备）→ 出发，全是原版流程，队友不用装 HellBox。
--   这里照训练场菜单 generate_trials（menu_screen_provinggrounds_mission.lua 237 行）的写法拼一个 trial 写进 selected_trial：
--     地图编号 = DifficultySettings.modulate_seed(时间, 光照, 环境 5 = 训练场, 变体 1, 种族, 类型 3（据点防守 4）, 难度, 地形号)
--     第二个编号 = ProvinggroundsSettings.modulate_seed_flat_indicies(目标, 装备规则, 场上事件)
--   同时清掉 current_planet（原菜单也这样，任务结束才不会把成绩记到战役星球上），并把飞船 is_training 设成 true
--   （不推进战役、不上传）。离开飞船进了这一关就算用掉；回到飞船时把 selected_trial 去掉、current_planet 放回原来那颗。
--   训练场菜单进飞船时会向服务器要「今天的训练场」，不在名单里的 selected_trial 会被清掉（3013 行）；这里挂一层，
--   我们的 trial 不让它清。
--   只有房主能设。
--
-- 二、自定义（HellBox 版）：任何关卡都带，不改关卡本身。
--   场上事件（红色轰炸 / 蓝色支援 / EMP）：房主这边用游戏自己的 ProvingGroundsModifiersManager 再开一份，每帧 update，
--     落下来的东西是房主生成的，全队同步。原版每次只盯一个人（传进去的列表里最后一个）；这里每帧随机给一个活着的队友，
--     轮到谁炸谁。EMP 的那个球只在虫族、生化人的资源包里（race_bugs / race_cyborgs），光能者关卡不开 EMP。
--     真训练场关卡自己有一份，这里不再叠。
--   装备规则：现在只接了「换弹随机换枪」（reload_surprise）：给自己控制的潜兵的 character 状态设 reload_surprise，
--     换弹时游戏自己的那段（character_state_reload.lua 153 行）换枪。只对装了 HellBox 并开着的人有效。
--
--   V0.97（2026-11-18 用户定，docs/任务/HD1-033-玩法页方案.md 第四节 2）：场上事件可以叠加，event= 改成逗号隔开的一串。
--   - 随机掉落 drop（代替红色轰炸 / 蓝色支援）：掉哪些战备由 HellBox 的 drop= 给（逗号隔开的战备名）。房主这边自己数时间，
--     照原版两个事件的节奏：打击类（stratagem_type = offensive）落完等 15 秒 + 它的呼叫时间、呼叫时间不到 2 秒多给 2 秒
--     （照 orbital_bombardments），别的等 20 秒（照 orbital_support）；每次随机挑一个活着的队友，在他身边 4～10 米落
--     （SpatialSpawnUtlity.generate_points_in_donut，同原版）。落法同原版 spawn_stratagem：生一个 flare_01，带 stratagem_id、
--     has_been_thrown。没有扔它的人（owner_unit = nil）。增援、求救信标不落（DROP_BAN）：增援要发复活消息带扔的人，
--     求救信标会把房间改成公开。旧的 event=orbital_bombardments / orbital_support 当成掉全部打击类 / 支援类。
--   - EMP 照旧用游戏的 ProvingGroundsModifiersManager（只在虫族、生化人关卡）。
--   - 装了才有的四个（打中回弹药、神射手、超级靴子、以牙还牙）：游戏的写法是 generated_level.provinggrounds_params.sub_modifier
--     == 某个名字（只能等于一个），所以不去改关卡，而是在游戏判断它的那几个函数调用期间临时给 provinggrounds_params 一个
--     { sub_modifier = 名字 }，调用完马上拿掉（只在本来没有 provinggrounds_params、也就是不是真训练场的时候）：
--       神射手 marksman：FirearmComponent.reload_slave / remake_raycast、FlameweaponComponent.reload_slave、
--         BeamweaponComponent.reload_slave
--       超级靴子 super_boots（2026-11-23 用户改）：不再用游戏那套，改成 HellBox 自己在 boots_update 里做：
--         自带心肺加速器（体力不消耗）+ 受到伤害 +50%
--       以牙还牙 what_goes_around：HealthComponent.command_master、HealthComponent.filter_slave_command
--       打中回弹药 get_ammo_from_hits_double_reload_time：游戏在 Firearm / Flameweapon 的 init 按关卡种子设
--         get_ammo_from_hits_half_magazine；这里记下每个实例，开关时直接改这个标记。
--     以牙还牙在 HealthComponent.command_master / filter_slave_command 里判断（超级靴子改走 boots_update 以后，两边不再抢）。
--   - 副武器换成军刀 sidearm_saber（2026-11-21 用户要，装了才有）：见 saber_update。游戏「只能近战」把军刀放主武器格；
--     军刀自己的设置标着 sidearm = true、sword = true（倒地时游戏也认「手枪格里是刀」），模型和手枪在同一个包 mission_common，
--     每关都在。办法和填弹惊喜换枪一样，给自己控制的潜兵发 inventory 的 set_weapon，只换手枪格（旧手枪没有掉落物，直接没了）。
--
--   V0.97 第 ③ 步 环境：鬼城（env=ghost_town，只对装了 HellBox 并选了鬼城的电脑生效，没装的人看正常光照）。
--   游戏的鬼城 = GeneratedLevel 把 time_of_day 设成 "ghost_town"（generated_level.lua 47 行，只有真训练场的鬼城事件才会）。
--   time_of_day 全游戏只有 4 处读：spawn_levels 挑时间段灯光 object set（1923 行）、character_component（306 行）、
--   vehicle_component（263 行）开手电筒 + 设 flow 变量 ghost_town、tutorial_npc_component（教程，不管）。另外 shading_environment_setting
--   （天空 / 雾的配色名，generated_level.lua 2021 行、environment_area_manager 267 行读）鬼城时跟着是 "ghost_town"。
--   关键：spawn_levels 每块地图用关卡主随机数 random 挑一个时间段 set（1960 行），所以不能让它看到 ghost_town（会少一次随机数，
--   后面的挑选全错位，和没装的人地图对不上）。做法：spawn_levels 照原样用原来的 time_of_day（dawn/day/dusk/night）跑完，
--   随机数的调用次数和顺序和原版完全一样；只在它调 world_proxy:load_level_with_object_sets 时把传进去的 set 名单里
--   「名字里带原 time_of_day 的」那一个（就是它刚挑的时间段灯光，别的 set 名字都不含时间名，见 1921～1960 行的分支顺序）拿掉。
--   spawn_levels 回来以后再把 generated_level.time_of_day 改成 "ghost_town"：之后出生的角色 / 载具照游戏原本的代码开手电、设 flow 变量。
--   2026-11-19 发行抢先版改：时间段灯光那一套不再拿掉（没装 HellBox 的客机进来房主会闪退），改成照原版装、装完藏起来关灯，
--   见下面 hide_tod_units。
--   真训练场（有 provinggrounds_params）、本来就是鬼城的不动；出错时恢复原样。
--
--   V0.97 第 ⑥ 步 客机跟随房主：上面「装了才有」的那些（换弹惊喜、打中回弹药 / 神射手 / 超级靴子 / 以牙还牙、鬼城；配装块在
--   host_loadout.lua）现在谁说了算：
--   - 房主 / 单机 / 本机分屏：用自己的 play.txt。当房主时把「换弹惊喜 / 事件 / 环境」写进 Steam 房间数据 hellbox_play
--     （格式 1|开着没|换弹惊喜|事件逗号串|环境；HellBox 版关着写 1|0|||）。V0.96 的队友只认 hellbox_lo，多一个键不影响；
--     V0.97 的队友读到 V0.96 房主（没有这个键）当「房主没开」，不会坏。
--     环境（鬼城）是生成地图时定的：打开一关以后房间数据里的环境冻结成这一关实际用的（房主中途改了，这一关不变，下一关才变；
--     中途进来的队友读到的也是这一关的）。
--   - 在别人房间里：play.txt 的 follow=1（默认）时，照房主房间数据里的来，自己的设置不生效；follow=0 时都不开（照普通玩）；
--     读不到房间数据 / 房主没装 HellBox：都不开。出怪、怪物属性、随机掉落、EMP 是房主那边做的，不受这个开关影响。
--     生成地图（GeneratedLevel.spawn_levels）进来时先同步读一次房间数据，再决定要不要装鬼城。
--   - 回到自己房间 / 自己当房主：马上恢复用自己的。
--   「这一关实际的」和「下一关打算用的」分开（V0.97 用户定：HellBox 版的设置一律下一关生效）：一关开打时（GeneratedLevel.spawn_levels）
--   把当时生效的设置抄一份定下来（G.frozen：换弹惊喜 / 四个装了才有的 / 随机掉落和 EMP 是否开 / 掉落名单 / 环境 / 客机跟随与否），
--   整关不变，所有地方（事件、武器标记、鬼城、给客机的广播）都读这一份；房主 / 自己中途改设置、关总开关、客机中途切
--   「跟随 / 照原版」都等下一关。在关卡里房主广播的就是这一份（含环境、事件），迟加入的客机和房主一致；回飞船（这份清掉）
--   才按最新设置广播。键的格式没变，V0.96 / 旧客机照常读。
--   状态（play-status.txt）多 role=host|guest|none、follow=1|0、host_state=ok|old|none|err、host=（房主写的原串）。
--
-- 和 HellBox 怎么说话：%APPDATA%/Arrowhead/Helldivers/hellbox/play.txt（HellBox 写，0.5 秒看一次，内容变了才重读）：
--   HBPLAY1
--   custom=1 / 0            HellBox 版开没开
--   cond=reload_surprise    HellBox 版装备规则（空 = 不改）
--   event=drop,emp,marksman      HellBox 版场上事件，逗号隔开（空 = 不改；V0.97 起可以几个一起）
--   env=ghost_town          HellBox 版环境（V0.97 第 ③ 步；空 = 原版）
--   follow=1 / 0            当客机时跟不跟房主的玩法（V0.97 第 ⑥ 步；默认 1，没这一行也当 1）
--   drop=stratagem_airstrike,…    随机掉落会掉哪些战备（V0.97）
--   trial=随机串            真训练场：设为下一局（空 = 不要 / 取消）；每点一次「设为下一局」换一个串
--   race=bugs  tod=night  diff=2  chal=survivors  pcond=reload_surprise  pmod=emp  terrain=12345
-- 结果写 play-status.txt：trial=串、state=armed / used / done / none / not_host / bad、why=、events=（这一关在跑的事件）、
--   role= / follow= / host_state= / host=（第 ⑥ 步，见上）
do
	local G = HellBoxPlay or {}

	HellBoxPlay = G
	G.cfg = G.cfg or { custom = false }

	local function dir()
		local appdata = os.getenv and os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/")
	end

	local function log(err)
		if rawget(_G, "HellBoxLog") then
			HellBoxLog("hellbox_play", err)
		end
	end

	-- ------------------------------------------------------------ 读设置 / 写状态
	local function read_cfg()
		local d = dir()
		local f = d and io.open(d .. "play.txt", "rb")

		if not f then
			return
		end

		local text = f:read("*a") or ""

		f:close()

		if text == G.text or not text:match("^HBPLAY1") then
			return
		end

		G.text = text

		local c = {}

		for line in text:gmatch("[^\r\n]+") do
			local k, v = line:match("^([%w_]+)=(.*)$")

			if k then
				c[k] = v
			end
		end

		c.custom = c.custom == "1"
		c.follow = c.follow ~= "0"
		c.events = {}

		for name in (c.event or ""):gmatch("[^,%s]+") do
			c.events[name] = true
		end

		c.env = (c.env or ""):match("^%s*(.-)%s*$")
		c.drop_list = {}

		for name in (c.drop or ""):gmatch("[^,%s]+") do
			c.drop_list[#c.drop_list + 1] = name
		end

		G.cfg = c
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

	local function write_status(fields)
		local d = dir()

		if not d then
			return
		end

		local parts = { "HBPLAYST1" }

		for _, k in ipairs({ "trial", "state", "why", "events", "role", "follow", "host_state", "host" }) do
			parts[#parts + 1] = k .. "=" .. tostring(fields[k] or "")
		end

		local text = table.concat(parts, "\n") .. "\n"

		if text == G.status_text then
			return
		end

		local f = io.open(d .. "play-status.tmp", "wb")

		if not f then
			return
		end

		local okw = f:write(text)
		local okc = f:close()

		-- 写、关、改名全成功才记「已写」；失败下次再试
		if okw and okc and swap_in(d .. "play-status.tmp", d .. "play-status.txt") then
			G.status_text = text
		else
			os.remove(d .. "play-status.tmp")
		end
	end

	-- ------------------------------------------------------------ 真训练场
	local function index_of(list, name)
		for i, v in ipairs(list or {}) do
			if v == name then
				return i
			end
		end
	end

	local function flat_index(getter, name)
		local ok, i = pcall(getter, name)

		return ok and type(i) == "number" and i > 0 and i or nil
	end

	-- 按设置拼 trial；不合游戏规矩（黑名单）返回 nil, 原因
	function G.build_trial(c)
		local P, D = ProvinggroundsSettings, DifficultySettings
		local enemy = index_of(D.enemy_lookup, c.race)
		local tod = index_of(D.time_of_day_lookup, c.tod)
		local di = tonumber(c.diff)
		local step = di and P.difficulty_steps[di]
		local terrain = tonumber(c.terrain)

		if not enemy or not tod or not step or not terrain then
			return nil, "bad_params"
		end

		local ci = flat_index(P.get_flat_sub_challenge_index_from_name, c.chal)
		local coi = flat_index(P.get_flat_sub_condition_index_from_name, c.pcond)
		local mi = flat_index(P.get_flat_sub_modifier_index_from_name, c.pmod)

		if not ci or not coi or not mi then
			return nil, "bad_mode"
		end

		-- 游戏自己的黑名单：难度 + 目标 + 装备规则 三份合起来，名字（含装备规则的大类名）在里面就不行
		local black = {}

		P.get_difficulty_black_list(step.value, black)

		for _, ch in ipairs(P.challenges) do
			for _, s in ipairs(ch.sub) do
				if s.name == c.chal then
					for _, b in ipairs(s.black_list or {}) do
						black[#black + 1] = b
					end
				end
			end
		end

		local cond_group

		for _, cg in ipairs(P.conditions) do
			for _, s in ipairs(cg.sub) do
				if s.name == c.pcond then
					cond_group = cg.name

					for _, b in ipairs(s.black_list or {}) do
						black[#black + 1] = b
					end
				end
			end
		end

		for _, b in ipairs(black) do
			if b == c.chal or b == c.pcond or b == c.pmod or b == cond_group then
				return nil, "blocked:" .. b
			end
		end

		local mtype = P.is_genocide_map(c.chal) and 4 or 3
		local seed = D.modulate_seed(tod - 1, (tod - 1) % 3, 5, 1, enemy - 1, mtype, step.value, math.floor(terrain) % 2147483647)
		local pg = P.modulate_seed_flat_indicies(ci - 1, coi - 1, mi - 1)
		local params = P.get_provinggrounds_params_flat(pg)

		local okn, display = pcall(P.get_localized_provinggrounds_name_from_seeds, seed, pg)

		return {
			unlocked = true,
			index = 1,
			type = params.sub_challenge,
			seed = seed,
			params = params,
			name = okn and display or "HellBox",
			provinggrounds_seed = pg,
			hellbox = c.trial,
			planet = {
				region = 0,
				name = "city_superearth",
				difficulty = step.value,
				enemy = enemy - 1,
				environment = 5,
				environment_variant = 1,
				shading_environment = (tod - 1) % 3,
				seed = seed
			}
		}
	end

	-- 2026-11-19：hellbox == "map" 是「选图」设为下一局（hellbox_start.lua）的，不归这里管（不清它、不当成自己的）；
	--   服务器训练场名单那一步两种都保护（any_ours）。
	local function ours(t)
		return type(t) == "table" and t.hellbox ~= nil and t.hellbox ~= "map"
	end

	local function any_ours(t)
		return type(t) == "table" and t.hellbox ~= nil
	end

	-- 去掉我们设的 trial，战役星球放回去
	local function disarm(ship)
		if ours(SaveManager:get("selected_trial")) then
			SaveManager:set("selected_trial", nil)
		end

		if ours(SaveManager:get("last_trial")) then
			SaveManager:set("last_trial", nil)
		end

		if G.saved_planet ~= nil and SaveManager:get("current_planet") == nil then
			SaveManager:set("current_planet", G.saved_planet)
		end

		G.saved_planet = nil

		if ship and G.training_ship == ship then
			ship.is_training = false
		end

		G.training_ship = nil
		G.armed = nil
	end

	-- 打完了：把 play.txt 里这个串去掉（HellBox 关着时也不会下次开游戏又设一遍）
	local function forget_trial(id)
		local d = dir()
		local f = d and io.open(d .. "play.txt", "rb")

		if not f then
			return
		end

		local text = f:read("*a") or ""

		f:close()

		local new, n = text:gsub("\ntrial=" .. id:gsub("%p", "%%%0") .. "\r?\n", "\ntrial=\n")

		if n == 0 then
			return
		end

		local w = io.open(d .. "play.tmp", "wb")

		if w then
			local okw = w:write(new)
			local okc = w:close()

			if not (okw and okc and swap_in(d .. "play.tmp", d .. "play.txt")) then
				os.remove(d .. "play.tmp")
			end
		end
	end

	local BUSY = { [2] = true, [3] = true, [4] = true } -- 简报 / 选装备 / 正在出发：这时不换

	local function trial_tick(name, state)
		local want = G.cfg.trial

		if want == "" then
			want = nil
		end

		if name == "menu" then
			if G.used then
				-- 打完回来了：恢复原样，这一次的串记成用过（HellBox 不点新的「设为下一局」就不会再设）
				G.done = G.used
				G.used = nil
				disarm(state)
				pcall(forget_trial, G.done)
			end

			if want and want == G.done then
				return { trial = want, state = "done" }
			end

			if not want then
				if G.armed then
					disarm(state)
				end

				-- 刚打完那一次：串已经从 play.txt 去掉了，照样报 done，让 HellBox 知道
				return { trial = G.done or "", state = G.done and "done" or "none" }
			end

			if not state.is_server then
				if G.armed then
					disarm(state)
				end

				return { trial = want, state = "not_host" }
			end

			if G.armed ~= want or G.armed_text ~= G.text then
				if BUSY[state.menu_state] then
					return { trial = want, state = G.armed and "armed" or "waiting", why = "busy" }
				end

				local trial, why = G.build_trial(G.cfg)

				if not trial then
					if G.armed then
						disarm(state)
					end

					return { trial = want, state = "bad", why = why }
				end

				if G.armed == nil then
					local cur = SaveManager:get("current_planet")

					-- 2026-11-19：「选图」设为下一局时星球已经被拿掉、存在它的 trial 里（hellbox_start.lua hb_planet），接过来
					local prev = SaveManager:get("selected_trial")

					if cur == nil and type(prev) == "table" and prev.hellbox == "map" then
						cur = prev.hb_planet
					end

					G.saved_planet = cur
				end

				SaveManager:set("selected_trial", trial)
				SaveManager:set("current_planet", nil)

				G.armed = want
				G.done = nil
				G.armed_text = G.text
				G.armed_pg = trial.provinggrounds_seed
				G.armed_seed = trial.seed
			end

			-- 换了别的星球 / 别的菜单把它清掉了：再放回去（只要还想要）
			local cur = SaveManager:get("selected_trial")

			if not ours(cur) then
				local trial = G.build_trial(G.cfg)

				if trial then
					SaveManager:set("selected_trial", trial)
					SaveManager:set("current_planet", nil)
				end
			end

			state.is_training = true
			G.training_ship = state

			return { trial = want, state = "armed" }
		end

		if (name == "mission_start" or name == "game") and G.armed then
			-- 出发了：是我们这一关就算用掉（出了飞船以后不再动存档）
			if state.mission_seed == G.armed_seed then
				G.used = G.armed
				G.armed = nil -- training_ship 留着：回飞船时 disarm 把它的训练标记撤掉
			end
		end

		if G.used then
			return { trial = G.used, state = "used" }
		end

		return { trial = want or "", state = want and "waiting" or "none", why = want and "not_ship" or nil }
	end

	-- ------------------------------------------------------------ 谁说了算：房主 / 客机（V0.97 第 ⑥ 步）
	local KEY = "hellbox_play"
	local GHOST = "ghost_town"
	local KNOWN_EVENTS = { drop = true, emp = true, marksman = true, super_boots = true, what_goes_around = true,
		get_ammo_from_hits_double_reload_time = true, sidearm_saber = true }
	local NOTHING = { custom = false, cond = "", events = {}, env = "", drop_list = {} }

	-- 下一关打算用的设置：客机 = 房主房间数据里的（跟随开着时）或什么都没有；别的情况 = 自己的 play.txt
	-- 2026-11-25 用户定：HellBox 关了（hellbox_alive.lua，tick 里记成 G.off）= 玩法全部按原版，马上生效（不等下一关）：
	--   live() / eff() 都给 NOTHING，事件、随机掉落、EMP、换弹惊喜、装了才有的那几个都停，当房主时广播「没开」；
	--   已经生成的鬼城地图、已经换上的军刀不倒回。HellBox 再打开就照原来的（这一关定下的 G.frozen 还在）。
	local function live()
		if G.off then
			return NOTHING
		end

		return G.eff or G.cfg
	end

	-- 这一关实际用的设置（V0.97 用户定：HellBox 版的设置一律「下一关生效」）：生成地图（GeneratedLevel.spawn_levels）时把当时的
	-- live() 抄一份定下来（G.frozen），整关不变——房主 / 自己中途改设置、客机中途切「跟随 / 照原版」都等下一关；关卡一没了
	-- （tick 看到当前 state 的 generated_level 不是它）就清掉。关卡里的每个地方（随机掉落 / EMP / 换弹惊喜 / 四个装了才有的 / 鬼城 /
	-- 给客机广播）都读这一份，没有这一份（飞船、或别的原因没走到 spawn_levels）时才读 live()。
	local function snapshot(c, gl)
		local s = { custom = c.custom == true, cond = c.cond or "", env = c.env or "", events = {}, drop_list = {}, gl = gl }

		for k, v in pairs(c.events or {}) do
			s.events[k] = v
		end

		for i, v in ipairs(c.drop_list or {}) do
			s.drop_list[i] = v
		end

		if not s.custom then
			s.env = ""
		end

		return s
	end

	local function eff()
		if G.off then
			return NOTHING
		end

		return G.frozen or live()
	end

	local function lobby_now()
		local ng = rawget(_G, "NetworkGlobal")
		local lobby = type(ng) == "table" and ng.lobby

		if type(lobby) == "table" and lobby.lobby and lobby.is_valid and lobby:is_valid() then
			return lobby
		end

		return nil
	end

	local function lobby_api(lobby)
		local api = (lobby.backend_type == "STEAM" and rawget(_G, "SteamLobby"))
			or (lobby.backend_type == "LAN" and rawget(_G, "LanLobby")) or nil

		return type(api) == "table" and api or nil
	end

	-- 读房间数据一个键：返回 值（字符串，空 = nil）, 出错原因（nil = 没出错）
	local function lobby_read(lobby, key)
		local api = lobby_api(lobby)

		if not api or type(api.data) ~= "function" then
			return nil, "missing"
		end

		local ok, v = pcall(api.data, lobby.lobby, key)

		if not ok then
			return nil, "err:" .. tostring(v)
		end

		if type(v) ~= "string" or v:match("^%s*$") then
			return nil
		end

		return v
	end

	local function split_bar(text)
		local p = {}

		for part in (text .. "|"):gmatch("([^|]*)|") do
			p[#p + 1] = part
		end

		return p
	end

	-- 房间数据串 → 设置表；不是我们的格式返回 nil。只认认识的名字（别的丢掉，不会坏）
	local function parse_play(text)
		if type(text) ~= "string" or text:sub(1, 2) ~= "1|" then
			return nil
		end

		local p = split_bar(text)
		local events = {}

		for name in (p[4] or ""):gmatch("[^,%s]+") do
			if KNOWN_EVENTS[name] then
				events[name] = true
			end
		end

		return {
			custom = p[2] == "1",
			cond = p[3] == "reload_surprise" and p[3] or "",
			events = events,
			env = p[5] == GHOST and GHOST or "",
			drop_list = {}
		}
	end

	local function play_string(c, env_now)
		local names = {}

		for name in pairs(c.events or {}) do
			if KNOWN_EVENTS[name] then
				names[#names + 1] = name
			end
		end

		table.sort(names)

		if not c.custom then
			return "1|0|||"
		end

		return table.concat({ "1", "1", c.cond == "reload_surprise" and c.cond or "", table.concat(names, ","),
			env_now == GHOST and GHOST or "" }, "|")
	end

	-- 看一眼自己是房主还是客机，算出现在管用的设置；name / state 给了就顺便当房主时发布（没给 = 只读，进关生成地图前用）
	function G.refresh_role(name, state)
		local lobby = lobby_now()
		local ok_host, is_host = false, false

		if lobby then
			ok_host, is_host = pcall(lobby.is_host, lobby)
		end

		if not lobby or not ok_host then
			G.role, G.eff, G.host_state, G.host_raw, G.published = "none", nil, nil, nil, nil

			return
		end

		if is_host then
			G.role, G.eff, G.host_state, G.host_raw = "host", nil, nil, nil

			if name then
				local c, env_now = G.cfg, G.cfg.env

				-- 在一关里：广播的是这一关实际在用的（含环境、事件）：房主中途关了总开关 / 改了设置，迟加入的客机读到的还是这一关的；
				-- 回到飞船（G.frozen 清掉）才按房主最新设置广播
				if name == "game" and type(state) == "table" and type(state.generated_level) == "table" then
					env_now = rawget(state.generated_level, "_hb_ghost") and GHOST or ""

					if G.frozen and G.frozen.gl == state.generated_level then
						c = G.frozen
					end
				end

				if G.off then
					c = NOTHING
				end

				local text = play_string(c, env_now)
				local now = Application.time_since_launch()

				if text ~= G.published or now >= (G.pub_at or 0) then
					local api = lobby_api(lobby)

					if api and type(api.set_data) == "function" then
						pcall(api.set_data, lobby.lobby, KEY, text)
					end

					G.published = text
					G.pub_at = now + 30
				end
			end

			return
		end

		G.role, G.published = "guest", nil

		local raw, why = lobby_read(lobby, KEY)
		local parsed = raw and parse_play(raw)

		G.host_raw = raw or ""

		if why then
			G.host_state = "err"
		elseif parsed then
			G.host_state = "ok"
		else
			-- 没有 hellbox_play：V0.96 房主（有 hellbox 键）还是根本没装 HellBox
			local hb, why2 = lobby_read(lobby, "hellbox")

			G.host_state = why2 and "err" or (hb and "old" or "none")
		end

		if G.cfg.follow ~= false and parsed then
			G.eff = parsed
		else
			G.eff = NOTHING
		end
	end

	-- ------------------------------------------------------------ 自定义（HellBox 版）
	local EMP_RACES = { bugs = true, cyborgs = true }
	local DROP_BAN = { stratagem_reinforce = true, stratagem_emergency_beacon = true }

	local function players_avatars(state)
		local out = {}

		for _, p in pairs(state.players or {}) do
			local go = p.player_go
			local ok, unit = pcall(function()
				return go and go:exists() and go:get("avatar_unit")
			end)

			if ok and unit and Unit.alive(unit) then
				local hs = EntityAux.state(unit, "health")

				if not hs or not hs.is_dead then
					out[#out + 1] = unit
				end
			end
		end

		return out
	end

	-- clean = 同一关里换 / 关事件：EMP 的球要收起来，不然那一片一直叫不了战备（manager 自己的 destroy 不管它）。
	-- 关卡已经结束（换了 state）时不碰旧关卡里的东西，只把引用丢掉。
	local function stop_events(clean)
		local m = G.mgr

		if m then
			if clean and m.triggerbox and Unit.alive(m.triggerbox) then
				pcall(EntityAux.queue_command_master, m.triggerbox, "stratagems_disabled_area", "disable")
				pcall(function()
					m.entity_spawner:despawn_entity(m.triggerbox)
				end)
			end

			pcall(m.destroy, m)
		end

		G.mgr = nil
		G.mgr_state = nil
		G.mgr_event = nil
	end

	local function host_custom(state)
		local c = eff()

		return c.custom and c.events and state.is_server and not state.provinggrounds_seed
	end

	local function event_wanted(state)
		if not host_custom(state) or not eff().events.emp then
			return nil
		end

		local race = state.generated_level and state.generated_level.enemy

		return EMP_RACES[race] and "emp" or nil
	end

	-- 随机掉落：核对过的战备名单（不认识的、DROP_BAN 的去掉；旧的红色轰炸 / 蓝色支援换成整类）
	local function drop_names()
		local c, out, seen = eff(), {}, {}

		if c.drop_names then
			return c.drop_names
		end

		-- 2026-11-19 发行抢先版 用户定：只掉房主自己解锁了的（profile_tool.lua 的 strat_on：等级 / DLC / 奖励 / 开局就带）；
		--   没解锁的勾上了也不掉。拿不到存档（strat_on 返回 nil）时这次不记下名单，下次再核对。
		local pt = rawget(_G, "ProfileToolMod")
		local strat_on = type(pt) == "table" and type(pt.strat_on) == "function" and pt.strat_on or nil
		local unsure = false

		local function unlocked(name)
			if not strat_on then
				return true
			end

			local ok, yes = pcall(strat_on, name)

			if not ok or yes == nil then
				unsure = true

				return false
			end

			return yes
		end

		local function add(name)
			if type(name) == "string" and not seen[name] and not DROP_BAN[name] and unlocked(name) then
				local ok, item = pcall(LoadoutSettings.get_item, "stratagems", name)

				if ok and type(item) == "table" then
					seen[name] = true
					out[#out + 1] = name
				end
			end
		end

		if c.events and c.events.drop then
			for _, name in ipairs(c.drop_list or {}) do
				add(name)
			end
		end

		local pgc = rawget(_G, "ProvinggroundsConditions")

		if c.events and c.events.orbital_bombardments and pgc then
			for _, name in ipairs(pgc.get_all_stratagems_by_subtypes("strike")) do
				add(name)
			end
		end

		if c.events and c.events.orbital_support and pgc then
			for _, name in ipairs(pgc.get_all_stratagems_by_subtypes("support", "support_weapon")) do
				add(name)
			end
		end

		if not unsure then
			c.drop_names = out  -- 记在这份设置上（play.txt 重读 / 下一关换了一份设置就自然重核对）
		end

		return out
	end

	-- 2026-11-26 用户：「随机掉落战备为什么默认按照一级而不是房主的算了呢」。原版试炼场的掉落（provinggrounds_modifiers_manager
	--   spawn_stratagem，这里照它写的）不带升级，战略配备组件就当 0 级（没升级的基础版）。现在带上房主（掉落是房主生成的）
	--   自己存档里这个战备的升级（item_upgrades，军械库升级写的那份，出发选装备也读它）；拿不到就 0 级，和以前一样。
	--   客机那边照原版：激活时 rpc_activate_stratagem 带着升级值发过去。
	local function host_upgrade(name)
		local ok, value = pcall(function()
			local uid = UserManager:get_user_id(GameSettings.get_main_pad_number())
			local ups = SaveManager:user_get("item_upgrades", uid)

			return type(ups) == "table" and ups[name] or 0
		end)

		return ok and type(value) == "number" and value or 0
	end

	local function spawn_drop(state, name, pos, extra)
		local data = {
			has_been_thrown = true,
			stratagem_id = LoadoutSettings.get_item_id_by_name("stratagems", name),
			upgrade_value = host_upgrade(name),
			extra_activation_time = extra
		}
		local unit = state.entity_spawner:spawn_entity("gameobjects/flare_01", pos, Quaternion.identity(), nil, data)

		EntityAux.queue_command_master(unit, "stratagem", "set_thrown_direction", Vector3Aux.box({}, Vector3(0, 0, 0)))
	end

	local function drop_update(state, dt)
		local names = host_custom(state) and drop_names() or nil

		if not names or #names == 0 then
			G.drop_state, G.drop_timer = nil, nil

			return
		end

		if G.drop_state ~= state or not G.drop_timer then
			G.drop_state, G.drop_timer = state, 15
		end

		G.drop_timer = G.drop_timer - dt

		if G.drop_timer > 0 then
			return
		end

		G.drop_timer = 1  -- 这次落不成（没人活着、找不到落点）：1 秒后再试

		local units = players_avatars(state)

		if #units == 0 then
			return
		end

		local pos = Unit.world_position(units[math.random(#units)], 0)
		local pts = SpatialSpawnUtlity.generate_points_in_donut(pos, 4, 10, 360, Quaternion.identity(), 1, 1, state.world_proxy:get_world())
		local at = pts and pts[1]

		if not at then
			return
		end

		local name = names[math.random(#names)]
		local item = LoadoutSettings.get_item("stratagems", name)
		local act = item.activation_time or 0
		local extra, wait = 0, 20

		if item.stratagem_type == "offensive" then
			wait = 15 + act
			extra = act < 2 and 2 or 0
		end

		spawn_drop(state, name, at, extra)

		G.drop_timer = wait
		G.drops = (G.drops or 0) + 1
		G.last_drop = name
	end

	local function events_update(state, dt)
		drop_update(state, dt)

		local ev = event_wanted(state)

		if ev ~= G.mgr_event or state ~= G.mgr_state then
			stop_events(state == G.mgr_state)

			if ev then
				local mi = ProvinggroundsSettings.get_flat_sub_modifier_index_from_name(ev)
				local seed = ProvinggroundsSettings.modulate_seed_flat_indicies(0, 0, mi - 1)

				G.mgr = ProvingGroundsModifiersManager(seed, state.entity_spawner, state.entity_manager, state.world_proxy)
				G.mgr_state = state
				G.mgr_event = ev
			end
		end

		if G.mgr then
			local units = players_avatars(state)

			if #units > 0 then
				local target = G.target or {}

				G.target = target

				for k in pairs(target) do
					target[k] = nil
				end

				target[units[math.random(#units)]] = true

				G.mgr:update(dt, target)
			end
		end
	end

	local function surprise_update(state)
		local c = eff()
		local on = c.custom and c.cond == "reload_surprise" and not state.provinggrounds_seed

		for _, p in pairs(state.players or {}) do
			local go = p.player_go
			local ok, unit = pcall(function()
				return go and go:exists() and go:owned() and go:get("avatar_unit")
			end)

			if ok and unit and Unit.alive(unit) and EntityAux.has_component(unit, "character") then
				local st = EntityAux.state_master(unit, "character")

				if st then
					if on and not st.reload_surprise then
						st.item_upgrades = st.item_upgrades or SaveManager:user_get("item_upgrades", UserManager:get_user_id(0))
						st.reload_surprise = true
						st.hellbox_surprise = true
					elseif not on and st.hellbox_surprise then
						st.reload_surprise = false
						st.hellbox_surprise = nil
					end
				end
			end
		end
	end

	-- ------------------------------------------------------------ 装了才有的事件（临时给 provinggrounds_params）
	local SELF_EVENTS = { marksman = true, super_boots = true, what_goes_around = true,
		get_ammo_from_hits_double_reload_time = true, sidearm_saber = true }
	local FAKE = {}

	for name in pairs(SELF_EVENTS) do
		FAKE[name] = { sub_modifier = name }
	end

	local function self_on(name)
		local c = eff()

		return c.custom and c.events and c.events[name] or false
	end

	local function with_fake(gl, name, fn, ...)
		if type(gl) ~= "table" or gl.provinggrounds_params ~= nil or not name then
			return fn(...)
		end

		gl.provinggrounds_params = FAKE[name]

		local r = { pcall(fn, ...) }

		gl.provinggrounds_params = nil

		if not r[1] then
			error(r[2], 0)
		end

		return unpack(r, 2)
	end

	local function ctx_level(self)
		local cc = rawget(self, "creation_context") or self.creation_context

		return type(cc) == "table" and cc.generated_level or nil
	end

	-- cls[method] 包一层：pick(self) 返回这一下要假装的名字（nil = 不假装），level(self) 返回 generated_level
	local function wrap(cls, method, pick, level)
		local orig = type(cls) == "table" and rawget(cls, method)
		local mark = "_hb_play_" .. method

		if type(orig) ~= "function" or rawget(cls, mark) then
			return
		end

		cls[method] = function(self, ...)
			local name = pick(self)

			if not name then
				return orig(self, ...)
			end

			return with_fake(level(self), name, orig, self, ...)
		end
		cls[mark] = true
	end

	local function pick_marksman()
		return self_on("marksman") and "marksman" or nil
	end

	local function pick_health()
		return self_on("what_goes_around") and "what_goes_around" or nil
	end

	local function pick_wga()
		return self_on("what_goes_around") and "what_goes_around" or nil
	end

	local function char_level(self)
		return rawget(self, "generated_level") or self.generated_level or ctx_level(self)
	end

	-- 打中回弹药：记下 Firearm / Flameweapon 的实例，开关时改标记（不是真训练场的实例才管）
	G.ammo_comps = G.ammo_comps or setmetatable({}, { __mode = "k" })

	local function wrap_ammo_init(cls)
		local orig = type(cls) == "table" and rawget(cls, "init")

		if type(orig) ~= "function" or rawget(cls, "_hb_play_init") then
			return
		end

		cls.init = function(self, ctx, ...)
			local r = { orig(self, ctx, ...) }

			if type(ctx) == "table" and not ctx.provinggrounds_seed then
				G.ammo_comps[self] = true

				if self_on("get_ammo_from_hits_double_reload_time") then
					self.get_ammo_from_hits_half_magazine = true
					self.hb_ammo = true
				end
			end

			return unpack(r)
		end
		cls._hb_play_init = true
	end

	local function ammo_update()
		local on = self_on("get_ammo_from_hits_double_reload_time")

		for comp in pairs(G.ammo_comps) do
			if on and not comp.get_ammo_from_hits_half_magazine then
				comp.get_ammo_from_hits_half_magazine = true
				comp.hb_ammo = true
			elseif not on and comp.hb_ammo then
				comp.get_ammo_from_hits_half_magazine = nil
				comp.hb_ammo = nil
			end
		end
	end

	-- 副武器换成军刀：每个潜兵单位（每条命一个）出生、配装发好后换一次，记在它的 character 状态上（hellbox_saber）；
	-- 之后手枪格再被别的东西换掉（比如以后加的功能）也不再换回。手里正拿着手枪就直接换到手上，否则军刀收起来、手里的不变。
	local SABER_PATH = "equipment/wep_saber_01"

	local function is_sword(unit)
		local ok, s = pcall(function()
			return LuaSettingsManager:get_settings_by_unit(unit)
		end)
		local wi = ok and type(s) == "table" and s.weapon_info

		return type(wi) == "table" and type(wi.attributes) == "table" and wi.attributes.sword == true
	end

	local function saber_update(state)
		if not self_on("sidearm_saber") or state.provinggrounds_seed then
			return
		end

		for _, p in pairs(state.players or {}) do
			local go = p.player_go
			local ok, unit = pcall(function()
				return go and go:exists() and go:owned() and go:get("avatar_unit")
			end)

			if ok and unit and Unit.alive(unit) and EntityAux.has_component(unit, "character")
				and EntityAux.has_component(unit, "inventory") then
				local st = EntityAux.state_master(unit, "character")
				local inv = EntityAux.state_master(unit, "inventory")
				local side = inv and inv.sidearm_weapon

				if st and not st.hellbox_saber and side and Unit.alive(side) then
					st.hellbox_saber = true

					if not is_sword(side) then
						EntityAux.queue_command_master(unit, "inventory", "set_weapon", {
							weapon_slot = "sidearm_weapon",
							weapon_path = SABER_PATH,
							upgrade_value = 0,
							ignore_set_ammo = true,
							ignore_auto_weapon_switch = inv.current_weapon ~= side
						})
						log("saber: sidearm -> " .. SABER_PATH)
					end
				end
			end
		end
	end

	-- 侦察兵（super_boots，2026-11-25 用户定）：自带心肺加速器（体力不消耗），但受到怪物的伤害 +50%。只管本机自己的潜兵。
	--   体力：照心肺加速器天赋（perk_settings perk_cardio）给 character 发 infinite_stamina = true；本来就有（带了天赋）就不动。
	--   伤害：照游戏原版侦察兵（health_component command_master 479 行，原版是 ×2）的位置，
	--     在本机潜兵挨怪打的那一下把 HealthComponent.calculate_damage 算出的伤害 ×1.5（见 wrap_boots_damage）。
	--   真训练场里不管：那里是游戏自己的侦察兵（跑快 40%、挨怪打翻倍）。
	local BOOTS_DAMAGE = 1.5

	local function boots_update(state)
		local on = self_on("super_boots") and not state.provinggrounds_seed

		for _, p in pairs(state.players or {}) do
			local go = p.player_go
			local ok, unit = pcall(function()
				return go and go:exists() and go:owned() and go:get("avatar_unit")
			end)

			if ok and unit and Unit.alive(unit) and EntityAux.has_component(unit, "character") then
				local st = EntityAux.state_master(unit, "character")

				if st then
					if on and not st.infinite_stamina and not st.hellbox_cardio then
						st.hellbox_cardio = true
						EntityAux.queue_command_master(unit, "character", "infinite_stamina", true)
					elseif not on and st.hellbox_cardio then
						st.hellbox_cardio = nil
						EntityAux.queue_command_master(unit, "character", "infinite_stamina", false)
					end
				end
			end
		end
	end

	-- 本机潜兵挨怪打：这一次 command_master 期间把 calculate_damage 换成乘 1.5 的（只乘打这个单位的那一下）
	local function boots_hit(self, unit, data)
		if not self_on("super_boots") or type(data) ~= "table" then
			return false
		end

		local gl = ctx_level(self)
		local pg = type(gl) == "table" and gl.provinggrounds_params

		if pg and FAKE[pg.sub_modifier] ~= pg then
			return false
		end

		local enemy = data.owner_unit

		return Unit.alive(unit) and EntityAux.owned(unit) and EntityAux.has_component(unit, "character")
			and enemy ~= nil and Unit.alive(enemy) and EntityAux.has_component(enemy, "enemy")
	end

	local function wrap_boots_damage(hc)
		local orig = type(hc) == "table" and rawget(hc, "command_master")

		if type(orig) ~= "function" or rawget(hc, "_hb_play_boots") then
			return
		end

		hc.command_master = function(self, unit, ctx, cmd, data, ...)
			if cmd ~= "do_damage" then
				return orig(self, unit, ctx, cmd, data, ...)
			end

			local ok, hit = pcall(boots_hit, self, unit, data)
			local calc = rawget(hc, "calculate_damage")

			if not (ok and hit) or type(calc) ~= "function" then
				return orig(self, unit, ctx, cmd, data, ...)
			end

			local function scaled(d, ...)
				if type(d) == "number" then
					d = d * BOOTS_DAMAGE
				end

				return d, ...
			end

			hc.calculate_damage = function(target, ...)
				if target == unit then
					return scaled(calc(target, ...))
				end

				return calc(target, ...)
			end

			local r = { pcall(orig, self, unit, ctx, cmd, data, ...) }

			hc.calculate_damage = calc

			if not r[1] then
				error(r[2], 0)
			end

			return unpack(r, 2, table.maxn(r))
		end
		hc._hb_play_boots = true
	end

	local function install_self_events()
		local fa, fl, bw = rawget(_G, "FirearmComponent"), rawget(_G, "FlameweaponComponent"), rawget(_G, "BeamweaponComponent")
		local ch, hc = rawget(_G, "CharacterComponent"), rawget(_G, "HealthComponent")

		wrap(fa, "reload_slave", pick_marksman, ctx_level)
		wrap(fa, "remake_raycast", pick_marksman, ctx_level)
		wrap(fl, "reload_slave", pick_marksman, ctx_level)
		wrap(bw, "reload_slave", pick_marksman, ctx_level)
		wrap(hc, "command_master", pick_health, ctx_level)
		wrap(hc, "filter_slave_command", pick_wga, ctx_level)
		wrap_boots_damage(hc)
		wrap_ammo_init(fa)
		wrap_ammo_init(fl)
	end

	-- ------------------------------------------------------------ 环境：鬼城（V0.97 第 ③ 步）
	local function ghost_on(gl)
		local c = eff()

		return c.custom == true and c.env == GHOST and type(gl) == "table" and gl.provinggrounds_params == nil
			and type(gl.time_of_day) == "string" and gl.time_of_day ~= GHOST and type(gl.world_proxy) == "table"
	end

	-- 带 ghost_town 那套设置的配色（和 mod/ghost_shading.bin 一致，tools/ghost_shading.py 生成）
	local GHOST_SE = {}

	for _, n in ipairs({ "env_desert/shading_environment_01", "env_desert/shading_environment_02", "env_desert/shading_environment_03",
		"env_desert/shading_environment_bugs", "env_forest/shading_environment_01", "env_forest/shading_environment_02",
		"env_forest/shading_environment_03", "env_forest/shading_environment_illuminates", "env_snow/shading_environment_01",
		"env_snow/shading_environment_02", "env_snow/shading_environment_03", "env_snow/shading_environment_cyborgs",
		"env_lava/shading_environment_01", "env_lava/shading_environment_02", "env_lava/shading_environment_03",
		"env_city/shading_environment_01", "env_city/shading_environment_02", "env_city/shading_environment_03" }) do
		GHOST_SE[n] = true
	end

	-- 这一关能不能用真鬼城配色：HellBox 装核心时换好的地图包写在 ghost-maps.txt（mod/ghost_maps.py，一行「包名=文件名=大小」）；
	-- 这一关的地图包在里面、配色在 GHOST_SE 里、不改的教程 / 试炼场包都没加载（同名配色先加载的那份算数）才行
	local NO_GHOST_PKGS = { "resource_packages/tutorial", "env_provinggrounds/provinggrounds_bugs", "env_provinggrounds/provinggrounds_cyborgs",
		"env_provinggrounds/provinggrounds_illuminates", "env_provinggrounds/provinggrounds_genocide_map_bugs",
		"env_provinggrounds/provinggrounds_genocide_map_cyborgs", "env_provinggrounds/provinggrounds_genocide_map_illuminates" }

	-- 2026-11-20 HD1-036：配色改成补丁装法（<地图包>.patch_N），这一行多一个「=补丁编号」，第二行「contents=游戏 contents 目录/」。
	--   这里再核对一次文件：我们的补丁在、下面的编号一个不缺（缺了游戏读不到我们的）、上面没有别人的补丁
	--   （比如 Obsidian 后来部署的 Enhanced Visuals，它的配色会盖掉我们的、没有 ghost_town）→ 才算有，否则退回夜晚。
	local function file_there(path)
		local f = io.open(path, "rb")

		if f then
			f:close()

			return true
		end

		return false
	end

	local function ghost_maps_has(pkg)
		local d = dir()
		local f = d and type(pkg) == "string" and io.open(d .. "ghost-maps.txt", "rb")

		if not f then
			return false
		end

		local text = "\n" .. (f:read("*a") or "")

		f:close()

		local at = string.find(text, "\n" .. pkg .. "=", 1, true)

		if not at then
			return false
		end

		local line = string.match(text, "^\n[^\n]*", at) or ""
		local fn, slot = string.match(line, "=(%x+)=%d+=(%d+)")

		if not fn then
			return true -- 老装法（整份换过的包）：配色就在包里
		end

		local contents = string.match(text, "\ncontents=([^\r\n]*)")

		if not contents or contents == "" then
			return false
		end

		local base = contents .. fn .. ".patch_"

		for i = 0, tonumber(slot) do
			if not file_there(base .. i) then
				return false
			end
		end

		return not file_there(base .. (tonumber(slot) + 1))
	end

	local function real_ghost_ok(gl, se_name)
		if not (se_name and GHOST_SE[se_name] and ghost_maps_has(gl.environment_package_name)) then
			return false
		end

		local pm = rawget(_G, "Boot") and Boot.package_manager

		if type(pm) ~= "table" or type(pm.is_package_online) ~= "function" then
			return false
		end

		for _, name in ipairs(NO_GHOST_PKGS) do
			local ok, on = pcall(pm.is_package_online, pm, name)

			if not ok or on then
				return false
			end
		end

		return true
	end

	-- 2026-11-19 发行抢先版改（用户实测：房主开鬼城，没装 HellBox 的客机进来，加载地图时房主闪退）：
	--   以前是把时间段灯光那一套 object set 从名单里拿掉、不装。没装 HellBox 的客机照原版装了这一套，两边地图里的物体
	--   不一样多，联机按编号对物体就对不上（推断，原因没在实机上抓到）。
	--   现在照原版全装（物体和没装的人完全一样），装完再把这一套里的物体藏起来、灯关掉，画面上等于没装。
	--   LevelResource.unit_indices_in_object_set / Level.unit_by_index / Unit.num_lights / Unit.light / Light.set_enabled /
	--   Unit.set_unit_visibility 都在游戏程序里（helldivers.exe 里有这些名字）；哪一步不行就跳过（只是没那么黑），不会闪退。
	local function tod_sets(sets, tod)
		local out = {}

		for _, name in ipairs(type(sets) == "table" and sets or {}) do
			if type(name) == "string" and string.find(name, tod) then
				out[#out + 1] = name
			end
		end

		return out
	end

	local function hide_unit(u)
		local n = 0
		local ok_n, nl = pcall(Unit.num_lights, u)

		if ok_n and type(nl) == "number" then
			for i = 0, nl - 1 do
				local ok_l, light = pcall(Unit.light, u, i)

				if ok_l and light and pcall(Light.set_enabled, light, false) then
					n = n + 1
				end
			end
		end

		pcall(Unit.set_unit_visibility, u, false)

		-- 2026-11-20 HD1-035 蜜蜂灯：藏起来的带灯物体记下来，鬼城里给无人机借一盏（hellbox_drone_light.lua）
		if n > 0 then
			G.ghost_lamps = G.ghost_lamps or {}
			G.ghost_lamps[#G.ghost_lamps + 1] = u
		end

		return n
	end

	-- loaded = { {level, 资源名, {要藏的 set 名}} ... }；返回 (藏了几个物体, 关了几盏灯)
	local function hide_tod_units(loaded)
		local LR = rawget(_G, "LevelResource")
		local get = type(LR) == "table" and LR.unit_indices_in_object_set
		local units, lights = 0, 0

		G.ghost_lamps = {}

		if type(get) ~= "function" then
			return 0, 0
		end

		for _, it in ipairs(loaded) do
			for _, set in ipairs(it[3]) do
				local ok, idx = pcall(get, it[2], set)

				for _, i in ipairs(ok and type(idx) == "table" and idx or {}) do
					local ok_u, u = pcall(Level.unit_by_index, it[1], i)

					if ok_u and u and Unit.alive(u) then
						units = units + 1
						lights = lights + hide_unit(u)
					end
				end
			end
		end

		return units, lights
	end

	local function wrap_spawn_levels(cls)
		local orig = type(cls) == "table" and rawget(cls, "spawn_levels")

		if type(orig) ~= "function" or rawget(cls, "_hb_play_spawn_levels") then
			return
		end

		cls.spawn_levels = function(self, ...)
			-- 客机：生成地图之前先读一次房主这一关的环境（地图每台电脑自己生成，之后再读就晚了）
			pcall(G.refresh_role)

			-- 这一关的设置在这里定下来（整关不变，见 snapshot 的说明）；env 先是「打算用的」，下面确定用上了才留着
			local snap = snapshot(live(), self)

			G.frozen = snap

			if not ghost_on(self) then
				snap.env = ""

				return orig(self, ...)
			end

			local wp, tod = self.world_proxy, self.time_of_day
			local saved_setting = self.shading_environment_setting
			local had = rawget(wp, "load_level_with_object_sets")
			local base = wp.load_level_with_object_sets

			if type(base) ~= "function" then
				snap.env = ""

				return orig(self, ...)
			end

			-- 照原样装（名单不改），记下每块地图装了哪几套时间段灯光，spawn_levels 跑完再藏（原版之后还会触发
			-- level_loaded 的 flow，可能再开灯，所以等它跑完）
			local loaded = {}
			local ok_set = pcall(function()
				rawset(wp, "load_level_with_object_sets", function(w, name, res, flag, sets, ...)
					local lr = { base(w, name, res, flag, sets, ...) }
					local hide = tod_sets(sets, tod)

					if lr[1] and #hide > 0 then
						loaded[#loaded + 1] = { lr[1], res, hide }
					end

					return unpack(lr)
				end)
			end)

			if not ok_set then
				snap.env = ""

				return orig(self, ...)
			end

			-- 天空 / 雾的配色名：真试炼场鬼城用 "ghost_town"，但那一套原版只在试炼场的配色（env_provinggrounds/）里有；
			-- 普通关卡的配色（env_desert/、env_forest/……）没有，设了引擎找不到直接闪退（2026-11-18 V0.98 实测）。
			-- 现在装核心时把 45 个地图包里的普通配色换成带 ghost_town 的（mod/ghost_maps.py、tools/ghost_shading.py）；
			-- 这一关对不上（包没换好、配色不在名单、教程 / 试炼场包开着）就退回 "night"，不冒闪退的险。
			local env = type(self.environment) == "table" and self.environment.path
			local se_name = type(env) == "string" and type(self.shading_environment) == "string" and (env .. self.shading_environment)
			local ok_real, real = pcall(real_ghost_ok, self, se_name)

			self.shading_environment_setting = (ok_real and real) and GHOST or "night"

			-- 2026-11-19 闪退探针（hb_probe.lua）：鬼城这几步记下来，闪退时看停在哪
			local probe = rawget(_G, "HellBoxProbe")

			if probe then
				probe("鬼城：配色 " .. tostring(self.shading_environment_setting) .. "，" .. tostring(G.role or "?"))
			end

			local r = { pcall(orig, self, ...) }

			pcall(function()
				rawset(wp, "load_level_with_object_sets", had)
			end)

			if r[1] then
				if probe then
					probe("鬼城：开始藏灯（" .. #loaded .. " 块地图）")
				end

				local ok_h, nu, nl = pcall(hide_tod_units, loaded)

				if probe then
					probe("鬼城：藏灯完成")
				end

				G.ghost_hidden = ok_h and { units = nu, lights = nl, levels = #loaded } or { error = tostring(nu) }

				if rawget(_G, "HellBoxLog") then
					HellBoxLog("hellbox_play", ok_h and string.format("ghost hide: %d levels, %d units, %d lights", #loaded, nu, nl)
						or ("ghost hide error: " .. tostring(nu)))
				end

				self.time_of_day = GHOST
				rawset(self, "_hb_ghost", true)
			else
				snap.env = ""
				self.shading_environment_setting = saved_setting
				error(r[2], 0)
			end

			return unpack(r, 2)
		end
		cls._hb_play_spawn_levels = true
	end

	-- ------------------------------------------------------------ 挂钩
	local function install()
		install_self_events()
		wrap_spawn_levels(rawget(_G, "GeneratedLevel"))
		local game = rawget(_G, "StateGame")

		if type(game) == "table" and type(game.update) == "function" and G.game_class ~= game then
			G.game_class = game

			local orig = game.update

			game.update = function(self, dt, ...)
				local r = { orig(self, dt, ...) }
				local ok, err = pcall(function()
					events_update(self, dt or 0)
				end)

				if not ok then
					G.errors = (G.errors or 0) + 1
					stop_events()

					if (G.errors or 0) < 5 then
						log(err)
					end
				end

				return unpack(r)
			end
		end

		local menu = rawget(_G, "StateMenu")

		if type(menu) == "table" and type(menu.provinggrounds_request_completed) == "function" and G.menu_class ~= menu then
			G.menu_class = menu

			local orig = menu.provinggrounds_request_completed

			-- 服务器的训练场名单里没有我们拼的这一关：别让原版把它清掉、把人踢出菜单
			menu.provinggrounds_request_completed = function(self, ...)
				local t = SaveManager:get("selected_trial")

				if any_ours(t) then
					SaveManager:set("selected_trial", nil)

					local r = { pcall(orig, self, ...) }

					SaveManager:set("selected_trial", t)

					if not r[1] then
						error(r[2], 0)
					end

					return unpack(r, 2)
				end

				return orig(self, ...)
			end
		end
	end

	local function tick()
		pcall(read_cfg)
		pcall(install)

		-- 2026-11-25：HellBox 开没开着（hellbox_alive.lua）；关了 live() / eff() 都按原版，见 live() 上面的说明
		local alive = rawget(_G, "HellBoxAlive")

		G.off = type(alive) == "table" and type(alive.off) == "function" and alive.off() or false

		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine

		if not sm then
			return
		end

		local name = sm:get_current_state_name()
		local state = sm:get_current_state()

		if type(state) ~= "table" then
			return
		end

		if name ~= "game" and G.mgr then
			stop_events()
		end

		-- 这一关结束了（当前 state 里的关卡不是定下设置的那个）：下一关再按最新设置定
		if G.frozen and G.frozen.gl ~= state.generated_level then
			G.frozen = nil
		end

		pcall(G.refresh_role, name, state)

		local st = trial_tick(name, state) or {}

		pcall(ammo_update)

		if name == "game" then
			surprise_update(state)
			pcall(saber_update, state)
			pcall(boots_update, state)

			local running = {}

			if G.mgr_event then
				running[#running + 1] = G.mgr_event
			end

			if G.drop_timer then
				running[#running + 1] = "drop"
			end

			if type(state.generated_level) == "table" and rawget(state.generated_level, "_hb_ghost") then
				running[#running + 1] = GHOST
			end

			for ev in pairs(SELF_EVENTS) do
				if self_on(ev) and not state.provinggrounds_seed then
					running[#running + 1] = ev
				end
			end

			table.sort(running)
			st.events = table.concat(running, ",")
		end

		st.role = G.role or "none"
		st.follow = G.cfg.follow ~= false and "1" or "0"
		st.host_state = G.host_state or ""
		st.host = G.host_raw or ""

		write_status(st)
	end

	G.drop_update = drop_update  -- 离线测试用
	G.with_fake = with_fake
	G.self_on = self_on
	G.ghost_on = ghost_on
	G.parse_play = parse_play
	G.play_string = play_string

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.tick then
		local orig = wm.update
		local next_check = 0

		G.tick = function(self, ...)
			local now = Application.time_since_launch()

			if now >= next_check then
				next_check = now + 0.5

				local ok, err = pcall(tick)

				if not ok then
					G.tick_errors = (G.tick_errors or 0) + 1

					if G.tick_errors < 5 then
						log(err)
					end
				end
			end

			return orig(self, ...)
		end
		wm.update = G.tick
	end
end
