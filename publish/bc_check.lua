-- CI 用：GitHub 上编出来的 LuaJIT 编这个文件，字节要和开发机上的一样（见 .github/workflows/release.yml）。
local M = {}

function M.mix(t, k)
	local out, n = {}, 0
	for i, v in ipairs(t) do
		if type(v) == "number" and v % 2 == 0 then
			n = n + 1
			out[n] = string.format("%s=%d", k or "x", v * 3)
		end
	end
	return table.concat(out, ";"), n, 0.5, 2 ^ 40, -1.25e-3
end

M.flag = { a = true, b = false, c = "text", [10] = 3.75 }

return M
