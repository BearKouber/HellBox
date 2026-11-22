local boot=assert(loadfile(arg[1]))
local expected={}
for id in (arg[2] or ""):gmatch("%a+") do expected[id]=true end
Application={platform=function() return "win32" end,build=function() return "release" end,time_since_launch=function() return 0 end}
Unit,Gui,Vector3,PhysicsWorld,DisplayAdapter,Profiler,PS4,PSVita,Steam={},{},{},{},{},{},{},{},{}
loadstring=function() error("dynamic compiler unavailable") end
loadfile=loadstring
boot()
if next(expected) then
    assert(HelldiversBridgeHost and HelldiversBridgeHost.abi==1)
    for _,id in ipairs({"camera","captain"}) do
        assert((HelldiversBridgeHost.modules[id]~=nil)==(expected[id] or false),id)
        if expected[id] then
            if id=="captain" then assert(CaptainHelldiverBridgeBootOk,CaptainHelldiverBridgeBootError)
            else assert(_G["HelldiversBridgeBootOk_"..id],_G["HelldiversBridgeBootError_"..id]) end
        end
    end
    assert(update==HelldiversBridgeHost.dispatch)
else assert(not HelldiversBridgeHost) end
print("PASS boot modules: "..(arg[2] or "none"))
