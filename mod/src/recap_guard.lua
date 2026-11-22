-- [recap guard] 开机战役回顾不再闪退（2026-10-18）。由 build.py 追加到 character_state_machine 末尾（在 ai_mech 后面）。
--
-- 闪退：lua/menu/menu_screen_campaign_recap.lua: attempt to call method 'exit' (a nil value)，每次开机必崩。
--   开机进战役界面总会放回顾（show_recap -> full_recap），回顾向服务器要"上次看过之后"的战役快照
--   （CampaignManager:get_snapshots(赛季, last_shown_recap_time)）。服务器一天只出一张快照（本地早上 8 点），
--   存档里的 last_shown_recap_time 晚于最新一张时就回 0 张，recieve_snapshots 走"No campaign snapshots"
--   -> self.parent:exit()，而这时 parent 上没有 exit（原因没查清，可能回调到达时界面已经销毁），就崩。
--   同一天关了游戏再开就会碰上（2026-10-17 实机四次，服务器实测 start 晚于 8 点回 0 张）。
--
-- 包 MenuScreenCampaignRecap.recieve_snapshots：
--   1. parent 没有 exit（界面已经不在了）：这次回调直接丢掉，什么也不做。
--   2. 服务器回了 0 张但存档里有上次看过的状态：拿上次看过的状态补一张快照，回顾照常放（从上次到现在），不走 exit。
--   其他情况原样交给原版。
-- 回顾脚本不一定比这个文件先加载，所以加载时先试一次，没包上就挂 WorldManager.update 每帧再试，包上为止。
do
	local G = RecapGuard or {}

	RecapGuard = G

	local function clone(v)
		if type(v) ~= "table" then
			return v
		end

		local c = {}

		for k, x in pairs(v) do
			c[k] = clone(x)
		end

		return c
	end

	local function install()
		local cls = rawget(_G, "MenuScreenCampaignRecap")

		if type(cls) ~= "table" or type(cls.recieve_snapshots) ~= "function" then
			return false
		end

		if cls.recieve_snapshots == G.wrapped then
			return true
		end

		local orig = cls.recieve_snapshots

		G.wrapped = function(self, order, snapshots, defend_events, attack_events, season, ...)
			local parent = self and self.parent

			if type(parent) ~= "table" or type(parent.exit) ~= "function" then
				G.dropped = (G.dropped or 0) + 1

				return
			end

			local last = self.last_shown_recap_status
			local last_time = self.last_shown_recap_time

			if order and type(snapshots) == "table" and #snapshots == 0 and type(last) == "table" and last[1] and last_time then
				snapshots[1] = {
					data = clone(last),
					season = season or last[1].season,
					time = last_time
				}
				G.filled = (G.filled or 0) + 1
			end

			return orig(self, order, snapshots, defend_events, attack_events, season, ...)
		end
		cls.recieve_snapshots = G.wrapped

		return true
	end

	if not install() then
		local wm = rawget(_G, "WorldManager")

		if type(wm) == "table" and type(wm.update) == "function" and not G.wm_hooked then
			G.wm_hooked = true

			local orig_update = wm.update

			wm.update = function(...)
				if not G.done then
					local ok, res = pcall(install)

					G.done = ok and res
				end

				return orig_update(...)
			end
		end
	end
end
