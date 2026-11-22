-- HellBox 2026-11-19: own camera follows like the vanilla single-player camera
-- (camera_manager.lua follow: goal = position + forward look-ahead + (-1,-1,0), chase at follow_position_interp per second).
-- The author's original height-filter test is kept as camera_focus_test.author.lua.txt.
local factory=assert(loadfile(arg[1]))()
local function close(actual,expected,tolerance)
    assert(math.abs(actual-expected)<(tolerance or 0.000001),tostring(actual).." ~= "..tostring(expected))
end
local function at(x,y,z) return {x=x,y=y or 0,z=z or 0} end

-- first frame: straight onto the goal (vanilla offset -1,-1)
local focus=factory()
local c=focus.follow("player",at(10,5,2),0)
close(c.x,9);close(c.y,4);close(c.z,2)

-- standing still: stays put
c=focus.follow("player",at(10,5,2),1)
close(c.x,9);close(c.y,4)

-- a 10 m step: after 1 s the camera has covered 1-exp(-0.6) of it, not all of it (not locked)
focus=factory()
focus.follow("player",at(0),0)
for i=1,60 do c=focus.follow("player",at(10),i/60) end
close(c.x,-1+10*(1-math.exp(-0.6)),1e-6)
assert(c.x<9)

-- frame-rate independent
local function run(rate)
    local f=factory();f.follow("player",at(0),0)
    local r
    for i=1,rate do r=f.follow("player",at(10),i/rate) end
    return r.x
end
close(run(30),run(60),1e-9);close(run(60),run(144),1e-9)

-- custom rate from the game is used
focus=factory()
focus.follow("player",at(0),0)
c=focus.follow("player",at(10),1,nil,10)
close(c.x,-1+10*(1-math.exp(-10)))

-- look-ahead moves the goal forward
focus=factory()
c=focus.follow("player",at(0),0,{x=5,y=0,z=0})
close(c.x,4);close(c.y,-1)

-- running with look-ahead: the steady state keeps the player near the middle instead of dragging behind
focus=factory()
local speed=5
for i=0,600 do
    local t=i/60
    c=focus.follow("player",at(speed*t),t,{x=speed*2,y=0,z=0}) -- vanilla: not aiming = |velocity| * 2
end
local lag=speed*10-(c.x+1)
assert(math.abs(lag)<2,"running lag "..lag)

-- teleport (> 30 m in one frame): snaps
focus=factory()
focus.follow("player",at(0),0)
c=focus.follow("player",at(100),0.016)
close(c.x,99)

-- fast vehicle: being far behind is not a teleport (no snapping every frame)
focus=factory()
focus.follow("vehicle",at(0),0)
local prev
for i=1,240 do
    local t=i/60
    c=focus.follow("vehicle",at(25*t),t)
    if prev then assert(c.x-prev<1,"no jump") end
    prev=c.x
end
assert(25*4-(c.x+1)>20,"camera lags behind a fast vehicle like vanilla")

-- switching anchor (boarding): 0.5 s blend from where the camera was
focus=factory()
focus.follow("player",at(0),0)
focus.follow("player",at(0),0.1)
c=focus.follow("vehicle",at(10),0.2)
close(c.x,-1)
c=focus.follow("vehicle",at(10),0.45)
close(c.x,-1+10*0.5)
c=focus.follow("vehicle",at(10),0.71)
close(c.x,9)

-- death, spectate a teammate, respawn: blend back to self
focus=factory()
focus.follow("player",at(0),0)
focus.die(1)
close(focus.look(nil).x,-1)
close(focus.look(at(50)).x,50)
c=focus.follow("respawn",at(0),3)
close(c.x,50)
c=focus.follow("respawn",at(0),3.51)
close(c.x,-1)

-- clock reset (new mission): no crash, no jump
focus=factory()
focus.follow("player",at(0),10)
c=focus.follow("player",at(1),2)
assert(c.x>=-1 and c.x<=0)
print("PASS vanilla follow: offset, chase rate, frame rates, look-ahead, teleport, vehicle, boarding, death, clock reset")
