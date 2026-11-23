HellBox V1.09
=============

作者：07
发布页（下载新版、看更新、反馈问题）：https://www.nexusmods.com/helldivers/mods/63
也可以在 GitHub 下载：https://github.com/BearKouber/HellBox/releases

HELLDIVERS（1 代）MOD 工具：带箱子上车、给好友点赞、刷新星球、报复关数量、
选图（报复关 / 大图 / 首领战）、玩法（试炼场联机版、修正参数、武装配置、鬼城）、
数据修改（怪物属性 / 出怪逻辑）、各种显示、指针颜色、快捷语音、战绩等（选图、分屏在开发者模式里）。

【V1.09 改了什么】（和 V1.08 比）
- 修复游戏开着时改名、改角色设置报「打不开游戏进程」：写游戏内存漏传了进程句柄。
- 修复 HellBox 自己被打成 Medium 完整性级别、拿不到游戏写权限（目录被加了强制标签）。
- 设置文件改成直接写入，不再走临时文件换名。
- 文案：玩法页、昵称页描述改为「游戏运行时可修改」；「全队」改「共享」，「装了就有」改「客机需装」；
  「带箱子上车」「丢支援装备」「补给背包自己用」去掉「当客机时」那句；「先丢哪个」改「看手上：优先丢手持装备。」；
  数据页等待提示去掉括号说明。

【V1.08 改了什么】（和 V1.07 比）
- 玩法页：试炼场目标描述移进框里，hover 只留不能开的原因；修正参数补回军刀、鬼城排第一；条件文案按用户给的改。
- 用词：试验场改试炼场，赛博人改生化人，光能族改光能者。
- 修复保存设置时的权限问题：hop.txt、ghost-maps.txt、play.txt 等改成直接写入，失败时走 PowerShell 兜底。
- 修复窗口被强制置顶 / 抢焦点。

【V1.07 改了什么】（和 V1.06 比）
- 界面文字整体整理（感谢 Oct0pu5）：用词更统一、说明更短，卡片标题更简洁；「关于」鸣谢加「文本 Oct0pu5」。
  · 玩法页修正参数改名：超级地球支援（原随机掉落）、电磁干扰、命中补给、精确打击、侦察兵、以牙还牙、军刀；填弹惊喜改叫换弹惊喜。
  · 选「鬼城」环境时才显示无人机探照灯、战备信标更亮两行。
  · 底栏「完成」提示过 8 秒自动回到「就绪」。
- 房间名统一为「[HellBox] 名字」（不再写 [Hex]、玩法个数、炼狱）。
- 联机限制：带箱子上车、丢支援装备、补给背包自己用、自动定位任务位置、分屏这几项，
  当客机时只在房主也装了 HellBox（或开着分屏 CameraCTRL）的房间生效，进普通房间不生效；
  自己当房主、单机、本机多人照常用。

【V1.06 改了什么】（和 V1.05 比）
- 「功能」页「解锁其他战线」改成选一种：关 / 普通星区 / 进攻母星 / 保卫超级地球（再选是哪个种族打过来）。
  · 普通星区：和以前一样，没开放的战线也能选。
  · 进攻母星：三个种族的母星和那 5 关（难度 3～15）直接出来，不用等进攻事件。
  · 保卫超级地球：超级地球的防守关直接出来。
  · 这两种星球也能用刷新键重抽 5 关；报复关数量照样管。
  · 这些关只在自己游戏里打，结果不报给服务器，不算进银河战争；结算按普通任务算（没有事件的双倍经验）。
  · 游戏开着也能切，退出战役地图再进一次生效。

【V1.05 改了什么】（和 V1.04 比）
- 「功能」页「解锁其他战线」发布版也有了：没开放的战线也能选（还没出场的、已攻破的都算）。
- 「功能」页「过场加速」回来了（借鉴 QoL Mod）：结算、进关过场、星球扫描按 ×2～×5 快放，开着时跳过开游戏的片头。
  能和 QoL Mod 一起装。
- 「报复关数量」母星那 5 关也照设置来了（以前打到母星时这个设置不准）；难度 3 那关不会是报复关。
- 选图：游戏关着时点「开始」，现在是正常在线开游戏，进到飞船后自动开这张图（一个人直接进关，有队友就设为下一局）。
  以前这样开会进离线。
- 程序文件夹里少了一个套着的压缩包（_internal 里的 base_library.zip 改成散放的文件），HellBox.exe 右键属性能看到版本信息。
  目录和用法都没变。

【V1.04 改了什么】（和 V1.03 比）
- 房间名改短了，找房间列表里一眼能看懂：
  · 只开了自己用的功能：「[HellBox] 名字」。
  · 开了玩法、改了数据、带箱子上车或丢支援装备：「[Hex] 名字」。
  · 方括号里：鬼城写出来，其他玩法只写个数（「鬼城 +3」，没有鬼城就是「玩法 +2」）；
    敌人改得比原版难（敌人数量、场上上限、怪物属性任何一项超过原版）再写「炼狱」。
    例：[Hex · 鬼城 +3 · 炼狱] 小明的房间。「隐藏 HellBox 房间」筛选也认 [Hex]。
- 选地形改成点地图挑：点小地图，这一组所有不同的图一次列出来，点哪张换哪张。
  · 选图（开发者模式）：编号和「换一张图」去掉（报复关每个种族 + 环境只有两块场地，就只有两张）。
  · 玩法页「试炼场」：地形编号和「换一张」去掉，换成小地图。
  · 要开着游戏才能把图拼出来。
- 来自 Dive Harder 的两项改名「HUD 显示延迟」「自动定位任务位置」；装了 Dive Harder 时那几行写「此项已由 DH 提供」。
- 「关于」鸣谢里 Dive Harder 后面的括号说明、「Bug 修复」标题旁的说明去掉了。

【V1.03 改了什么】（和 V1.02 比）
- 能和 QoL Mod、Dive Harder 一起装：只有 HellBox、加 QoL、加 Dive Harder、三个都装都行，谁也不盖掉谁。
  先装后装都可以，换了组合 HellBox 自己发现、关游戏后自动重装。「恢复原版」只拿掉 HellBox 自己的东西，
  QoL 和 Dive Harder 的文件不动。
- 去掉了以前借鉴 QoL Mod 的功能（QoL 作者希望各自独立、能一起装）。想用这些功能，请装正版 QoL Mod。
  刷新星球、报复关数量、解锁战线、快捷语音这些 HellBox 自己做的照旧。
- 新加（来自 Dive Harder，作者 Oct0pu5 同意收录）：HUD 显示延迟、自动定位任务位置、
  好友列表自动刷新、配合 QoL 的两处修正。游戏里装着 Dive Harder 时，这几项交给它。
- 找房间的「筛选」里多一条「隐藏 HellBox 房间」，和游戏自带的筛选一样能开能关（默认不隐藏）。
- 「昵称」页：房间名可以选「[HellBox] 名字」还是「名字 [HellBox]」。
- 给人点赞：同一个人每周只能点一次（好友、路人都算）。

【V1.02 改了什么】（和 V1.01 比）
- 修好：开着「显示 → HUD 透明度」进任务就闪退；名字深色底现在跟着名字一起淡出。
- 去掉：战备信标落地时信标周围那个颜色奇怪、慢慢缩小的光圈。
- 玩法页：填弹惊喜改成「修正参数」里的一张卡片（排第一个）；新修正参数「副武器换成军刀」：手枪那一格换成军刀（装了才有）。
- 「关于」页加「源码」一行，点开就是 GitHub。
- HellBox 开源了（MIT 授权）：源码在 GitHub（github.com/BearKouber/HellBox），授权说明见 LICENSE.txt。
- 分屏不再需要单独的程序（CameraCTRL-bridge.exe），由 HellBox 自己装进游戏，效果不变。

【V1.01 改了什么】（和 V1.0 比）
- 新「显示」页（游戏开着也能改，下一秒生效）：
  · 军械库和百科显示真实数值和护甲、身上真的在生效的状态、被混乱打中时的操作反转提示、空降时显示每个人的配装。
  · 名字更好认（聊天字体、深色底、玩家列表、长名字不乱码）。
  · 潜兵一直有轮廓、HUD 透明度、镜头震动、电弧光束变细、界面缩放放大、PS 手柄图标、按键说话图标、
    装备预览不变形、藏起「按 A 加入」。
- 「功能」页新加：
  · 起身和终端改成长按 / 连按、手柄切枪互换、鼠标滚轮动作、建构连续装填、禁止本机再加人。
  · 重置解锁时连升级一起清。
  · 屏蔽的人进不了房（你找房间时，他们在的房间也不显示）、选房按任务 / 奖励筛选、好友列表显示房间名、
    推荐任务队友也看得到、中途加入多给选装备时间。
  · Bug 修复 7 项，每项单独开关：搬东西上车不闪退、任务物品卡高处拿回来、护送幸存者不卡死、空降聊天不错名、
    星球和排行榜不卡住、电弧枪充能不少算、跳过训练连教学对话一起跳。
- 「语音」页新加：快捷语音冷却、换弹语音别太吵。
- 「玩法 → 环境」新加两盏鬼城的灯（只在鬼城亮，亮度都能调，只有你自己电脑上看得到）：
  · 蜜蜂无人机光圈：叫下来蜜蜂型无人机时，你头顶一盏白光灯照亮脚边一圈，无人机来时慢慢亮、走时慢慢暗。
  · 战备信标更亮：落地亮起来的战备信标照得更亮更远，用完后慢慢暗回原样。
- 每个功能下面写了来源（来自 QoL Mod、来自 半糖（HalfSugar）等）。
- 装法改了：不再整份替换游戏文件，改成游戏文件旁边的补丁（contents 里的 xxxx.patch_0），游戏原文件保持原版，
  鬼城地图也不用再备份 1.3GB。以前装过 HellBox 的，打开新版（游戏要关着）会自动换成新装法：
  照备份把原文件换回原版再放补丁，45 张地图约一两分钟，换完再开游戏。
- 能和 Obsidian（Alomare 的 MOD 管理器）一起装：两边的补丁谁也不删谁；被 Enhanced Visuals 换过光照的地图，
  鬼城在那里是夜晚的样子。「功能」页顶上会写两边一起用时的说明。
- 「关于」页鸣谢加：QoL Mod 作者 SomeDogge。
- 注意：换成 V1.01 以后别再打开旧版 HellBox（它认不出新装法，会又把游戏文件整份换掉）。

【V1.0 的 2026-11-20 修复】
- 修好开着 HellBox 进丛林、雪地普通任务直接闪退到桌面（自己开或进别人房间都会）。
  原因是鬼城配色里引用了这两种地图没有的贴图，现在改用这张地图自己夜晚的贴图，鬼城照样有。
  打开新版 HellBox（游戏要关着）会自动把地图文件重换一遍，底栏显示「鬼城地图：几 / 45」，换完再开游戏。
- 在别人房间里时，我们改的数据（武器 / 战备 / 潜兵 / 怪物属性）在结算画面、飞船、出发界面也一律不生效
  （以前打完一局在结算画面就套回去了）。回到自己当房主照常生效。
- 打开「核心」时指针保持游戏原版（以前会自动变成绿色）；在「指针」页改过的照你的设置装，
  关掉「核心」再打开也会记得。

【V1.0 改了什么】（和 V1.0pre 发行抢先版比）
- 版本改成 V1.0 正式版。
- 「功能」页新加：
  · 补给背包自己用（来自 Lhgrzr）：背着补给背包时给自己补一次弹药，背包少一格，
    会做一下原本从背包拿弹药的动作（约 1 秒，这时收枪）。
    键盘按主键盘数字键（字母上面那排，4～9 可选，默认 5；小键盘不算）；手柄按住换弹键 0.6 秒（换弹照常换）。
    弹药满了、背包空了不扣次数；倒地、搬箱子、坐车、打字时不会触发。
  · 隐藏样本描边（来自 Lhgrzr）：地上样本外圈的发光轮廓不显示，样本照样看得见、捡得起，侦察装备标样本照常。
  · 聊天输入法防闪退（来自 HalfSugar，默认开）：原版换房间后第一次在聊天框用中文输入法打字可能直接闪退，开了就不会；
    关聊天时顺手清掉输入法残留，免得输入法卡住键盘。
  · 「过场加速」开着时，开游戏时的片头动画直接跳过（视频没法快放，只能跳）。
- 分屏时自己的镜头改成和原版单人一样跟随：镜头稍慢一拍跟上，并往你面朝 / 跑动的方向多看一点
  （以前是死锁在人头顶上，跟得太紧）；爆炸、空袭等的镜头震动也和原版一样有了。上下载具、复活的过渡和死后看队友照旧。
- 开发者模式的「训练」页改名「选图」，并且能多人玩了：
  · 在飞船上当房主点「开始」：一个人（或本机分屏）照旧直接进关。
  · 房间里有联机队友时变成「设为下一局」：照常走进出发舱出发就是这张图，队友不用装 HellBox，
    大家照常记经验和银河战争；打完回到飞船，原来的星球自动放回去，不会把这一关算成那颗星球的任务。
    想取消就在星图上选别的星球。和「玩法」页的试炼场「设为下一局」只能二选一，设选图时会自动取消那边的。
  · 战绩里的「原版训练 / 自定义训练」改叫「原版选图 / 自定义选图」。
- 「关于」页鸣谢：单开一行写 HalfSugar 的功能贡献（分屏、聊天输入法防闪退）；协助测试加 Kent、QiQi。

【V1.0pre 发行抢先版改了什么】（和 V0.99 比）
- 名字改成 V1.0pre（1.0 预览版），不再叫群友测试版。
- 分屏换成半糖（HalfSugar）的新版 CameraCTRL：
  · 新加「画面比例」：跟随游戏 / 16:9 / 16:10 / 4:3 / 5:4，只改自己的镜头，多出的地方留黑边，
    不改分辨率、不拉伸，也不改队友的画面范围。要先开「解除视角限制」。
  · 上坡下坡时镜头高度会平滑跟上（短暂踩高不会晃）。
  · 修了队友中途加入后房主的「解除位置限制」失效、人质走到避难所后还往门外走（作者说还要联机验证）。
- 出关回飞船进舱门偶尔闪退：加了保护（原版出发倒计时的空值报错）。
- 房间名只在内容变化时写、只在进舱门前写（关卡里不再改房间名）。
- 「潜兵」页（等级、武器解锁、披风）挪进开发者模式，平时看不到。
- 开发者模式「怪物属性」里，坦克的「投放单位」、刺钉虫触手、投掷物这些选怪 / 选弹的下拉框，
  现在只列这个种族自己的（一张图只加载一个种族，选别的种族会闪退）。以前存的块里如果有别的种族的，
  进游戏会自动跳过。它和「出怪逻辑」的「坦克屁股出兵」管同一件事：那边设了就以那边为准。
- 「关于」页加了作者、鸣谢名单、声明；借鉴别人的功能，在那个功能下面用小字写了来源。
- 发行抢先版新改的：
  · 选星球界面按刷新键，只刷新当前这个阵营，另外两个阵营不动（HellBox 里的「现在刷新」还是三个全刷）。
  · 刷新星球时「检测威胁」那段扫描动画的加速，之前没生效，修好了。
  · 鬼城：没装 HellBox 的人进鬼城房间不会再让房主闪退（他们看到的是正常光照）；开鬼城自动去掉挡视线的雾。
  · 队友关了「跟随房主的玩法」、自己换了装备时，房主的选装备界面会显示队友真正选的。
  · 「丢支援装备」可以选先丢武器还是先丢背包。
  · 随机掉落只能选你自己解锁了的战略配备，没解锁的灰掉，以前勾上的也不会掉。
  · 武装配置「固定」格的下拉框只显示你已解锁的；以前存下的没解锁的那格，游戏里当「自由」。
  · 机枪 Mk3 升级上那行「需要激光大炮 Mk2」的红字是原版就有的，不是 MOD 造成的，没改。
  · 游戏装了 Dive Harder 时，打开「核心」会直接说明 HellBox 不能和它一起用（以前弹的是一行乱码
    「分屏模块叠不进去」）。先卸载 Dive Harder，或在 Steam 里验证游戏文件完整性，再打开「核心」。
  · 鬼城的雾再修了一次：上一版只推远了起雾距离，这次把盖在整张图上的那层飘动的亮蓝灰尘也关了（照训练场鬼城的设置）。
  · 第一次打开「核心」快了很多（多核一起压缩），底栏显示「鬼城地图：几 / 45」。
    第一次打开会问要不要备份原版地图：备份（多占约 1.3GB、慢一些，以后在「关于」关掉「核心」一键恢复原版）
    或不备份（快很多，以后要恢复原版地图用 Steam「验证游戏文件完整性」）。已经备份过的不会再问。
  · 开着 MOD 进别人的房间（当客机）：数据修改（怪物、出怪、武器、战略配备、潜兵）全部不生效、按原版，回到自己的房间再套上；
    功能（丢装备、换弹不滑、加速等）照常。
  · 分屏还在调整，先挪进开发者模式：平时看不到「分屏」页，游戏里也不开分屏（设置保留，开开发者模式就照原来的来）。
  · 「训练」页（V1.0 改名「选图」）也挪进开发者模式。
  · 「关于 · 设置」里加了「K-ON!增强UI定制版」开关：开着时左边只有 功能 / 玩法 / 数据 / 指针 / 关于 五页
    （开着开发者模式也一样），只是界面变简单，已经设好的功能照常生效。
  · 加了闪退探针：游戏没正常退出（闪退）时，HellBox「日志」页会记下闪退前停在哪一步，报问题时一起发过来。

【怎么用】
1. 把整个文件夹解压到任意位置（桌面、D 盘都行），最好是一个新文件夹，别解压进旧版 HellBox 里面。
   不要放进 C:\Program Files，那里程序没法写文件。
2. 双击 HellBox.exe。右上角 CN / EN 切换中英文。
3. 第一次用：先关掉游戏，到左下角「关于」页打开「核心」开关（第一次要几分钟，机械硬盘更久）。
   装好后开游戏就生效。
   之后大部分设置游戏开着也能改。
4. 核心没开或者出了问题，右上角会出现红色提示，点它就能跳过去处理。
5. 开发者模式：在「关于」页的版本号上连点 10 次打开。打开后数据页能细改，左边多出「选图」「分屏」「潜兵」「日志」。

【第一次打开时 Windows 拦截】
程序没有付费的数字签名，Windows 可能弹出蓝色的「Windows 已保护你的电脑」。
点「更多信息」→「仍要运行」即可，之后不会再问。
如果杀毒软件误报，可以把 HellBox 文件夹加进信任 / 排除列表。

【显示「认不出游戏文件」】
说明游戏文件被别的 MOD 或其他版本的 HellBox 改过（QoL Mod、Dive Harder 不算，能一起用）。
到「关于」页，点「游戏文件认不出」那一行的「恢复原版」：有原版备份就直接换回；
没有就会让 Steam 检查修复游戏文件（一两分钟）。

【卸载】
1. 关游戏，在「关于」页把「核心」开关关掉（游戏恢复原版）。
2. 删掉 HellBox 文件夹。
   设置和原版备份在 %APPDATA%\Arrowhead\Helldivers\hellbox，也可以一起删。

【出问题了】
到「关于」页点「复制诊断信息」，反馈问题时直接粘贴。

【鸣谢】
- 外层 UI 设计：91
- 高难增强数据指导：吃大份
- 分屏、聊天输入法防闪退：HalfSugar
- 协助测试：91、HalfSugar、吃大份、K-ON!、Kent、QiQi
- 总体 UI 规划、代码设计：Claude
- QoL Mod：SomeDoggo
- Dive Harder：Oct0pu5
- 分屏来自 HalfSugar 的 CameraCTRL（经作者同意收录）；补给背包自己用、隐藏样本描边来自 Lhgrzr；
  HUD 显示延迟、自动定位任务位置、好友列表自动刷新、配合 QoL 的修正来自 Dive Harder（Oct0pu5，经作者同意收录，MIT 授权）。

【声明】
- HellBox 完全免费，按 MIT 授权开源，源码在 GitHub（github.com/BearKouber/HellBox）。如果你是花钱买到的，请找卖家退款。
- 可以自由修改、再发布，但请保留作者 07 的署名和授权说明（LICENSE.txt），并注明原发布页
  （https://www.nexusmods.com/helldivers/mods/63）。
- 收录的别人的作品（比如分屏、半糖的优化功能、Dive Harder 的几项）归原作者，转发时请一并注明。
- 非官方 MOD，和游戏官方无关。用 MOD 有风险，出了问题可以用「关于」页的「恢复原版」。
- 用到的开源组件：Python、PySide6 / Qt（LGPL-3.0）、LuaJIT、Silkscreen 字体，授权说明见 LICENSE.txt。

【写在最后】
希望大家能在游戏里找到它本身的乐趣，也希望这个工具能让你玩得开心。
请不要滥用，不要影响别的玩家的体验。
—— 07

--------------------------------------------------------------

HellBox V1.07

Author: 07
Home page (new versions, changelog, feedback): https://www.nexusmods.com/helldivers/mods/63

A mod tool for HELLDIVERS (the first game): carry boxes into vehicles, commend friends, refresh planets,
retaliation mission count, Map Select (retaliation / big maps / boss fights), game modes (online Proving
Grounds, modifiers, loadout rules, Ghost Town), data edits (enemies / spawn logic), more displays, cursor color, quick
voice, mission stats and more (Map Select and split screen are in developer mode).

WHAT'S NEW IN V1.07 (since V1.06)
- Interface text cleaned up throughout (thanks to Oct0pu5): more consistent wording, shorter descriptions,
  simpler card headers; "Text: Oct0pu5" added to the credits.
  * Modifier names on the Modes page: Super Earth Support (was Random Drops), EM Interference, Ammo on Hit,
    Precision Strike, Scout, Eye for an Eye, Saber; Reload Surprise keeps its name.
  * The drone searchlight / brighter beacon rows only show when the Ghost Town environment is selected.
  * The "Done" message in the footer goes back to "Ready" after 8 seconds.
- Room names are always "[HellBox] name" now (no more [Hex], mode counts or Inferno).
- Guest restriction: carrying boxes into vehicles, dropping support gear, self-resupply, auto-locating objectives
  and split screen only work as a guest in rooms whose host also runs HellBox (or has CameraCTRL split screen on);
  they do nothing in other rooms. As host, solo or in local co-op they work as before.

WHAT'S NEW IN V1.06 (since V1.05)
- "Unlock other fronts" (Features page) is now a choice: Off / Normal sectors / Attack homeworld / Defend Super
  Earth (then pick which race is attacking).
  * Normal sectors: same as before, fronts that aren't open can be picked.
  * Attack homeworld: the homeworlds of all three races and their 5 missions (difficulty 3 to 15) appear right away,
    no need to wait for an attack event.
  * Defend Super Earth: the Super Earth defence missions appear right away.
  * These planets can be rerolled with the refresh key too; the retaliation mission count still applies.
  * These missions are only played in your own game. Results are not sent to the server and don't count toward the
    Galactic War; the results screen treats them as normal missions (no event double XP).
  * Can be switched while the game runs; leave and reopen the war map to apply.

WHAT'S NEW IN V1.05 (since V1.04)
- "Unlock other fronts" (Features page) is now in the public release: fronts that aren't open can be picked
  too (ones that haven't appeared yet and ones already lost).
- "Faster cutscenes" is back (Features page, based on QoL Mod): results, mission intros and planet scans play
  at x2 to x5, and the intro videos at game start are skipped. Works together with QoL Mod.
- "Retaliatory strikes" now also applies to the 5 homeworld missions (it wasn't reliable there before); the
  difficulty 3 one is never a strike.
- Map Select: clicking Start while the game is closed now starts the game online as usual, and the map opens by
  itself once you reach the ship (alone: straight in; with teammates: it becomes your next mission). Before, starting
  this way put you offline.
- One nested archive fewer in the program folder (_internal\base_library.zip is now loose files), and HellBox.exe
  shows version info in its file properties. Same folders, same use.

WHAT'S NEW IN V1.04 (since V1.03)
- Shorter room names that read at a glance in the room list:
  * Only features for yourself: "[HellBox] name".
  * Play modes, data changes, carrying boxes into vehicles or dropping support gear: "[Hex] name".
  * Inside the brackets: Ghost Town is written out, other modes only as a count ("Ghost Town +3", or "Modes +2"
    without Ghost Town); "Inferno" is added when enemies are harder than vanilla (enemy count, on-field cap or any
    enemy stat above vanilla). Example: [Hex · Ghost Town +3 · Inferno] Bob's room. The "Hide HellBox games" filter
    also recognises [Hex].
- Terrain is now picked by clicking the map: every different map of the current kind is listed, click one to use it.
  * Map Select (developer mode): the map number box and "New map" are gone (Retaliation has only two arenas per
    race + environment, so only two show).
  * Play page, Proving Grounds: the terrain number and "New" are replaced by a map.
  * The game has to be running to build the maps.
- The Dive Harder rows are now called "Ping on HUD" and "Auto-locate objectives"; with Dive Harder installed they
  say "Provided by Dive Harder".
- About: the bracketed note after Dive Harder in the credits and the note next to "Bug fixes" are gone.

WHAT'S NEW IN V1.03 (since V1.02)
- Works together with QoL Mod and Dive Harder: HellBox alone, with QoL, with Dive Harder, or all three. Install them in
  any order; HellBox notices a change and reinstalls itself after you close the game. "Restore vanilla" removes only
  HellBox's own files and never touches QoL or Dive Harder.
- Removed the features that were based on QoL Mod (its author prefers the mods to stay separate and work together).
  If you want them, install the real QoL Mod. HellBox's own features (refresh planets, retaliation mission count,
  unlock fronts, quick voice and so on) stay.
- New, from Dive Harder (included with the permission of its author, Oct0pu5): ping on HUD,
  auto-locate objectives, friends list auto-refresh, two fixes for QoL Mod. If Dive Harder is installed in
  the game, these are left to it.
- The room browser's Filters list has a new "Hide HellBox games" entry that works like the game's own filters
  (off by default).
- Names page: choose whether the room name reads "[HellBox] name" or "name [HellBox]".
- Commends: you can commend the same player only once per week (friends and strangers alike).

WHAT'S NEW IN V1.02 (since V1.01)
- Fixed: entering a mission with Display > HUD opacity on crashed the game. Name plates now fade with the name.
- Removed: the odd-coloured, shrinking ring around a stratagem beacon when the drop lands.
- Modes page: Reload Surprise is now a card in Modifiers (first one); new modifier "Saber Sidearm": your pistol slot
  gets a saber (HellBox players only).
- About page: new "Source code" row that opens GitHub.
- HellBox is now open source (MIT license): the source code is on GitHub (github.com/BearKouber/HellBox);
  see LICENSE.txt.
- Split screen no longer needs a separate program (CameraCTRL-bridge.exe); HellBox installs it into the game
  itself. It works the same.

WHAT'S NEW IN V1.01 (since V1.0)
- New Display page (can be changed while the game runs; applies within a second):
  * Real numbers in the armory and armor in the encyclopedia, statuses really active on you, a hint whether
    confusion really reversed your controls, everyone's loadout during the drop.
  * More readable names (chat font, dark plate, player list, no garbled long names).
  * Always-on helldiver outlines, HUD opacity, camera shake, thinner arc beams, larger UI scale, PlayStation icons,
    push-to-talk icon, undistorted loadout preview, hide "Press A to join".
- New on the Features page:
  * Hold or mash for getting up and terminals, swap controller weapon switch, mouse wheel actions, Constitution
    continuous reload, block extra local players.
  * Reset upgrades together with unlocks.
  * Keep blocked players out (and hide the rooms they are in when you look for rooms), filter rooms by mission /
    reward, room names in the friend list, mission suggestions visible to the team, more loadout time when joining.
  * 7 bug fixes, each with its own switch: no crash carrying items into vehicles, recover stuck mission items,
    no stuck survivor escort, correct chat names during drop, no planet / leaderboard lockup, full arc charge on
    release, skip tutorial dialogue with training.
- New on the Voice page: callout cooldown, quieter reload lines.
- Play > Environment: two Ghost Town lights (Ghost Town only, adjustable brightness, visible on your PC only):
  * Humblebee drone halo: while a Humblebee UAV drone is out, a white light above your head lights up the ground
    around you; it fades in as the drone arrives and out as it leaves.
  * Brighter stratagem beacons: landed, lit-up stratagem beacons glow brighter and reach further, fading back when used up.
- Each feature shows where it comes from (QoL Mod, HalfSugar, ...).
- New install method: HellBox no longer replaces whole game files. It adds patch files next to them (xxxx.patch_0 in
  contents), the original files stay vanilla, and the Ghost Town maps no longer need a 1.3 GB backup. If you had
  HellBox installed before, open the new one with the game closed: it switches over automatically (restores the
  original files from the backup, then adds the patches; about a minute or two for the 45 maps).
- Works alongside Obsidian (Alomare's mod manager): neither deletes the other's patches; on maps whose lighting
  Enhanced Visuals changed, Ghost Town looks like night. The Features page explains this when both are installed.
- Credits on About: SomeDogge (QoL Mod) added.
- Note: after switching to V1.01, don't open an older HellBox again (it doesn't know the new method and would replace
  the game files again).

V1.0 FIX 2026-11-20
- Fixed: with HellBox installed, Jungle and Snow normal missions crashed straight to desktop (hosting or joining).
  The Ghost Town lighting referenced textures those maps don't have; it now uses the map's own night textures,
  so Ghost Town still works. Open the new HellBox with the game closed: it re-patches the map files automatically
  (the bottom bar shows "Ghost Town maps: n / 45"); start the game after it finishes.
- In someone else's room your data edits (weapons / stratagems / helldivers / enemies) now stay off on the results
  screen, the ship and the launch screen too (they used to come back right after a mission). Hosting is unchanged.
- Turning on "Core" keeps the vanilla cursor (it used to turn green). Settings you saved on the Cursor page are
  installed as saved, and are remembered when you turn Core off and on again.

WHAT'S NEW IN V1.0 (since V1.0pre Early Access)
- This is the V1.0 release.
- New on the Features page:
  * Self-resupply from Resupply Pack (by Lhgrzr): while wearing a Resupply Pack, resupply yourself once and use one
    charge, with the original take-ammo-from-the-pack animation (about 1 s, weapon holstered). Keyboard: a top-row number key (4-9, default 5; not the numpad). Controller: hold Reload for 0.6 s (the
    reload still happens). No charge is used when your ammo is full or the pack is empty; doesn't trigger while
    downed, carrying, in a vehicle or typing.
  * Hide sample outlines (by Lhgrzr): the glowing outline around research samples on the ground is removed; samples
    stay visible and can be picked up, and scout gear still marks them.
  * Chat IME crash fix (by HalfSugar, on by default): in the original game, the first chat message typed with an IME
    (e.g. Chinese input) after changing rooms can crash the game; this prevents it. Leftover IME input is also
    cleared when chat closes, so the IME can't lock the keyboard.
  * With "Faster cutscenes" on, the intro video at game start is skipped (videos can't be sped up, only skipped).
- Split screen: your own camera now follows like the original single-player camera: it trails slightly and looks a bit
  ahead in the direction you face / run (before, it was locked right above you and felt too tight), and camera shake
  from explosions and strikes works like the original. Vehicle and
  respawn transitions and spectating teammates after death are unchanged.
- The developer-mode Training page is renamed Map Select, and now works with teammates:
  * On the ship as host, click Start: alone (or with local split screen) you still drop straight in.
  * With online teammates in the room it becomes "set as next mission": walk into a drop pod as usual and this map
    is what you drop into. Teammates don't need HellBox, and everyone earns XP and galactic war progress as normal.
    Back on the ship your original planet is restored, and this map never counts as one of that planet's missions.
    To cancel, pick another planet on the war table. It shares a slot with the Play page's Proving Grounds
    "next mission", so setting a map cancels that one.
  * In mission stats, "Vanilla / Custom training" is now "Vanilla / Custom Map Select".
- Credits on About: a separate line for HalfSugar's contributions (split screen, chat IME crash fix); Kent and QiQi
  added to testers.

WHAT WAS NEW IN V1.0pre EARLY ACCESS (since V0.99)
- Renamed to V1.0pre (1.0 preview); no longer a community test build.
- Split screen updated to HalfSugar's new CameraCTRL:
  * New "Aspect ratio": Game / 16:9 / 16:10 / 4:3 / 5:4. Changes only your own view, with black bars;
    no resolution change, no stretching, teammates' view area unchanged. Needs "Unlock camera" on.
  * The camera follows height changes smoothly on slopes (brief steps up don't make it shake).
  * Fixes for the host's "Unlock position" stopping after a teammate joins mid-mission, and hostages walking
    out of the shelter door (the author says these still need online testing).
- Added a guard for the occasional crash when entering the drop pod after returning to the ship
  (a vanilla countdown script error).
- The room name is only rewritten when it changes, and only before entering the drop pod.
- The Helldiver page (level, weapon unlocks, capes) moved into developer mode.
- Developer-mode enemy editor: the unit / projectile pickers (Tank dropped unit, Impaler tentacle,
  grenades / bombs) now only list the enemy's own faction (a map loads one faction; another faction's unit
  would crash the game). Old saved blocks with another faction's unit are skipped in game. "Troops from
  Tanks" in Spawn Logic controls the same thing and wins when set.
- About page: author, credits and notice. Features borrowed from others show their source under the feature.
- New in Early Access:
  * The refresh key on the planet screen now refreshes only the current faction; the other two stay as they
    are ("Refresh now" in HellBox still refreshes all three).
  * The speed-up for the "scanning for threats" animation when refreshing planets didn't work; fixed.
  * Ghost Town: players without HellBox can join a Ghost Town room without crashing the host (they see normal
    lighting); Ghost Town also removes the fog that blocked the view.
  * If a teammate turns off "Follow host" and changes gear, the host's loadout screen now shows
    what the teammate actually picked.
  * "Drop Support Gear" can be set to drop the weapon or the backpack first.
  * Random Drops can only use stratagems you have unlocked; locked ones are greyed out and never drop,
    even if they were ticked before.
  * The Fixed dropdowns in Loadout only list items you have unlocked; an old fixed slot holding something
    you haven't unlocked counts as Free in game.
  * The red "requires LAS-98 Mk2" text on the MG Mk3 upgrade is from the base game, not the mod; unchanged.
  * If Dive Harder is installed, turning on Core now says plainly that HellBox can't be used with it (before,
    it showed a garbled "Couldn't add the split module" error). Uninstall Dive Harder, or verify the game
    files in Steam, then turn on Core.
  * Ghost Town fog, second fix: last time only the fog distance was pushed back; this time the drifting
    bright-blue dust layer over the whole map is turned off too (same as Proving Grounds' Ghost Town).
  * Turning on Core the first time is much faster (multi-core compression), and the bottom bar shows
    "Ghost Town maps: N / 45". The first time, it asks whether to back up the original maps: Back up
    (about 1.3GB extra, a bit slower; later turning off Core on About restores vanilla in one click) or
    No backup (much faster; restore the original maps later with Steam's "Verify integrity of game files").
    If you already have the backup, it won't ask.
  * In someone else's room (as a guest), data changes (monsters, spawns, weapons, Stratagems, Helldiver) don't
    apply; everything is vanilla until you are back in your own room. Features (drop gear, no-slide reload,
    speed-ups...) still work.
  * Split screen is still being adjusted and moved to developer mode: the Split page is hidden and split screen
    stays off in game (your settings are kept; turning on developer mode brings them back).
  * The Training page (renamed Map Select in V1.0) also moved into developer mode.
  * New "K-ON! Enhanced UI" switch in About · Settings: when on, the left side only shows Features / Modes /
    Data / Cursor / About (even in developer mode). It only simplifies the window; your settings keep working.
  * Crash probe: if the game doesn't exit normally, the Log page in HellBox records the last steps before
    the crash. Please include it when reporting a problem.

HOW TO USE
1. Extract the whole folder anywhere (Desktop, D:\ ...), preferably a new folder, not inside an old HellBox.
   Not into C:\Program Files: HellBox needs to write files next to itself.
2. Run HellBox.exe. Switch language with CN / EN at the top right.
3. First time: close the game, open About (bottom left) and turn on "Core" (takes a few minutes the first
   time, longer on a hard disk).
   Start the game and it works. Most settings can be changed while the game runs.
4. If Core is off or something is wrong, a red button appears at the top right; click it.
5. Developer mode: click the version number on the About page 10 times (adds Map Select, Split, Helldiver and Log).

WINDOWS SMARTSCREEN
HellBox isn't code-signed, so Windows may show "Windows protected your PC".
Click "More info" -> "Run anyway". It only asks once.

"UNRECOGNIZED GAME FILES"
The game files were changed by another mod or another HellBox version (QoL Mod and Dive Harder are fine; they work together).
On the About page, click "Restore vanilla" in the "Unrecognized game files" row.

UNINSTALL
Close the game, turn Core off on the About page (the game goes back to vanilla), then delete the folder.
Settings and backups: %APPDATA%\Arrowhead\Helldivers\hellbox

PROBLEMS
On the About page click "Copy diagnostics" and paste it with your report.

CREDITS
Outer UI design: 91
Hard-mode data guidance: 吃大份
Split screen, chat IME crash fix: HalfSugar
Testing: 91, HalfSugar, 吃大份, K-ON!, Kent, QiQi
Overall UI planning, code design: Claude
QoL Mod: SomeDoggo
Dive Harder: Oct0pu5
Split screen is HalfSugar's CameraCTRL (included with permission); Self-resupply and Hide sample outlines are by
Lhgrzr; ping on HUD, auto-locate objectives, friends list refresh and the QoL fixes are from Dive Harder (Oct0pu5, included
with permission, MIT license).

NOTICE
- HellBox is completely free and open source under the MIT license; the source code is on GitHub
  (github.com/BearKouber/HellBox). If you paid for it, ask the seller for a refund.
- You may modify and redistribute it. Keep the author credit (07) and the license notice (LICENSE.txt), and link
  the original release page (https://www.nexusmods.com/helldivers/mods/63).
- Work by others included in HellBox (such as split screen, HalfSugar's optimizations and the Dive Harder features) belongs to its authors;
  credit them too when sharing.
- This is an unofficial mod, not affiliated with the game's developers. Mods carry risk; if something goes
  wrong, use "Restore vanilla" on the About page.
- Open-source components: Python, PySide6 / Qt (LGPL-3.0), LuaJIT, Silkscreen font; see LICENSE.txt.

LAST WORDS
I hope everyone finds the fun the game itself has to offer, and that this tool makes your games more enjoyable.
Please don't abuse it, and don't spoil other players' experience.
-- 07
