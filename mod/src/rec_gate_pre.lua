-- [rec gate pre] HD1-034 录制接口（只进发行版 / 录制器核心，自用版不装）：
-- 在 ai_bridge、ai_mech 挂上去之前，先记下原版的 CharacterStateMachine.update。
-- rec_gate_post.lua（排在 ai_mech 后面）用它：录制器没开时直接走原版，ai_bridge / ai_mech 一行都不跑。
do
	local G = rawget(_G, "HellBoxRecGate") or {}

	HellBoxRecGate = G

	if not G.orig then
		G.orig = CharacterStateMachine.update
	end
end
