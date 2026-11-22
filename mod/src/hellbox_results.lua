-- Local personal results from the game's own mission summary.
do
    local N = 4096
    local G = HellBoxResults or {rows = {}}
    HellBoxResults = G
    if not G.t then
        local t = {}
        for i = 1, N + 11 do t[i] = 0 end
        t[1], t[2], t[3], t[4], t[5] = 72187331.5, -141551.875, 4217.5625, 17179869184.875, 1
        G.t = t
    end

    local function flag(value)
        return value and 1 or 0
    end

    local function star_count(mask)
        local count = 0
        for i = 1, 3 do
            if BitAux.is_bit_set(mask or 0, i) then count = count + 1 end
        end
        return count
    end

    -- 2026-11-16 用户要：战绩卡片写出这局改了什么（高难的正好当战绩）。从 data_live.lua 最后套上的命令和
    -- spawn_rules 现在的设置抽一份短清单，存在这一行最后一格「#M 项;项;…」（老 HellBox 认不出这一格，会跳过）：
    --   P:god=heal|true   P:路径*倍数        潜兵
    --   E:路径*倍数       E:set=单只改了几项   怪物属性
    --   W:路径*倍数|=值   T:路径*倍数|=值       武器 / 战备（同一项多把武器、多类战备只记一次）
    --   S:g=mult*3|only|none|custom  S:a=…  S:p=…  S:v=only|none  S:spread=2   出怪
    local function split_list(text)
        local out = {}
        for item in string.gmatch(text or "", "[^,]+") do
            out[#out + 1] = item
        end
        return out
    end

    local function mod_items()
        local items, seen = {}, {}
        local function add(s)
            if not seen[s] then
                seen[s] = true
                items[#items + 1] = s
            end
        end
        local dl = rawget(_G, "HellBoxDataLive") or {}
        local pc = dl.player_cmd
        if type(pc) == "string" and pc ~= "reset" then
            local god = string.match(pc, "god=(%a+)")
            if god == "heal" or god == "true" then add("P:god=" .. god) end
            for _, e in ipairs(split_list(string.match(pc, "common=([^;]*)"))) do add("P:" .. e) end
        end
        local ec = dl.params_cmd
        if type(ec) == "string" and ec ~= "reset" then
            for _, e in ipairs(split_list(string.match(ec, "common=([^;]*)"))) do add("E:" .. e) end
            local n = #split_list(string.match(ec, "set=([^;]*)"))
            if n > 0 then add("E:set=" .. n) end
        end
        local function short(prefix, cmd)
            if type(cmd) ~= "string" or cmd == "reset" then return end
            for _, e in ipairs(split_list(string.match(cmd, "common=([^;]*)"))) do add(prefix .. e) end
            for _, e in ipairs(split_list(string.match(cmd, "set=([^;]*)"))) do
                -- 「武器短名.路径*倍数」去掉武器名，同一项只记一次
                local rest = string.match(e, "^[%w_]+%.(.+)$") or e
                add(prefix .. rest)
            end
        end
        short("W:", dl.weapon_cmd)
        for _, cmd in pairs(dl.strat_cmd or {}) do short("T:", cmd) end
        local sp = rawget(_G, "SpawnRulesMod")
        local cfg = sp and sp.cfg
        if type(cfg) == "table" then
            local maps = { g = sp.gmap, a = sp.amap, p = sp.pmap }
            local mults = { g = cfg.multg, a = cfg.mult, p = cfg.multp }
            for _, s in ipairs({ "g", "a", "p" }) do
                if cfg[s] == "mult" then
                    add("S:" .. s .. "=mult*" .. tostring(mults[s] or cfg.mult))
                elseif cfg[s] == "only" or cfg[s] == "none" then
                    add("S:" .. s .. "=" .. cfg[s])
                elseif next(maps[s] or {}) then
                    add("S:" .. s .. "=custom")
                end
            end
            if cfg.v == "only" or cfg.v == "none" then add("S:v=" .. cfg.v) end
            if cfg.v ~= "none" and (tonumber(cfg.vn) or 0) > 0 then add("S:vn=" .. tostring(cfg.vn)) end
            if (tonumber(cfg.spread) or 0) > 0 then add("S:spread=" .. tostring(cfg.spread)) end
            -- 2026-11-18 V0.96 场上上限：-1 = 破限，17～300 = 固定
            local cap = tonumber(cfg.cap) or 0
            if cap < 0 or cap > 16 then add("S:cap=" .. tostring(cap)) end
        end
        return items
    end

    local function record(state)
        if state.hellbox_result_recorded then return end
        local stats = state.mission_stats_go
        if not stats or not stats:exists() then return end
        local seed = stats:get("mission_seed") or 0
        if seed <= 0 then return end
        local player
        for _, entry in ipairs(state.players or {}) do
            -- 2026-11-14 修：结算画面的 players 表里没有 owned 字段（那是 active_players 才有的），
            -- 以前判 entry.owned 永远是空，一局都记不下来；改成问玩家对象自己是不是本机的。
            local go = entry.player_go
            if go and go:exists() and go:owned() then
                if not player or entry.pad_number == GameSettings.get_main_pad_number() then
                    player = entry.player_go
                end
            end
        end
        if not player then return end
        local deaths, kills = player:get("deaths"), player:get("kills")
        if type(deaths) ~= "number" or type(kills) ~= "number" then return end

        local drill = rawget(_G, "AIDrillMod")
        local wave = ARGUMENTS and tonumber(ARGUMENTS.start_wave)
        local enemies = rawget(_G, "EnemyParamsMod")
        local ok_items, items = pcall(mod_items)
        items = ok_items and items or {}
        if wave and wave > 1 then table.insert(items, 1, "D:wave=" .. math.floor(wave)) end
        -- 2026-11-16：武器、战备、潜兵（含无敌）改过也算自定义
        local modified = (drill and drill.cfg) or #items > 0
            or enemies and (next(enemies.common or {}) or next(enemies.ov or {}))
        local params = DifficultySettings.get_mission_params(seed)
        -- 2026-11-19「选图」设为下一局不再标训练（照常记经验），房主这边的战绩照样归到选图那两类（hellbox_start.lua played_seed）
        local start = rawget(_G, "HellBoxStart")
        local picked = state.is_training or (type(start) == "table" and start.played_seed == seed)
        local mode = picked and (modified and 2 or 1) or (modified and 3 or 0)
        local elapsed = math.max(0, math.floor(stats:get("mission_time") or 0))
        local objectives = state.objective_count or 0
        local done = state.objectives_complete_count or 0
        local epoch = os.time()
        local stamp = math.floor(Application.time_since_launch() * 1000)
        local fields = {
            epoch .. "-" .. stamp .. "-" .. seed, epoch, seed, params.enemy, params.difficulty, mode,
            flag(stats:get("mission_completed")), flag(player:get("has_extracted")), star_count(stats:get("mission_stars")),
            elapsed, done, objectives, kills, deaths, player:get("research_samples_picked_up") or 0,
            player:get("team_kills") or 0, state.total_players or 1,
        }
        -- 2026-11-13：每个玩家一格（第 17 格起），格内用 Tab 分：名字、杀敌、死亡、误杀、开枪、命中、样本、撤离、是不是自己
        for _, entry in ipairs(state.players or {}) do
            local go = entry.player_go
            if go and go:exists() then
                local name = tostring(go:get("name") or "?"):gsub("[|\t\r\n]", " ")
                local function num(key)
                    local v = go:get(key)
                    return type(v) == "number" and math.floor(v) or 0
                end
                fields[#fields + 1] = table.concat({
                    name, num("kills"), num("deaths"), num("team_kills"), num("shots"), num("hits"),
                    num("research_samples_picked_up"), flag(go:get("has_extracted")), flag(go == player),
                }, "\t")
            end
        end
        if #items > 0 then
            local cell = "#M" .. (table.concat(items, ";"):gsub("[|%c]", " "))
            fields[#fields + 1] = string.sub(cell, 1, 700)
        end
        local row = table.concat(fields, "|")
        state.hellbox_result_recorded = true
        G.rows[#G.rows + 1] = row
        if #G.rows > 24 then table.remove(G.rows, 1) end
        local text = table.concat(G.rows, "\n")
        while #text > N and #G.rows > 1 do  -- 信箱最多 N 字节：多人局一行更长，装不下就少留几局（桌面会存到本地文件）
            table.remove(G.rows, 1)
            text = table.concat(G.rows, "\n")
        end
        for i = 1, #text do G.t[11 + i] = text:byte(i) end
        G.t[11] = #text
        G.t[10] = G.t[10] + 1
        -- Keep results even when the desktop was closed, where the engine permits local Lua file I/O.
        if io and io.open and os.getenv then
            local data = os.getenv("APPDATA")
            if data then
                local f = io.open(data .. "/Arrowhead/Helldivers/hellbox-results-feed.txt", "a")
                if f then f:write(row, "\n"); f:close() end
            end
        end
    end

    local function hook()
        local cls = rawget(_G, "StateMissionEnd")
        if not cls or type(cls.update) ~= "function" or cls.update == G.update then return end
        local original = cls.update
        G.update = function(self, ...)
            local result = original(self, ...)
            if not self.hellbox_result_recorded and self.current_state
                    and self.current_state ~= MissionEndStateWaitingForData then
                pcall(record, self)
            end
            return result
        end
        cls.update = G.update
    end
    pcall(hook)
    if not G.update and WorldManager and WorldManager.update then
        local original = WorldManager.update
        WorldManager.update = function(self, ...)
            if not G.update then pcall(hook) end
            return original(self, ...)
        end
    end
end
