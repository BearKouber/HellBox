-- [host loadout menu] 房主配装的选装备界面画法（2026-11-18 V0.97，HD1-033）。由 build.py 追加到 character_state_machine 末尾，
-- 在 host_loadout.lua 后面。
--
-- 用户定：配装每一格「固定 / 自由 / 随机」；固定格照训练场那样显示锁，随机格照游戏随机配装那样显示 ???。
-- 原版 MenuScreenLoadout.draw_menu 只会「整套随机」（random_loadout）和「整个界面锁住」（is_proving_ground_trial），
-- 所以这里一字不差照抄原版 draw_menu（mod/lua_src/lua__menu__menu_screen_loadout.lua 第 941～1357 行），只改了 6 处判断：
--   天赋 / 主武器 / 每个战备格的「画 ???」改成 hb_rand（这一格随机，或整套随机且这一格不是固定）；
--   这三处「画锁」加上 hb_lock（这一格固定）。别的一行没动。
-- 只在有房主规则、又不是训练场的时候用这份（host_loadout.lua 的 hook_draw），否则走原版。
do
	local G = HellBoxHostLoadout or {}

	HellBoxHostLoadout = G

	-- 原版文件开头的常量（menu_screen_loadout.lua 第 6～13 行）
	local var_0_2 = 1
	local var_0_3 = 2
	local var_0_4 = 3
	local var_0_5 = 4
	local var_0_6 = 1
	local var_0_7 = 2

	local function hb_mode(e)
		return type(G.slot_mode) == "function" and G.slot_mode(e) or nil
	end

	local function hb_rand(self, m, e)
		local mode = hb_mode(e)

		if mode == "random" then
			return true
		elseif mode == "fixed" then
			return false
		end

		return m.random_loadout
	end

	local function hb_lock(self, e)
		return hb_mode(e) == "fixed"
	end

	G.draw_menu = function(arg_6_0, arg_6_1, arg_6_2, arg_6_3, arg_6_4, arg_6_5, arg_6_6, arg_6_7, arg_6_8, arg_6_9, arg_6_10)
		arg_6_4:set_clip_region({
			10,
			100,
			arg_6_5 - 20,
			2000
		})
		arg_6_4:set_current_font("body_large")

		local var_6_0 = arg_6_10:get("index")
		local var_6_1 = arg_6_0.parent.players[var_6_0].pad_number
		local var_6_2 = arg_6_4.ui_scale

		if not arg_6_8.submenu then
			local var_6_3 = false
			local var_6_4 = false
			local var_6_5 = false

			for iter_6_0, iter_6_1 in ipairs(arg_6_8.new_unlocks) do
				if string.find(iter_6_1, "perk_") then
					var_6_3 = true
				elseif string.find(iter_6_1, "weapon_") then
					var_6_4 = true
				elseif string.find(iter_6_1, "stratagem_") then
					var_6_5 = true
				end
			end

			local var_6_6 = Vector3(-4, -2, 0)

			arg_6_2:set_clip_region()
			arg_6_2:set_current_font("body_large")
			arg_6_2:set_ignore_size_scale(true)

			local var_6_7, var_6_8, var_6_9 = arg_6_2:get_text_extents(tostring(arg_6_9.level))

			arg_6_2:set_ignore_size_scale(false)
			arg_6_2:text(tostring(arg_6_9.level), Vector3(2, arg_6_6 - var_6_8 - 6, arg_6_7 + 100), Color(255, 240, 175, 80))

			local var_6_10 = LocalizationManager:string(arg_6_9.title)

			arg_6_2:set_ignore_size_scale(true)

			local var_6_11 = arg_6_2:get_text_box_strings(var_6_10, 210)

			arg_6_2:set_ignore_size_scale(false)

			local var_6_12 = 0

			for iter_6_2, iter_6_3 in ipairs(var_6_11) do
				arg_6_2:text(iter_6_3, Vector3(2 + var_6_7, arg_6_6 - var_6_8 - 6 + var_6_12, arg_6_7 + 100))

				var_6_12 = var_6_12 - 16
			end

			local var_6_13 = 215

			arg_6_2:image("loadout_skull_01", Vector3(0, arg_6_6 - 140, arg_6_7 - 1), Vector2(232, 120), nil, Vector2(0, 0), Vector2(-1, 1))

			local var_6_14 = arg_6_8.loadout_menu
			local var_6_15
			local var_6_16
			local var_6_17
			local var_6_18 = Vector2(45, 40)
			local var_6_19 = arg_6_6 - 60
			local var_6_20 = LocalizationManager:string("loadout_favorites_title")

			arg_6_2:set_current_font("body_large")
			arg_6_2:text(var_6_20, Vector3(10, var_6_19, arg_6_7 + 11), Color(255, 178, 178, 178))

			local var_6_21 = var_6_19 - 50
			local var_6_22 = arg_6_5 - 235
			local var_6_23 = 60

			if arg_6_0.is_proving_ground_trial then
				arg_6_2:image("listbox_01", Vector3(5, var_6_21 - 5, arg_6_7 + 15), Vector2(arg_6_5 - 10, 51), Color(160, 255, 255, 255))
			else
				arg_6_2:image("listbox_01", Vector3(5, var_6_21 - 5, arg_6_7), Vector2(arg_6_5 - 10, 51), Color(160, 255, 255, 255))
			end

			local var_6_24 = Vector3(var_6_22, var_6_21, arg_6_7 + 11)

			if arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_24, var_6_18, var_6_1) then
				arg_6_8.loadout_hover_index_cursor = var_0_2
				var_6_16 = var_6_24
			end

			local var_6_25 = "loadout_fav_closed_01"

			if not arg_6_0.is_proving_ground_trial and arg_6_8.loadout_index == var_0_2 then
				var_6_17 = var_6_24
				var_6_25 = "loadout_fav_open_01"
			end

			arg_6_2:image(var_6_25, var_6_24, var_6_18, Color(255, 255, 255, 255))

			local var_6_26 = var_6_22 + var_6_23
			local var_6_27 = Vector3(var_6_26, var_6_21, arg_6_7 + 12)

			if arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_27, var_6_18, var_6_1) then
				arg_6_8.loadout_hover_index_cursor = var_0_3
				var_6_16 = var_6_27
			end

			local var_6_28 = "loadout_fav_closed_02"

			if arg_6_8.loadout_index == var_0_3 then
				var_6_17 = var_6_27
				var_6_28 = "loadout_fav_open_02"
			end

			arg_6_2:image(var_6_28, var_6_27, var_6_18, Color(255, 255, 255, 255))

			local var_6_29 = var_6_26 + var_6_23
			local var_6_30 = Vector3(var_6_29, var_6_21, arg_6_7 + 13)

			if arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_30, var_6_18, var_6_1) then
				arg_6_8.loadout_hover_index_cursor = var_0_4
				var_6_16 = var_6_30
			end

			local var_6_31 = "loadout_fav_closed_03"

			if arg_6_8.loadout_index == var_0_4 then
				var_6_17 = var_6_30
				var_6_31 = "loadout_fav_open_03"
			end

			arg_6_2:image(var_6_31, var_6_30, var_6_18, Color(255, 255, 255, 255))

			local var_6_32 = var_6_29 + var_6_23
			local var_6_33 = Vector3(var_6_32, var_6_21, arg_6_7 + 10)

			if arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_33, var_6_18, var_6_1) then
				arg_6_8.loadout_hover_index_cursor = var_0_5
				var_6_16 = var_6_33
			end

			local var_6_34 = "loadout_random_unselected"

			if arg_6_8.loadout_index == var_0_5 then
				var_6_17 = var_6_33
				var_6_34 = "loadout_random_selected"
			end

			arg_6_2:image(var_6_34, var_6_33, var_6_18, Color(255, 255, 255, 255))

			local var_6_35 = arg_6_8.loadout_menu[var_0_6].item
			local var_6_36 = LocalizationManager:string("loadout_perk_title")
			local var_6_37 = LocalizationManager:string(var_6_35.name)
			local var_6_38 = var_6_35.icon
			local var_6_39 = Vector2(unpack(arg_6_0.perk_icon_size))
			local var_6_40 = var_6_21 - 25

			arg_6_2:set_current_font("body_large")

			local var_6_41 = FontSettings.fonts.body_large.font_size

			arg_6_2:text(var_6_36, Vector3(10, var_6_40, arg_6_7 + 11), Color(255, 178, 178, 178))

			if var_6_3 and not arg_6_0.is_proving_ground_trial then
				arg_6_2:image("icon_new", Vector3(arg_6_5 - 16, var_6_40, arg_6_7 + 11) + var_6_6, Vector2(16, 16), Color(255, 255, 255, 255))
			end

			local var_6_42 = Vector3(5, var_6_40 - 95, arg_6_7)
			local var_6_43 = Vector2(arg_6_5 - 10, 90)

			if hb_rand(arg_6_0, arg_6_8, arg_6_8.loadout_menu[var_0_6]) then
				arg_6_2:image("listbox_01", Vector3(5, var_6_40 - 95, arg_6_7), Vector2(arg_6_5 - 10, 90), Color(120, 255, 255, 255))
				arg_6_2:image("loadout_random_primary", Vector3(arg_6_5 / 2 - 80, var_6_40 - 85, arg_6_7 + 1), Vector2(160, 56))
				arg_6_0:draw_selection_scroll_hd_gui(arg_6_4, arg_6_7 + 2, Vector3(10, var_6_40 - 25, 0), LocalizationManager:string("random_loadout"), (arg_6_5 - 30) * var_6_2, arg_6_8.current_selection_index == var_0_6, arg_6_1)
			else
				arg_6_2:image(var_6_38, Vector3(arg_6_5 / 2 - 120, var_6_40 - 90, arg_6_7 + 1), var_6_39)
				arg_6_2:image("listbox_01", Vector3(5, var_6_40 - 95, arg_6_7), Vector2(arg_6_5 - 10, 90), Color(120, 255, 255, 255))
				arg_6_0:draw_selection_scroll_hd_gui(arg_6_4, arg_6_7 + 2, Vector3(10, var_6_40 - 25, 0), var_6_37, (arg_6_5 - 30) * var_6_2, arg_6_8.current_selection_index == var_0_6, arg_6_1)
			end

			if arg_6_0.is_proving_ground_trial or hb_lock(arg_6_0, arg_6_8.loadout_menu[var_0_6]) then
				arg_6_2:image("icon_lock_big", Vector3(var_6_13, var_6_40 - 30, arg_6_7 + 11), Vector2(30, 30), Color(255, 255, 255, 255))
				arg_6_2:image("listbox_01", Vector3(5, var_6_40 - 95, arg_6_7 + 10), Vector2(arg_6_5 - 10, 90), Color(120, 255, 255, 255))
			end

			if arg_6_8.current_selection_index == var_0_6 then
				var_6_15 = var_6_42
			end

			if not arg_6_0.is_proving_ground_trial and arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_42, var_6_43, var_6_1) then
				arg_6_8.current_selection_index_cursor = var_0_6
			end

			local var_6_44 = LocalizationManager:string("loadout_primary_weapon_title")
			local var_6_45 = arg_6_8.loadout_menu[var_0_7].item
			local var_6_46
			local var_6_47
			local var_6_48

			if var_6_45 then
				var_6_46 = arg_6_8.item_upgrades[var_6_45.name] or arg_6_8.loadout_menu[var_0_7].upgrade_value or 0
				var_6_47 = LocalizationManager:string(var_6_45.name)
				var_6_48 = var_6_45.icon
			else
				var_6_46 = 0
				var_6_47 = LocalizationManager:string("no_primary")
			end

			local var_6_49 = Vector2(unpack(arg_6_0.primary_weapon_icon_size))
			local var_6_50 = Vector2(unpack(arg_6_0.upgrade_icon_size))
			local var_6_51 = var_6_40 - 115

			arg_6_2:set_current_font("body_large")
			arg_6_2:text(var_6_44, Vector3(10, var_6_51, arg_6_7 + 11), Color(255, 178, 178, 178))

			if var_6_4 and not arg_6_0.is_proving_ground_trial then
				arg_6_2:image("icon_new", Vector3(arg_6_5 - 16, var_6_51, arg_6_7 + 11) + var_6_6, Vector2(16, 16), Color(255, 255, 255, 255))
			end

			local var_6_52 = Vector3(5, var_6_51 - 95, arg_6_7)
			local var_6_53 = Vector2(arg_6_5 - 10, 90)

			if hb_rand(arg_6_0, arg_6_8, arg_6_8.loadout_menu[var_0_7]) then
				arg_6_2:image("listbox_01", Vector3(5, var_6_51 - 95, arg_6_7), Vector2(arg_6_5 - 10, 90), Color(120, 255, 255, 255))
				arg_6_2:image("loadout_random_primary", Vector3(arg_6_5 / 2 - 80, var_6_51 - 90, arg_6_7 + 1), Vector2(160, 56))
				arg_6_0:draw_selection_scroll_hd_gui(arg_6_4, arg_6_7 + 2, Vector3(10, var_6_51 - 25, 0), LocalizationManager:string("random_loadout"), (arg_6_5 - 30) * var_6_2, arg_6_8.current_selection_index == var_0_7, arg_6_1)
			else
				arg_6_2:image("listbox_01", var_6_52, var_6_53, Color(120, 255, 255, 255))

				if var_6_48 then
					arg_6_2:image(var_6_48, Vector3(arg_6_5 / 2 - var_6_49.x / 2 - var_6_50.x, var_6_51 - 90, arg_6_7 + 1), var_6_49)
				end

				if var_6_45 and var_6_45.upgrades then
					for iter_6_4, iter_6_5 in ipairs(var_6_45.upgrades) do
						if BitAux.is_bit_set(var_6_46, iter_6_4) then
							arg_6_2:image(iter_6_5.upgrade_icon, Vector3(arg_6_5 - var_6_50.x - 10 - (iter_6_4 - 1) * (var_6_50.x + 2), var_6_51 - 90, arg_6_7 + 1), var_6_50)
						else
							arg_6_2:image("weapon_upgrade_empty_slot", Vector3(arg_6_5 - var_6_50.x - 10 - (iter_6_4 - 1) * (var_6_50.x + 2), var_6_51 - 90, arg_6_7 + 1), var_6_50)
						end
					end
				end

				arg_6_0:draw_selection_scroll_hd_gui(arg_6_4, arg_6_7 + 2, Vector3(10, var_6_51 - 25, 0), var_6_47, (arg_6_5 - 30) * var_6_2, arg_6_8.current_selection_index == var_0_7, arg_6_1)
			end

			if arg_6_0.is_proving_ground_trial or hb_lock(arg_6_0, arg_6_8.loadout_menu[var_0_7]) then
				arg_6_2:image("icon_lock_big", Vector3(var_6_13, var_6_51 - 30, arg_6_7 + 11), Vector2(30, 30), Color(255, 255, 255, 255))
				arg_6_2:image("listbox_01", Vector3(5, var_6_51 - 95, arg_6_7 + 10), Vector2(arg_6_5 - 10, 90), Color(120, 255, 255, 255))
			end

			if arg_6_8.current_selection_index == var_0_7 then
				var_6_15 = var_6_52
			end

			if not arg_6_0.is_proving_ground_trial and arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_52, var_6_53, var_6_1) then
				arg_6_8.current_selection_index_cursor = var_0_7
			end

			local var_6_54 = LocalizationManager:string("loadout_stratagems_title")
			local var_6_55 = var_6_51 - 115
			local var_6_56 = 10
			local var_6_57 = 10

			arg_6_2:set_current_font("body_large")
			arg_6_2:text(var_6_54, Vector3(10, var_6_55, arg_6_7 + 11), Color(255, 178, 178, 178))

			if var_6_5 and not arg_6_0.is_proving_ground_trial then
				arg_6_2:image("icon_new", Vector3(arg_6_5 - 16, var_6_55, arg_6_7 + 11) + var_6_6, Vector2(16, 16), Color(255, 255, 255, 255))
			end

			for iter_6_6, iter_6_7 in ipairs(var_6_14) do
				if iter_6_7.type == "stratagems" then
					local var_6_58 = iter_6_7.item
					local var_6_59

					if var_6_58 then
						var_6_59 = arg_6_8.item_upgrades[var_6_58.name] or iter_6_7.upgrade_value or 0
					else
						var_6_59 = 0
					end

					local var_6_60 = Vector2(unpack(arg_6_0.stratagem_icon_size))

					if hb_rand(arg_6_0, arg_6_8, iter_6_7) then
						arg_6_2:image("loadout_random", Vector3(var_6_57, var_6_55 - 60, arg_6_7 + 10), var_6_60)
					elseif var_6_58 then
						MenuScreenBase:draw_stratagem_icon(nil, arg_6_2, var_6_58, var_6_59, Vector3(var_6_57, var_6_55 - 60, arg_6_7 + 10), var_6_60)
					end

					if arg_6_0.is_proving_ground_trial or hb_lock(arg_6_0, iter_6_7) then
						arg_6_2:image("listbox_01", Vector3(var_6_57, var_6_55 - 60, arg_6_7 + 11), var_6_60, Color(125, 255, 255, 255))
						arg_6_2:image("icon_lock_small", Vector3(var_6_57 + 31, var_6_55 - 29, arg_6_7 + 12), Vector2(20, 20), Color(255, 255, 255, 255))
					end

					local var_6_61 = Vector3(var_6_57 - 4, var_6_55 - 64, arg_6_7)
					local var_6_62 = Vector2(58, 58)

					if arg_6_8.current_selection_index == iter_6_6 then
						var_6_15 = var_6_61
					end

					if not arg_6_0.is_proving_ground_trial and arg_6_8.is_owned and arg_6_8.enabled and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_61, var_6_62, var_6_1) then
						arg_6_8.current_selection_index_cursor = iter_6_6
					end

					var_6_57 = var_6_57 + var_6_60.x + var_6_56
				end
			end

			arg_6_2:image("listbox_01", Vector3(5, var_6_55 - 65, arg_6_7), Vector2(arg_6_5 - 10, 60), Color(120, 255, 255, 255))
			arg_6_2:set_current_font("body_large")

			if arg_6_8.enabled then
				local var_6_63

				if arg_6_10:owned() then
					var_6_63 = LocalizationManager:string("loadout_confirm_loadout")
				else
					var_6_63 = LocalizationManager:string("loadout_client_loadout_in_progress")
				end

				local var_6_64 = arg_6_2:get_text_extents(var_6_63, nil, nil, true)

				arg_6_2:text(var_6_63, Vector3(arg_6_5 / 2 - var_6_64 / 2, var_6_55 - 92, arg_6_7 + 100))
			else
				local var_6_65

				if arg_6_10:owned() then
					var_6_65 = LocalizationManager:string("loadout_change_loadout")
				else
					var_6_65 = LocalizationManager:string("loadout_client_loadout_done")
				end

				local var_6_66 = arg_6_2:get_text_extents(var_6_65, nil, nil, true)

				arg_6_2:text(var_6_65, Vector3(arg_6_5 / 2 - var_6_66 / 2, var_6_55 - 92, arg_6_7 + 100))
				arg_6_2:rect(Vector3(0, 0, arg_6_7 + 100), Vector2(arg_6_5, arg_6_6 + 30), Color(150, 0, 0, 0))
			end

			arg_6_2:image("listbox_01", Vector3(5, var_6_55 - 100, arg_6_7), Vector2(arg_6_5 - 10, 30), Color(120, 255, 255, 255))
			arg_6_2:rect(Vector3(0, 0, arg_6_7 + 91), Vector2(arg_6_5, arg_6_6 + 20), Color(100 * arg_6_8.confirm_loadout_blink, 200, 200, 200))

			local var_6_67 = Vector3(5, var_6_55 - 100, arg_6_7)
			local var_6_68 = Vector2(arg_6_5 - 10, 30)
			local var_6_69 = var_6_67

			if arg_6_8.current_selection_index == #var_6_14 then
				var_6_15 = var_6_67
			end

			if arg_6_8.is_owned and MenuScreenBase.is_box_selected_by_cursor(arg_6_0, arg_6_2, var_6_67, var_6_68, var_6_1) then
				arg_6_8.current_selection_index_cursor = #var_6_14
			end

			local var_6_70 = arg_6_0.parent.selection_blink
			local var_6_71 = arg_6_0.parent.selection_outline_blink
			local var_6_72 = var_6_14[arg_6_8.current_selection_index or 1]

			if var_6_72 == nil then
				return
			end

			local var_6_73
			local var_6_74
			local var_6_75

			if var_6_72.type == "perks" then
				var_6_73 = Vector2(arg_6_5 - 10, 90)
				var_6_74 = "selectionbox_01"
				var_6_75 = Color(200 - 80 * var_6_70, 255, 255, 255)
			elseif var_6_72.type == "primary_weapon" then
				var_6_73 = Vector2(arg_6_5 - 10, 90)
				var_6_74 = "selectionbox_01"
				var_6_75 = Color(200 - 80 * var_6_70, 255, 255, 255)
			elseif var_6_72.type == "stratagems" then
				var_6_73 = Vector2(58, 58)
				var_6_74 = "selectionbox_outline_01"
				var_6_75 = Color(255 - 120 * var_6_71, 255, 255, 255)
			elseif var_6_72.type == "button" then
				var_6_73 = Vector2(arg_6_5 - 10, 30)
				var_6_74 = "selectionbox_01"
				var_6_75 = Color(200 - 80 * var_6_70, 255, 255, 255)
			elseif var_6_72.type == "radio_button" then
				var_6_73 = Vector2(25, 25)
				var_6_74 = "selectionbox_outline_01"
				var_6_75 = Color(255 - 120 * var_6_71, 255, 255, 255)
			end

			if not arg_6_0.is_proving_ground_trial then
				arg_6_2:image(var_6_74, var_6_15, var_6_73, var_6_75)
				arg_6_2:rect(var_6_15 + Vector3(0, 0, 100), var_6_73, Color(200 * arg_6_8.confirm_selection_blink, 200, 200, 200))

				local var_6_76 = var_6_17 - Vector2(6, 4, 2)
				local var_6_77 = var_6_18 + Vector2(11, 9)

				arg_6_2:image("selectionbox_outline_01", var_6_76, var_6_77, Color(255 - 120 * var_6_71, 255, 255, 255))
				arg_6_2:rect(var_6_76 + Vector3(0, 0, 100), var_6_77, Color(50, 200, 200, 200))

				if arg_6_8.loadout_hover_index_cursor and var_6_16 then
					local var_6_78 = var_6_16 + Vector3(0, 0, 100)
					local var_6_79 = var_6_18

					arg_6_2:image("selectionbox_outline_01", var_6_78, var_6_79, Color(255 - 120 * var_6_71, 255, 255, 255))
					arg_6_2:rect(var_6_78, var_6_79, Color(50, 200, 200, 200))
				end
			else
				arg_6_2:image("selectionbox_01", Vector3(5, 5, 999), Vector3(238, 30, 0), Color(200 - 80 * var_6_70, 255, 255, 255))
				arg_6_2:rect(Vector3(5, 5, 1000), Vector3(238, 30, 0), Color(200 * arg_6_8.confirm_selection_blink, 200, 200, 200))
			end
		elseif arg_6_8.submenu == "perks" then
			arg_6_0:draw_perks(arg_6_1, arg_6_2, arg_6_3, arg_6_5, arg_6_6, arg_6_7, arg_6_8, var_6_1)
		elseif arg_6_8.submenu == "primary_weapon" then
			arg_6_0:draw_primary_weapon(arg_6_1, arg_6_2, arg_6_3, arg_6_5, arg_6_6, arg_6_7, arg_6_8, var_6_1)
		elseif arg_6_8.submenu == "stratagems" then
			arg_6_0:draw_stratagems(arg_6_1, arg_6_2, arg_6_3, arg_6_5, arg_6_6, arg_6_7, arg_6_8, var_6_1)
		end

		arg_6_0:validate_scroll()
	end
end
