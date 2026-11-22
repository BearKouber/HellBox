# BridgeCore

Helldivers 1 共用的资源安装库和游戏线程调度器，不依赖 CaptainHelldiver 或 CameraCTRL。

两个应用分别静态链接本库、内嵌自己的 LuaJIT 模块；用户只需相应 exe，无需单独部署库、Python 或 LuaJIT。

见 [共享桥接与模块独立安装](../docs/20-共享桥接与模块独立安装.md)。
