-- [hud name guard] 人不在了，头顶名字别留在屏幕上（2026-11-26 用户：「上飞机之后名字会在飞船上显示,人走了,三个名字印在飞船上面了」）。
-- 由 build.py 追加到 character_state_machine 末尾。
--
-- 原版（lua/hud/hud.lua）：头顶名字是「保留型」文字（create_text 一次、之后每帧 update_text 挪位置，destroy_text 才消失）。
--   pre_update_and_draw_hud 只在人物 Unit.alive 时更新屏幕位置 screen_pos_immediate；人物被删掉（上撤离机等）以后
--   player_go 里的 avatar_unit 还是那个死句柄，update_and_draw_hud 用缓存的血量状态（没死）照样调 draw_player_name_in_world，
--   名字就一直按最后那个屏幕位置画。镜头跟着撤离机走，看着就像名字印在飞机上。
-- 这里：draw_player_name_in_world 的人物已经不存在时，把这个人的头顶名字删掉、这一帧不画（和原版人死了时的处理一样）。
--   状态栏面板不受影响。全部 pcall 包着，出错就照原版画。
do
	local G = HellBoxHudNameGuard or {}

	HellBoxHudNameGuard = G

	local KEY = "in_world_name"

	local function gone(unit)
		local ok, alive = pcall(Unit.alive, unit)

		return ok and not alive
	end

	local function install()
		local hud = rawget(_G, "Hud")

		if type(hud) ~= "table" or rawget(hud, "_hb_name_guard") or type(hud.draw_player_name_in_world) ~= "function" then
			return type(hud) == "table" and rawget(hud, "_hb_name_guard") ~= nil
		end

		local orig = hud.draw_player_name_in_world

		-- 参数照原版：draw_player_name_in_world(self, dt, hud_info, player, unit, health, shield, character, name, ...)
		hud.draw_player_name_in_world = function(self, dt, info, player, unit, ...)
			if unit ~= nil and gone(unit) then
				pcall(function()
					local texts = info.gui_objects.texts

					if texts[KEY] then
						self.hd_gui:destroy_text(texts[KEY])

						texts[KEY] = nil
					end
				end)

				return
			end

			return orig(self, dt, info, player, unit, ...)
		end
		hud._hb_name_guard = true

		return true
	end

	if not pcall(install) or not (rawget(_G, "Hud") and rawget(Hud, "_hb_name_guard")) then
		local wm = rawget(_G, "WorldManager")

		if type(wm) == "table" and type(wm.update) == "function" and not G.waiting then
			G.waiting = true

			local original = wm.update

			wm.update = function(self, ...)
				if G.waiting then
					local ok, done = pcall(install)

					if ok and done then
						G.waiting = false
					end
				end

				return original(self, ...)
			end
		end
	end
end
