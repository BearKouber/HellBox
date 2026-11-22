-- [rec gate post] HD1-034 录制接口（只进发行版 / 录制器核心，自用版不装）：
-- 平时休眠：CharacterStateMachine.update 直接走原版（rec_gate_pre 记下的），ai_bridge / ai_mech 不采集、不打射线。
-- 录制器开着时每几秒往 %APPDATA%/Arrowhead/Helldivers/hellbox/recorder-alive.txt 写当前时间（秒）；
-- 这里隔 CHECK_EVERY 次调用读一次，时间在 ALIVE_SECS 以内就走 ai_mech → ai_bridge → 原版这一串。
-- 录制器关掉或崩了，心跳过期，自动回到休眠。
-- 发行版不带锁血：ai_mech 的锁血键只在 lock_key == nil 时去找，这里先设成 false，它就永远不找、不开。
do
	local G = rawget(_G, "HellBoxRecGate") or {}
	local CHECK_EVERY = 240
	local ALIVE_SECS = 20

	HellBoxRecGate = G
	G.marker = "HellBoxRecGate v1"

	local mech = rawget(_G, "AIMech")

	if mech then
		mech.lock = false
		mech.lock_key = false
	end

	local orig = G.orig or CharacterStateMachine.update
	local wrapped = CharacterStateMachine.update

	G.active = false
	G.calls = CHECK_EVERY

	local function heartbeat_fresh()
		local appdata = os.getenv and os.getenv("APPDATA")

		if not appdata then
			return false
		end

		local f = io.open(appdata .. "/Arrowhead/Helldivers/hellbox/recorder-alive.txt", "rb")

		if not f then
			return false
		end

		local s = f:read("*l")

		f:close()

		local ts = tonumber(s)

		if not ts then
			return false
		end

		local age = os.time() - ts

		return age >= -ALIVE_SECS and age <= ALIVE_SECS
	end

	if wrapped ~= orig then
		function CharacterStateMachine.update(...)
			G.calls = G.calls + 1

			if G.calls >= CHECK_EVERY then
				G.calls = 0

				local ok, fresh = pcall(heartbeat_fresh)

				G.active = ok and fresh or false
			end

			if G.active then
				return wrapped(...)
			end

			return orig(...)
		end
	end
end
