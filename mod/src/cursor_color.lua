-- [cursor_color] 2026-11-03：瞄准指针 mod 的脚本部分。
-- 松开瞄准后，系统指针藏起来，input_component 自己画一个小十字飘回角色：
--     Gui.bitmap_uv(cursor_gui, "cursor_game", uv0, uv1, pos, size, Color(255 * t * t, 255, 255, 255))
-- 原版白色、边飞边变淡。这里把它换成指针 mod 选的颜色和固定不透明度（大小照旧边飞边缩）。
-- 设置由 build.py 从 cursor_settings.json 填进来："r,g,b,a"，空 = 原版。
do
	local setting = "@CURSOR_COLOR@"
	local r, g, b, a = string.match(setting, "^(%d+),(%d+),(%d+),(%d+)$")

	if r and type(Gui) == "table" and type(Gui.bitmap_uv) == "function" and not rawget(_G, "CursorColorModHooked") then
		CursorColorModHooked = true
		r, g, b, a = tonumber(r), tonumber(g), tonumber(b), tonumber(a)

		local orig = Gui.bitmap_uv

		Gui.bitmap_uv = function(gui, material, ...)
			if material == "cursor_game" then
				local uv0, uv1, pos, size = ...

				return orig(gui, material, uv0, uv1, pos, size, Color(a, r, g, b))
			end

			return orig(gui, material, ...)
		end
	end
end
