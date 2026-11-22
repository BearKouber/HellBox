-- ABI 1. Embedded in each module; get_host installs exactly one dispatcher.
return function()
    local existing = rawget(_G, "HelldiversBridgeHost")
    if existing then
        assert(existing.abi == 1, "bridge_host_abi_mismatch")
        assert(rawget(_G, "update") == existing.dispatch, "bridge_update_replaced")
        return existing
    end
    local native_update = assert(rawget(_G, "update"), "missing_game_update")
    local host = {abi=1, modules={}, order={}, resources={}, errors={}}
    function host:register(id, callbacks)
        assert(type(id)=="string" and id:match("^[a-z][a-z0-9_]*$"), "invalid_module_id")
        assert(not self.modules[id], "duplicate_bridge_module:"..id)
        assert(type(callbacks)=="table", "invalid_callbacks")
        for _, key in ipairs({"pre","post","on_error"}) do
            assert(callbacks[key]==nil or type(callbacks[key])=="function", "invalid_callback:"..key)
        end
        self.modules[id] = callbacks
        self.order[#self.order+1] = id
        table.sort(self.order)
    end
    -- Future modules must claim shared hook sites before replacing a game method.
    -- A claim is an exclusivity check, not a substitute for restoration.
    function host:claim(id, resource)
        assert(self.modules[id], "module_not_registered")
        local owner = self.resources[resource]
        if owner and owner~=id then return false,owner end
        self.resources[resource]=id
        return true
    end
    function host:release(id, resource)
        if self.resources[resource]==id then self.resources[resource]=nil; return true end
        return false
    end
    local function phase(name, dt, order)
        for _, id in ipairs(order) do
            local module=host.modules[id]
            local callback=module[name]
            if callback then
                local ok,problem=pcall(callback,dt)
                if not ok then
                    host.errors[id]=name..":"..tostring(problem):sub(1,256)
                    if module.on_error then pcall(module.on_error,name,problem) end
                end
            end
        end
    end
    host.dispatch=function(dt)
        local order={unpack(host.order)}
        phase("pre",dt,order)
        -- Do not swallow engine failures or update the native simulation twice.
        native_update(dt)
        phase("post",dt,order)
    end
    rawset(_G,"HelldiversBridgeHost",host)
    rawset(_G,"update",host.dispatch)
    return host
end
