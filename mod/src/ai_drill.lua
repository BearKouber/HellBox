-- [ai drill] 训练关出怪练习（2026-11-07，HellBox「快速开局」页用，取代 ai_tank_drill.lua）。由 build.py 追加到 character_state_machine 末尾。
-- 只有带启动参数 -drill_mode（或老参数 -tank_drill N）加本地训练关（主机）才生效，平时什么都不改。
--
-- 启动参数（游戏脚本的规矩：-名字 值，值里不能有空格）：
--   -drill_mode only|seq     only = 场上保持最多 N 只，死了隔几秒补上；seq = 按节奏一批一批出，这批全死了隔几秒出下一批
--   -drill_units a/b,c/d     要出的怪，characters/ 后面那段，逗号隔开（如 bug_tank/bug_tank,bug_warrior/bug_warrior_elite）
--                            多种怪轮流出（第一只 a、第二只 c、第三只 a……）；不是这张图种族的会被跳过（不会跨阵营刷）
--   -drill_max N             only 模式场上最多几只（默认 1）
--   -drill_seq 1,2           seq 模式每批几只，轮着来（默认 1）
--   -drill_gap 秒            死光（only：少了）以后隔几秒再出（默认 3）
--   -tank_drill N            老参数，等于 -drill_mode only -drill_units bug_tank/bug_tank -drill_max N
--
-- 生效时：
--   报复关自己的出波停掉（每帧把 check_wave_done_timer 顶回 5 秒，objective_genocide_component 344 行那段永远不跑），
--   遭遇战 / 叫援军（EncounterManager.spawn_group）、单个刷怪（spawn_enemy，比如装甲车放兵）、巡逻（PatrolManager.spawn_patrol）一律不刷，
--   场上只有这里刷的怪（数量才准）。穿刺虫的触手、方尖碑的盾不走这几条路，照常出。
--   怪由这里自己刷：位置照报复关的做法，从它的 spawn_positions 里随便挑一个、z 设 100 交给 spawn_group（spawn_manager 往下打射线找地面）。
--   等报复关开场等待（initial_wait_time）走完才开始刷。击杀数、任务完成照原版算。
--
-- 信箱（2026-11-13）：同样的设置也能开游戏以后写进来，不用启动参数。用户 2026-11-12 晚起游戏只要多带任何启动参数
--   （连一个谁都不认的 -foo bar 也算）就常在主菜单自动建房那一刻崩（0xC0000005），只带 -autohost 不崩；所以 ai\drill_run.py
--   改成只带 -autohost，出怪设置开游戏后经这个信箱写进来（mod\room_name_live.py 的 live_set(命令, magic=MAGIC_DRILL)）。
--   布局同 room_name.lua：1-4 魔数；5 VERSION；6 请求号；7 已收到的请求号；8 字节数；9 起命令文字。
--   命令 "drill_mode=only;drill_units=bug_tank/bug_tank;drill_max=1;drill_seq=1;drill_gap=3;start_wave=5"：
--   每个键原样写进全局 ARGUMENTS（和启动参数同一张表），然后让这里重新读一遍设置；ai_start_wave.lua 每次都现读 ARGUMENTS。
do
    local G = AIDrillMod or {}
    AIDrillMod = G
    local RACE_PREFIX = { bugs = "bug_", cyborgs = "cyborg_", illuminates = "illuminate_" }
    local MB_VERSION, MB_MAX, MB_B0 = 1, 512, 9
    local MB_KEYS = { drill_mode = true, drill_units = true, drill_max = true, drill_seq = true, drill_gap = true,
                      start_wave = true }

    if not G.mb or G.mb[5] ~= MB_VERSION then
        local t = {}
        for i = 1, MB_B0 + MB_MAX - 1 do
            t[i] = 0
        end
        t[1] = tonumber("33166247.5")
        t[2] = tonumber("-223606.625")
        t[3] = tonumber("2449.4375")
        t[4] = tonumber("68719476736.875")
        t[5] = MB_VERSION
        G.mb = t
        G.mb_seq = 0
        G.mb_count = 0
    end

    local function poll_mailbox()
        local t = G.mb
        local seq = t[6]
        if seq == G.mb_seq then return end
        G.mb_seq = seq
        local len = t[8]
        if type(len) == "number" and len >= 0 and len <= MB_MAX and len % 1 == 0 then
            local bytes = {}
            for i = 1, len do
                local b = t[MB_B0 + i - 1]
                if type(b) ~= "number" or b < 0 or b > 255 or b % 1 ~= 0 then
                    bytes = nil
                    break
                end
                bytes[i] = string.char(b)
            end
            if bytes then
                local a = rawget(_G, "ARGUMENTS")
                if type(a) ~= "table" then
                    a = {}
                    _G.ARGUMENTS = a
                end
                for part in string.gmatch(table.concat(bytes), "[^;]+") do
                    local k, v = string.match(part, "^%s*([%w_]+)%s*=%s*(.-)%s*$")
                    if k and MB_KEYS[k] then
                        a[k] = v ~= "" and v or nil
                    end
                end
                G.cfg, G.hooked = nil, false   -- 重新读设置、重新挂钩子
                G.mb_count = G.mb_count + 1
            end
        end
        t[7] = seq
    end

    local function split(s)
        local out = {}
        if type(s) ~= "string" then return out end
        for part in string.gmatch(s, "[^,]+") do
            out[#out + 1] = part
        end
        return out
    end

    local function config()
        if G.cfg ~= nil then return G.cfg or nil end
        local a = rawget(_G, "ARGUMENTS")
        if type(a) ~= "table" then return nil end
        local cfg = false
        local mode, units, max = a.drill_mode, a.drill_units, tonumber(a.drill_max)
        if not mode and a.tank_drill then
            mode, units, max = "only", "bug_tank/bug_tank", tonumber(a.tank_drill) or 1
        end
        if mode == "only" or mode == "seq" then
            local list, set = {}, {}
            for _, u in ipairs(split(units)) do
                if string.match(u, "^[a-z0-9_]+/[a-z0-9_]+$") then
                    local path = "characters/" .. u
                    if not set[path] then
                        set[path] = true
                        list[#list + 1] = path
                    end
                end
            end
            local seq = {}
            for _, s in ipairs(split(a.drill_seq)) do
                local n = tonumber(s)
                if n and n >= 1 then seq[#seq + 1] = math.floor(n) end
            end
            if #seq == 0 then seq = { 1 } end
            if #list > 0 then
                cfg = { mode = mode, all = list, max = math.max(1, math.floor(max or 1)), seq = seq,
                        gap = math.max(0, tonumber(a.drill_gap) or 3) }
            end
        end
        G.cfg = cfg
        return cfg or nil
    end

    local function training_host()
        local b = rawget(_G, "Boot")
        local sm = type(b) == "table" and b.state_machine
        if not sm or sm:get_current_state_name() ~= "game" then return false end
        local s = sm:get_current_state()
        return type(s) == "table" and s.is_training == true and s.is_server == true
    end

    local function active()
        local cfg = config()
        if cfg and training_host() then return cfg end
    end

    local function cap()
        local gs = rawget(_G, "GameSettings")
        return (type(gs) == "table" and tonumber(gs.MAX_NUM_ALLOWED_ENEMIES)) or 40
    end

    -- 这张图种族能出的怪（按名字前缀挑）。种族变了（换了一局）重算。
    local function pick_race(cfg, race)
        if G.race == race and G.units then return G.units end
        local pre = RACE_PREFIX[race]
        local units, set = {}, {}
        for _, p in ipairs(cfg.all) do
            local name = string.match(p, "/([^/]+)$") or ""
            if pre and string.sub(name, 1, #pre) == pre then
                units[#units + 1] = p
                set[p] = true
            end
        end
        G.race, G.units, G.set = race, units, set
        G.rr, G.batch, G.timer, G.spawned = 1, 1, 0, 0
        return units
    end

    local function alive(comp)
        local n = comp.encounter_manager:get_num_queued_enemies()
        for unit in comp.entity_manager:all_slaves_iterator("enemy") do
            if not EntityAux.state(unit, "health").is_dead then
                n = n + 1
            end
        end
        return n
    end

    local function spawn(comp, st, n)
        local units = G.units
        if not units or #units == 0 or n < 1 or not G.orig_spawn_group then return end
        local pos = Vector3Aux.unbox(st.spawn_positions[math.random(1, #st.spawn_positions)])
        pos.z = 100
        local counts, order = {}, {}
        for _ = 1, n do
            local p = units[G.rr] or units[1]
            G.rr = (G.rr % #units) + 1
            if not counts[p] then order[#order + 1] = p end
            counts[p] = (counts[p] or 0) + 1
        end
        local group = { units = {} }
        for _, p in ipairs(order) do
            group.units[#group.units + 1] = { unit_path = p, amount = counts[p] }
        end
        G.own = true
        local ok, err = pcall(G.orig_spawn_group, comp.encounter_manager, pos, group)
        G.own = false
        if ok then
            G.spawned = (G.spawned or 0) + n
        else
            G.last_error = tostring(err)
        end
    end

    local function step(comp, st, cfg, dt)
        local gl = comp.generated_level
        local units = pick_race(cfg, gl and gl.enemy)
        if #units == 0 or type(st.spawn_positions) ~= "table" or #st.spawn_positions == 0 then return end
        local have = alive(comp)
        local room = cap() - have
        if cfg.mode == "only" then
            local want = math.min(cfg.max, cap())
            if have >= want then
                G.timer = cfg.gap
                return
            end
            G.timer = (G.timer or 0) - dt
            if G.timer <= 0 then
                spawn(comp, st, math.min(want - have, room))
                G.timer = cfg.gap
            end
        else
            if have > 0 then
                G.timer = cfg.gap
                return
            end
            G.timer = (G.timer or 0) - dt
            if G.timer <= 0 then
                local n = cfg.seq[G.batch] or cfg.seq[1]
                G.batch = (G.batch % #cfg.seq) + 1
                spawn(comp, st, math.min(n, room))
                G.timer = cfg.gap
            end
        end
    end

    local function hook_genocide(c)
        if type(c) ~= "table" or rawget(c, "_drill_hooked") or type(c.update_masters) ~= "function" then return end
        local orig = c.update_masters
        c.update_masters = function(self, masters, dt, ...)
            local ok, cfg = pcall(active)
            if not (ok and cfg) or type(masters) ~= "table" then
                return orig(self, masters, dt, ...)
            end
            for _, m in pairs(masters) do
                local st = type(m) == "table" and m.state
                if type(st) == "table" then
                    st.check_wave_done_timer = 5  -- 原版出波停掉
                end
            end
            local res = { orig(self, masters, dt, ...) }
            for _, m in pairs(masters) do
                local st = type(m) == "table" and m.state
                if type(st) == "table" and (tonumber(st.initial_wait_time) or 0) <= 0 then
                    local ok2, err = pcall(step, self, st, cfg, dt or 0)
                    if not ok2 then G.last_error = tostring(err) end
                end
            end
            return unpack(res)
        end
        c._drill_hooked = true
    end

    local function hook_encounter(c)
        if type(c) ~= "table" or rawget(c, "_drill_hooked") then return end
        if type(c.spawn_group) ~= "function" or type(c.spawn_enemy) ~= "function" then return end
        local spawn_group, spawn_enemy = c.spawn_group, c.spawn_enemy
        G.orig_spawn_group = spawn_group
        c.spawn_group = function(self, pos, group, ...)
            if G.own then
                return spawn_group(self, pos, group, ...)
            end
            local ok, cfg = pcall(active)
            if not (ok and cfg) then
                return spawn_group(self, pos, group, ...)
            end
            -- 遭遇战 / 叫援军 / 报复关漏网的一组：不刷（场上只有这里刷的怪，数量才准）
            G.blocked = (G.blocked or 0) + 1
        end
        c.spawn_enemy = function(self, path, ...)
            if G.own then
                return spawn_enemy(self, path, ...)
            end
            local ok, cfg = pcall(active)
            if ok and cfg then
                G.blocked = (G.blocked or 0) + 1  -- 单个刷怪（装甲车放兵这类）也不刷
                return
            end
            return spawn_enemy(self, path, ...)
        end
        c._drill_hooked = true
    end

    local function hook_patrol(c)
        if type(c) ~= "table" or rawget(c, "_drill_hooked") or type(c.spawn_patrol) ~= "function" then return end
        local orig = c.spawn_patrol
        c.spawn_patrol = function(self, ...)
            local ok, cfg = pcall(active)
            if ok and cfg then
                return false
            end
            return orig(self, ...)
        end
        c._drill_hooked = true
    end

    local wm = rawget(_G, "WorldManager")
    if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_drill_hooked") then
        local orig = wm.update
        wm.update = function(self, dt, ...)
            pcall(poll_mailbox)
            if not G.hooked then
                local ok, cfg = pcall(config)
                if ok and cfg then
                    pcall(hook_encounter, rawget(_G, "EncounterManager"))
                    pcall(hook_patrol, rawget(_G, "PatrolManager"))
                    pcall(hook_genocide, rawget(_G, "ObjectiveGenocideComponent"))
                    local e, p, o = rawget(_G, "EncounterManager"), rawget(_G, "PatrolManager"),
                        rawget(_G, "ObjectiveGenocideComponent")
                    G.hooked = type(e) == "table" and rawget(e, "_drill_hooked") and type(p) == "table"
                        and rawget(p, "_drill_hooked") and type(o) == "table" and rawget(o, "_drill_hooked") or false
                elseif ok then
                    G.hooked = rawget(_G, "ARGUMENTS") ~= nil  -- 没带参数：以后不用再查
                end
            end
            return orig(self, dt, ...)
        end
        wm._drill_hooked = true
    end
end
