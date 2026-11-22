-- HellBox own hooks. Settings are compiled from the desktop configuration.
-- 2026-11-21 HD1-038（用户定）：来自 QoL Mod 的六项（手柄改键保护、禁用求救信标、显示延迟数字、军械库降级退点、过场加速、
--   暂停星球进度）删了：QoL 作者希望各自独立、能一起装，想用就装正版 QoL（HellBox 能和它共存）。
-- 2026-11-14 V0.91 用户要求所有开关热生效：装 MOD 时编进来的只是初始值；游戏每秒读 HellBox 写的
--   %APPDATA%/Arrowhead/Helldivers/hellbox/options.txt（HBOPT1，一行一个 键=值），读到就改 cfg。
--   所有挂钩一直装着，每次用的时候看开关（关着就照原版走）。带箱子上车也在这个文件里（carry=true/false，
--   carry_vehicle.lua 看全局 HellBoxCarryOn）。
do
    local cfg = "@HELLBOX_OPTIONS@"
    HellBoxOptions = cfg
    if HellBoxCarryOn == nil then HellBoxCarryOn = true end

    local BOOL_KEYS = {refresh = true, voice = true, drop = true, noslide = true,
                       dh_ping = true, dh_hidden = true, dh_friends = true, dh_qol_fix = true,  -- 2026-11-21 Dive Harder 四项（hellbox_dh.lua）
                       supply = true, hide_samples = true, ime_fix = true}  -- 2026-11-19 补给热键 / 样本描边（Lhgrzr）、输入法防闪退（HalfSugar）
    local ACTION_OK = {reload = true, switch_weapon = true, [""] = true}
    local DROP_KEY_OK = {x = true, z = true, c = true, b = true, h = true, t = true}
    -- 补给热键可选的键：主键盘 4～9（原版键盘只用了 1～3；小键盘是另外的键名，不受影响）
    local SUPPLY_KEY_OK = {["4"] = true, ["5"] = true, ["6"] = true, ["7"] = true, ["8"] = true, ["9"] = true}
    local DROP_FIRST_OK = {weapon = true, backpack = true, [""] = true}
    local function read_options()
        local appdata = os.getenv and os.getenv("APPDATA")
        local f = appdata and io and io.open and io.open(appdata .. "/Arrowhead/Helldivers/hellbox/options.txt", "rb")
        if not f then return end
        local text = f:read("*a") or ""
        f:close()
        if text == cfg.options_text or not text:match("^HBOPT1") then return end
        cfg.options_text = text
        for line in text:gmatch("[^\r\n]+") do
            local k, v = line:match("^([%w_]+)=(.*)$")
            if k and BOOL_KEYS[k] then
                cfg[k] = v == "true"
            elseif k == "carry" then
                HellBoxCarryOn = v ~= "false"
            elseif k == "action" and ACTION_OK[v] then
                cfg.action = v
            elseif k == "drop_key" and DROP_KEY_OK[v] then
                cfg.drop_key = v
            elseif k == "drop_first" and DROP_FIRST_OK[v] then
                cfg.drop_first = v
            elseif k == "supply_key" and SUPPLY_KEY_OK[v] then
                cfg.supply_key = v
            elseif k == "ping_window" and (v == "3" or v == "5" or v == "10") then
                cfg.ping_window = tonumber(v)
            elseif k and k:match("^voice[5-8]$") and v:match("^[%w_]+$") then
                cfg[k] = v
            end
        end
    end

    local actions = {
        reload = {"reload_pressed", "reload_button"},
        switch_weapon = {"switch_weapon_down"},
    }
    local navigation = {
        "left_shoulder", "right_shoulder", "left_trigger", "right_trigger",
        "select", "back", "_esc", "_back", "options", "options_mouse",
        "select_mouse", "select_mouse_down", "cross", "circle", "up", "down", "left", "right",
        "d_up", "d_down", "d_left", "d_right", "enter",
    }
    local function indexed(bindings)
        local out = {}
        for _, binding in ipairs(bindings or {}) do
            out[binding.output_name] = binding
        end
        return out
    end

    local function key_for(binding, value)
        if binding and binding.func ~= "filter" then
            local key = value or binding.key or binding.scan_code
            if key then return (binding.controller_type or "") .. ":" .. tostring(key) end
        end
    end

    local function reserve(output, binding)
        local key = key_for(binding)
        if key then
            output[key] = true
            if binding.alt_key then output[key_for(binding, binding.alt_key)] = true end
        end
    end

    -- 2026-11-16 改：以前要求「键盘和所有手柄都不冲突」才算能用——插着手柄时换弹（手柄 RB = 菜单翻页）
    -- 连键盘的 R 也一起灰掉；切换武器键盘上根本没有单独的键，玩键盘时永远是灰的。
    -- 现在每个设备分开判：哪个设备上这个键不冲突，就只听那个设备上的这个键（直接读设备，不走合并后的 input）。
    local function device_keys(action)
        local out = {}
        if not InputRebinder or not InputRebinder.keybindings then
            return out
        end
        local active_pads = {}
        if PadManager and PadManager.get_active_pads then
            for _, pad in ipairs(PadManager:get_active_pads() or {}) do
                active_pads["pad" .. pad.pad_number] = true
            end
        end
        for device, current in pairs(InputRebinder.keybindings) do
            if device == "keyboard_mouse" or active_pads[device] then
                local bindings = indexed(current)
                local reserved = {}
                for _, name in ipairs(navigation) do
                    reserve(reserved, bindings[name])
                end
                local valid, keys = true, {}
                for _, output in ipairs(actions[action] or {}) do
                    local binding = bindings[output]
                    local button = key_for(binding)
                    if button then
                        valid = valid and not reserved[button]
                            and (not binding.alt_key or not reserved[key_for(binding, binding.alt_key)])
                        keys[#keys + 1] = {binding.controller_type, binding.key or binding.scan_code}
                        if binding.alt_key then keys[#keys + 1] = {binding.controller_type, binding.alt_key} end
                    end
                end
                if valid and #keys > 0 then
                    out[#out + 1] = {device = device, keys = keys}
                end
            end
        end
        return out
    end

    function cfg.refresh_choices()
        local available = {}
        for action in pairs(actions) do
            available[action] = #device_keys(action) > 0
        end
        return available
    end

    local function raw_pressed(device, ctype, key)
        local ok, hit = pcall(function()
            if ctype == "keyboard" and Keyboard then
                local i = Keyboard.button_index(key)
                return i and Keyboard.pressed(i)
            elseif ctype == "mouse" and Mouse then
                local i = Mouse.button_index(key)
                return i and Mouse.pressed(i)
            elseif ctype == "pad" then
                local pad = rawget(_G, "Pad" .. (string.match(device, "^pad(%d)$") or ""))
                local i = pad and pad.button_index(key)
                return i and pad.pressed(i)
            end
        end)
        return ok and hit and true or false
    end

    -- 这一帧有没有在「不冲突的设备」上按下刷新键
    function cfg.refresh_pressed(action)
        for _, d in ipairs(device_keys(action)) do
            for _, k in ipairs(d.keys) do
                if raw_pressed(d.device, k[1], k[2]) then
                    return true
                end
            end
        end
        return false
    end

    -- 2026-11-13：没有「QoL 增强」总开关了，MOD 装着就按各自的开关
    local function enabled(key)
        return cfg[key]
    end

    local hooks = {}
    local function wrap(class_name, method, callback)
        local class = rawget(_G, class_name)
        if type(class) ~= "table" or type(class[method]) ~= "function" then
            return
        end
        local key = class_name .. "." .. method
        -- 每个类只包一次（2026-11-14）：原来按"现在的函数是不是我包的"判断，别的脚本（training_loadout.lua）
        -- 再包一层后这里会以为没包上，每 0.5 秒又包一层，越叠越多（比如加速被乘好几次）。
        if hooks[key] == class then return end
        local original = class[method]
        class[method] = function(...) return callback(original, ...) end
        hooks[key] = class
    end

    local function install_hooks()
        -- 2026-11-19 出发倒计时闪退保护（用户实测：出关回飞船、进舱门就闪退，崩溃报告 state_menu.lua update_client
        --   「bad argument #1 to 'min' (number expected, got nil)」）。原版只在 menu_state 刚变成倒计时那一帧给
        --   predicted_countdown_timer 设初值（30），选装备阶段设 20；这台电脑在倒计时 / 选装备进行中从房主那条路切到客机这条路
        --   （或刚进来时状态就已经是倒计时）就跳过了那一帧，空值传进 math.min / math.max 直接报错退出。
        --   这里只在它是空的时候补上原版那两个初值，别的不动。
        do
            wrap("StateMenu", "update_client", function(original, self, dt, ...)
                pcall(function()
                    if type(self.predicted_countdown_timer) ~= "number" then
                        if self.menu_state == self.MENU_STATE_COUNTDOWN then
                            self.predicted_countdown_timer = type(self.countdown_timer) == "number" and self.countdown_timer or 30
                        elseif self.menu_state == self.MENU_STATE_LOADOUT then
                            self.predicted_countdown_timer = 20
                        end
                    end
                end)
                return original(self, dt, ...)
            end)
        end

        do
            -- 快捷语音：键鼠按 F5～F8；手柄长按十字键 上 / 下 / 左 / 右（对应 F5 / F6 / F7 / F8）。
            -- 原版手柄十字键一按下就喊 是 / 否 / 留守 / 移动。这里改成松手时再决定：
            --   按住不到 HOLD 秒就松开 = 原版那句（只是从"按下时"挪到"松开时"）；按满 HOLD 秒 = 喊这里设的语音，松开后不再喊原版那句。
            local HOLD = 0.45
            local dpad = {
                {"communication_yes", "d_up", 5}, {"communication_no", "d_down", 6},
                {"communication_stay", "d_left", 7}, {"communication_move", "d_right", 8},
            }
            local holding = {} -- unit -> {event = 原版那句, button = 十字键, slot = 5~8, t0 = 按下时刻, fired = 是否已喊}

            local function now()
                return Application.time_since_launch()
            end

            local function say(unit, event, ignore_animation)
                EntityAux.queue_command_master(unit, "customization", "communication_event",
                    TempTableFactory:get_map("event", event, "ignore_animation", ignore_animation))
            end

            local function pad_of(unit)
                local current = Boot.state_machine:get_current_state()
                if not current or current.paused or current.text_chat and current.text_chat.active then
                    return nil
                end
                for _, player in pairs(current.players or {}) do
                    if player.player_go and player.player_go:exists() and player.player_go:get("avatar_unit") == unit then
                        return player.pad_number
                    end
                end
            end

            local function held(pad, button)
                local controller = PadManager:get_pad(pad)
                if not controller or not controller.button_index or not controller.button then
                    return false
                end
                local ok, value = pcall(function() return controller.button(controller.button_index(button)) end)
                return ok and type(value) == "number" and value > 0.5
            end

            -- 2026-11-16 V0.95 丢战备（用户要求：原版没有把支援武器 / 背包丢地上的操作）。
            -- 用游戏自己的指令 inventory drop（人死时掉东西、捡新武器换下旧的都是它），丢下的东西全队同步、谁都能捡。
            -- 顺序：手里拿着支援武器 → 丢它；不然有背包 → 丢背包；再不然丢背着的支援武器。
            -- 键盘：按选的键（X/Z/C/B/H/T，原版都没用；被玩家改键占了就不响应）。
            -- 手柄：没有空键，按住交互键（一般是 A）满 DROP_HOLD 秒。按下那一刻身边有能交互的东西就不算；
            --   只在站着 / 走 / 跑 / 瞄准时数（这几个状态才走到这里），倒地、搬箱子、坐车、正在交互都不触发，
            --   中途换了状态（比如开始救人）这次长按作废，松手重来。
            local DROP_HOLD = 0.6
            local DROP_STATES = {CharacterStateIdle = true, CharacterStateWalk = true, CharacterStateAim = true,
                                 CharacterStateAimWalk = true, CharacterStateSprint = true}
            local drop_hold = {} -- unit -> {t0 = 按下时刻, last = 上次看到按着, blocked = 这次不算, fired = 已丢}

            local function drop_now(unit, data)
                local inv = data.state.inventory_state
                if not inv then return false end
                local cur, sup, bp = inv.current_weapon, inv.support_weapon, inv.backpack
                local what
                -- 2026-11-19 发行抢先版 用户要求：能选先丢武器（weapon）还是先丢背包（backpack）；空 = 原来的看手上
                local first = cfg.drop_first
                local has_sup, has_bp = sup and Unit.alive(sup), bp and Unit.alive(bp)
                if first == "weapon" and (has_sup or has_bp) then
                    what = has_sup and "support_weapon" or "backpack"
                elseif first == "backpack" and (has_sup or has_bp) then
                    what = has_bp and "backpack" or "support_weapon"
                elseif sup and cur == sup and Unit.alive(sup) then
                    what = "support_weapon"
                elseif bp and Unit.alive(bp) then
                    what = "backpack"
                elseif sup and Unit.alive(sup) then
                    what = "support_weapon"
                end
                if not what then return false end
                EntityAux.queue_command_master(unit, "inventory", "drop", what)
                return true
            end

            local function keyboard_free(key)
                local binds = InputRebinder and InputRebinder.keybindings and InputRebinder.keybindings.keyboard_mouse
                for _, b in ipairs(binds or {}) do
                    if b.func ~= "filter" and b.controller_type == "keyboard" and (b.key == key or b.alt_key == key) then
                        return false
                    end
                end
                return true
            end

            local function interact_button(pad)
                local binds = InputRebinder and InputRebinder.keybindings and InputRebinder.keybindings["pad" .. tostring(pad)]
                for _, b in ipairs(binds or {}) do
                    if b.output_name == "interact" and b.key then return b.key end
                end
                return "a"
            end

            local function drop_tick(unit, data, pad)
                local st = data.state
                local name = st.current_state and st.current_state.name
                if not DROP_STATES[name] or st.current_carry_unit or (st.health_state and st.health_state.is_downed) then
                    drop_hold[unit] = nil
                    return
                end
                if pad == KEYBOARD_MOUSE_PAD_NUMBER then
                    drop_hold[unit] = nil
                    local key = cfg.drop_key or "x"
                    if Window.has_focus() then
                        local i = Keyboard.button_index(key)
                        if i and Keyboard.pressed(i) and keyboard_free(key) then
                            drop_now(unit, data)
                        end
                    end
                    return
                end
                if not held(pad, interact_button(pad)) then
                    drop_hold[unit] = nil
                    return
                end
                local t = now()
                local h = drop_hold[unit]
                if not h or t - h.last > 0.15 then
                    -- 这一帧才按下（input.interact）才算新的一次；按着从别的状态回来的不算
                    local near = st.interactor_state and Unit.alive(st.interactor_state.interactable_unit)
                    h = {t0 = t, blocked = not st.input.interact or near or false, fired = false}
                    drop_hold[unit] = h
                end
                h.last = t
                if not h.blocked and not h.fired and t - h.t0 >= DROP_HOLD then
                    h.fired = true
                    drop_now(unit, data)
                end
            end

            -- 2026-11-19 补给背包热键（Lhgrzr 写的 backpack_hotkey.lua，用户要求收进 HellBox，手柄加「长按换弹」）。
            -- 背着补给背包时给自己补一次弹药、背包扣一格；弹药满了 / 背包空了不扣。用的是原版"从队友背包拿补给"那两条指令
            -- （背包 backpack_used + 自己 ammo_pickup，来源填这个背包，原版就不会拿它给它自己补满）。
            -- 背包不归这台电脑管（has_component_master 不成立，比如当客机时）就什么都不做，不会出错。
            -- 键盘：按选的键（默认主键盘 5，被玩家改键占了就不响应；小键盘是另外的键名，不受影响）。
            -- 手柄：按住换弹键满 SUPPLY_HOLD 秒（换弹照常换，到时间再补给）。站着 / 走 / 跑 / 瞄准时才数，和丢支援装备一样。
            local SUPPLY_PACK = "equipment/wep_ammo_backpack_01"
            local SUPPLY_HOLD = 0.6
            local supply_hold = {} -- unit -> {t0 = 按下时刻, last = 上次看到按着, fired = 已补}

            local function supply_now(unit, st)
                local inv = st.inventory_state
                local pack = inv and inv.backpack
                if not pack or not Unit.alive(pack) or not Unit.is_a(pack, SUPPLY_PACK) then return false end
                if not EntityAux.has_component_master(pack, "ammo_backpack") then return false end
                local uses = EntityAux.state_master_interface(pack, "backpack")
                if not uses or not uses.num_uses or uses.num_uses < 1 then return false end
                if InventoryComponent.has_full_ammo(inv, true, SUPPLY_PACK) then return false end
                local function give()
                    -- 动作开始时再看一次（按下到进动作中间，队友可能拿走了最后一格）
                    if not Unit.alive(pack) or inv.backpack ~= pack then return end
                    local left = EntityAux.state_master_interface(pack, "backpack")
                    if not left or not left.num_uses or left.num_uses < 1 then return end
                    if InventoryComponent.has_full_ammo(inv, true, SUPPLY_PACK) then return end
                    EntityAux.queue_command_master(pack, "ammo_backpack", "backpack_used")
                    EntityAux.queue_command_master(unit, "inventory", "ammo_pickup", pack)
                end
                -- 2026-11-19 用户要求带原本的动作：照队友从补给背包拿弹药那一下（interactable_character_component
                -- self_service_reload）：动作和时长取背包设置 interact_info（原版 help_up、0.9 秒），收枪，进 CharacterStateInteract；
                -- 补给在动作开始时给（原版 interact_action 也是进状态第一帧就跑）。拿不到交互状态就照旧直接补。
                local is = EntityAux.state_master(unit, "interactor")
                if type(is) ~= "table" then give(); return true end
                if is.busy then return false end
                local info = LuaSettingsManager and LuaSettingsManager:get_settings_by_unit(pack)
                info = info and info.interact_info or {}
                is.interact_event = info.interact_event or "help_up"
                is.interact_time = info.interact_time or 0.9
                is.interact_direction = nil
                is.interact_holster = true
                is.interact_speed = 1
                is.interact_collision_enabled = true
                is.interact_angle = 0
                is.interact_target_state = nil
                is.interact_action = give
                EntityAux.queue_command_master(unit, "character", "interact")
                return true
            end

            local function reload_button(pad)
                local binds = InputRebinder and InputRebinder.keybindings and InputRebinder.keybindings["pad" .. tostring(pad)]
                for _, b in ipairs(binds or {}) do
                    if b.output_name == "reload_button" and b.key then return b.key end
                end
                return "right_shoulder" -- 原版默认 RB（controller_settings.lua）
            end

            local function supply_tick(unit, data, pad)
                local st = data.state
                local name = st.current_state and st.current_state.name
                if not DROP_STATES[name] or st.current_carry_unit or (st.health_state and st.health_state.is_downed) then
                    supply_hold[unit] = nil
                    return
                end
                if pad == KEYBOARD_MOUSE_PAD_NUMBER then
                    supply_hold[unit] = nil
                    local key = cfg.supply_key or "5"
                    if Window.has_focus() then
                        local i = Keyboard.button_index(key)
                        if i and Keyboard.pressed(i) and keyboard_free(key) then
                            supply_now(unit, st)
                        end
                    end
                    return
                end
                if not held(pad, reload_button(pad)) then
                    supply_hold[unit] = nil
                    return
                end
                local t = now()
                local h = supply_hold[unit]
                if not h or t - h.last > 0.15 then
                    h = {t0 = t, fired = false}
                    supply_hold[unit] = h
                end
                h.last = t
                if not h.fired and t - h.t0 >= SUPPLY_HOLD then
                    h.fired = true -- 一次长按只补一次，松手再按才补下一次
                    supply_now(unit, st)
                end
            end

            wrap("CharacterComponent", "handle_communication", function(original, self, unit, data, ignore_animation)
                if enabled("supply") then
                    local ok = pcall(function()
                        if EntityAux.owned(unit) then
                            local pad = pad_of(unit)
                            if pad == nil then
                                supply_hold[unit] = nil
                            else
                                supply_tick(unit, data, pad)
                            end
                        end
                    end)
                    if not ok then
                        cfg.supply_errors = (cfg.supply_errors or 0) + 1
                        supply_hold[unit] = nil
                    end
                else
                    supply_hold[unit] = nil
                end
                if enabled("drop") then
                    local ok = pcall(function()
                        if EntityAux.owned(unit) then
                            local pad = pad_of(unit)
                            if pad == nil then
                                drop_hold[unit] = nil
                            else
                                drop_tick(unit, data, pad)
                            end
                        end
                    end)
                    if not ok then
                        cfg.drop_errors = (cfg.drop_errors or 0) + 1
                        drop_hold[unit] = nil
                    end
                else
                    drop_hold[unit] = nil
                end
                if not enabled("voice") then
                    holding[unit] = nil
                    return original(self, unit, data, ignore_animation)
                end
                local ok, skip = pcall(function()
                    if not EntityAux.owned(unit) or not EntityAux.has_component(unit, "customization") then
                        return false
                    end
                    local pad = pad_of(unit)
                    if pad == nil then
                        holding[unit] = nil
                        return false
                    end
                    if pad == KEYBOARD_MOUSE_PAD_NUMBER then
                        if Window.has_focus() then
                            for i = 5, 8 do
                                if Keyboard.pressed(Keyboard.button_index("f" .. i)) then
                                    say(unit, cfg["voice" .. i], ignore_animation)
                                    break
                                end
                            end
                        end
                        return false
                    end
                    -- 手柄
                    local input = data.state.input
                    local h = holding[unit]
                    if h then
                        if held(pad, h.button) then
                            if not h.fired and now() - h.t0 >= HOLD then
                                h.fired = true
                                say(unit, cfg["voice" .. h.slot], ignore_animation)
                            end
                        else
                            holding[unit] = nil
                            if not h.fired then
                                say(unit, h.event, ignore_animation)
                            end
                        end
                        return true -- 按着的这段时间原版不再喊
                    end
                    for _, d in ipairs(dpad) do
                        if input[d[1]] then
                            holding[unit] = {event = d[1]:sub(15), button = d[2], slot = d[3], t0 = now()}
                            return true
                        end
                    end
                    return false
                end)
                if not ok then
                    cfg.voice_errors = (cfg.voice_errors or 0) + 1
                    holding[unit] = nil
                    skip = false
                end
                if not skip then
                    original(self, unit, data, ignore_animation)
                end
            end)
        end




        do
            -- 2026-11-19 隐藏样本描边（Lhgrzr 写的 sample_highlight.lua，用户要求收进 HellBox）。
            -- 三个阵营的地面样本外面那圈发光轮廓是单独一块网格（只有一个材质 m_outline），只藏这一块：
            --   样本本身照样看得见、捡得起，侦察装备在战术地图上标样本照常。只改本机画面。
            -- 样本在生成时（setup_slave）记下来；开关改了以后每 0.5 秒对还在场上的样本补一次，不用等下一关。
            -- 组件脚本先 require 一次（Lhgrzr 原版的做法），保证关卡生成样本之前已经包上。
            if not cfg.samples_required then
                cfg.samples_required = true
                pcall(require, "lua/components/research_sample_pickup_component")
            end
            local samples = cfg.sample_units or {}
            cfg.sample_units = samples
            local function set_outline(unit, s, hidden)
                for _, index in ipairs(s.list) do
                    Unit.set_mesh_visibility(unit, index, not hidden)
                end
                s.hidden = hidden
            end
            wrap("ResearchSamplePickupComponent", "setup_slave", function(original, self, unit, ...)
                local function finish(...)
                    pcall(function()
                        local list = {}
                        for index = 0, Unit.num_meshes(unit) - 1 do
                            local mesh = Unit.mesh(unit, index)
                            if Mesh.num_materials(mesh) == 1 and Mesh.has_material(mesh, "m_outline") then
                                list[#list + 1] = index
                            end
                        end
                        if #list > 0 then
                            local s = {list = list, hidden = false}
                            samples[unit] = s
                            if enabled("hide_samples") then set_outline(unit, s, true) end
                        end
                    end)
                    return ...
                end
                return finish(original(self, unit, ...))
            end)
            local want = enabled("hide_samples") and true or false
            for unit, s in pairs(samples) do
                if not Unit.alive(unit) then
                    samples[unit] = nil
                elseif s.hidden ~= want then
                    set_outline(unit, s, want)
                end
            end
        end

        do
            -- 2026-11-19 聊天输入法防闪退（HalfSugar 写的 HelldiversOptimization「输入法防卡」ime_focus.lua，移植进 HellBox）。
            -- 闪退原因（2026-11-19 用户在飞船聊天时闪退，崩溃在 unicode_aux insert_text_at「compare nil with number」）：
            --   换房间 / 换场景会新建聊天框，光标记录 id_state.marker 是空的；原版 TextChat.update 先把输入法上屏的字
            --   塞进输入框（add_characters），后面的 do_input 才给光标设初值，第一下是中文输入法上屏就拿空光标比大小。
            -- 修法照 HalfSugar：开始打字时光标设到开头；每帧打字前光标是空的就照原版的初值补上；关聊天 / 聊天框销毁时
            --   关掉输入法并清掉残留的上屏结果（有的输入法关掉时会把没打完的字提交出来，不能留给下一个聊天框）；
            --   销毁时原版不调 stop_typing，键盘焦点也一起还回去（不然输入法会卡住键盘）。
            -- 不改系统输入法、不拦键盘；游戏原来的开始 / 结束打字照常管中文聊天。
            local CHAT_IF = "chat_dummy_interface"
            local chat_owner
            local chat_prepared = setmetatable({}, {__mode = "k"})
            local function ime_ok()
                return enabled("ime_fix") and type(Window) == "table" and type(Window.set_ime_enabled) == "function"
                    and type(Window.has_ime_result) == "function" and type(Window.pop_ime_result) == "function"
            end
            local function kb_user()
                return InputManager and InputManager.users and InputManager.users[KEYBOARD_MOUSE_USER_NAME]
            end
            local function release_chat_focus()
                local input = kb_user()
                if not input or not input.controller_interfaces or not input.controller_interfaces[CHAT_IF] then return end
                for _, name in ipairs(input.interface_stack or {}) do
                    if name == CHAT_IF then
                        InputManager:release_focus(KEYBOARD_MOUSE_USER_NAME, CHAT_IF)
                        return
                    end
                end
            end
            local function close_ime()
                Window.set_ime_enabled(false)
                for _ = 1, 64 do
                    if not Window.has_ime_result() then break end
                    Window.pop_ime_result()
                end
            end
            local function chat_cursor(self)
                self.id_state = self.id_state or {}
                -- 和原版 InputField.do_input 的初值一样（文字末尾）
                if self.id_state.marker == nil and type(self.text) == "string" then
                    self.id_state.marker = #self.text + 1
                end
            end
            local function chat_reset(self)
                self.has_candidates = false
                self.previous_has_candidates = false
                self.ime_panel_alpha = 0
                self.ime_candidate_stopped_time = nil
            end
            local function chat_prepare(self)
                chat_owner = self
                chat_prepared[self] = true
                if self.active then
                    chat_cursor(self)
                    local input = kb_user()
                    if input and input.controller_interfaces and input.controller_interfaces[CHAT_IF] then
                        InputManager:take_focus(KEYBOARD_MOUSE_USER_NAME, CHAT_IF)
                    end
                    Window.set_ime_enabled(true)
                else
                    release_chat_focus()
                    close_ime()
                    chat_reset(self)
                end
            end
            wrap("TextChat", "init", function(original, self, ...)
                local function finish(...)
                    if ime_ok() then pcall(chat_prepare, self) end
                    return ...
                end
                return finish(original(self, ...))
            end)
            wrap("TextChat", "start_typing", function(original, self, ...)
                if ime_ok() then
                    pcall(function()
                        chat_owner = self
                        chat_prepared[self] = true
                        close_ime()
                        self.id_state = {marker = 1} -- 新打一句从空串开始，不带上一次的光标 / 连按状态
                        chat_reset(self)
                    end)
                end
                return original(self, ...)
            end)
            wrap("TextChat", "stop_typing", function(original, self, ...)
                local function finish(...)
                    if ime_ok() then
                        pcall(function()
                            if not chat_owner or chat_owner == self then close_ime() end
                            chat_reset(self)
                        end)
                    end
                    return ...
                end
                return finish(original(self, ...))
            end)
            wrap("TextChat", "destroy", function(original, self, ...)
                if ime_ok() then
                    pcall(function()
                        if not chat_owner or chat_owner == self then
                            release_chat_focus()
                            close_ime()
                            self.active = false
                            self.text = nil
                            self.typing_player = nil
                            chat_reset(self)
                            chat_owner = nil
                        end
                    end)
                end
                chat_prepared[self] = nil
                return original(self, ...)
            end)
            wrap("TextChat", "update", function(original, self, ...)
                if ime_ok() then
                    pcall(function()
                        if not chat_prepared[self] then chat_prepare(self) end
                        if self.active then chat_cursor(self) end
                    end)
                end
                return original(self, ...)
            end)
        end

        -- 2026-11-18 V0.96 换弹不滑（用户要求：冲刺里换弹会往前滑走，做成开关）。
        -- 原因（character_substate_sprint.lua on_enter）：冲刺子状态给 mover 开 lock_direction（只能朝脸跑）和
        --   constant_movement（不推杆也照脸的方向走）。从冲刺进换弹时子状态还是冲刺，这两样一直开着，换弹时转身又乘
        --   turn_speed_reload 变慢，所以松杆、往别处推都会先往前冲一段。
        -- 做法：开关开着时，在换弹状态里只要子状态是冲刺就把这两样关掉（每帧看 mover 实际状态，冲刺子状态重进时又开的也再关）；
        --   离开换弹时子状态还是冲刺就原样打开，交给下一个状态（和原版一样）。只动自己控制的人。
        do
            local released = {} -- unit -> true：这次换弹里我们关过
            wrap("CharacterStateReload", "update", function(original, unit, data, dt, sm)
                local res = {original(unit, data, dt, sm)}
                if enabled("noslide") then
                    pcall(function()
                        local st = data.state
                        local ms = st.mover_state
                        if st.new_state == nil and st.current_substate == CharacterSubstateSprint
                                and type(ms) == "table" and (ms.lock_direction or ms.constant_movement)
                                and EntityAux.owned(unit) then
                            EntityAux.queue_command_master(unit, "mover", "lock_direction", false)
                            EntityAux.queue_command_master(unit, "mover", "constant_movement", false)
                            released[unit] = true
                        end
                    end)
                end
                return unpack(res)
            end)
            wrap("CharacterStateReload", "on_exit", function(original, unit, data, new_state, sm)
                if released[unit] then
                    released[unit] = nil
                    pcall(function()
                        if data.state.current_substate == CharacterSubstateSprint then
                            EntityAux.queue_command_master(unit, "mover", "lock_direction", true)
                            EntityAux.queue_command_master(unit, "mover", "constant_movement", true)
                        end
                    end)
                end
                return original(unit, data, new_state, sm)
            end)
        end


    end

    local function safe_install()
        local ok, err = pcall(install_hooks)
        if not ok and rawget(_G, "HellBoxLog") then HellBoxLog("hellbox_qol", err) end
    end
    pcall(read_options)
    safe_install()
    if WorldManager and WorldManager.update then
        local original = WorldManager.update
        local next_check = 0
        WorldManager.update = function(self, ...)
            local now = Application and Application.time_since_launch and Application.time_since_launch() or os.clock()
            if now >= next_check then
                next_check = now + 0.5
                pcall(read_options)
                safe_install()
            end
            return original(self, ...)
        end
    end
end
