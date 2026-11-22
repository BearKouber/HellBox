-- [hb log] HellBox 日志本的游戏这一半（2026-11-14 用户要求：记录报错，HellBox「日志」页能看）。
-- 由 build.py 追加到 character_state_machine 末尾，排在 HellBox 自己的脚本前面。
--
-- HellBoxLog(来源, 内容, 级别) 追加一行到 %APPDATA%/Arrowhead/Helldivers/hellbox/logs/game.log：
--   2026-11-14 03:12:45<TAB>ERROR<TAB>来源<TAB>内容（换行换成空格）
-- 同一条 60 秒内只记一次（每帧都报的错不刷屏）；文件超过 512KB 就把旧的改名 game.log.1 重新开始。
-- 目录由 HellBox 建好；没有目录（没装 HellBox 的自用版）就什么都不写。写不进去也不影响游戏。
do
	local G = HellBoxLogState or { recent = {} }

	HellBoxLogState = G

	local MAX_BYTES = 512 * 1024
	local REPEAT = 60

	local function dir()
		local appdata = os.getenv("APPDATA")

		return appdata and (appdata .. "/Arrowhead/Helldivers/hellbox/logs/")
	end

	local function now()
		local ok, t = pcall(function()
			return Application.time_since_launch()
		end)

		return ok and t or os.clock()
	end

	function HellBoxLog(source, message, level)
		local ok = pcall(function()
			local text = tostring(message or ""):gsub("[\r\n\t]+", " ")
			local key = tostring(source) .. "|" .. text
			local t = now()

			if G.recent[key] and t - G.recent[key] < REPEAT then
				return
			end

			G.recent[key] = t

			local d = dir()

			if not d then
				return
			end

			local path = d .. "game.log"
			local f = io.open(path, "ab")

			if not f then
				return
			end

			local size = f:seek("end") or 0

			if size > MAX_BYTES then
				f:close()
				os.remove(path .. ".1")
				os.rename(path, path .. ".1")
				f = io.open(path, "ab")

				if not f then
					return
				end
			end

			f:write(os.date("%Y-%m-%d %H:%M:%S"), "\t", tostring(level or "ERROR"), "\t", tostring(source), "\t", text, "\n")
			f:close()
		end)

		return ok
	end
end
