-- 找房间的「筛选」里加一条「隐藏 HellBox 房间」（2026-11-21 HD1-038 用户要求：QoL 的房间列表功能删了，做一个我们自己的）。
-- 原版：公开房间列表的筛选面板 = GameSettings.multiplayer_filters 这张表（game_settings.lua），每条
--   {name = 语言键, default_value = 默认开没开, filter_func = function(房间, 开着) 返回真 = 这个房间不显示}；
--   进找房间界面时照这张表建开关（menu_screen_campaign_multiplayer.lua on_enter），选的结果游戏自己存进
--   存档的 multiplayer_filters（按 name 记），列房间时每个房间挨个过 filter_func。
-- 这里：往表里加一条，和原版那几条一模一样能开能关、游戏自己记住；默认不隐藏。
--   认 HellBox 房间：房间名里有「[HellBox」（room_name.lua 当房主时一直写这个标记，放前面放后面都有）。
--   只有公开列表有筛选面板（原版就这样），好友列表不管。没装 HellBox 的人看不到这条。
--   名字：语言表里没有这个键，LocalizationManager.string 碰到它时照游戏现在的语言给中文或英文。
do
	local KEY = "filter_hide_hellbox"
	local G = HellBoxRoomFilter or {}
	HellBoxRoomFilter = G

	local function hidden(room, enabled)
		return enabled and type(room) == "table" and type(room.name) == "string"
			and room.name:find("[HellBox", 1, true) ~= nil
	end

	local function add_filter()
		local gs = rawget(_G, "GameSettings")
		local list = type(gs) == "table" and gs.multiplayer_filters
		if type(list) ~= "table" then
			return false
		end
		for _, item in ipairs(list) do
			if type(item) == "table" and item.name == KEY then
				return true
			end
		end
		list[#list + 1] = {name = KEY, default_value = false, filter_func = hidden}
		return true
	end

	local function label(orig, manager)
		-- 照原版「隐藏满员房间」那条的语言和大小写写
		local ok, sample = pcall(orig, manager, "filter_hide_full_games")
		sample = ok and type(sample) == "string" and sample or ""
		if sample:find("[\228-\233]") then
			return "隐藏 HellBox 房间"
		end
		local text = "Hide HellBox games"
		if sample ~= "" and sample == sample:upper() then
			text = text:upper()
		end
		return text
	end

	local function hook_loc()
		local lm = rawget(_G, "LocalizationManager")
		if type(lm) ~= "table" or type(lm.string) ~= "function" then
			return false
		end
		local orig = lm.string
		lm.string = function(self, key, ...)
			if key == KEY then
				return label(orig, self)
			end
			return orig(self, key, ...)
		end
		return true
	end

	local function tick()
		if not G.added then
			local ok, done = pcall(add_filter)
			G.added = ok and done
		end
		if not G.loc then
			local ok, done = pcall(hook_loc)
			G.loc = ok and done
		end
		return G.added and G.loc
	end

	if not tick() then
		local wm = rawget(_G, "WorldManager")
		if type(wm) == "table" and type(wm.update) == "function" and not G.wm then
			G.wm = true
			local orig = wm.update
			wm.update = function(self, ...)
				if not (G.added and G.loc) then
					pcall(tick)
				end
				return orig(self, ...)
			end
		end
	end
end
