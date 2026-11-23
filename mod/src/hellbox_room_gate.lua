-- [room gate] 联机限制（2026-11-23 V1.07，用户定）。由 build.py 追加到 character_state_machine 末尾，要在用到它的脚本前面。
--
-- 带箱子上车、丢支援装备、补给背包自己用、自动定位任务位置、分屏：当客机时只在「有 MOD 的房间」生效，进普通房间不生效。
--   能用：没有房间（单机 / 主菜单）、自己是房主、房主装了 HellBox（房间数据有 hellbox_play 或 hellbox 键）、
--         房主开着分屏（CameraCTRL：任务里房主角色的 camera_target 上有分屏模块的暗号，判断照 peer_modes.lua 的 read）。
--   看到过房主的分屏暗号后，这个房间一直算有 MOD（回飞船时没有暗号也不收回），换房间才重新看。
-- 别的脚本调 HellBoxRoomGate.ok()（每秒最多重算一次）；这个脚本没装时它们当「能用」。
do
	local G = HellBoxRoomGate or {}

	HellBoxRoomGate = G
	G.next_at = G.next_at or -1
	G.last = G.last ~= false
	G.why = G.why or "solo"

	local function now()
		return Application.time_since_launch()
	end

	local function lobby_now()
		local ng = rawget(_G, "NetworkGlobal")
		local lobby = type(ng) == "table" and ng.lobby

		if type(lobby) == "table" and lobby.lobby and lobby.is_valid and lobby:is_valid() then
			return lobby
		end

		return nil
	end

	local function lobby_has(lobby, key)
		local api = (lobby.backend_type == "STEAM" and rawget(_G, "SteamLobby"))
			or (lobby.backend_type == "LAN" and rawget(_G, "LanLobby")) or nil

		if type(api) ~= "table" or type(api.data) ~= "function" then
			return false
		end

		local ok, v = pcall(api.data, lobby.lobby, key)

		return ok and type(v) == "string" and not v:match("^%s*$")
	end

	-- 房主角色的分屏暗号：look_ahead 8～15（整数）、is_reverse = true、active = false，每 0.5 秒换一档，连着往前走两步才算
	local obs = {}

	local function watch_camera(lobby)
		local boot = rawget(_G, "Boot")
		local sm = type(boot) == "table" and boot.state_machine
		local game = type(sm) == "table" and sm.current_state_name == "game" and sm.state

		if type(game) ~= "table" or type(game.entity_manager) ~= "table" then
			return
		end

		local okh, host = pcall(lobby.lobby_host, lobby)

		if not okh or host == nil then
			return
		end

		local groups = game.entity_manager.component_name_to_contexts
		local group = type(groups) == "table" and groups.camera_target

		if type(group) ~= "table" or type(group.slave) ~= "table" then
			return
		end

		for _, player in ipairs(game.players or {}) do
			local go = player.player_go
			local unit = go and go:exists() and not go:owned() and go:get("avatar_unit")

			if unit and Unit.alive(unit) and EntityAux.owner(unit) == host then
				local context = group.slave[unit]
				local state = context and context.state
				local value = state and state.look_ahead

				if not state or state.active ~= false or state.is_reverse ~= true or type(value) ~= "number"
					or value < 8 or value > 15 or math.abs(value - math.floor(value + 0.5)) > 0.04 then
					obs[unit] = nil
				else
					local phase = math.floor((math.floor(value + 0.5) - 8) / 2)
					local t = now()
					local p = obs[unit]

					if not p or p.state ~= state or t - p.changed > 2 then
						obs[unit] = { state = state, phase = phase, changed = t, steps = 0 }
					elseif phase ~= p.phase then
						local advance = (phase - p.phase) % 4

						p.steps = (advance == 1 or advance == 2) and math.min(2, p.steps + 1) or 0
						p.phase, p.changed = phase, t

						if p.steps >= 2 then
							G.cam_lobby = lobby.lobby
						end
					end
				end
			end
		end
	end

	local function compute()
		local lobby = lobby_now()

		if not lobby then
			return "solo"
		end

		local okh, is_host = pcall(lobby.is_host, lobby)

		if not okh then
			return "solo"
		elseif is_host then
			return "host"
		elseif lobby_has(lobby, "hellbox_play") or lobby_has(lobby, "hellbox") then
			return "hellbox"
		elseif G.cam_lobby ~= nil and G.cam_lobby == lobby.lobby then
			return "camera"
		end

		return "vanilla"
	end

	function G.ok()
		local t = now()

		if t >= G.next_at then
			G.next_at = t + 1

			local ok, why = pcall(compute)

			-- 读不出来（引擎接口变了之类）当能用，不因为这里出错把功能全关掉
			G.why = ok and why or "error"
			G.last = G.why ~= "vanilla"

			if not ok and rawget(_G, "HellBoxLog") then
				HellBoxLog("room_gate", tostring(why))
			end
		end

		return G.last
	end

	-- 客机在任务里时每 0.25 秒看一眼房主的分屏暗号（WorldManager.update 每帧走；只包一次）
	local wm = rawget(_G, "WorldManager")

	if type(wm) == "table" and type(wm.update) == "function" and not rawget(wm, "_hb_room_gate") then
		local orig = wm.update
		local watch_at = -1

		wm.update = function(self, dt, ...)
			local t = now()

			if t >= watch_at then
				watch_at = t + 0.25

				pcall(function()
					local lobby = lobby_now()

					-- 只在「普通房间的客机」时看（G.why 由 ok() 每秒更新，分屏脚本每秒都会调 ok()）
					if lobby and G.why == "vanilla" and G.cam_lobby ~= lobby.lobby then
						watch_camera(lobby)
					end
				end)
			end

			return orig(self, dt, ...)
		end
		rawset(wm, "_hb_room_gate", true)
	end
end
