local factory=assert(loadfile(arg[1]))()
local calls={}
update=function(dt) calls[#calls+1]="game:"..dt end
HelldiversBridgeHost=nil
local h=factory()
local first_update=update
h:register("camera",{pre=function() calls[#calls+1]="camera_pre" end,
    post=function() calls[#calls+1]="camera_post" end})
h:register("captain",{pre=function() error("module_failure") end,
    post=function() calls[#calls+1]="captain_post" end,
    on_error=function(phase) calls[#calls+1]="captain_error:"..phase end})
assert(factory()==h and update==first_update)
assert(not pcall(function() h:register("camera",{}) end))
update(0.25)
assert(table.concat(calls,",")=="camera_pre,captain_error:pre,game:0.25,camera_post,captain_post")
assert(h.errors.captain:find("module_failure",1,true))
assert(h:claim("camera","CameraManager.update"))
assert(not h:claim("captain","CameraManager.update"))
assert(not h:release("captain","CameraManager.update"))
assert(h:release("camera","CameraManager.update"))
h:register("later_registration",{pre=function()
    if not h.modules.new_module then h:register("new_module",{post=function() calls[#calls+1]="new_module" end}) end
end})
calls={}
update(1)
assert(not table.concat(calls,","):find("new_module",1,true))
update(1)
assert(calls[#calls]=="new_module")
update=function() end
assert(not pcall(factory)) -- Never silently chain around an unknown replacement.
HelldiversBridgeHost=nil
update=function() error("native_failure") end
factory()
local ok,err=pcall(update,0)
assert(not ok and err:find("native_failure",1,true))
print("PASS host isolation, deterministic dispatch, ownership and engine error propagation")
