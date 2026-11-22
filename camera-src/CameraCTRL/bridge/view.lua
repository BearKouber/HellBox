-- Private viewport geometry. Never mutate the team viewport's rect or limits.
return function(display,team,permille)
    if not team.rect then return end
    local rect={}
    for key,value in pairs(team.rect) do rect[key]=value end
    display.rect=rect
    display.minimum_aspect,display.maximum_aspect=team.minimum_aspect,team.maximum_aspect
    if not permille or permille==0 then return end
    assert(permille==1250 or permille==1333 or permille==1600 or permille==1778,"invalid_personal_aspect")
    local ratio=({[1250]=5/4,[1333]=4/3,[1600]=16/10,[1778]=16/9})[permille]
    local width,height=Application.back_buffer_size()
    assert(width>0 and height>0,"invalid_back_buffer")
    display.minimum_aspect,display.maximum_aspect=ratio,ratio
    if width/height>ratio then
        rect.width,rect.height=height*ratio/width,1
        rect.x,rect.y=(1-rect.width)/2,0
    else
        rect.width,rect.height=1,width/ratio/height
        rect.x,rect.y=0,(1-rect.height)/2
    end
end
