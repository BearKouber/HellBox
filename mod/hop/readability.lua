return function(config,hooks)
    -- 2026-11-21 HD1-038：来自 QoL 的四项（玩家列表字体、名字字体、潜兵轮廓、HUD 透明度）删了，只留半糖自己的名字深色底和长文字不截断
    -- 2026-11-26 用户：名字深色底删了（「这个删除了」）；长文字截断留着，开关改名「名字不乱码」，同一个开关还管字体缺字（src/hellbox_name_font.lua）
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
    return function()
        local ready=true
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
