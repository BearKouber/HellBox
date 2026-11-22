return function(config,hooks)
    -- 2026-11-21 HD1-038：来自 QoL 的四项（玩家列表字体、名字字体、潜兵轮廓、HUD 透明度）删了，只留半糖自己的名字深色底和长文字不截断
    local function trim(text,width,measure)
        if type(text)~="string" or not Utf8.valid(text) or width<=0 then return "" end
        if measure(text)<=width then return text end
        if measure("...")>width then return "" end
        local ends={0}
        for i=2,#text do
            local byte=string.byte(text,i)
            if byte<128 or byte>=192 then ends[#ends+1]=i-1 end
        end
        ends[#ends+1]=#text
        local low,high,best=1,#ends,0
        while low<=high do
            local middle=math.floor((low+high)/2)
            if measure(text:sub(1,ends[middle]).."...")<=width then best=ends[middle];low=middle+1
            else high=middle-1 end
        end
        return text:sub(1,best).."..."
    end
    -- 颜色拆成（透明度, 红, 绿, 蓝）。2026-11-21 HellBox 修：
    -- 游戏里 Color(...) 造出来的颜色不能用 color.w 读（读到空值，HUD 透明度一开进任务就闪退），
    -- 原版读法是 Quaternion.to_elements，第一个数是透明度【源码 hud.lua:1742/1753】；
    -- 存在表里的颜色（QuaternionAux.box_elements）才是 x=透明度、y/z/w=红绿蓝。
    local function color_parts(color)
        if color==nil then return nil end
        if type(color)=="table" then return color.x,color.y,color.z,color.w end
        local ok,a,r,g,b=pcall(Quaternion.to_elements,color)
        if ok and type(a)=="number" then return a,r,g,b end
    end
    local function color_alpha(color)
        return (color_parts(color))
    end
    return function()
        local ready=true
        if config.name_background=="1" then
            ready=hooks.wrap("Hud","draw_player_name_in_world","name_background",function(native)
                return function(self,...)
                    local gui=self.hd_gui
                    if not gui then return native(self,...) end
                    local create,update=gui.create_text,gui.update_text
                    local function background(text,position,color,font,size)
                        if type(text)~="string" or text=="" or not position then return end
                        local font_size=size or gui.current_font and gui.current_font.font_size
                        if type(font_size)~="number" then return end
                        local width,height=gui:get_text_extents(text,font,font_size,true)
                        if type(width)~="number" or type(height)~="number" then return end
                        gui:rect(Vector3(position.x-3,position.y-3,position.z-1),Vector2(width+6,height+6),
                            Color((color_alpha(color) or 255)*0.6,0,0,0))
                    end
                    local args={n=select("#",...),...}
                    return hooks.scoped(gui,"create_text",function(target,text,position,color,font,size,...)
                        background(text,position,color,font,size)
                        return create(target,text,position,color,font,size,...)
                    end,function()
                        return hooks.scoped(gui,"update_text",function(target,id,text,position,color,font,size,...)
                            background(text,position,color,font,size)
                            return update(target,id,text,position,color,font,size,...)
                        end,function() return native(self,unpack(args,1,args.n)) end)
                    end)
                end
            end) and ready
        end
        if config.long_text=="1" then
            for _,spec in ipairs({{"draw_selection_scroll","get_text_bounds","draw_text"},
                {"draw_selection_scroll_hd_gui","get_text_extents","text"}}) do
                local method,measure,draw=unpack(spec)
                ready=hooks.wrap("MenuScreenBase",method,"long_text",function(native)
                    return function(self,gui,z,pos,text,width,selected,...)
                        if selected or type(text)~="string" or not Utf8.valid(text) then
                            return native(self,gui,z,pos,text,width,selected,...)
                        end
                        local clipped=trim(text,width,function(value) return gui[measure](gui,value) end)
                        return gui[draw](gui,clipped,Vector3(pos.x,pos.y,z))
                    end
                end) and ready
            end
        end
        return ready
    end
end
