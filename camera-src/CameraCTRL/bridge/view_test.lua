local apply=assert(loadfile(arg[1]))()
local width,height=1920,1080
Application={back_buffer_size=function() return width,height end}
local team={rect={x=0,y=0,width=1,height=1},minimum_aspect=1.25,maximum_aspect=16/9}
local display=setmetatable({},{__index=team})
apply(display,team,1333)
assert(display.rect~=team.rect and math.abs(display.rect.width-0.75)<1e-9)
assert(math.abs(display.rect.x-0.125)<1e-9 and display.rect.height==1)
assert(team.rect.width==1 and team.rect.x==0 and team.minimum_aspect==1.25)
width,height=1280,1024
apply(display,team,1778)
assert(math.abs(display.rect.height-0.703125)<1e-9 and display.rect.width==1)
apply(display,team,0)
assert(display.rect.width==1 and display.rect.height==1 and display.minimum_aspect==team.minimum_aspect)
assert(not pcall(apply,display,team,9999))
print('PASS private letterbox geometry, native restore and team viewport isolation')
