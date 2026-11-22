-- HellBox 转接层的启动部分（2026-11-20 HD1-035）。tools/make_hop.py 把它和半糖 HelldiversOptimization 的模块
-- 拼成 src/hellbox_hop.lua。上面已经有：hop_defaults（编译时填的初始值）、各模块工厂（*_factory）。
--
-- 和半糖原版 bootstrap 的区别：
--   - 设置不是装 MOD 时写死的：游戏每秒读 HellBox 写的 %APPDATA%/Arrowhead/Helldivers/hellbox/hop.txt
--     （HBHOP1，一行一个 键=值），改了就生效。
--   - 挂钩一直装着，每次被调用时看开关（gate），关着就照原版走；不需要重开游戏。
--   - 2026-11-21 HD1-038（用户定）：来自 QoL Mod 的功能全部删掉（QoL 作者希望各自独立、能一起装；想用就装正版 QoL，HellBox 能和它共存）。
--     只留半糖自己的：建构连续装填、名字深色底、长文字不截断（2026-11-22 用户：军械库显示真实数值、显示身上的状态也是 QoL 的，删了）。
--   - 没有 BridgeCore：host 是这里的一个小替身（claim 永远成功），每帧的驱动挂在 WorldManager.update 上。
do
	local live = {}
	local defaults = hop_defaults or {}
	local config = setmetatable({}, {__index = function(_, key)
		local value = live[key]
		if value == nil then value = defaults[key] end
		return value
	end})

	local function on(key) return config[key] == "1" end

	-- 挂钩名字 -> 什么时候算开着：同名设置是 "1"
	local function gate_of(feature)
		return function() return on(feature) end
	end

	local marker = {version = "hellbox-1", status = "waiting", features = {}, module_errors = {}, config = config}  -- config：蜜蜂灯等别的脚本也读
	rawset(_G, "HellBoxHop", marker)

	local function log(where, problem)
		if rawget(_G, "HellBoxLog") then pcall(HellBoxLog, "hellbox_hop", tostring(where) .. ": " .. tostring(problem)) end
	end

	-- 替身 host：BetterHUD 适配器要 claim / release
	local host = {}
	function host:claim() return true end
	function host:release() end

	-- 和半糖 hooks.lua 一样的注册办法，多一层「每次调用看开关」
	local hooks = {}
	do
		local installed = setmetatable({}, {__mode = "k"})
		function hooks.wrap(class_name, method, feature, factory)
			local class = rawget(_G, class_name)
			if type(class) ~= "table" or type(class[method]) ~= "function" then
				marker.features[feature] = "waiting:" .. class_name .. "." .. method
				return false
			end
			local methods = installed[class]
			if not methods then methods = {}; installed[class] = methods end
			local key = feature .. ":" .. method
			if methods[key] then return true end
			local native = class[method]
			local wrapper = factory(native)
			assert(type(wrapper) == "function", "invalid_optimization_wrapper")
			local gate = gate_of(feature)
			local gated = function(...)
				if gate() then return wrapper(...) end
				return native(...)
			end
			class[method] = gated
			methods[key] = gated
			marker.features[feature] = "installed"
			return true
		end
		function hooks.copy(value)
			local copy = {}
			for k, v in pairs(value or {}) do copy[k] = v end
			return copy
		end
		function hooks.scoped(object, key, value, call)
			local previous = object[key]
			object[key] = value
			local function finish(ok, ...)
				object[key] = previous
				if not ok then error((...), 0) end
				return ...
			end
			return finish(pcall(call))
		end
	end

	-- 读 HellBox 写的设置文件
	local last_text
	local function read_live()
		local appdata = os.getenv and os.getenv("APPDATA")
		local f = appdata and io and io.open and io.open(appdata .. "/Arrowhead/Helldivers/hellbox/hop.txt", "rb")
		if not f then return end
		local text = f:read("*a") or ""
		f:close()
		if text == last_text or not text:match("^HBHOP1") then return end
		last_text = text
		local fresh = {}
		for line in text:gmatch("[^\r\n]+") do
			local k, v = line:match("^([%w_]+)=(.*)$")
			if k then fresh[k] = v end
		end
		live = fresh
	end

	local env = context_factory()
	local extensions = {
		readability = readability_factory(config, hooks),
	}
	local disabled = {}

	local weapons_installed = false
	local function install()
		for name, extension in pairs(extensions) do
			if not disabled[name] then
				local ok, result = pcall(extension)
				if not ok then
					disabled[name] = true
					marker.module_errors[name] = tostring(result):sub(1, 512)
					log(name, result)
				end
			end
		end
		if not weapons_installed and type(CharacterStateMachine) == "table"
				and type(CharacterStateMachine.update) == "function" then
			local native = CharacterStateMachine.update
			local wrapped = constitution_factory(env)(native)
			CharacterStateMachine.update = function(...)
				if on("bolt_reload") then return wrapped(...) end
				return native(...)
			end
			weapons_installed = true
		end
		marker.status = next(disabled) and "partial_error" or "installed"
	end

	pcall(read_live)
	pcall(install)
	if WorldManager and WorldManager.update then
		local original = WorldManager.update
		local next_read, next_install = 0, 0
		WorldManager.update = function(self, ...)
			local now = Application and Application.time_since_launch and Application.time_since_launch() or os.clock()
			if now >= next_read then
				next_read = now + 1
				pcall(read_live)
			end
			if now >= next_install then
				next_install = now + 0.25
				local ok, problem = pcall(install)
				if not ok then log("install", problem) end
			end
			return original(self, ...)
		end
	end
end
