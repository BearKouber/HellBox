//! Find a local installation without a machine-specific drive or username.
use std::{
    ffi::OsString,
    os::windows::ffi::OsStringExt,
    path::{Component, Path, PathBuf},
};
use windows_sys::Win32::{System::Registry::*, UI::Controls::Dialogs::*};

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(Some(0)).collect()
}

fn registry(root: HKEY, key: &str, name: &str, view: u32) -> Option<PathBuf> {
    let (key, name) = (wide(key), wide(name));
    let mut text = vec![0u16; 32768];
    let mut bytes = (text.len() * 2) as u32;
    let result = unsafe {
        RegGetValueW(
            root,
            key.as_ptr(),
            name.as_ptr(),
            RRF_RT_REG_SZ | view,
            std::ptr::null_mut(),
            text.as_mut_ptr().cast(),
            &mut bytes,
        )
    };
    if result != 0 {
        return None;
    }
    let end = text.iter().position(|c| *c == 0)?;
    if end == 0 {
        return None;
    }
    Some(PathBuf::from(OsString::from_wide(&text[..end])))
}

pub fn is_game_dir(path: &Path) -> bool {
    path.join("contents").join(super::install::BUNDLE).is_file()
        && path.join("binaries/x64/helldivers.exe").is_file()
}
pub fn from_executable(path: &Path) -> Option<PathBuf> {
    path.ancestors()
        .find(|p| is_game_dir(p))
        .map(Path::to_path_buf)
}

// Small KeyValues lexer: preserve escaped Windows paths and Unicode, ignore
// comments, and keep braces distinct so section names cannot become file paths.
fn pairs(text: &str) -> Vec<(String, String)> {
    let mut tokens: Vec<Option<String>> = Vec::new();
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '/' && chars.peek() == Some(&'/') {
            for c in chars.by_ref() {
                if c == '\n' {
                    break;
                }
            }
        } else if c == '{' || c == '}' {
            tokens.push(None);
        } else if c == '"' {
            let mut value = String::new();
            while let Some(c) = chars.next() {
                if c == '"' {
                    break;
                }
                if c == '\\' && matches!(chars.peek(), Some('\\' | '"')) {
                    value.push(chars.next().unwrap());
                } else {
                    value.push(c);
                }
            }
            tokens.push(Some(value));
        }
    }
    let mut result = Vec::new();
    let mut index = 0;
    while index + 1 < tokens.len() {
        if let (Some(key), Some(value)) = (&tokens[index], &tokens[index + 1]) {
            result.push((key.clone(), value.clone()));
            index += 2;
        } else {
            index += 1;
        }
    }
    result
}
fn manifest_dir(text: &str) -> Option<String> {
    let items = pairs(text);
    if !items.iter().any(|(k, v)| k == "appid" && v == "394510") {
        return None;
    }
    let name = &items.iter().find(|(k, _)| k == "installdir")?.1;
    // An install directory is a single child of steamapps/common, not a path.
    let mut parts = Path::new(name).components();
    if !matches!(parts.next(), Some(Component::Normal(_))) || parts.next().is_some() {
        return None;
    }
    Some(name.clone())
}
fn library_paths(text: &str) -> Vec<PathBuf> {
    pairs(text)
        .into_iter()
        .filter_map(|(k, v)| {
            // Current format uses path; older Steam versions use numeric keys.
            let path = PathBuf::from(v);
            ((k == "path" || k.chars().all(|c| c.is_ascii_digit())) && path.is_absolute())
                .then_some(path)
        })
        .collect()
}
pub fn game_in_libraries(steam: &Path) -> Option<PathBuf> {
    let mut libraries = vec![steam.to_path_buf()];
    if let Ok(vdf) = std::fs::read_to_string(steam.join("steamapps/libraryfolders.vdf")) {
        libraries.extend(library_paths(&vdf));
    }
    for library in libraries {
        let apps = library.join("steamapps");
        let Ok(text) = std::fs::read_to_string(apps.join("appmanifest_394510.acf")) else {
            continue;
        };
        let Some(name) = manifest_dir(&text) else {
            continue;
        };
        let path = apps.join("common").join(name);
        if is_game_dir(&path) {
            return Some(path);
        }
    }
    None
}
pub fn game(preferred: Option<&Path>) -> Option<PathBuf> {
    if let Some(root) = crate::win::find_pid("helldivers.exe")
        .and_then(crate::win::process_image_path)
        .and_then(|p| from_executable(&p))
    {
        return Some(root);
    }
    if let Some(path) = preferred.filter(|p| is_game_dir(p)) {
        return Some(path.to_path_buf());
    }
    let mut steam = Vec::new();
    if let Some(p) = crate::win::find_pid("steam.exe").and_then(crate::win::process_image_path) {
        if let Some(p) = p.parent() {
            steam.push(p.to_path_buf());
        }
    }
    if let Some(p) = registry(HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath", 0) {
        steam.push(p);
    }
    for view in [RRF_SUBKEY_WOW6432KEY, RRF_SUBKEY_WOW6464KEY] {
        if let Some(p) = registry(
            HKEY_LOCAL_MACHINE,
            r"Software\Valve\Steam",
            "InstallPath",
            view,
        ) {
            steam.push(p);
        }
    }
    for env in ["ProgramFiles(x86)", "ProgramFiles"] {
        if let Some(p) = std::env::var_os(env) {
            steam.push(PathBuf::from(p).join("Steam"));
        }
    }
    steam.into_iter().find_map(|p| game_in_libraries(&p))
}

pub fn choose_game() -> Result<Option<PathBuf>, String> {
    let mut file = vec![0u16; 32768];
    let filter = wide("Helldivers 程序\0helldivers.exe\0");
    let title = wide("选择游戏的 binaries\\x64\\helldivers.exe");
    let mut dialog: OPENFILENAMEW = unsafe { std::mem::zeroed() };
    dialog.lStructSize = std::mem::size_of::<OPENFILENAMEW>() as u32;
    dialog.lpstrFilter = filter.as_ptr();
    dialog.nFilterIndex = 1;
    dialog.lpstrFile = file.as_mut_ptr();
    dialog.nMaxFile = file.len() as u32;
    dialog.lpstrTitle = title.as_ptr();
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_EXPLORER | OFN_NOCHANGEDIR;
    if unsafe { GetOpenFileNameW(&mut dialog) } == 0 {
        let error = unsafe { CommDlgExtendedError() };
        return if error == 0 {
            Ok(None)
        } else {
            Err(format!("打开选择窗口失败：{error}"))
        };
    }
    let end = file.iter().position(|c| *c == 0).unwrap_or(file.len());
    let selected = PathBuf::from(OsString::from_wide(&file[..end]));
    from_executable(&selected)
        .map(Some)
        .ok_or_else(|| "所选文件旁未找到完整的 Helldivers 游戏目录".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn steam_paths_support_new_old_unicode_and_spaces() {
        let new = r#""libraryfolders" { "0" { "path" "F:\\游戏库\\Steam Library" "apps" { "394510" "42" } } }"#;
        assert_eq!(
            library_paths(new),
            vec![PathBuf::from(r"F:\游戏库\Steam Library")]
        );
        let old = "\"LibraryFolders\" {\n// \"path\" \"Z:\\\\fake\"\n\"1\" \"G:\\\\Games\"\n}";
        assert_eq!(library_paths(old), vec![PathBuf::from(r"G:\Games")]);
    }
    #[test]
    fn manifest_rejects_another_game_and_paths_outside_common() {
        assert_eq!(
            manifest_dir(r#""AppState" { "appid" "394510" "installdir" "Helldivers" }"#),
            Some("Helldivers".into())
        );
        for name in ["..", r"..\outside", r"C:\outside", ""] {
            assert!(
                manifest_dir(&format!("\"appid\" \"394510\" \"installdir\" \"{name}\"")).is_none()
            );
        }
        assert!(manifest_dir(r#""appid" "123" "installdir" "Helldivers""#).is_none());
    }
}
