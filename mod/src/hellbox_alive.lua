-- [hellbox alive] HellBox 开没开着（2026-11-25 用户定：HellBox 关了，影响平衡的东西马上全部按原版）。
-- 由 build.py 追加到 character_state_machine 末尾，排在 hb_log 后面、用它的脚本（data_live / hellbox_strong / hellbox_play /
-- host_loadout）前面。
--
-- HellBox 开着时每 3 秒往 %APPDATA%/Arrowhead/Helldivers/hellbox/hellbox-alive.txt 写当前时间（秒，os.time 同一种），
-- 正常关掉时写 0（hellbox/alive.py）。这里每秒最多读一次：时间在 ALIVE_SECS 以内 = 开着；文件没有、写的 0、过期了
-- （HellBox 闪退 / 被强关）= 关了。
--   HellBoxAlive.on()  开着 → true
--   HellBoxAlive.off() 关了 → true
-- 关了以后谁按原版：数据页全部（怪物属性、出怪和场上上限 / 破限、武器、战备、潜兵；data_live.lua）、玩法页的模式和事件
-- （hellbox_play.lua）、房主配装（host_loadout.lua）、选图「变强」（hellbox_strong.lua）。功能页、显示、指针这些不管。
-- HellBox 再打开，下一次检查时套回去。已经发生的不倒回：已生成的鬼城地图、已换上的军刀、变强已经跳过的波数。
do
	local G = rawget(_G, "HellBoxAlive") or {}

	HellBoxAlive = G

	local ALIVE_SECS = 15 -- HellBox 3 秒写一次，留出 HellBox 忙、硬盘慢的余量
	local CHECK_EVERY = 1

	local function path()
		local appdata = os.getenv and os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/hellbox-alive.txt")
	end

	local function fresh()
		local p = path()
		local f = p and io.open(p, "rb")

		if not f then
			return false
		end

		local s = f:read("*l")

		f:close()

		local ts = tonumber(s)

		if not ts or ts <= 0 then
			return false
		end

		local age = os.time() - ts

		return age >= -ALIVE_SECS and age <= ALIVE_SECS
	end

	local function clock()
		local ok, t = pcall(function()
			return Application.time_since_launch()
		end)

		return ok and t or os.clock()
	end

	function G.on()
		local t = clock()

		if G.alive == nil or not G.checked or t - G.checked >= CHECK_EVERY or t < G.checked then
			G.checked = t

			local ok, yes = pcall(fresh)
			local now = ok and yes or false

			if now ~= G.alive then
				if G.alive ~= nil and rawget(_G, "HellBoxLog") then
					HellBoxLog("hellbox_alive", now and "HellBox 打开了：数据和玩法重新套上" or "HellBox 关了：数据和玩法全部按原版", "INFO")
				end

				G.alive = now
			end
		end

		return G.alive
	end

	function G.off()
		return not G.on()
	end
end
