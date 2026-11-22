//! Local display preference, independent of synchronized player mode bits.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct ViewSettings(pub u32);
impl ViewSettings {
    pub const CHOICES: &'static [(u32, &'static str)] = &[
        (0, "跟随游戏"),
        (1250, "5:4"),
        (1333, "4:3"),
        (1600, "16:10"),
        (1778, "16:9"),
    ];
    pub fn valid(self) -> bool {
        Self::CHOICES.iter().any(|(value, _)| *value == self.0)
    }
    pub fn label(self) -> &'static str {
        Self::CHOICES
            .iter()
            .find(|(value, _)| *value == self.0)
            .map(|(_, label)| *label)
            .unwrap_or("跟随游戏")
    }
    pub fn load() -> Result<Self, String> {
        let text = match std::fs::read_to_string(crate::directory()?.join("view-settings.txt")) {
            Ok(text) => text,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                return Ok(Self::default())
            }
            Err(error) => return Err(error.to_string()),
        };
        let value = Self(text.trim().parse().map_err(|_| "个人视口配置格式错误")?);
        if !value.valid() {
            return Err("个人视口比例无效".into());
        }
        Ok(value)
    }
    pub fn save(self) -> Result<(), String> {
        if !self.valid() {
            return Err("个人视口比例无效".into());
        }
        let root = crate::directory()?;
        std::fs::create_dir_all(&root).map_err(|error| error.to_string())?;
        crate::transport::atomic_write(
            &root.join("view-settings.txt"),
            format!("{}\n", self.0).as_bytes(),
        )
    }
}
