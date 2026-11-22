"""怪物参数的中文名和说明（「怪物」页用）。

键：`分组.字段`（分组里的数组序号会去掉，比如 damage_zones.1.size → damage_zones.size）。
查不到完整键时退回按字段名查；再查不到就显示原字段名。
说明一句话，鼠标停在名字上能看。
"""
try:
    from i18n import T, tr  # HellBox 里跑时有中英文切换
except ImportError:
    def tr(s):
        return s

    def T(template, *args, **kw):
        return template.format(*args, **kw)

GROUP = {
    "health_info": "血量护甲",
    "enemy_info": "行为",
    "melee_info": "近战",
    "explosive_info": "爆炸",
    "damage_zones": "受伤判定区",
    "shield_info": "护盾",
    "steering_info": "转向避障",
    "flocking_info": "群体行为",
    "decay_info": "尸体消失",
    "actor_spawner_info": "召唤生成",
    "spawn_events": "出场方式",
    "shoot_events": "开火动作",
    "shoot_effect": "开火特效",
    "weapon_info": "武器",
    "attributes": "属性",
    "track_animation_info": "履带动画",
    "fire": "火焰",
    "poison": "毒",
    "lightning": "电",
    "slow": "减速",
    "stun": "眩晕",
    "generic_stun": "眩晕",
    "confuse": "干扰",
    "psychic": "精神",
    "damage": "伤害",
    "environment": "环境",
    "burn": "燃烧",
    "left": "左履带",
    "right": "右履带",
    "unit_radius": "体积半径",
    "heavy": "重型单位",
    "surface_type_damage": "命中材质",
    "surface_type_deflected": "弹开材质",
}

# 完整键（分组.字段）优先；说明写在值里
FIELD = {
    # ---- 血量 / 护甲
    "health_info.health": ("血量", "打死它要打掉多少血。"),
    "health_info.armor_max": ("护甲上限（正面）", "打正面要够这个穿透才能伤到它；不够会被弹开。"),
    "health_info.armor_min": ("护甲下限（背面）", "打背面 / 弱点只需要这个穿透。"),
    "health_info.constitution": ("重伤值", "血掉到这个值以下算倒地 / 重伤。"),
    "health_info.health_decay": ("持续掉血（每秒）", "每秒钟自己掉多少血，0 = 不掉。"),
    "health_info.constitution_decay": ("重伤后掉血（每秒）", "倒地以后每秒钟掉多少血。"),
    "health_info.large": ("大型单位", "是不是大型目标（影响能不能被某些东西撞开 / 压制）。"),
    "damage_zones.size": ("判定角度", "这一块受伤判定覆盖多少度。"),
    "damage_zones.dir": ("判定方向", "判定中心朝向（度，0 = 正面）。"),
    "damage_zones.event": ("命中事件", "打中这一块时播的动画 / 特效名。"),
    "damage_zones.armor_max": ("这块护甲上限", "这一块单独的护甲上限。"),
    "damage_zones.armor_min": ("这块护甲下限", "这一块单独的护甲下限。"),
    "damage_zones.disabled": ("关闭这块判定", "打开后这一块不算受伤。"),
    # ---- 行为
    "enemy_info.movement_speed": ("移动速度", "平时走路速度（米/秒）。"),
    "enemy_info.movement_speed_flee": ("逃跑速度", "跑开时速度。"),
    "enemy_info.wounded_movement_speed": ("受伤后速度", "受伤以后的移动速度。"),
    "enemy_info.turn_speed": ("转身速度", "转身快慢。"),
    "enemy_info.acceleration": ("加速度", "起步快慢。"),
    "enemy_info.aggro_range": ("发现距离", "离你多近会发现 / 追你。"),
    "enemy_info.patrol_speed": ("巡逻速度", "没发现人时的巡逻速度。"),
    "enemy_info.patrol_range": ("巡逻范围", "巡逻时离巡逻点能走多远。"),
    "enemy_info.attack_angle": ("攻击角度", "正面多少度以内才会攻击。"),
    "enemy_info.attack_range": ("攻击距离", "够到这个距离就打。"),
    "enemy_info.attack_range_shoot_min": ("开火最近距离", "比这个近就不开枪。"),
    "enemy_info.attack_range_shoot_max": ("开火最远距离", "比这个远就不开枪。"),
    "enemy_info.attack_range_shoot_preferred": ("最舒服的开火距离", "尽量保持在这个距离开火。"),
    "enemy_info.attack_target_distance": ("贴身距离", "和目标的理想距离。"),
    "enemy_info.back_distance": ("后退距离", "太近时往后退多远。"),
    "enemy_info.encounter_countdown_time": ("见面准备时间", "发现你之后先站多久再动手。"),
    "enemy_info.remove_time": ("尸体消失时间", "死后多久消失。"),
    "enemy_info.collision_removal_delay": ("死后碰撞消失延迟", "死后多久不再挡路。"),
    "enemy_info.spawn_duration": ("出场时间", "从地里 / 仓里出来的动画时间。"),
    "enemy_info.spawn_interval": ("召唤间隔", "连续召唤小怪时每只隔多久。"),
    "enemy_info.spawn_amount": ("召唤数量", "一次召唤几只。"),
    "enemy_info.spawn_group_cooldown": ("召唤冷却", "两次召唤之间隔多久。"),
    "enemy_info.spawn_unit_path": ("召唤的怪", "召唤出来的是哪种怪（内部路径）。"),
    "enemy_info.summon_unit_path_01": ("召唤的怪 1", "召唤 / 放出的第一种怪（内部路径）。"),
    "enemy_info.summon_unit_path_02": ("召唤的怪 2", "召唤 / 放出的第二种怪。"),
    "enemy_info.enemy_name": ("内部名", "游戏代码里的名字，别改。"),
    "enemy_info.enemy_type": ("类型", "游戏用它决定用哪套行为，别改。"),
    "enemy_info.follow_range": ("跟随距离", "跟着队友 / 目标时保持多远。"),
    "enemy_info.follow_range_deviation": ("跟随距离浮动", "跟随距离在这个范围里随机。"),
    "enemy_info.can_help_up": ("会扶起同伴", "队友倒地时会不会过去扶。"),
    "enemy_info.help_up_time": ("扶起用时", "扶起同伴要多久。"),
    "enemy_info.downed_get_up_time": ("倒地起身时间", "倒地后多久自己起来。"),
    "enemy_info.idle_threshold": ("发呆判定阈值", "速度低于这个算站着不动。"),
    "enemy_info.enemy_idle_threshold": ("发呆判定阈值", "速度低于这个算站着不动。"),
    "enemy_info.enemy_move_threshold": ("移动判定阈值", "速度高于这个才算在移动。"),
    "enemy_info.minimum_z": ("最低高度", "掉到这个高度以下算掉坑。"),
    "enemy_info.z_direction": ("朝向轴", "判断方向用哪根轴。"),
    "enemy_info.realarm_range": ("叫增援的距离", "离你多近会叫警报。"),
    "enemy_info.recovery_flee_distance": ("逃跑后回退距离", "跑开多远再回来。"),
    "enemy_info.hit_recovery": ("受击硬直", "被打中后多久恢复行动。"),
    "enemy_info.max_range": ("最大射程", "最远打多远。"),
    "enemy_info.min_range": ("最小射程", "最近打多近。"),
    "enemy_info.power": ("威力", "这一招的伤害。"),
    "enemy_info.projectile": ("子弹 / 弹丸", "打出去的弹丸（内部路径）。"),
    "enemy_info.range_increase_per_second": ("射程每秒增加", "开火时射程每秒涨多少。"),
    "enemy_info.player_within_angle_threshold": ("面向玩家角度", "玩家在多少度以内算「面对」。"),
    "enemy_info.shoot_players_within_angle": ("见人就开火角度", "玩家在多少度内就直接开火。"),
    "enemy_info.effect_hit": ("命中特效", "打中东西时播的特效。"),
    "enemy_info.can_teleport": ("会传送", "会不会瞬移。"),
    "enemy_info.emergency_teleport_max_range": ("紧急传送距离", "被贴脸时能瞬移多远。"),
    "enemy_info.emergency_teleport_cooldown": ("紧急传送冷却", "两次紧急传送间隔。"),
    "enemy_info.confuses": ("会干扰", "会不会让人眩晕 / 混乱。"),
    "enemy_info.confuse_range": ("干扰距离", "多远能干扰。"),
    "enemy_info.confuse_cooldown": ("干扰冷却", "两次干扰间隔。"),
    "enemy_info.confuse_recovery": ("干扰恢复", "干扰持续多久。"),
    "enemy_info.confuse_startup": ("干扰前摇", "干扰前要准备多久。"),
    "enemy_info.confuse_start_cooldown": ("开局干扰冷却", "刚出场多久内不能干扰。"),
    # 冲锋
    "enemy_info.rush_distance_min": ("冲锋最近距离", "离得多近才会冲。"),
    "enemy_info.rush_distance_max": ("冲锋最远距离", "离得多远就不冲了。"),
    "enemy_info.rush_distance": ("冲锋距离", "一次冲多远。"),
    "enemy_info.rush_time": ("冲锋持续时间", "一次冲多久。"),
    "enemy_info.rush_cooldown": ("冲锋冷却", "两次冲锋间隔。"),
    "enemy_info.rush_startup_time": ("冲锋前摇", "冲之前先蓄多久。"),
    "enemy_info.rush_movement_speed": ("冲锋速度", "冲起来的速度。"),
    "enemy_info.rush_turn_speed": ("冲锋转向速度", "冲的过程中能拐多快。"),
    "enemy_info.rush_target_angle": ("冲锋判定角度", "目标在多少度内才冲。"),
    "enemy_info.rush_max_angle_to_target": ("冲锋最大偏角", "偏离目标多少度就不冲了。"),
    "enemy_info.rush_leave_time": ("冲锋后停留", "冲完在原地停多久。"),
    "enemy_info.rush_melee_interval": ("冲锋攻击间隔", "冲撞时每隔多久打一下。"),
    "enemy_info.rush_charge_time": ("冲锋蓄力时间", "冲锋前蓄力多久。"),
    "enemy_info.rush_hit_obstacle_range": ("撞障碍距离", "撞到东西后的反应距离。"),
    "enemy_info.rush_hit_obstacle_side_range": ("撞障碍侧向距离", "侧着撞到东西的判定距离。"),
    "enemy_info.rush_hit_obstacle_time": ("撞障碍停顿", "撞到东西后停多久。"),
    "enemy_info.aoe_trigger_distance": ("范围攻击触发距离", "离你多近会放范围攻击。"),
    "enemy_info.aoe_cooldown": ("范围攻击冷却", "两次范围攻击间隔。"),
    # 闪避
    "enemy_info.avoid_charge_time": ("闪避蓄力", "闪避前准备多久。"),
    "enemy_info.avoid_cooldown": ("闪避冷却", "两次闪避间隔。"),
    "enemy_info.avoid_start_cooldown": ("开局闪避冷却", "刚出场多久内不会闪。"),
    "enemy_info.avoid_range_min": ("闪避最近距离", "多近才闪。"),
    "enemy_info.avoid_range_max": ("闪避最远距离", "多远还闪。"),
    "enemy_info.avoid_recovery": ("闪避恢复", "闪完多久恢复。"),
    "enemy_info.avoid_speed": ("闪避速度", "闪避时的速度。"),
    # 跳跃
    "enemy_info.jump_charge_time": ("跳跃蓄力", "跳之前准备多久。"),
    "enemy_info.jump_close_height_diff": ("跳上高差", "能跳上多高的台子。"),
    "enemy_info.jump_cooldown": ("跳跃冷却", "两次跳跃间隔。"),
    "enemy_info.jump_duration": ("跳跃时长", "一次跳多久。"),
    "enemy_info.jump_range_min": ("跳跃最近距离", "多近才跳。"),
    "enemy_info.jump_range_max": ("跳跃最远距离", "最远跳多远。"),
    "enemy_info.jump_recovery": ("落地恢复", "落地后多久能动。"),
    "enemy_info.jump_start_cooldown": ("开局跳跃冷却", "刚出场多久内不跳。"),
    # 传送
    "enemy_info.teleport_charge_dodge_time": ("传送蓄力闪避", "蓄力时闪避的时间。"),
    "enemy_info.teleport_charge_time": ("传送蓄力", "传送前准备多久。"),
    "enemy_info.teleport_cooldown": ("传送冷却", "两次传送间隔。"),
    "enemy_info.teleport_cooldown_on_fail": ("传送失败冷却", "传送失败后多久再试。"),
    "enemy_info.teleport_cooldown_on_success": ("传送成功冷却", "传送成功后多久再传。"),
    "enemy_info.teleport_criteria_distance_to_target": ("传送目标距离", "离目标多远才会传。"),
    "enemy_info.teleport_distance": ("传送距离", "一次传多远。"),
    "enemy_info.teleport_duration": ("传送用时", "传送动画多久。"),
    "enemy_info.teleport_range_max": ("传送最远距离", "最远能传多远。"),
    "enemy_info.teleport_range_min": ("传送最近距离", "最近传多远。"),
    "enemy_info.teleport_recovery": ("传送恢复", "传完多久能动。"),
    "enemy_info.teleport_target_distance_multiplier": ("传送距离倍数", "按离目标的距离乘多少。"),
    # 护盾 / 护盾墙
    "enemy_info.shield_time": ("举盾时间", "护盾挡住多久。"),
    "enemy_info.shield_turn_speed": ("举盾转身速度", "举着盾时转多快。"),
    "enemy_info.shield_players_within_angle": ("举盾角度", "玩家在多少度内才会举盾。"),
    "enemy_info.unshield_damage_taken": ("破盾后受伤", "盾破了以后挨打的伤害。"),
    "enemy_info.shield_wall_cooldown": ("护盾墙冷却", "两堵盾墙间隔。"),
    "enemy_info.shield_wall_distance_from_unit": ("盾墙离本体", "盾墙放在离自己多远。"),
    "enemy_info.shield_wall_exit_time": ("盾墙收起时间", "多久后收起。"),
    "enemy_info.shield_wall_max_length": ("盾墙最长", "最长多长。"),
    "enemy_info.shield_wall_min_length": ("盾墙最短", "最短多长。"),
    "enemy_info.shield_wall_time": ("盾墙存在时间", "立多久。"),
    # 开火节奏
    "enemy_info.shoot_charge": ("开火蓄力", "要不要蓄力再打。"),
    "enemy_info.shoot_charge_time": ("蓄力时间", "打之前蓄多久。"),
    "enemy_info.shoot_cooldown": ("开火冷却", "两枪间隔。"),
    "enemy_info.shoot_cooldown_time": ("开火冷却时间", "两枪间隔多久。"),
    "enemy_info.shoot_startup": ("开火前摇", "举枪到开枪多久。"),
    "enemy_info.shoot_recovery": ("开火后摇", "打完多久能再动。"),
    "enemy_info.shoot_time": ("开火时长", "一次开火持续多久。"),
    "enemy_info.stop_shoot_time": ("停火时间", "停火后多久恢复。"),
    "enemy_info.enter_shoot_time": ("进入开火时间", "进入开火状态要多久。"),
    "enemy_info.aim_time": ("瞄准时间", "瞄准多久。"),
    "enemy_info.aim_turn_speed": ("瞄准转身速度", "瞄准时转多快。"),
    "enemy_info.shoot_type": ("开火类型", "弹道 / 火焰 / 弧线这类。"),
    "enemy_info.shoot_unit": ("发射物", "打出去的东西。"),
    "enemy_info.shoot_node": ("枪口位置", "从哪个位置开火。"),
    "enemy_info.shoot_direction_node": ("枪口朝向", "按哪个方向开火。"),
    "enemy_info.shoot_fire_dir_ignore_z": ("忽略高低朝向", "开火方向是否忽略高度差。"),
    "enemy_info.turret_turn_speed": ("炮塔转速", "炮塔转多快。"),
    "enemy_info.turret_turn_cooldown": ("炮塔转向冷却", "炮塔两次转向间隔。"),
    # 钻地
    "enemy_info.burrow_cooldown": ("钻地冷却", "两次钻地间隔。"),
    "enemy_info.burrow_exit_time": ("钻出时间", "从地里出来要多久。"),
    "enemy_info.burrow_max_time": ("最长钻地时间", "最多在地下待多久。"),
    "enemy_info.burrow_exit_criteria_damage_taken": ("被打出来阈值", "挨多少伤害会钻出来。"),
    "enemy_info.burrow_exit_criteria_self_to_target_max_distance": ("离目标多远钻出", "离你太远就出来。"),
    "enemy_info.burrow_exit_criteria_self_to_target_min_distance": ("离目标多近钻出", "离你够近就出来。"),
    "enemy_info.burrow_exit_criteria_tentacle_to_target_max_distance": ("触手离目标距离", "触手离你多远时钻出。"),
    "enemy_info.burrow_num_tentacles": ("触手数量", "钻地时放几根触手。"),
    "enemy_info.burrow_tentacle_angle_to_target_requirement": ("触手角度要求", "触手朝你方向的角度要求。"),
    "enemy_info.burrow_tentacle_max_retries": ("触手重试次数", "触手放不出来重试几次。"),
    "enemy_info.burrow_tentacle_random_offset": ("触手随机偏移", "触手落点的随机偏移。"),
    "enemy_info.burrow_tentacle_spacing_angle": ("触手间隔角度", "几根触手之间隔多少度。"),
    "enemy_info.burrow_tentacle_spawn_close_range": ("近距触手范围", "近距离时触手的范围。"),
    "enemy_info.burrow_tentacle_spawn_delay": ("触手出现延迟", "钻出后多久长触手。"),
    "enemy_info.burrow_tentacle_spawn_distance_from_target_close": ("近距触手落点", "近距离触手离你多远。"),
    "enemy_info.burrow_tentacle_spawn_distance_from_target_far": ("远距触手落点", "远距离触手离你多远。"),
    "enemy_info.burrow_tentacle_unit_path": ("触手用哪种", "触手的单位路径。"),
    # 近战
    "melee_info.power": ("近战威力", "近战一下多少伤害。"),
    "melee_info.radius": ("近战范围", "挥击覆盖的半径。"),
    "melee_info.center_distance": ("近战中心距离", "判定中心离自己多远。"),
    "melee_info.delay": ("出手延迟", "抬手到打中多久。"),
    "melee_info.duration": ("动作时长", "一次近战动画多久。"),
    "melee_info.distance": ("近战距离", "够到多远。"),
    "melee_info.armorpiercing": ("近战穿甲", "近战能不能无视护甲。"),
    "melee_info.hit_all": ("打到所有人", "一下是否打中范围内所有玩家。"),
    "melee_info.hit_status_effects": ("附加状态", "打中后附加什么状态（倒地等）。"),
    "melee_info.ignore_components": ("忽略组件", "判定时忽略哪些组件。"),
    "special_attacks.power": ("特殊攻击威力", "这一招的特殊攻击伤害。"),
    "special_attacks.armorpiercing": ("特殊攻击穿甲", "这一招能不能无视护甲。"),
    "special_attacks.center_distance": ("特殊攻击中心距离", "判定中心离自己多远。"),
    "special_attacks.delay": ("特殊攻击延迟", "抬手到打中多久。"),
    "special_attacks.duration": ("特殊攻击时长", "动作多久。"),
    # 爆炸
    "explosive_info.blast_radius": ("爆炸半径", "爆炸最大半径。"),
    "explosive_info.blast_power": ("爆炸威力", "边缘伤害。"),
    "explosive_info.center_radius": ("中心半径", "中心高伤区的半径。"),
    "explosive_info.center_power": ("中心威力", "中心伤害。"),
    "explosive_info.force": ("冲击力", "把人推开的力量。"),
    "explosive_info.always_explode": ("一定爆炸", "碰到东西都炸。"),
    "explosive_info.hit_status_effects": ("附加状态", "炸到后附加什么状态。"),
    "explosive_info.effect": ("爆炸特效用哪个", "爆炸动画 / 特效名。"),
    "explosive_info.audio": ("爆炸音效", "爆炸用哪个声音。"),
    # 护盾
    "shield_info.shield": ("护盾类型", "护盾模型类型。"),
    "shield_info.armor_max": ("护盾正面护甲", "护盾正面需要的穿透。"),
    "shield_info.armor_min": ("护盾背面护甲", "护盾背面需要的穿透。"),
    "shield_info.shield_regen": ("护盾回复速度", "每秒回多少。"),
    "shield_info.shield_regen_delay": ("护盾回复延迟", "打掉后多久开始回。"),
    "shield_info.base_intensity": ("护盾亮度", "平时多亮。"),
    "shield_info.hit_flash_intensity": ("受击闪光亮度", "被打时闪多亮。"),
    "shield_info.hit_flash_time": ("受击闪光时长", "闪多久。"),
    "shield_info.shield_mesh": ("护盾模型", "护盾用哪个模型。"),
    "shield_info.uv_speed_full_health_x": ("贴图流动速度 X（满血）", "满盾时贴图横向流动速度。"),
    "shield_info.uv_speed_full_health_y": ("贴图流动速度 Y（满血）", "满盾时贴图纵向流动速度。"),
    "shield_info.uv_speed_no_health_x": ("贴图流动速度 X（快没盾）", "快破盾时贴图横向流动速度。"),
    "shield_info.uv_speed_no_health_y": ("贴图流动速度 Y（快没盾）", "快破盾时贴图纵向流动速度。"),
    # 转向 / 群体
    "steering_info.avoidance_factor": ("避障强度", "躲障碍物的力度。"),
    "steering_info.feeler_length": ("探路长度", "往前面探多远躲障碍。"),
    "flocking_info.cohesion_radius": ("聚拢范围", "同类之间多近会靠在一起。"),
    "flocking_info.cohesion_factor": ("聚拢强度", "靠在一起的力度。"),
    "flocking_info.separation_radius": ("散开范围", "离同类多近会分开。"),
    "flocking_info.separation_factor": ("散开强度", "分开的力度。"),
    "flocking_info.alignment_factor": ("方向对齐强度", "和同类走同一方向的力度。"),
    "flocking_info.update_nearby_entities_interval": ("刷新间隔", "多久重算一次附近同类。"),
    # 尸体
    "decay_info.delay": ("消失延迟", "死后多久开始消失。"),
    "decay_info.duration": ("消失时长", "消失过程多久。"),
    "decay_info.distance": ("消失距离", "离玩家多远就消失。"),
    # 召唤器
    "actor_spawner_info.actor_spawn_delay": ("召唤延迟", "出来后多久开始放怪。"),
    "actor_spawner_info.actors": ("召唤的东西", "放出来的是什么。"),
    # 出场
    "spawn_events.default": ("默认出场", "平时怎么出场。"),
    "spawn_events.patrol": ("巡逻出场", "随巡逻队出现时怎么出场。"),
    "spawn_events.ifv": ("步兵战车放兵", "从车上下来的方式。"),
    # 开火动作
    "shoot_events.time": ("动作时间点", "这个动作在整段开火里第几秒。"),
    "shoot_events.animation_time": ("动画时长", "这个动作播多久。"),
    "shoot_events.can_abort": ("能被打断", "这个阶段能不能被打断。"),
    "shoot_events.disable_fire": ("这一帧不开火", "这个阶段要不要禁止出弹。"),
    "shoot_events.aim": ("瞄准角度", "这个阶段枪口抬到哪。"),
    # 开火特效
    "shoot_effect.particle": ("粒子特效", "用哪个粒子。"),
    "shoot_effect.max_distance": ("特效长度", "特效最远多长。"),
    "shoot_effect.start_variable": ("起点参数", "特效起点参数名。"),
    "shoot_effect.end_variable": ("终点参数", "特效终点参数名。"),
    "shoot_effect.length_variable": ("长度参数", "特效长度参数名。"),
    "shoot_effect.position_node": ("特效位置", "从哪个节点出特效。"),
    "shoot_effect.particle_start_node": ("粒子起点", "粒子从哪个节点开始。"),
    "shoot_effect.direction_node": ("特效方向", "按哪个节点决定方向。"),
    "shoot_effect.move_particles": ("移动粒子", "粒子是否跟着动。"),
    "shoot_effect.destroy": ("结束后销毁", "特效放完是否销毁。"),
    # 武器
    "weapon_info.power": ("武器威力", "这一枪多少伤害。"),
    "weapon_info.power_crit": ("暴击威力", "打弱点时的伤害。"),
    "weapon_info.range": ("武器射程", "最远打多远。"),
    "weapon_info.firerate": ("射速", "每秒几发。"),
    "weapon_info.spread": ("散布", "子弹散开的角度。"),
    "weapon_info.attach_node": ("挂点", "武器挂在哪个节点。"),
    "weapon_info.effect_hit": ("命中特效", "打中东西播什么。"),
    "weapon_info.effect_scale": ("特效大小", "命中特效缩放。"),
    "weapon_info.hit_status_effects": ("附加状态", "打中后附加什么状态。"),
    # 属性
    "attributes.armorpiercing": ("穿甲", "能不能无视护甲。"),
    "attributes.explosive": ("爆炸", "打出去是不是爆炸类。"),
    "attributes.fixed_spread": ("固定散布", "散布是否固定。"),
    "attributes.unstoppable": ("不可阻挡", "会不会被挡住。"),
    # 履带
    "track_animation_info.material_speed_multiplier": ("履带速度倍数", "履带贴图滚动快慢。"),
    "track_animation_info.speed_threshold": ("履带启动速度", "速度超过多少算在开。"),
    "track_animation_info.track_mesh": ("履带模型", "用哪个履带模型。"),
    # 材质 / 特殊（这几个字段不在分组里，键就是字段名）
    "surface_type_damage": ("命中材质", "打中它算哪种材质（影响伤害音效）。"),
    "surface_type_deflected": ("弹开材质", "没打穿时算哪种材质。"),
    "unit_radius": ("体积半径", "身体半径（米），影响碰撞和近战判定。"),
    "heavy": ("重型单位", "是不是重型（车可以撞开？）。"),
}

# 按字段名兜底的翻译（不分分组）
SHORT = {
    "immune": "免疫",
    "particle_effect_name": "粒子特效",
    "particle_effect_node": "特效节点",
    "material": "材质",
    "node": "节点",
}


FIELD.update({
    "hit_status_effects": ("命中附加效果", "打中人以后附带的效果。"),
    "melee_info.hit_status_effects": ("近战附加效果", "近战打中人以后附带的效果。"),
    "weapon_info.hit_status_effects": ("开火附加效果", "子弹 / 火焰打中人以后附带的效果。"),
    "explosive_info.hit_status_effects": ("爆炸附加效果", "炸到人以后附带的效果。"),
    "shield_info.shield": ("护盾量", "护盾一共能挡多少伤害，打光了才伤到本体。"),
    "shield_info.shield_regen": ("护盾回复（每秒）", "护盾每秒回多少。"),
    "shield_info.armor_max": ("护盾正面护甲", "打护盾正面要多高穿透。"),
    "shield_info.armor_min": ("护盾背面护甲", "打护盾背面要多高穿透。"),
    "weapon_info.spread": ("散布", "子弹散开的角度，越大越打不准。"),
    "enemy_info.z_direction": ("抛射仰角", "扔榴弹时往上抬多少度。"),
    "enemy_info.shoot_charge": ("开火要蓄力", "开枪前要不要先蓄一下。"),
    "enemy_info.rush_target_angle": ("冲锋判定角度", "目标在正前方多少度以内才冲。"),
    "enemy_info.shoot_type": ("开火方式", "打出去的是什么样的攻击。"),
    "enemy_info.can_teleport": ("会传送", "会不会瞬移（三脚机原版关着）。"),
    "enemy_info.can_help_up": ("会扶起同伴", "队友倒地时会不会过去扶。"),
})

# 单位（括号里）。角度字段游戏里是弧度，界面上换成度
RADIAN_FIELDS = {"rush_max_angle_to_target", "burrow_tentacle_angle_to_target_requirement",
                 "burrow_tentacle_spacing_angle", "spread", "z_direction"}
DEGREE_FIELDS = {"rush_target_angle", "shoot_players_within_angle", "shield_players_within_angle",
                 "attack_angle", "player_within_angle_threshold", "size", "dir"}


def unit_of(field):
    """字段的单位（显示在名字后面）；没有就空串。"""
    f = field
    if f in RADIAN_FIELDS or f in DEGREE_FIELDS:
        return "度"
    if f in ("shield_regen",):
        return "每秒"
    if "speed" in f and "turn" not in f:
        return "米/秒"
    if f.endswith(("_time", "cooldown", "delay", "duration", "recovery", "startup", "interval", "_on_fail",
                   "_on_success", "remove_time")) or f in ("delay", "duration", "shoot_time", "hit_recovery"):
        return "秒"
    if any(k in f for k in ("range", "distance", "radius", "_length", "height_diff", "random_offset")):
        return "米"
    if "power" in f or f == "unshield_damage_taken" or f == "burrow_exit_criteria_damage_taken":
        return "伤害"
    return ""


# ---------------------------------------------------------------- 免疫（status_info）
# 游戏规则（status_component.lua）：一个效果有「来源」（毒 / 火 / 电……）和「效果」（减速 / 眩晕 / 掉血……），
# 来源免疫 或 效果免疫 任一个打开，这个效果就挂不上。
IMMUNE_ELEMENTS = [
    ("poison", "毒", "毒虫的毒、毒气：中毒掉血和中毒减速都不吃。"),
    ("fire", "火", "喷火器、燃烧弹点着：不会着火。"),
    ("lightning", "电", "电弧枪、电击：不吃电击减速 / 电晕。"),
    ("generic_stun", "闪光 / 震荡", "闪光弹、子弹打出的硬直：不会被晕、不会被打慢。"),
    ("psychic", "精神干扰", "光明会那种让人操作反过来的干扰。"),
    ("environment", "地形减速", "水里、雪地里不会变慢。"),
]
IMMUNE_STATUSES = [
    ("slow", "减速", "不管什么来源，都不会变慢。"),
    ("stun", "眩晕", "不管什么来源，都不会被晕住。"),
    ("burn", "着火", "不管什么来源，都不会烧起来。"),
    ("damage", "持续掉血", "中毒、铁丝网这类持续掉血都不吃。"),
]

# 命中附加效果（StatusTemplateSettings 的名字）
STATUS_FX = {
    "poison_slow": "中毒减速（慢 60%，4 秒）",
    "poison_heavy_slow": "重度中毒减速（慢 75%，6 秒）",
    "poison_damage": "中毒掉血（每秒 4，4 秒）",
    "poison_medium_damage": "中度中毒掉血（每秒 15，3 秒）",
    "heavy_poison_damage": "重度中毒掉血（每秒 100，5 秒）",
    "regular_burn": "点着（每 0.25 秒 24，5 秒）",
    "small_burn": "小火（每 0.25 秒 12，2 秒）",
    "heavy_burn": "大火（每 0.25 秒 100，2 秒）",
    "regular_knockdown": "撞倒",
    "lightning_stun": "电击定身（0.3 秒）",
    "lightning_slow": "电击减速（慢 75%，0.25 秒）",
    "flashbang_stun": "闪光眩晕（3 秒）",
    "flashbang_slow": "闪光减速（慢 75%，3 秒）",
    "bullet_stun": "子弹硬直（0.3 秒）",
    "barbwire_slow": "铁丝网减速（3 秒）",
    "barbwire_damage": "铁丝网掉血（3 秒）",
    "confuse": "操作混乱（8 秒）",
    "confuse_short": "操作混乱（3 秒）",
    "invert_move_confuse": "移动反向（5 秒）",
    "switch_move_aim_confuse": "移动和瞄准对调（5 秒）",
}

# 打出去 / 放出来的东西（路径 -> 中文）。怪本身的名字从 enemy_settings.json 补
THING_ZH = {
    "characters/cyborg_soldier/cyborg_soldier_grenade": "榴弹（班长 / 军团士兵扔的）",
    "characters/illuminate_apprentice/illuminate_apprentice_bomb": "光能学徒的光弹",
    "characters/illuminate_illusionist/illuminate_illusionist_bomb": "幻光大师的光弹",
    "characters/illuminate_illusionist/illuminate_councilmember_bomb": "光能决策者的光弹",
    "characters/bug_impaler/bug_impaler_tentacle": "刺钉虫的触手",
    "gameobjects/enemy_tesla_01": "电击塔",
    "gameobjects/enemy_nanobot_strike": "纳米机器人打击",
}
# 哪些字段是「打出去的东西」、哪些是「放出来的怪」
PROJECTILE_FIELDS = {"projectile", "shoot_unit"}
SUMMON_FIELDS = {"summon_unit_path_01", "summon_unit_path_02"}
UNIT_FIELDS = {"spawn_unit_path", "burrow_tentacle_unit_path"}
SHOOT_TYPE_ZH = {"flame": "喷火"}


def _lookup(parts):
    """从最具体到最笼统找中文名：分组.字段 → 倒数第二个非数字段.字段 → 字段。"""
    field = parts[-1]
    names = [p for p in parts[:-1] if not p.isdigit()]
    for g in [parts[0]] + names[::-1]:
        key = f"{g}.{field}"
        if key in FIELD:
            return FIELD[key]
    if field in FIELD:
        return FIELD[field]
    if field in SHORT:
        return SHORT[field], ""
    return None


def describe(path):
    """返回 (中文名, 说明, 原字段名)。名字后面带单位，比如「冲锋冷却（秒）」。"""
    parts = path.split(".")
    group = parts[0]
    field = parts[-1]
    if field.isdigit() and len(parts) >= 2:  # 列表里的第几项（hit_status_effects.1）
        found = _lookup(parts[:-1])
        name, tip = found if found else (parts[-2], "游戏里的原始参数。")
        return f"{name} {int(field)}", tip, parts[-2]
    found = _lookup(parts)
    name, tip = found if found else (field, "游戏里的原始参数。")
    unit = unit_of(field)
    if unit:
        name = f"{name}（{unit}）"
    idx = [p for p in parts[1:-1] if p.isdigit()]
    if idx and group == "damage_zones":
        name = T('第{0}块 · {1}', int(idx[-1]), name)
    elif idx and group == "shoot_events":
        name = T('第{0}帧 · {1}', int(idx[-1]), name)
    return name, tip, field


def group_label(path):
    """独特属性里每一小节的标题：近战 · 第1招 · 爆炸 这样。"""
    parts = path.split(".")
    if parts[-1].isdigit():
        parts = parts[:-1]
    out = []
    i = 0
    while i < len(parts) - 1:
        p = parts[i]
        if p == "special_attacks" and i + 1 < len(parts) - 1 and parts[i + 1].isdigit():
            out.append(T('特殊招式 第{0}招', int(parts[i + 1])))
            i += 2
            continue
        if p.isdigit():
            out.append(T('第{0}项', int(p)))
        elif p == "attributes":
            out.append("子弹属性")
        else:
            out.append(GROUP.get(p, p))
        i += 1
    return " · ".join(out) or GROUP.get(parts[0], parts[0])
