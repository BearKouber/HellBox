-- Presentation only: plain-number snapshots survive the engine's temporary-vector arena.
return function()
    local center, source, transition, died_at, selected
    local height_pending,height_direction,height_tracking,height_sample,height_stable_at,last_time
    local height_delay,height_tolerance,height_response=0.5,0.03,0.15
    local held={}
    local SNAP=30
    local last_p
    local function reset_height()
        height_pending,height_direction,height_tracking,height_sample,height_stable_at=nil,nil,nil,nil,nil
    end
    local function follow_height(target,now,elapsed)
        local difference=target-center.z
        if not height_tracking then
            if math.abs(difference)<=height_tolerance then reset_height();return center.z end
            local direction=difference>0 and 1 or -1
            if not height_pending or direction~=height_direction then
                height_pending,height_direction=now,direction
            end
            if now-height_pending<height_delay then return center.z end
            height_tracking=true
            height_sample,height_stable_at=target,now
            elapsed=0
        end
        local height=center.z+difference*(1-math.exp(-elapsed/height_response))
        if math.abs(target-height_sample)>height_tolerance then
            height_sample,height_stable_at=target,now
        end
        if now-height_stable_at>=height_delay and math.abs(target-height)<=0.005 then
            reset_height()
            return target
        end
        return height
    end
    local function copy(p) return {x=p.x,y=p.y,z=p.z} end
    local function blend(a,b,t)
        t=math.max(0,math.min(1,t));t=t*t*(3-2*t)
        return {x=a.x+(b.x-a.x)*t,y=a.y+(b.y-a.y)*t,z=a.z+(b.z-a.z)*t}
    end
    return {
        follow=function(id,p,now,ahead,rate)
            local elapsed=last_time and math.max(0,now-last_time) or 0
            if last_time and now<last_time then reset_height();transition=nil end
            last_time=now
            if center and source~=id then
                transition={from=copy(center),time=now}
                reset_height()
            end
            source=id
            -- HellBox 2026-11-19（用户：分屏时自己的镜头跟自己玩一样）：照原版单人镜头（camera_manager.lua follow）——
            -- 目标 = 位置 + 朝向 x 往前多看 + (-1,-1,0)，镜头每秒按 rate（原版 follow_position_interp 0.6）往目标追。
            -- 换载具 / 复活还是作者的 0.5 秒过渡（过渡的终点也是这个目标）；人一帧瞬移超过 SNAP 米直接对准（开车时镜头落后几十米是正常的，不算）。
            local a=ahead or {x=0,y=0,z=0}
            local goal={x=p.x+a.x-1,y=p.y+a.y-1,z=p.z+a.z}
            if transition then
                center=blend(transition.from,goal,(now-transition.time)/0.5)
                if now-transition.time>=0.5 then transition=nil end
            elseif center then
                local dx,dy,dz=goal.x-center.x,goal.y-center.y,goal.z-center.z
                local jx,jy,jz=last_p and p.x-last_p.x or 0,last_p and p.y-last_p.y or 0,last_p and p.z-last_p.z or 0
                if jx*jx+jy*jy+jz*jz>SNAP*SNAP then -- 人 / 载具一帧挪了 SNAP 米以上 = 瞬移
                    center=copy(goal)
                else
                    local k=1-math.exp(-(rate or 0.6)*elapsed)
                    center={x=center.x+dx*k,y=center.y+dy*k,z=center.z+dz*k}
                end
            else center=copy(goal);reset_height() end
            last_p=copy(p)
            return center
        end,
        die=function(now)
            died_at=now;selected=nil;transition=nil;held={}
            reset_height();last_time=nil
        end,
        watch=function(candidates,keys,blocked,now)
            local previous,next_key=false,false
            for _,key in ipairs({'w','a','s','d'}) do
                local down=keys[key]==true
                if down and not held[key] and not blocked then
                    if key=='w' or key=='a' then previous=true else next_key=true end
                end
                held[key]=down
            end
            if now-died_at<2 then return nil,'spectator_wait' end
            if #candidates==0 then selected=nil;return nil,'spectator_no_teammate' end
            local index
            for i,item in ipairs(candidates) do if item.id==selected then index=i;break end end
            index=index or 1
            if previous~=next_key then index=(index-1+(previous and -1 or 1))%#candidates+1 end
            selected=candidates[index].id
            return candidates[index],'spectator_follow'
        end,
        look=function(p)
            if p then center=copy(p);reset_height();last_time=nil end
            return center
        end
    }
end
