use helldivers_bridge_core::{
    install::{self, Module},
    transport,
};
use std::{
    fs::{self, File},
    io::Read,
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

mod view;
pub use view::ViewSettings;

pub fn module() -> Result<Module, String> {
    let source = include_str!("../bridge/runtime.lua").replace("\r\n", "\n");
    let bytes = include_bytes!("../bridge/runtime.luac");
    let hashes: Vec<_> = include_str!("../bridge/runtime.sha256").lines().collect();
    let host = format!(
        "local get_host = (function()\n{}\nend)()",
        helldivers_bridge_core::HOST_SOURCE.replace("\r\n", "\n")
    );
    let camera = format!(
        "local camera_factory = (function()\n{}\nend)()",
        include_str!("../bridge/camera.lua").replace("\r\n", "\n")
    );
    let spawning = format!(
        "local spawning_factory = (function()\n{}\nend)()",
        include_str!("../bridge/spawning.lua").replace("\r\n", "\n")
    );
    let encounters = format!(
        "local encounter_factory = (function()\n{}\nend)()",
        include_str!("../bridge/encounters.lua").replace("\r\n", "\n")
    );
    let supply = format!(
        "local supply_factory = (function()\n{}\nend)()",
        include_str!("../bridge/patrol_supply.lua").replace("\r\n", "\n")
    );
    let respawn = format!(
        "local respawn_factory = (function()\n{}\nend)()",
        include_str!("../bridge/respawn.lua").replace("\r\n", "\n")
    );
    let escort = format!(
        "local escort_factory = (function()\n{}\nend)()",
        include_str!("../bridge/escort.lua").replace("\r\n", "\n")
    );
    let escort_transfer = format!(
        "local escort_transfer_factory = (function()\n{}\nend)()",
        include_str!("../bridge/escort_transfer.lua").replace("\r\n", "\n")
    );
    let vehicle_modules = [
        ("peer_modes", include_str!("../bridge/peer_modes.lua")),
        ("vehicles", include_str!("../bridge/vehicles.lua")),
        ("extraction", include_str!("../bridge/extraction.lua")),
        ("camera_focus", include_str!("../bridge/camera_focus.lua")),
        ("view", include_str!("../bridge/view.lua")),
    ];
    if hashes.len() != 2
        || install::hash(source.as_bytes()) != hashes[0]
        || install::hash(bytes) != hashes[1]
        || !source.contains(&host)
        || !source.contains(&camera)
        || !source.contains(&spawning)
        || !source.contains(&encounters)
        || !source.contains(&supply)
        || !source.contains(&respawn)
        || !source.contains(&escort)
        || !source.contains(&escort_transfer)
        || vehicle_modules.iter().any(|(name, text)| {
            !source.contains(&format!(
                "local {name}_factory = (function()\n{}\nend)()",
                text.replace("\r\n", "\n")
            ))
        })
    {
        return Err("源码和内嵌字节码不一致，请重新编译桥接".into());
    }
    Module::new("camera", bytes)
}
pub fn install(game: &Path, remove: bool) -> Result<String, String> {
    install::install(game, module()?, remove)
}
pub fn directory() -> Result<PathBuf, String> {
    Ok(
        PathBuf::from(std::env::var_os("APPDATA").ok_or("缺少 APPDATA")?)
            .join("Arrowhead/Helldivers/camera_ctrl_v1"),
    )
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SpawnSettings {
    pub encounter: u32,
    pub patrol: u32,
}
impl Default for SpawnSettings {
    fn default() -> Self {
        Self {
            encounter: 2,
            patrol: 4,
        }
    }
}
impl SpawnSettings {
    pub fn valid(self) -> bool {
        (1..=100).contains(&self.encounter) && (1..=100).contains(&self.patrol)
    }
    pub fn regional(total: u32) -> f64 {
        (total as f64 / 4.0).max(1.0)
    }
    fn parse(text: &str) -> Result<Self, String> {
        let fields: Vec<_> = text.lines().collect();
        if fields.len() != 3 || fields[0] != "CAMSPAWN1" {
            return Err("刷怪配置格式错误".into());
        }
        let settings = Self {
            encounter: fields[1].parse().map_err(|_| "增援倍率无效")?,
            patrol: fields[2].parse().map_err(|_| "巡逻倍率无效")?,
        };
        if !settings.valid() {
            return Err("倍率范围为 1–100".into());
        }
        Ok(settings)
    }
    pub fn load() -> Result<Self, String> {
        match fs::read_to_string(directory()?.join("spawn-settings.txt")) {
            Ok(text) => Self::parse(&text),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(Self::default()),
            Err(error) => Err(error.to_string()),
        }
    }
    pub fn save(self) -> Result<(), String> {
        if !self.valid() {
            return Err("倍率范围为 1–100".into());
        }
        let root = directory()?;
        fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        transport::atomic_write(
            &root.join("spawn-settings.txt"),
            format!("CAMSPAWN1\n{}\n{}\n", self.encounter, self.patrol).as_bytes(),
        )
    }
}
pub struct Client {
    root: PathBuf,
    _lock: File,
    counter: u64,
    identity: String,
    pending: Option<(String, Instant)>,
    control_pending: Option<(String, u64, Instant)>,
    session: Option<String>,
    spawn_config_supported: bool,
    view_config_supported: bool,
}
impl Client {
    pub fn new() -> Result<Self, String> {
        let root = directory()?;
        fs::create_dir_all(&root).map_err(|e| e.to_string())?;
        let lock = transport::exclusive_file(&root.join("camera-client.lock"))?;
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_nanos();
        Ok(Self {
            root,
            _lock: lock,
            counter: 0,
            identity: format!("p{}t{stamp}", std::process::id()),
            pending: None,
            control_pending: None,
            session: None,
            spawn_config_supported: false,
            view_config_supported: false,
        })
    }
    pub fn poll(&mut self) -> Result<Option<String>, String> {
        if let Some((nonce, sent)) = &self.pending {
            if let Ok(file) = File::open(self.root.join("camera-status.txt")) {
                let mut text = String::new();
                file.take(1025)
                    .read_to_string(&mut text)
                    .map_err(|e| e.to_string())?;
                if let Some(detail) = parse_reply(&text, nonce) {
                    self.pending = None;
                    return Ok(Some(describe(detail)));
                }
            }
            if sent.elapsed() < Duration::from_secs(3) {
                return Ok(None);
            }
            self.pending = None;
            return Err("未收到新回执：请确认桥接已安装并重启游戏，且游戏仍在更新".into());
        }
        self.counter += 1;
        let nonce = format!("{}q{}", self.identity, self.counter);
        transport::atomic_write(
            &self.root.join("camera-request.txt"),
            format!("CAM1\n{nonce}\nINSPECT\nEND\n").as_bytes(),
        )?;
        self.pending = Some((nonce, Instant::now()));
        Ok(None)
    }
    pub fn control(&mut self, mask: u32) -> Result<Option<ControlStatus>, String> {
        self.control_with_settings(mask, SpawnSettings::default())
    }
    pub fn control_with_settings(
        &mut self,
        mask: u32,
        settings: SpawnSettings,
    ) -> Result<Option<ControlStatus>, String> {
        self.control_with_view(mask, settings, ViewSettings::default())
    }
    pub fn control_with_view(&mut self, mask: u32, settings: SpawnSettings, view: ViewSettings) -> Result<Option<ControlStatus>,String> {
        if !settings.valid() { return Err("倍率范围为 1–100".into()); }
        if !view.valid() { return Err("个人视口比例无效".into()); }
        if !valid_mask(mask) {
            return Err("位置解锁需要独立视角".into());
        }
        if let Some((nonce, serial, sent)) = &self.control_pending {
            if let Ok(file) = File::open(self.root.join("control-status.txt")) {
                let mut text = String::new();
                file.take(1025)
                    .read_to_string(&mut text)
                    .map_err(|e| e.to_string())?;
                if let Some(reply) = parse_control(&text, nonce, *serial) {
                    self.session = Some(reply.session.clone());
                    self.view_config_supported=reply.detail.split(';').any(|field| field=="view_config:1");
                    self.spawn_config_supported = reply
                        .detail
                        .split(';')
                        .any(|field| field == "spawn_config:1");
                    self.control_pending = None;
                    return Ok(Some(reply));
                }
            }
            if sent.elapsed() < Duration::from_secs(3) {
                return Ok(None);
            }
            self.control_pending = None;
            self.session = None;
            self.spawn_config_supported = false;
            self.view_config_supported = false;
            return Err("桥接回执超时，等待重新连接；远处还原需先归队".into());
        }
        if mask >= 4 && self.session.is_some() && !self.spawn_config_supported {
            return Err("当前桥接不支持刷怪配置，请退出游戏安装新版 Camera 模块并重启".into());
        }
        if view.0!=0 && mask%4!=0 && self.session.is_some() && !self.view_config_supported {
            return Err("当前桥接不支持个人视口比例，请更新 Camera 模块".into());
        }
        self.send_control(
            if self.session.is_some() { mask } else { 0 },
            self.spawn_config_supported.then_some(settings),
            self.view_config_supported.then_some(view),
        )?;
        Ok(None)
    }
    fn send_control(&mut self, mask: u32, settings: Option<SpawnSettings>, view: Option<ViewSettings>) -> Result<(), String> {
        self.counter = self
            .counter
            .checked_add(1)
            .filter(|v| *v <= i32::MAX as u64)
            .ok_or("请求序号耗尽，请重新打开")?;
        let nonce = format!("{}c{}", self.identity, self.counter);
        let session = self.session.as_deref().unwrap_or("-");
        let mut config = settings
            .map(|value| format!("SPAWN\n{}\n{}\n", value.encounter, value.patrol))
            .unwrap_or_default();
        if let Some(view)=view { config.push_str(&format!("VIEW\n{}\n",view.0)); }
        transport::atomic_write(
            &self.root.join("control-request.txt"),
            format!(
                "CAM2\n{nonce}\n{session}\n{}\n{}\n{mask}\n{config}END\n",
                self.identity, self.counter
            )
            .as_bytes(),
        )?;
        self.control_pending = Some((nonce, self.counter, Instant::now()));
        Ok(())
    }
    pub fn cancel(&mut self) {
        if self.session.is_some() {
            let _ = self.send_control(0, None, None);
        }
    }
}
impl Drop for Client {
    fn drop(&mut self) {
        self.cancel();
    }
}
#[derive(Debug, Clone)]
pub struct ControlStatus {
    pub session: String,
    pub desired: u32,
    pub applied: u32,
    pub owned: u32,
    pub detail: String,
}
impl ControlStatus {
    pub fn message(&self) -> String {
        let (camera, spawn) = self
            .detail
            .split_once(";spawn=")
            .unwrap_or((&self.detail, "off"));
        let fields: Vec<_> = spawn.split(';').collect();
        let spawn = fields[0];
        let field = |prefix: &str| fields.iter().find_map(|value| value.strip_prefix(prefix));
        let pending = field("alarm_pending:").unwrap_or("0");
        let camera_fields: Vec<_> = camera.split(';').collect();
        let mut camera_message: String = match camera_fields[0] {
            "off" => "已还原".into(),
            "menu" => "等待进入地面任务".into(),
            "local_ready_peer_unverified" => "本机已应用；队友视角隔离待双机验证".into(),
            "spectator_wait" => "死亡镜头停留 2 秒，然后观战队友".into(),
            "spectator_follow" => "观战队友：W/A 上一位，S/D 下一位".into(),
            "spectator_no_teammate" => "暂无存活队友；镜头停留，等待复活".into(),
            "return_to_team" => "等待返回团队屏幕范围，再恢复限制和镜头资格".into(),
            "vehicle_return_to_team" => "载具等待归队；返回公共范围后恢复边界与公共视角".into(),
            "vehicle_unlocked" => "载具可离屏；所有乘员均已启用独立视角和位置解锁".into(),
            "vehicle_team_boundary" => "载具保留公共边界；乘员尚未全部解除位置限制".into(),
            "vehicle_public_passenger" => "载具保留公共视角与边界；有公共视角乘员或同步尚未确认".into(),
            "vehicle_passenger" => "乘客独立视角已应用；车辆边界由驾驶控制端决定".into(),
            "vehicle_waiting_owner" => "独立视角已应用；等待原生车辆控制权迁移".into(),
            "vehicle_waiting_seats" => "独立视角已应用；等待载具乘员信息".into(),
            "suspended_character_or_vehicle" => "角色未就绪或座位不受支持，已暂停".into(),
            "waiting_follow_camera" => "等待正常跟随镜头，过场期间暂停".into(),
            "waiting_camera_replication" => "等待自身相机目标的复制与移除确认".into(),
            detail => describe(detail),
        };
        for field in camera_fields.iter().skip(1) {
            let message = if let Some(status) = field.strip_prefix("escort_transfer=") {
                match status.strip_prefix("waiting:") {
                    Some(count) => format!("人质控制权接收中：{count}；请留在交互范围内"),
                    None => "人质控制权已接收，已发送跟随交互".into(),
                }
            } else if let Some(error) = field.strip_prefix("escort_transfer_error=") {
                format!("人质接管未完成，本次交互未放行：{error}")
            } else {
                describe(field)
            };
            camera_message.push('\n');
            camera_message.push_str(&message);
        }
        let spawn_message = match spawn {
            "off" => return camera_message,
            "host_only" => "刷怪扩展：仅房主生效，当前为客机".into(),
            "waiting_task" | "waiting_managers" => "刷怪扩展：等待房主任务就绪".into(),
            "native_same_screen" => "刷怪扩展：已启用；全员同屏，按一个区域计算".into(),
            value if value.starts_with("expanded:") => {
                format!("刷怪扩展：覆盖 {} 名离屏玩家", &value["expanded:".len()..])
            }
            value => format!("刷怪扩展暂停：{value}"),
        };
        let alarm_message = if pending == "0" {
            "警报：不受公共视角限制；由房主运行敌人 AI".to_string()
        } else {
            format!("警报：等待 {pending} 个敌人的 AI 归属迁移至房主")
        };
        if matches!(spawn, "native_same_screen") || spawn.starts_with("expanded:") {
            let regional = field("regions:")
                .map(|count| {
                    format!(
                        "\n增援：{count} 个合并区域；最近选兵已占成本/总预算 {}",
                        field("regional_cost:").unwrap_or("待警报")
                    )
                })
                .unwrap_or_default();
            let capacity = field("regional_caps:")
                .map(|caps| {
                    format!(
                        "\n增援上限（每区/合计）：{caps}；全场敌人上限：{}",
                        field("global_cap:").unwrap_or("待确认")
                    )
                })
                .unwrap_or_default();
            let patrol = field("patrol_caps:")
                .map(|caps| format!("\n巡逻上限（每区/合计）：{caps}；各区额度独立"))
                .unwrap_or_default();
            format!(
                "{camera_message}\n{spawn_message}\n{alarm_message}{regional}{capacity}{patrol}"
            )
        } else {
            format!("{camera_message}\n{spawn_message}")
        }
    }
}
pub fn valid_mask(mask: u32) -> bool {
    matches!(mask, 0 | 1 | 3 | 4 | 5 | 7)
}
fn parse_control(text: &str, nonce: &str, serial: u64) -> Option<ControlStatus> {
    if text.len() > 1024 {
        return None;
    }
    let lines: Vec<_> = text.lines().collect();
    if lines.len() != 9
        || lines[0] != "CAM2"
        || lines[1] != nonce
        || lines[8] != "END"
        || lines[3].parse::<u64>().ok() != Some(serial)
        || lines[2].is_empty()
        || lines[2].len() > 80
        || !lines[2].bytes().all(|v| v.is_ascii_alphanumeric())
    {
        return None;
    }
    let mask = |index: usize| lines[index].parse::<u32>().ok().filter(|v| valid_mask(*v));
    Some(ControlStatus {
        session: lines[2].into(),
        desired: mask(4)?,
        applied: mask(5)?,
        owned: mask(6)?,
        detail: lines[7].into(),
    })
}
fn parse_reply<'a>(text: &'a str, nonce: &str) -> Option<&'a str> {
    if text.len() > 1024 {
        return None;
    }
    let lines: Vec<_> = text.lines().collect();
    if lines.len() != 6
        || lines[0] != "CAM1"
        || lines[1] != nonce
        || lines[5] != "END"
        || lines[2].is_empty()
        || !lines[2].bytes().all(|v| v.is_ascii_alphanumeric())
        || lines[3].parse::<u64>().ok().filter(|v| *v > 0).is_none()
    {
        return None;
    }
    Some(lines[4])
}
fn describe(detail: &str) -> String {
    match detail {
        "menu" => "桥接已响应；等待进入任务".into(),
        "waiting_avatar" => "桥接已响应；等待自己的角色".into(),
        "waiting_players" => "桥接已响应；等待玩家数据".into(),
        "waiting_own_master" => "自身镜头或移动组件尚未就绪".into(),
        value if value.starts_with("camera_error_pending_return:") => format!(
            "相机异常，尚有修改待归队还原：{}",
            &value["camera_error_pending_return:".len()..]
        ),
        value if value.starts_with("camera_error:") => format!(
            "相机异常，已停止应用；查看还原状态，取消后可重试：{}",
            &value["camera_error:".len()..]
        ),
        value if value.starts_with("local_players=") => format!("需要恰好一个本地玩家：{value}"),
        value => value.replace(';', "\n"),
    }
}
#[cfg(test)]
mod tests {
    #[test]
    fn embedded_module_valid() {
        super::module().unwrap();
    }
    #[test]
    fn stale_reply_not_accepted() {
        let text = "CAM1\nold\nsession1\n1\nmenu\nEND\n";
        assert!(super::parse_reply(text, "new").is_none());
        assert_eq!(super::parse_reply(text, "old"), Some("menu"));
        assert!(super::parse_reply(&(text.to_owned() + "garbage"), "old").is_none());
    }
    #[test]
    fn regional_capacity_and_migration_fields_are_independent() {
        let text = "CAM2\nnonce\nsession\n7\n4\n4\n4\noff;spawn=expanded:3;alarm_pending:2;regions:4;regional_cost:0/20;regional_caps:40/80;global_cap:200;patrol_caps:8/32;spawn_config:1\nEND\n";
        let message = super::parse_control(text, "nonce", 7).unwrap().message();
        assert!(message.contains("等待 2 个敌人"));
        assert!(message.contains("4 个合并区域"));
        assert!(message.contains("每区/合计）：40/80"));
        assert!(message.contains("全场敌人上限：200"));
        assert!(message.contains("巡逻上限（每区/合计）：8/32"));
    }
    #[test]
    fn spawn_settings_validate_saved_values_and_regional_formula() {
        use super::SpawnSettings;
        assert_eq!(
            SpawnSettings::parse("CAMSPAWN1\n2\n4\n").unwrap(),
            SpawnSettings::default()
        );
        for invalid in [
            "CAMSPAWN1\n0\n4",
            "CAMSPAWN1\n2\n101",
            "CAMSPAWN1\nNaN\n4",
            "CAMSPAWN1\n2\n4\nextra",
            "CAMSPAWN1\n1.5\n4",
        ] {
            assert!(SpawnSettings::parse(invalid).is_err());
        }
        for (total, regional) in [
            (1, 1.0),
            (2, 1.0),
            (4, 1.0),
            (5, 1.25),
            (8, 2.0),
            (100, 25.0),
        ] {
            assert_eq!(SpawnSettings::regional(total), regional);
        }
    }
    #[test]
    fn control_reply_requires_matching_nonce_sequence_and_supported_masks() {
        let text = "CAM2\nnonce\nsession\n7\n3\n1\n3\nreturn_to_team\nEND\n";
        assert!(super::parse_control(text, "old", 7).is_none());
        assert!(super::parse_control(text, "nonce", 8).is_none());
        assert_eq!(super::parse_control(text, "nonce", 7).unwrap().owned, 3);
        assert!(super::parse_control(&text.replace("\n3\n1\n", "\n2\n1\n"), "nonce", 7).is_none());
        let combined = "CAM2\nnonce\nsession\n7\n7\n5\n7\nreturn_to_team;spawn=expanded:2\nEND\n";
        assert_eq!(
            super::parse_control(combined, "nonce", 7).unwrap().applied,
            5
        );
        assert!(
            super::parse_control(&combined.replace("\n7\n5\n7\n", "\n6\n5\n7\n"), "nonce", 7)
                .is_none()
        );
        assert!(super::parse_control(combined, "nonce", 7)
            .unwrap()
            .message()
            .contains("2 名"));
    }
}
