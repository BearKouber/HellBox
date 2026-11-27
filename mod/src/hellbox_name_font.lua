-- [hellbox name font] 名字不乱码：字体里没有的字改用聊天字体画（2026-11-26 用户要，自己研究的做法，不借鉴别的 MOD）。
-- 用户：「长名字乱码，改为名字乱码，这个有时候会出现名字乱码，比如 hud 里面的或者是消息里面的，可能是使用字体的原因」
--
-- 原因（mod/glyphs.py 拆字体查的）：HUD 用的字体只收了游戏自己文字用到的字（简体中文版汉字 1842 个，英文版没有汉字），
--   名字里有字体没有的字就画成乱码；聊天框的 chat 字体有全部常用汉字、韩文、假名、俄文。
-- 做法：装 MOD 时把玩家游戏里每个字体（每种语言）有哪些字编进来（"@HELLBOX_GLYPHS@"）。游戏里 HdGui 画字 / 量字宽之前看一下：
--   这段字里有当前字体没有、chat 字体有的字，这一段就换成 chat 字体（字号不变）；字体里都有的照原样画，原版界面一个字都不变。
--   量字宽和画字用同一个判断，排版跟着对齐。两套画字都接：HdGui（任务里的 HUD、头顶名字、状态栏、消息提示）和
--   GuiDrawer（GuiManager 菜单：加载页、结算页、ESC 菜单、大厅；2026-11-26 用户实测这些还是「?」后补上）。
--   带按键图标（╦¬E¬）的文字不换（换了图标变成制表符，看着像 T）。
-- 开关是「显示」页「名字不乱码」（hop.txt 的 long_text，热生效；和半糖的长名字截断同一个开关）。
-- 全部 pcall 包着：哪一步不行就照原版画。
do
	local G = HellBoxNameFont or {}

	HellBoxNameFont = G

	local DATA = "@HELLBOX_GLYPHS@"
	local CHAT_FONT, CHAT_MATERIAL = "fonts/chat", "chat"
	-- 游戏按语言装哪一份字体（Boot.language → 资源里的语言号；拆包对出来的：1 有假名、2 繁体、4 韩文、8 俄文、0x4000000 简体）
	local LANG = { ja = 1, ch = 2, ko = 4, ru = 8, pl = 8, chs = 67108864 }

	local function log(text)
		if rawget(_G, "HellBoxLog") then
			pcall(HellBoxLog, "name_font", text)
		end
	end

	local function on()
		local hop = rawget(_G, "HellBoxHop")
		local cfg = hop and hop.config

		return type(DATA) == "table" and cfg ~= nil and cfg.long_text == "1"
	end

	local function parse(text)
		local out = {}

		for part in string.gmatch(text or "", "[^,]+") do
			local a, b = part:match("^(%x+)%-(%x+)$")

			if a then
				out[#out + 1] = { tonumber(a, 16), tonumber(b, 16) }
			else
				local c = tonumber(part, 16)

				if c then
					out[#out + 1] = { c, c }
				end
			end
		end

		return out
	end

	local function has(list, c)
		local lo, hi = 1, #list

		while lo <= hi do
			local mid = math.floor((lo + hi) / 2)
			local r = list[mid]

			if c < r[1] then
				hi = mid - 1
			elseif c > r[2] then
				lo = mid + 1
			else
				return true
			end
		end

		return false
	end

	local sets = {} -- 字体名 -> 区间表（只解当前语言那份）；false = 没数据
	local chat_set

	local function font_set(font)
		local s = sets[font]

		if s == nil then
			s = false

			local by_lang = type(DATA) == "table" and DATA[font]

			if by_lang then
				local boot = rawget(_G, "Boot")
				local lang = LANG[boot and boot.language or ""] or 0
				local text = by_lang[lang] or by_lang[0]

				if text then
					s = parse(text)
				end
			end

			sets[font] = s
		end

		return s
	end

	-- UTF-8 一个个码位；坏的字节序列返回 nil（交给原版）
	local function each_codepoint(text, fn)
		local i, n = 1, #text

		while i <= n do
			local b = string.byte(text, i)
			local c, len

			if b < 0x80 then
				c, len = b, 1
			elseif b >= 0xF0 then
				c, len = b % 0x08, 4
			elseif b >= 0xE0 then
				c, len = b % 0x10, 3
			elseif b >= 0xC0 then
				c, len = b % 0x20, 2
			else
				return false
			end

			if i + len - 1 > n then
				return false
			end

			for k = i + 1, i + len - 1 do
				c = c * 64 + string.byte(text, k) % 64
			end

			if fn(c) then
				return true
			end

			i = i + len
		end

		return false
	end

	local cache, cache_n = {}, 0 -- 字体名 .. "\0" .. 文字 -> 要不要换

	local function needs_chat(text, font)
		if type(text) ~= "string" or type(font) ~= "string" or font == CHAT_FONT or not string.find(text, "[\128-\255]") then
			return false
		end

		-- 按键图标：游戏写成「╦¬E¬」（制表符 U+2500～257F 当键帽、¬ 当标记），换了字体图标就变成真的制表符（看着像 T）。
		-- 带图标的这段一律照原版画（2026-11-26 用户实测：键盘捡东西提示 E 显示成 T）。
		if string.find(text, "\226[\148\149]") or string.find(text, "\194\172", 1, true) then
			return false
		end

		local key = font .. "\0" .. text
		local hit = cache[key]

		if hit ~= nil then
			return hit
		end

		local own = font_set(font)
		local result = false

		if own then
			chat_set = chat_set or parse(DATA[CHAT_FONT] and (DATA[CHAT_FONT][0] or select(2, next(DATA[CHAT_FONT]))))
			result = each_codepoint(text, function(c)
				return c >= 0x80 and not has(own, c) and has(chat_set, c)
			end)
		end

		if cache_n > 4000 then
			cache, cache_n = {}, 0
		end

		cache[key] = result
		cache_n = cache_n + 1

		return result
	end

	-- 这块 gui 能不能用 chat 字体的材质；带裁剪区的（滚动列表）把 chat 也加进裁剪，不然换了字体的那行不被裁
	local gui_ok = setmetatable({}, { __mode = "k" })

	local function chat_ready(self)
		local ok = gui_ok[self]

		if ok == nil then
			ok = false
			pcall(function()
				local m1 = self.gui and Gui.material(self.gui, CHAT_MATERIAL)
				local m2 = self.gui_retained and Gui.material(self.gui_retained, CHAT_MATERIAL)

				ok = m1 ~= nil and (self.gui_retained == nil or m2 ~= nil)
			end)

			if ok and type(self.clippable_materials) == "table" and next(self.clippable_materials) ~= nil
					and self.clippable_materials[CHAT_MATERIAL] == nil then
				self.clippable_materials[CHAT_MATERIAL] = 1

				local set_clip = self.set_clip_region or HdGui.set_clip_region

				if self.clip_region and type(set_clip) == "function" then
					pcall(set_clip, self, self.clip_region)
				end
			end

			gui_ok[self] = ok
		end

		return ok
	end

	local function current_font(self)
		return self.current_font and self.current_font.font
	end

	-- 包一个 HdGui 方法：text_at = 文字是第几个参数，font_at = 字体，material_at = 材质（没有就 nil）
	local function wrap(name, text_at, font_at, material_at)
		local original = HdGui[name]

		if type(original) ~= "function" then
			return false
		end

		HdGui[name] = function(self, ...)
			if on() then
				local args = { n = select("#", ...), ... }
				local swap = false

				pcall(function()
					local font = args[font_at] or current_font(self)

					swap = needs_chat(args[text_at], font) and chat_ready(self)
				end)

				if swap then
					args[font_at] = CHAT_FONT

					if material_at then
						args[material_at] = CHAT_MATERIAL
					end

					args.n = math.max(args.n, font_at, material_at or 0)

					return original(self, unpack(args, 1, args.n))
				end
			end

			return original(self, ...)
		end

		return true
	end

	-- ===== 菜单那套（GuiManager → GuiDrawer）：加载页、结算页、ESC 菜单、大厅这些 =====
	-- GuiDrawer 的画字 / 量字宽都带「字体类」（body / heading …），由 get_font_info(类, 字号).font 换成真字体。
	-- 要换时把类改成 "chat"；这块 drawer 没登记 chat 类就补登记（和原版飞船菜单 state_menu 登记的一样）。
	local drawer_ok = setmetatable({}, { __mode = "k" })

	local function drawer_ready(self)
		local ok = drawer_ok[self]

		if ok == nil then
			ok = false
			pcall(function()
				ok = self.gui ~= nil and Gui.material(self.gui, CHAT_MATERIAL) ~= nil
			end)

			if ok and type(self.fonts) == "table" and self.fonts.chat == nil then
				local chat = FontSettings and FontSettings.fonts and FontSettings.fonts.chat
				local size = chat and (chat.gm_font_size or chat.font_size) or 30

				ok = pcall(self.add_font_class, self, "chat", { { font = CHAT_FONT, material = CHAT_MATERIAL, size = size } })
			end

			drawer_ok[self] = ok
		end

		-- 有裁剪表（滚动列表）就把 chat 也加进去，不然换了字体的那行不被裁。复制一份，不动原版可能共用的表。
		local list = ok and self.clippable_materials

		if type(list) == "table" and #list > 0 then
			local has = false

			for _, m in ipairs(list) do
				if m == CHAT_MATERIAL then
					has = true

					break
				end
			end

			if not has then
				local copy = { unpack(list) }

				copy[#copy + 1] = CHAT_MATERIAL
				self.clippable_materials = copy
			end
		end

		return ok
	end

	local function drawer_swap(self, text, class, size)
		if type(class) ~= "string" or class == "chat" or type(text) ~= "string" or not string.find(text, "[\128-\255]") then
			return false
		end

		local swap = false

		pcall(function()
			local info = self:get_font_info(class, tonumber(size) or 20)

			swap = info ~= nil and needs_chat(text, info.font) and drawer_ready(self)
		end)

		return swap
	end

	-- 包一个 GuiDrawer 方法：text_at = 文字第几个参数，class_at = 字体类，size_at = 字号（都不含 self）
	local function wrap_drawer(name, text_at, class_at, size_at)
		local original = GuiDrawer[name]

		if type(original) ~= "function" then
			return false
		end

		GuiDrawer[name] = function(self, ...)
			if on() then
				local n = select("#", ...)
				local args = { ... }

				if drawer_swap(self, args[text_at], args[class_at], args[size_at]) then
					args[class_at] = "chat"

					return original(self, unpack(args, 1, math.max(n, class_at)))
				end
			end

			return original(self, ...)
		end

		return true
	end

	local function install_drawer()
		if G.installed_drawer or not rawget(_G, "GuiDrawer") then
			return
		end

		G.installed_drawer = true

		local done = {}

		-- 参数位置照原版 foundation/lua/gui/gui_drawer.lua（不含 self）
		for _, spec in ipairs({
			{ "draw_text", 1, 5, 3 }, -- draw_text(text, pos, size, color, class, scale)
			{ "draw_text_shadow", 1, 5, 3 }, -- draw_text_shadow(text, pos, size, color, class, scale, shadow_color, offset)
			{ "get_text_extents", 1, 3, 2 }, -- get_text_extents(text, size, class)
			{ "get_text_bounds", 1, 3, 2 }, -- get_text_bounds(text, size, class)
			{ "get_word_wrapped_text", 1, 2, 3 }, -- get_word_wrapped_text(text, class, size, ...)
		}) do
			if wrap_drawer(spec[1], spec[2], spec[3], spec[4]) then
				done[#done + 1] = spec[1]
			end
		end

		log("installed drawer: " .. table.concat(done, ","))
	end

	local function install()
		pcall(install_drawer)

		if G.installed or not rawget(_G, "HdGui") then
			return
		end

		G.installed = true

		local done = {}

		-- 参数位置照原版 lua/gui/hd_gui.lua（PC 那一支）：不含 self
		for _, spec in ipairs({
			{ "text", 1, 4, 6 }, -- text(text, pos, color, font, size, material)
			{ "create_text", 1, 4, 6 }, -- create_text(text, pos, color, font, size, material)
			{ "update_text", 2, 5, 7 }, -- update_text(id, text, pos, color, font, size, material)
			{ "get_text_extents", 1, 2, nil }, -- get_text_extents(text, font, size, ignore_scale)
			{ "get_text_box_strings", 1, 3, 5 }, -- get_text_box_strings(text, width, font, size, material)
			{ "text_box", 1, 5, 7 }, -- text_box(text, pos, width, color, font, size, material, align, bottom)
		}) do
			if wrap(spec[1], spec[2], spec[3], spec[4]) then
				done[#done + 1] = spec[1]
			end
		end

		log("installed: " .. table.concat(done, ",") .. (type(DATA) == "table" and "" or " (no glyph data)"))
	end

	pcall(install)

	if not (G.installed and G.installed_drawer) and WorldManager and WorldManager.update then
		local original = WorldManager.update

		WorldManager.update = function(self, ...)
			if not (G.installed and G.installed_drawer) then
				pcall(install)
			end

			return original(self, ...)
		end
	end
end
