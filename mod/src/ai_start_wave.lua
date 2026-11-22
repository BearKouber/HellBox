-- [ai start wave] 训练关从第 N 波开打（2026-11-04，HD1-023，用户要："冲锋虫的关卡是否可以直接到达比如进度是50击杀"）。
-- 由 build.py 追加到 character_state_machine 末尾。只有启动参数 -start_wave N 加本地训练关（主机）才生效，平时什么都不改。
-- 报复关刷什么看的是第几波，不是杀了多少（objective_genocide_component 401~438 行：current_wave + 1，
-- 各组的 wave_start；genocide_settings_bugs：穿刺虫 wave_start = 4、冲锋虫 wave_start = 5），
-- 点数 = 难度 * 2 + 波数 * 4 * (人数 / 2)。所以把还没开第一波的 current_wave 从 0 改成 N - 1，第一波就是第 N 波，
-- 刷法和正常打到第 N 波一样（冲锋虫有机会刷、不保证每波都有）。击杀数照常从 0 开始数。
do
    local G = AIStartWaveMod or {}
    AIStartWaveMod = G

    local function wave()
        local a = rawget(_G, "ARGUMENTS")
        local v = type(a) == "table" and a.start_wave
        if not v then return nil end
        local n = tonumber(v)
        if not n or n < 2 then return nil end
        return math.floor(n)
    end

    local function training_host()
        local b = rawget(_G, "Boot")
        local sm = type(b) == "table" and b.state_machine
        if not sm or sm:get_current_state_name() ~= "game" then return false end
        local s = sm:get_current_state()
        return type(s) == "table" and s.is_training == true and s.is_server == true
    end

    local function bump(masters, n)
        for _, m in pairs(masters) do
            local st = type(m) == "table" and m.state
            if type(st) == "table" and not st._ai_start_wave then
                st._ai_start_wave = true
                if st.current_wave == 0 then
                    st.current_wave = n - 1
                    st.dirty = true
                end
            end
        end
    end

    local function hook(c)
        if type(c) ~= "table" or rawget(c, "_start_wave_hooked") then return end
        if type(c.update_masters) ~= "function" then return end
        local orig = c.update_masters
        c.update_masters = function(self, masters, dt, ...)
            local n = wave()
            if n and type(masters) == "table" then
                local ok, th = pcall(training_host)
                if ok and th then
                    pcall(bump, masters, n)
                end
            end
            return orig(self, masters, dt, ...)
        end
        c._start_wave_hooked = true
    end

    local wm = rawget(_G, "WorldManager")
    if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_start_wave_hooked") then
        local orig = wm.update
        wm.update = function(self, dt, ...)
            if wave() then
                pcall(hook, rawget(_G, "ObjectiveGenocideComponent"))
            end
            return orig(self, dt, ...)
        end
        wm._start_wave_hooked = true
    end
end
