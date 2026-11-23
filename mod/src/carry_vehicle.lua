-- [box mod] 搬箱子时对着载具按 E 可以带箱子上车。
-- 2026-11-19：以前是整份改过的原版搬箱子脚本；现在原版脚本从玩家自己的游戏里原样加载（build.py 的 vanilla:），
-- 这里接在后面，把原版的三个函数包一层，效果和以前逐行改的一样：
--   on_enter：原版会关掉互动器 → 开着带箱子上车时不让它关（搬运中还能识别到旁边的载具座位）
--   update  ：座位握手完成后切到互动状态（上车动画），等待握手时原地不动；面前是座位（且不在传送带旁）按 E 走上车，不丢箱子
--   on_exit ：因为上车而离开搬运状态时，不丢箱子、不重新打开互动器（交给上车流程）
-- false：下车后箱子“卡在手上”（同原 bug：不进入搬运状态，可用主武器、可冲刺），
--        只能在交付点（传送带）旁按 E 放下，见 box_mod_stuck_drop；
-- true ：下车后回到正常搬运状态（E 丢箱子）。
local box_mod_restore_carry_after_exit = false

-- 2026-11-14 V0.91：带箱子上车热切换。这个脚本一直装着，开关看全局 HellBoxCarryOn
-- （hellbox_qol.lua 每秒从 HellBox 写的 options.txt 读；没读到 = 开）。关着时每处都照原版走。
-- 2026-11-23 V1.07 联机限制：当客机时只在有 MOD 的房间生效（hellbox_room_gate.lua 的 HellBoxRoomGate.ok）
local function box_mod_on()
	if HellBoxCarryOn == false then
		return false
	end

	local gate = rawget(_G, "HellBoxRoomGate")

	return not (type(gate) == "table" and type(gate.ok) == "function") or gate.ok()
end

local function box_mod_is_seat(unit)
	return Unit.alive(unit) and EntityAux.has_component(unit, "seat")
end

-- 箱子在交付点（传送带）附近时，箱子自己会显示 E 提示，状态里有 near_drop_off
local function box_mod_near_drop_off(box)
	local var_0_0 = Unit.alive(box) and EntityAux.state(box, "objective_carry_object")

	return var_0_0 and var_0_0.near_drop_off and true or false
end

-- 卡手状态（箱子在身上但不在搬运状态）按 E：
-- 在传送带旁（有 E 提示）→ 放下箱子交付；其他地方 → 照常互动（如再次上车），箱子不会掉。
local function box_mod_stuck_drop(arg_0_0, arg_0_1, arg_0_3)
	local var_0_0 = arg_0_1.state

	if not var_0_0.input.interact or not Unit.alive(var_0_0.current_carry_unit) then
		return false
	end

	if var_0_0.interact or var_0_0.interactor_state.busy or Unit.alive(var_0_0.current_seat_unit) then
		return false
	end

	if box_mod_near_drop_off(var_0_0.current_carry_unit) then
		arg_0_3:queue_command_master(arg_0_0, "character", "drop_carry")

		return true
	end

	return false
end

-- 包装所有会响应 E 的普通状态（站立、走、冲刺、瞄准、瞄准走、换弹）
CharacterStateCarry.box_mod_orig = CharacterStateCarry.box_mod_orig or {}

local function box_mod_wrap(state, is_idle)
	if not state then
		return
	end

	local orig = CharacterStateCarry.box_mod_orig[state] or state.update

	CharacterStateCarry.box_mod_orig[state] = orig

	function state.update(arg_0_0, arg_0_1, arg_0_2, arg_0_3)
		local var_0_0 = arg_0_1.state

		if not box_mod_on() and not var_0_0.box_mod_carry_in_seat then
			return orig(arg_0_0, arg_0_1, arg_0_2, arg_0_3)
		end

		if is_idle and var_0_0.box_mod_carry_in_seat and not var_0_0.current_seat_unit then
			var_0_0.box_mod_carry_in_seat = nil

			if box_mod_restore_carry_after_exit and Unit.alive(var_0_0.current_carry_unit) then
				CharacterStateMachine.change_state(arg_0_0, arg_0_1, CharacterStateCarry)

				return
			end
		end

		if box_mod_stuck_drop(arg_0_0, arg_0_1, arg_0_3) then
			return
		end

		return orig(arg_0_0, arg_0_1, arg_0_2, arg_0_3)
	end
end

box_mod_wrap(CharacterStateIdle, true)
box_mod_wrap(CharacterStateWalk)
box_mod_wrap(CharacterStateSprint)
box_mod_wrap(CharacterStateAim)
box_mod_wrap(CharacterStateAimWalk)
box_mod_wrap(CharacterStateReload)

-- ---------------------------------------------------------------- 搬运状态本身（包原版的三个函数）
-- 上面的原版脚本每次加载都会重新定义这三个函数，所以这里每次都包刚定义的那份，不会包两层。

-- 跑 fn(...) 期间挡掉某些命令：EntityAux.queue_command_master(unit, comp, cmd, value) 里 skip(...) 为真的不发。
-- 原版函数是现查全局 EntityAux 的，临时换掉、跑完换回（出错也换回再报错）。
local function box_mod_without(skip, fn, ...)
	local queue = EntityAux.queue_command_master

	EntityAux.queue_command_master = function(a, b, c, d, ...)
		if skip(a, b, c, d) then
			return
		end

		return queue(a, b, c, d, ...)
	end

	local ok, err = pcall(fn, ...)

	EntityAux.queue_command_master = queue

	if not ok then
		error(err, 0)
	end
end

local box_mod_vanilla_enter = CharacterStateCarry.on_enter
local box_mod_vanilla_update = CharacterStateCarry.update
local box_mod_vanilla_exit = CharacterStateCarry.on_exit

-- 原版进搬运状态最后关掉互动器；开着带箱子上车时不关，这样搬运中还能识别到旁边的载具座位
function CharacterStateCarry.on_enter(arg_1_0, arg_1_1, arg_1_2, arg_1_3)
	if not box_mod_on() then
		return box_mod_vanilla_enter(arg_1_0, arg_1_1, arg_1_2, arg_1_3)
	end

	box_mod_without(function(unit, comp, cmd, value)
		return unit == arg_1_0 and comp == "interactor" and cmd == "set_enabled" and value == false
	end, box_mod_vanilla_enter, arg_1_0, arg_1_1, arg_1_2, arg_1_3)
end

-- 原版顺序：受伤 / 倒地检查 → 通讯 → 按 E 丢箱子……
-- 以前的改法：受伤检查后先看座位握手；通讯后、丢箱子前看「面前是座位」。这里照同样的顺序先做这两样，
-- 都没发生就整个交给原版（原版开头会再查一次受伤：前面查过没变，再查结果一样、也不改任何东西）。
function CharacterStateCarry.update(arg_2_0, arg_2_1, arg_2_2, arg_2_3)
	if not box_mod_on() then
		return box_mod_vanilla_update(arg_2_0, arg_2_1, arg_2_2, arg_2_3)
	end

	local var_2_0 = arg_2_1.state

	if arg_2_3:handle_health_status_change(arg_2_0, arg_2_1) then
		return
	end

	-- 座位握手完成后切到互动状态（上车动画），等待握手时原地不动
	if arg_2_3:handle_waiting_for_interact(arg_2_0, arg_2_1) then
		return
	end

	-- 面前是载具座位（且不在传送带旁）：走正常上车流程，而不是丢箱子（原版这一步在「箱子还在、没在看地图」那一支里）
	if Unit.alive(var_2_0.current_carry_unit) and not var_2_0.carry_is_map and var_2_0.input.interact and not var_2_0.is_dropping
		and box_mod_is_seat(var_2_0.interactor_state.interactable_unit) and not box_mod_near_drop_off(var_2_0.current_carry_unit) then
		arg_2_3:handle_communication(arg_2_0, arg_2_1, true)
		arg_2_3:handle_interact(arg_2_0, arg_2_1)

		return
	end

	return box_mod_vanilla_update(arg_2_0, arg_2_1, arg_2_2, arg_2_3)
end

-- 因为上车而离开搬运状态：箱子留在身上（原版会丢下并清掉 current_carry_unit），互动器保持被上车流程关闭（原版会打开）
function CharacterStateCarry.on_exit(arg_3_0, arg_3_1, arg_3_2, arg_3_3)
	local var_3_0 = arg_3_1.state
	local var_3_box = box_mod_on() and arg_3_2 == CharacterStateInteract and Unit.alive(var_3_0.current_seat_unit) and Unit.alive(var_3_0.current_carry_unit)

	if not var_3_box then
		return box_mod_vanilla_exit(arg_3_0, arg_3_1, arg_3_2, arg_3_3)
	end

	var_3_0.box_mod_carry_in_seat = true

	local carry = var_3_0.current_carry_unit
	-- 原版用 arg_3_3:queue_command_master(箱子, "objective_carry_object", "drop") 丢箱子：在这个对象上临时挡掉
	local own = rawget(arg_3_3, "queue_command_master")
	local queue = arg_3_3.queue_command_master

	arg_3_3.queue_command_master = function(self, unit, comp, cmd, ...)
		if unit == carry and comp == "objective_carry_object" and cmd == "drop" then
			return
		end

		return queue(self, unit, comp, cmd, ...)
	end

	local ok, err = pcall(box_mod_without, function(unit, comp, cmd, value)
		return unit == arg_3_0 and comp == "interactor" and cmd == "set_enabled" and value == true
	end, box_mod_vanilla_exit, arg_3_0, arg_3_1, arg_3_2, arg_3_3)

	arg_3_3.queue_command_master = own
	var_3_0.current_carry_unit = carry

	if not ok then
		error(err, 0)
	end
end
