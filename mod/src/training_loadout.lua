-- [training loadout] HellBox 训练模式开局前先选战备（2026-11-14 用户要求："训练模式进前能像普通模式那样选战备"）。
-- 由 build.py 追加到 character_state_machine 末尾。
--
-- HellBox 开训练走的是游戏自带的 -autohost：主菜单直接进出发画面（StateMissionStart），不带 do_loadout，
-- 所以跳过选装备，直接用存档里上次那套。中途加入别人房间时游戏会带 do_loadout = true，出发画面就先弹选装备界面
-- （MenuScreenLoadout：主武器 / 战备 / 天赋、预设套装、20 秒倒计时）。这里在 HellBox 开的训练上也打开它。
--   只认 HellBox 开的：HellBox 开游戏前写 %APPDATA%/Arrowhead/Helldivers/hellbox/training-loadout.txt（内容 = 写的时刻，秒），
--   这里读到 10 分钟内的就用一次并删掉。陪玩测试（ai\drill_run.py）也用 -autohost，但不写这个文件，照旧直接进关。
--   autohost 给的玩家名单是空的（游戏进关后再按手柄补人）；选装备界面要名单，这里照游戏开发版的写法补上主手柄一个人。
do
	local G = HellBoxTrainingLoadout or {}

	HellBoxTrainingLoadout = G

	local MAX_AGE = 600

	local function flag_path()
		local appdata = os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/training-loadout.txt")
	end

	local function take_flag()
		local path = flag_path()
		local f = path and io.open(path, "rb")

		if not f then
			return false
		end

		local stamp = tonumber((f:read(64) or ""):match("%d+"))

		f:close()
		os.remove(path)

		return stamp ~= nil and math.abs(os.time() - stamp) <= MAX_AGE
	end

	local function main_pad()
		local pad = GameSettings.get_main_pad_number()

		if pad ~= nil then
			return pad
		end

		local inputs = InputUtility.get_active_inputs()

		return inputs and inputs[1] and inputs[1].pad_number
	end

	local function prepare(params)
		local players = params.active_players

		if type(players) ~= "table" or #players == 0 then
			local pad = main_pad()

			if pad == nil then
				return false
			end

			local user = UserManager:get_user_id(pad)
			local xp = math.clamp(SaveManager:user_get("player_xp", user) or 0, 0, ProgressionSettings.final_rank.required_xp)

			params.active_players = {
				{
					owned = true,
					player_index = 1,
					pad_number = pad,
					peer_id = Network.peer_id(),
					name = UserManager:get_name(pad),
					xp = xp,
				},
			}
		end

		params.do_loadout = true

		return true
	end

	local function install()
		local cls = rawget(_G, "StateMissionStart")

		-- 每个类只包一次：别的脚本（hellbox_qol 的加速）也包 on_enter，按"现在的函数是不是我包的"判断会互相越叠越多
		if type(cls) ~= "table" or type(cls.on_enter) ~= "function" or G.class == cls then
			return
		end

		G.class = cls

		local orig = cls.on_enter

		G.wrapped = function(self, params, ...)
			if type(params) == "table" and params.is_training and params.planet_name == "Autohost" and not params.do_loadout then
				local ok, used = pcall(function()
					return take_flag() and prepare(params)
				end)

				G.last = ok and (used and "loadout" or "skip") or ("error: " .. tostring(used))

				if not ok and rawget(_G, "HellBoxLog") then
					HellBoxLog("training_loadout", used)
				end
			end

			return orig(self, params, ...)
		end
		cls.on_enter = G.wrapped
	end

	pcall(install)

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.tick then
		local orig = wm.update
		local next_check = 0

		G.tick = function(self, ...)
			local now = Application.time_since_launch()

			if now >= next_check then
				next_check = now + 0.5
				pcall(install)
			end

			return orig(self, ...)
		end
		wm.update = G.tick
	end
end
