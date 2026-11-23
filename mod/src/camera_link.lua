-- [camera link] 分屏（HalfSugar 的 CameraCTRL，作者同意收进 HellBox，2026-11-14）。由 build.py 追加到 character_state_machine 末尾。
--
-- 分屏模块（桥接）在游戏里每 0.2 秒读一次控制文件 control-request.txt，5 秒没收到新请求就自动关掉分屏
-- （原来要一直开着 CameraCTRL.exe 发请求，防止控制程序崩了分屏还开着）。
-- 这里改成游戏自己每秒发一次请求：设置从 HellBox「分屏」页存的 hellbox-split.txt 读，所以不用开着 HellBox，
-- 开着 HellBox 改设置，下一秒游戏里就跟着变。
--   hellbox-split.txt：HBSPLIT1 \n 掩码 \n 增援倍率 \n 巡逻倍率 \n
--   掩码：0 关；1 解除视角限制；3 视角 + 位置；+4 房主刷怪区域扩展（只能是 0 1 3 4 5 7）。
--   第 5 行（2026-11-19 半糖新版分屏，旧文件没有）：个人画面比例 0 跟随游戏 / 1778 16:9 / 1600 16:10 / 1333 4:3 / 1250 5:4；
--   不是 0 时照作者 lib.rs 在 SPAWN 后面加 VIEW 行（作者的 runtime 先拆 VIEW 再认 SPAWN）。
--   倍率：HellBox 固定写 4 = "分开几个人就几份、同屏按原版"（作者的倍率是全场份数的封顶，HD1 最多 4 人）。
-- 请求格式照 CameraCTRL 的 lib.rs（CAM2），会话号直接读桥接放在全局的 CameraCTRLBridge.session。
-- 队友有没有开分屏是桥接自己通过联机数据知道的，和这里无关。没装分屏模块（自用版）时这里什么都不做。
-- 2026-11-19 用户定：分屏还要调整，先放进开发者模式。HellBox 普通模式（hellbox/dev.txt 不是 "1"）时这里一律发「关」，
--   分屏页也藏起来；hellbox-split.txt 里的设置不动，打开开发者模式下一秒就照原来的设置开。
do
	local G = HellBoxCameraLink or {}

	HellBoxCameraLink = G
	G.serial = G.serial or 0
	G.last = G.last or -100

	local OWNER = "hellbox"
	local VALID = { [0] = true, [1] = true, [3] = true, [4] = true, [5] = true, [7] = true }
	local RATIO = { [0] = true, [1250] = true, [1333] = true, [1600] = true, [1778] = true }

	local function root()
		local appdata = os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/camera_ctrl_v1/")
	end

	local function dev_on()
		local appdata = os.getenv("APPDATA")
		local f = appdata and io.open(appdata .. "/Arrowhead/Helldivers/hellbox/dev.txt", "rb")

		if not f then
			return false
		end

		local text = f:read(8) or ""

		f:close()

		return text:match("^%s*1") ~= nil
	end

	-- 2026-11-23 V1.07 联机限制：当客机时只在有 MOD 的房间开分屏（房主装了 HellBox 或开着分屏，hellbox_room_gate.lua）
	local function room_ok()
		local gate = rawget(_G, "HellBoxRoomGate")

		return not (type(gate) == "table" and type(gate.ok) == "function") or gate.ok()
	end

	local function read_settings(dir)
		if not dev_on() or not room_ok() then
			return 0, 4, 4, 0
		end

		local f = io.open(dir .. "hellbox-split.txt", "rb")

		if not f then
			return 0, 4, 4, 0
		end

		local text = f:read(256) or ""

		f:close()

		local mask, enc, pat = text:match("^HBSPLIT1\r?\n(%d+)\r?\n(%d+)\r?\n(%d+)")
		local ratio = tonumber(text:match("^HBSPLIT1\r?\n%d+\r?\n%d+\r?\n%d+\r?\n(%d+)"))

		mask, enc, pat = tonumber(mask), tonumber(enc), tonumber(pat)

		if not mask or not VALID[mask] then
			return 0, 4, 4, 0
		end

		enc = math.max(1, math.min(4, enc or 4))
		pat = math.max(1, math.min(4, pat or 4))

		if not ratio or not RATIO[ratio] then
			ratio = 0
		end

		return mask, enc, pat, ratio
	end

	local function send()
		local bridge = rawget(_G, "CameraCTRLBridge")

		if type(bridge) ~= "table" or type(bridge.session) ~= "string" then
			return
		end

		local dir = root()

		if not dir then
			return
		end

		local mask, enc, pat, ratio = read_settings(dir)

		G.serial = G.serial + 1
		G.mask = mask

		local nonce = "hb" .. tostring(G.serial)
		local parts = { "CAM2", nonce, bridge.session, OWNER, tostring(G.serial), tostring(mask),
			"SPAWN", tostring(enc), tostring(pat) }

		if ratio ~= 0 then
			parts[#parts + 1] = "VIEW"
			parts[#parts + 1] = tostring(ratio)
		end

		parts[#parts + 1] = "END"
		parts[#parts + 1] = ""

		local text = table.concat(parts, "\n")
		local tmp = dir .. "control-request.hellbox.tmp"
		local f = io.open(tmp, "wb")

		if not f then
			return
		end

		f:write(text)
		f:close()
		os.remove(dir .. "control-request.txt")
		os.rename(tmp, dir .. "control-request.txt")
	end

	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and wm.update ~= G.wrapped then
		local orig = wm.update

		G.wrapped = function(self, dt, ...)
			local now = Application.time_since_launch()

			if now - G.last >= 1 then
				G.last = now

				local ok, err = pcall(send)

				if not ok then
					G.errors = (G.errors or 0) + 1
					G.last_error = tostring(err)
					if rawget(_G, "HellBoxLog") then HellBoxLog("camera_link", G.last_error) end
				end
			end

			return orig(self, dt, ...)
		end
		wm.update = G.wrapped
	end
end
