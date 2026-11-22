use std::{fs, path::Path};

pub const DIVE_HARDER_BUNDLE: &str = "05cd02202827e9a0";
pub const VANILLA_SHA: &str = "5ded3de9994ced0ee70597115c46c3604b754897b10de689c5b127ea8b1750a8";
pub const DIVE_VANILLA_SHA: &str =
    "e66e58696407ea4faf548d547d35284bb111276e9172c73a316d6dd02d02be45";
pub const DIVE_QOL_SHA: &str = "6ec601acf747b14666bde309e1f60f03df7db7f29ddda8b1c0039b40ee2acf1e";
const VANILLA_SCRIPT_SHA: &str = "8274d9e67af56be5f07bbff994ba4e7366599e439014d665c092c02a9f6ec624";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Boot {
    Vanilla,
    DiveHarder,
}

impl Boot {
    pub fn bundle(self) -> &'static str {
        match self {
            Self::Vanilla => super::install::BUNDLE,
            Self::DiveHarder => DIVE_HARDER_BUNDLE,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Vanilla => "原版启动包",
            Self::DiveHarder => "Dive Harder 启动包",
        }
    }

    pub fn accepts(self, hash: &str) -> bool {
        match self {
            Self::Vanilla => hash == VANILLA_SHA,
            Self::DiveHarder => matches!(hash, DIVE_VANILLA_SHA | DIVE_QOL_SHA),
        }
    }

    pub fn check_base(self, game: &Path, original_hash: &str) -> Result<(), String> {
        if self == Self::Vanilla {
            return Ok(());
        }
        let expected = match original_hash {
            DIVE_VANILLA_SHA => "72bebec1c173b046b03a933ef27860beddeca068a575d267fbaeb2122fffbcd4",
            DIVE_QOL_SHA => "c49e4597917682c4683f5062ccbc7d54992005120d994cf965e9aa73b735473d",
            _ => return Err("未验证的 Dive Harder 版本".into()),
        };
        let base = fs::read(game.join("contents/9cf71054ea26dddf"))
            .map_err(|error| format!("无法读取 Dive Harder 对应的基础资源：{error}"))?;
        if super::install::hash(&base) != expected {
            return Err("Dive Harder 与基础游戏 / QoL 资源版本不匹配，未安装桥接".into());
        }
        Ok(())
    }

    pub fn validate_original(self, bytes: &[u8]) -> Result<(), String> {
        let script = super::install::original_boot_hash(bytes)?;
        match self {
            Self::Vanilla if script == VANILLA_SCRIPT_SHA => Ok(()),
            Self::DiveHarder if self.accepts(&super::install::hash(bytes)) => Ok(()),
            _ => Err("启动脚本版本未验证；其他资源可修改，但不能跳过启动脚本校验".into()),
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
enum Token {
    Word(String),
    Quoted(String),
    Symbol(char),
}

fn tokens(text: &str) -> Result<Vec<Token>, String> {
    let mut input = text.trim_start_matches('\u{feff}').chars().peekable();
    let mut result = Vec::new();
    while let Some(character) = input.next() {
        if character.is_whitespace() {
            continue;
        }
        if character == '/' && input.peek() == Some(&'*') {
            input.next();
            let mut closed = false;
            while let Some(next) = input.next() {
                if next == '*' && input.peek() == Some(&'/') {
                    input.next();
                    closed = true;
                    break;
                }
            }
            if !closed {
                return Err("settings.ini 注释未闭合".into());
            }
        } else if character == '#' || (character == '/' && input.peek() == Some(&'/')) {
            for next in input.by_ref() {
                if next == '\n' {
                    break;
                }
            }
        } else if character == '"' {
            let mut value = String::new();
            let mut closed = false;
            while let Some(next) = input.next() {
                if next == '"' {
                    closed = true;
                    break;
                }
                if next == '\\' {
                    value.push(input.next().ok_or("settings.ini 字符串转义未完成")?);
                } else {
                    value.push(next);
                }
            }
            if !closed {
                return Err("settings.ini 字符串未闭合".into());
            }
            result.push(Token::Quoted(value));
        } else if character.is_ascii_alphanumeric() || character == '_' {
            let mut word = character.to_string();
            while input
                .peek()
                .is_some_and(|next| next.is_ascii_alphanumeric() || *next == '_')
            {
                word.push(input.next().unwrap());
            }
            result.push(Token::Word(word));
        } else {
            result.push(Token::Symbol(character));
        }
    }
    Ok(result)
}

pub fn parse(text: &str) -> Result<Boot, String> {
    let tokens = tokens(text)?;
    let mut depth = 0usize;
    let mut package = None;
    let mut script = None;
    for (index, token) in tokens.iter().enumerate() {
        match token {
            Token::Symbol('{' | '[') => depth += 1,
            Token::Symbol('}' | ']') => {
                depth = depth.checked_sub(1).ok_or("settings.ini 括号不匹配")?
            }
            Token::Word(key)
                if depth == 0 && matches!(key.as_str(), "boot_package" | "boot_script") =>
            {
                let destination = if key == "boot_package" {
                    &mut package
                } else {
                    &mut script
                };
                if destination.is_some() {
                    return Err(format!("settings.ini 存在重复 {key}，无法确定启动入口"));
                }
                match (tokens.get(index + 1), tokens.get(index + 2)) {
                    (Some(Token::Symbol('=')), Some(Token::Quoted(value))) => {
                        *destination = Some(value.as_str())
                    }
                    _ => return Err(format!("settings.ini 的 {key} 格式无法识别")),
                }
            }
            _ => {}
        }
    }
    if depth != 0 {
        return Err("settings.ini 括号未闭合".into());
    }
    if script != Some("lua/boot/boot") {
        return Err(format!("不支持的 boot_script：{script:?}，未修改启动配置"));
    }
    match package {
        Some("resource_packages/boot") => Ok(Boot::Vanilla),
        Some("resource_packages/boot_dh") => Ok(Boot::DiveHarder),
        _ => Err(format!(
            "不支持或缺失 boot_package：{package:?}，请收集诊断包"
        )),
    }
}

pub fn read(game: &Path) -> Result<(Boot, Vec<u8>), String> {
    let bytes = fs::read(game.join("contents/settings.ini"))
        .map_err(|error| format!("无法读取启动配置 settings.ini：{error}"))?;
    let text = std::str::from_utf8(&bytes).map_err(|_| "settings.ini 不是 UTF-8，未修改文件")?;
    Ok((parse(text)?, bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selects_only_top_level_settings_and_ignores_comments() {
        let settings = "\u{feff}// boot_package = \"fake\"\nboot_package = \"resource_packages/boot_dh\"\nboot_script = \"lua/boot/boot\"\nnetwork = { boot_package = \"other\" }\n/* boot_script = \"other\" */";
        assert_eq!(parse(settings).unwrap(), Boot::DiveHarder);
        assert_eq!(
            parse(&settings.replace("boot_dh", "boot")).unwrap(),
            Boot::Vanilla
        );
    }

    #[test]
    fn rejects_unknown_ambiguous_and_incomplete_entry_points() {
        for settings in [
            "", "boot_package = \"resource_packages/boot_dh\"",
            "boot_script = \"lua/boot/boot\" boot_package = \"unknown\"",
            "boot_script = \"lua/boot/boot\" boot_package = \"resource_packages/boot\" boot_package = \"resource_packages/boot_dh\"",
            "boot_script = \"lua/boot/boot\" boot_package = \"resource_packages/boot\" /*",
        ] { assert!(parse(settings).is_err(), "{settings}"); }
    }

    #[test]
    fn bundle_versions_do_not_cross_targets() {
        assert!(Boot::Vanilla.accepts(VANILLA_SHA));
        assert!(!Boot::Vanilla.accepts(DIVE_VANILLA_SHA));
        assert!(Boot::DiveHarder.accepts(DIVE_VANILLA_SHA));
        assert!(Boot::DiveHarder.accepts(DIVE_QOL_SHA));
        assert!(!Boot::DiveHarder.accepts(VANILLA_SHA));
    }
}
