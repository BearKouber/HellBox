//! Version-checked, reversible boot-resource patch. Never patches a running game.
use flate2::{read::ZlibDecoder, write::ZlibEncoder, Compression};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
};

pub const BUNDLE: &str = "9e13b2414b41b842";
use super::boot::{self, Boot};
use std::collections::{BTreeMap, BTreeSet};
const BOOT_ID: [u8; 16] = [
    0xe2, 0x17, 0xd1, 0x2c, 0xfa, 0x8d, 0x4e, 0xa1, 0x81, 0xdc, 0xbd, 0x8a, 0x61, 0x8a, 0x04, 0x37,
];
pub fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn u32_at(b: &[u8], p: usize) -> Result<usize, String> {
    Ok(u32::from_le_bytes(b.get(p..p + 4).ok_or("截断的资源包")?.try_into().unwrap()) as usize)
}
fn uleb(b: &[u8], p: &mut usize) -> Result<usize, String> {
    let mut n = 0;
    for shift in (0..35).step_by(7) {
        let v = *b.get(*p).ok_or("截断的字节码")?;
        *p += 1;
        n |= ((v & 127) as usize) << shift;
        if v < 128 {
            return Ok(n);
        }
    }
    Err("无效 ULEB128".into())
}
fn put_uleb(out: &mut Vec<u8>, mut n: usize) {
    loop {
        let v = (n & 127) as u8;
        n >>= 7;
        out.push(v | if n == 0 { 0 } else { 128 });
        if n == 0 {
            break;
        }
    }
}
fn instruction(op: u8, a: u8, d: usize) -> [u8; 4] {
    [op, a, d as u8, (d >> 8) as u8]
}

pub fn unpack(packed: &[u8]) -> Result<Vec<u8>, String> {
    if u32_at(packed, 0)? != 0xf0000004 || u32_at(packed, 8)? != 0 {
        return Err("不支持的资源包格式".into());
    }
    let size = u32_at(packed, 4)?;
    if size > 128 * 1024 * 1024 {
        return Err("资源包超出验证范围".into());
    }
    let mut out = Vec::new();
    let mut pos = 12;
    while out.len() < size {
        let n = u32_at(packed, pos)?;
        pos += 4;
        let block = packed.get(pos..pos + n).ok_or("压缩块截断")?;
        pos += n;
        let decoded = if n == 65536 {
            block.to_vec()
        } else {
            let mut bytes = Vec::new();
            ZlibDecoder::new(block)
                .take(65537)
                .read_to_end(&mut bytes)
                .map_err(|e| e.to_string())?;
            bytes
        };
        if decoded.len() != 65536 {
            return Err("解压块长度不符".into());
        }
        out.extend(decoded);
    }
    if pos != packed.len() {
        return Err("资源包存在未解析尾部".into());
    }
    out.truncate(size);
    Ok(out)
}
pub fn pack(raw: &[u8]) -> Result<Vec<u8>, String> {
    let mut out = Vec::new();
    for n in [0xf0000004u32, raw.len() as u32, 0] {
        out.extend(n.to_le_bytes());
    }
    for part in raw.chunks(65536) {
        let mut block = vec![0; 65536];
        block[..part.len()].copy_from_slice(part);
        let mut enc = ZlibEncoder::new(Vec::new(), Compression::default());
        enc.write_all(&block).map_err(|e| e.to_string())?;
        let compressed = enc.finish().map_err(|e| e.to_string())?;
        let chosen = if compressed.len() < 65536 {
            compressed
        } else {
            block
        };
        out.extend((chosen.len() as u32).to_le_bytes());
        out.extend(chosen);
    }
    Ok(out)
}

/// Keep every child prototype and all old constant indices unchanged.
/// The new constants are PREPENDED in serialized KGC order (reverse indices).
fn patch_chunk(chunk: &[u8], adapter: &[u8], module_id: &str) -> Result<Vec<u8>, String> {
    if adapter.get(..5) != Some(&[27, 76, 74, 1, 2]) || adapter.last() != Some(&0) {
        return Err("适配器字节码格式不符".into());
    }
    if chunk.get(..5) != Some(&[27, 76, 74, 1, 2]) {
        return Err("启动字节码不是已验证的 stripped LuaJIT v1".into());
    }
    let mut p = 5;
    let mut last = None;
    loop {
        let prefix = p;
        let size = uleb(chunk, &mut p)?;
        if size == 0 {
            break;
        }
        let end = p
            .checked_add(size)
            .filter(|n| *n <= chunk.len())
            .ok_or("原型长度无效")?;
        last = Some((prefix, p, end));
        p = end;
    }
    if p != chunk.len() {
        return Err("字节码尾部无效".into());
    }
    let (prefix, start, end) = last.ok_or("缺少启动原型")?;
    let original = &chunk[start..end];
    if original.len() < 4 {
        return Err("启动原型头截断".into());
    }
    let mut q = 4;
    let ngc = uleb(original, &mut q)?;
    let nnum = uleb(original, &mut q)?;
    let nbc = uleb(original, &mut q)?;
    let code_start = q;
    let code_end = q + nbc * 4;
    let uv_end = code_end + original[3] as usize * 2;
    if ngc > 65000
        || nbc == 0
        || uv_end > original.len()
        || original.get(code_end - 4..code_end) != Some(&[71, 0, 1, 0])
    {
        return Err("启动原型结构不匹配".into());
    }
    let mut body = original[..4].to_vec();
    body[0] |= 1; // PROTO_CHILD: the root now contains the adapter closure.
    body[2] = body[2].max(16);
    // The adapter root has zero upvalues; FNEW inherits this boot function's VM environment.
    put_uleb(&mut body, ngc + 4);
    put_uleb(&mut body, nnum);
    put_uleb(&mut body, nbc + 5);
    body.extend(&original[code_start..code_end - 4]);
    // pcall(precompiled_adapter); the release VM forbids dynamic loadstring.
    body.extend(instruction(52, 13, ngc));
    body.extend(instruction(49, 14, ngc + 1));
    body.extend([62, 13, 2, 3]); // pcall success flag, runtime error
    body.extend(instruction(53, 13, ngc + 2));
    body.extend(instruction(53, 14, ngc + 3));
    body.extend([71, 0, 1, 0]);
    body.extend(&original[code_end..uv_end]);
    let error_name = if module_id == "captain" {
        "CaptainHelldiverBridgeBootError".into()
    } else {
        format!("HelldiversBridgeBootError_{module_id}")
    };
    let success_name = if module_id == "captain" {
        "CaptainHelldiverBridgeBootOk".into()
    } else {
        format!("HelldiversBridgeBootOk_{module_id}")
    };
    for s in [&error_name, &success_name] {
        put_uleb(&mut body, s.len() + 5);
        body.extend(s.as_bytes());
    }
    body.push(0); // KGC_CHILD: pop the newly appended adapter root first.
    put_uleb(&mut body, "pcall".len() + 5);
    body.extend(b"pcall");
    body.extend(&original[uv_end..]);
    let mut result = chunk[..prefix].to_vec();
    result.extend(&adapter[5..adapter.len() - 1]);
    put_uleb(&mut result, body.len());
    result.extend(body);
    result.push(0);
    Ok(result)
}

/// Validate the complete resource index. Only the boot payload may change size.
fn boot_record(raw: &[u8]) -> Result<(usize, usize), String> {
    let count = u32_at(raw, 0)?;
    if count > 10000 {
        return Err("资源数量异常".into());
    }
    let mut pos = 260 + 16 * count;
    let mut found = None;
    let mut identifiers = BTreeSet::new();
    for i in 0..count {
        let id = raw.get(pos..pos + 16).ok_or("资源记录截断")?;
        if !identifiers.insert(id.to_vec())
            || Some(id) != raw.get(260 + 16 * i..276 + 16 * i)
            || u32_at(raw, pos + 16)? != 1
            || u32_at(raw, pos + 20)? != 0
        {
            return Err("资源索引/分段格式不符".into());
        }
        let size = u32_at(raw, pos + 28)?;
        if id == BOOT_ID {
            if found.is_some()
                || size < 8
                || u32_at(raw, pos + 24)? != 0
                || u32_at(raw, pos + 32)? != 0
                || u32_at(raw, pos + 36)? + 8 != size
                || u32_at(raw, pos + 40)? != 2
            {
                return Err("启动资源记录不符".into());
            }
            found = Some((pos, size));
        }
        pos = pos
            .checked_add(36 + size)
            .filter(|p| *p <= raw.len())
            .ok_or("资源越界")?;
    }
    if pos != raw.len() {
        return Err("资源表未覆盖完整文件".into());
    }
    found.ok_or_else(|| "未找到启动脚本资源".into())
}

pub(crate) fn original_boot_hash(packed: &[u8]) -> Result<String, String> {
    let raw = unpack(packed)?;
    let (start, size) = boot_record(&raw)?;
    let chunk = &raw[start + 44..start + 36 + size];
    validate_bytecode(chunk)?;
    Ok(hash(chunk))
}

fn patch_raw(raw: &[u8], adapter: &[u8], module_id: &str) -> Result<Vec<u8>, String> {
    let (start, size) = boot_record(raw)?;
    let chunk = patch_chunk(&raw[start + 44..start + 36 + size], adapter, module_id)?;
    let mut result = raw[..start + 44].to_vec();
    result[start + 28..start + 32].copy_from_slice(&((chunk.len() + 8) as u32).to_le_bytes());
    result[start + 36..start + 40].copy_from_slice(&(chunk.len() as u32).to_le_bytes());
    result.extend(chunk);
    result.extend(&raw[start + 36 + size..]);
    Ok(result)
}

#[derive(Clone, Debug)]
pub struct Module {
    pub id: String,
    pub bytecode: Vec<u8>,
}
impl Module {
    pub fn new(id: &str, bytecode: &[u8]) -> Result<Self, String> {
        if !matches!(id, "captain" | "camera" | "recorder" | "enemy") {
            return Err("未知模块标识".into());
        }
        validate_bytecode(bytecode)?;
        Ok(Self {
            id: id.into(),
            bytecode: bytecode.to_vec(),
        })
    }
}
fn validate_bytecode(bytes: &[u8]) -> Result<(), String> {
    if bytes.len() > 4 * 1024 * 1024 || bytes.get(..5) != Some(&[27, 76, 74, 1, 2]) {
        return Err("模块必须是 LuaJIT 2.0 stripped dump v1".into());
    }
    let mut p = 5;
    let mut root = None;
    loop {
        let len = uleb(bytes, &mut p)?;
        if len == 0 {
            break;
        }
        let end = p
            .checked_add(len)
            .filter(|n| *n <= bytes.len())
            .ok_or("模块原型越界")?;
        if len < 4 {
            return Err("模块原型头截断".into());
        }
        root = Some(p);
        p = end;
    }
    if p != bytes.len() || root.is_none() || bytes[root.unwrap() + 3] != 0 {
        return Err("模块必须完整且根闭包没有 upvalue".into());
    }
    Ok(())
}
pub fn prepare(original: &[u8], modules: &BTreeMap<String, Module>) -> Result<Vec<u8>, String> {
    let target = if Boot::DiveHarder.accepts(&hash(original)) {
        Boot::DiveHarder
    } else {
        Boot::Vanilla
    };
    target.validate_original(original)?;
    if modules.is_empty() {
        return Ok(original.to_vec());
    }
    let mut raw = unpack(original)?;
    for (id, module) in modules {
        if id != &module.id {
            return Err("模块名不匹配".into());
        }
        Module::new(id, &module.bytecode)?;
        raw = patch_raw(&raw, &module.bytecode, id)?;
    }
    let packed = pack(&raw)?;
    if unpack(&packed)? != raw {
        return Err("回包验证失败".into());
    }
    Ok(packed)
}
fn digest(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}
fn manifest(original: &str, patched: &str, modules: &BTreeMap<String, Module>) -> String {
    let mut text = format!("HDB1\n{original}\n{patched}\n");
    for (id, module) in modules {
        text.push_str(&format!("{id} {}\n", hash(&module.bytecode)));
    }
    text
}
fn parse_manifest(
    text: &str,
    original: &str,
    current: &str,
) -> Result<BTreeMap<String, String>, String> {
    let mut lines = text.lines();
    if text.len() > 4096
        || lines.next() != Some("HDB1")
        || lines.next() != Some(original)
        || lines.next() != Some(current)
    {
        return Err("共享桥接安装清单不匹配".into());
    }
    let mut result = BTreeMap::new();
    for line in lines {
        let (id, sha) = line.split_once(' ').ok_or("模块清单格式无效")?;
        if !matches!(id, "captain" | "camera" | "recorder" | "enemy")
            || !digest(sha)
            || result.insert(id.into(), sha.into()).is_some()
        {
            return Err("模块清单含重复、未知或损坏条目".into());
        }
    }
    Ok(result)
}
struct State {
    target: Boot,
    settings: Vec<u8>,
    path: PathBuf,
    original: Vec<u8>,
    current: Vec<u8>,
    store: PathBuf,
    modules: BTreeMap<String, Module>,
    legacy: bool,
}
fn read_state(game: &Path, owner: &str) -> Result<State, String> {
    let (target, settings) = boot::read(game)?;
    let path = game.join("contents").join(target.bundle());
    let current = fs::read(&path).map_err(|e| e.to_string())?;
    let backup = game
        .join("captain_bridge_backup")
        .join(format!("{}.original", target.bundle()));
    let current_sha = hash(&current);
    let store = game.join("helldivers_bridge_v1").join(target.bundle());
    let entry = store.join(format!("{current_sha}.manifest"));
    let mut modules = BTreeMap::new();
    let mut legacy = false;
    let original = if entry.exists() {
        let text = fs::read_to_string(entry).map_err(|e| e.to_string())?;
        let original_sha = text
            .lines()
            .nth(1)
            .filter(|value| digest(value))
            .ok_or("共享桥接清单缺少有效原包哈希")?;
        let versioned = store.join(format!("{original_sha}.original"));
        let original = fs::read(if versioned.exists() {
            versioned
        } else {
            backup.clone()
        })
        .map_err(|error| format!("缺少对应版本的桥接恢复资源：{error}"))?;
        if hash(&original) != original_sha {
            return Err("桥接恢复资源哈希不符，未覆盖".into());
        }
        target.validate_original(&original)?;
        for (id, sha) in parse_manifest(&text, &original_sha, &current_sha)? {
            let bytes = fs::read(store.join(format!("{sha}.luac")))
                .map_err(|e| format!("缺少已安装模块 {id}：{e}"))?;
            if hash(&bytes) != sha {
                return Err(format!("模块 {id} 校验失败，未覆盖"));
            }
            modules.insert(id.clone(), Module::new(&id, &bytes)?);
        }
        if unpack(&prepare(&original, &modules)?)? != unpack(&current)? {
            return Err("启动包与安装清单重建内容不一致，未覆盖".into());
        }
        original
    } else if target.validate_original(&current).is_ok() {
        current.clone()
    } else {
        let receipt = game
            .join("captain_bridge_backup")
            .join(format!("{}.sha256", target.bundle()));
        let recognized = fs::read_to_string(receipt)
            .unwrap_or_default()
            .lines()
            .any(|v| v == current_sha);
        if !recognized {
            return Err(
                "启动脚本或资源结构不受支持，且没有匹配的桥接清单；保留现场，未覆盖其他 Mod".into(),
            );
        }
        if owner != "captain" {
            return Err("检测到旧版 Captain 独占桥接；请先用新版 Captain 更新一次以迁移安装记录，之后两个模块可独立增删".into());
        }
        legacy = true;
        let original =
            fs::read(&backup).map_err(|error| format!("缺少旧版桥接恢复资源：{error}"))?;
        target.validate_original(&original)?;
        original
    };
    Ok(State {
        target,
        settings,
        path,
        original,
        current,
        store,
        modules,
        legacy,
    })
}
/// Prepare a complete package while preserving other registered modules.
pub fn prepare_game(game: &Path, module: Module) -> Result<Vec<u8>, String> {
    let mut state = read_state(game, &module.id)?;
    state.modules.insert(module.id.clone(), module);
    prepare(&state.original, &state.modules)
}
pub fn active_manifest_path(game: &Path, target: Boot) -> Result<PathBuf, String> {
    let bytes = fs::read(game.join("contents").join(target.bundle())).map_err(|e| e.to_string())?;
    Ok(game
        .join("helldivers_bridge_v1")
        .join(target.bundle())
        .join(format!("{}.manifest", hash(&bytes))))
}
/// The game resource is the commit point. Its SHA selects an immutable manifest.
/// A crash before/after replacement always leaves a matching complete manifest.
pub fn install(game: &Path, module: Module, remove: bool) -> Result<String, String> {
    if crate::win::find_pid("helldivers.exe").is_some() {
        return Err("请正常退出游戏后安装或卸载模块".into());
    }
    let legacy_dir = game.join("captain_bridge_backup");
    fs::create_dir_all(&legacy_dir).map_err(|e| e.to_string())?;
    // Same lock path as older Captain installers; operations cannot interleave.
    let _lock = crate::transport::exclusive_file(&legacy_dir.join("install.lock"))?;
    let mut state = read_state(game, &module.id)?;
    if !remove {
        state.target.check_base(game, &hash(&state.original))?;
    }
    let id = module.id.clone();
    if remove {
        state.modules.remove(&id);
    } else {
        state.modules.insert(id.clone(), module);
    }
    let patched = prepare(&state.original, &state.modules)?;
    fs::create_dir_all(&state.store).map_err(|e| e.to_string())?;
    let backup = legacy_dir.join(format!("{}.original", state.target.bundle()));
    if !backup.exists() {
        crate::transport::atomic_write(&backup, &state.original)?;
    }
    let original_sha = hash(&state.original);
    let versioned = state.store.join(format!("{original_sha}.original"));
    if versioned.exists() {
        if fs::read(&versioned).map_err(|error| error.to_string())? != state.original {
            return Err("对应版本的恢复资源损坏，未覆盖".into());
        }
    } else {
        crate::transport::atomic_write(&versioned, &state.original)?;
    }
    for module in state.modules.values() {
        let sha = hash(&module.bytecode);
        crate::transport::atomic_write(&state.store.join(format!("{sha}.luac")), &module.bytecode)?;
    }
    let patched_sha = hash(&patched);
    let record = manifest(&hash(&state.original), &patched_sha, &state.modules);
    crate::transport::atomic_write(
        &state.store.join(format!("{patched_sha}.manifest")),
        record.as_bytes(),
    )?;
    // IPC folders are independent. Do not remove another module's request files.
    let appdata = PathBuf::from(std::env::var_os("APPDATA").ok_or("缺少 APPDATA")?)
        .join("Arrowhead/Helldivers");
    for id in state.modules.keys() {
        fs::create_dir_all(appdata.join(match id.as_str() {
            "captain" => "captain_bridge_v1",
            "camera" => "camera_ctrl_v1",
            "recorder" => "game_recorder_v1",
            "enemy" => "enemy_edit_v1",
            _ => return Err("未知模块标识".into()),
        }))
        .map_err(|e| e.to_string())?;
    }
    if crate::win::find_pid("helldivers.exe").is_some()
        || fs::read(&state.path).map_err(|e| e.to_string())? != state.current
        || fs::read(game.join("contents/settings.ini")).map_err(|e| e.to_string())?
            != state.settings
    {
        return Err("安装期间游戏或资源状态变化，未提交启动包".into());
    }
    crate::transport::atomic_write(&state.path, &patched)?;
    if hash(&fs::read(&state.path).map_err(|e| e.to_string())?) != patched_sha {
        return Err("资源读回校验失败".into());
    }
    let remaining = state.modules.keys().cloned().collect::<Vec<_>>().join("、");
    Ok(format!(
        "{}：{}模块 {id}；{}{}。重启游戏后生效",
        state.target.label(),
        if remove { "已卸载" } else { "已安装" },
        if state.legacy {
            "已迁移旧版安装；"
        } else {
            ""
        },
        if remaining.is_empty() {
            "全部模块已移除，原始资源已恢复".into()
        } else {
            format!("保留模块：{remaining}")
        }
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn tiny(value: &str) -> Vec<u8> {
        let mut body = vec![2, 0, 2, 0, 1, 0, 2, 37, 0, 0, 0, 71, 0, 1, 0];
        put_uleb(&mut body, value.len() + 5);
        body.extend(value.as_bytes());
        let mut chunk = vec![27, 76, 74, 1, 2];
        put_uleb(&mut chunk, body.len());
        chunk.extend(body);
        chunk.push(0);
        chunk
    }
    #[test]
    fn independent_modules_can_be_composed_in_either_order() {
        let root = tiny("original");
        let a = tiny("camera");
        let b = tiny("captain");
        let recorder = tiny("recorder");
        let enemy = tiny("enemy");
        for order in [
            vec![
                (&a, "camera"),
                (&b, "captain"),
                (&recorder, "recorder"),
                (&enemy, "enemy"),
            ],
            vec![
                (&enemy, "enemy"),
                (&recorder, "recorder"),
                (&b, "captain"),
                (&a, "camera"),
            ],
        ] {
            let mut composed = root.clone();
            for (bytes, id) in order {
                composed = patch_chunk(&composed, bytes, id).unwrap();
            }
            validate_bytecode(&composed).unwrap();
            assert!(composed.windows(6).any(|v| v == b"camera"));
            assert!(composed.windows(7).any(|v| v == b"captain"));
            assert!(composed.windows(8).any(|v| v == b"recorder"));
            assert!(composed.windows(8).any(|v| v == b"original"));
            assert!(composed.windows(5).any(|v| v == b"enemy"));
        }
    }
    #[test]
    fn manifest_rejects_corruption_duplicates_and_path_escape() {
        let sha = "a".repeat(64);
        let header = format!("HDB1\n{sha}\n{sha}\n");
        assert!(parse_manifest(&format!("{header}camera {sha}\n"), &sha, &sha).is_ok());
        for tail in [
            format!("../escape {sha}\n"),
            format!("camera {sha}\ncamera {sha}\n"),
            "captain broken\n".into(),
        ] {
            assert!(parse_manifest(&(header.clone() + &tail), &sha, &sha).is_err());
        }
        assert!(parse_manifest(&header, &sha, &"b".repeat(64)).is_err());
    }
    #[test]
    fn removing_one_module_preserves_the_other_payload() {
        let mut modules = BTreeMap::new();
        for id in ["camera", "captain", "recorder", "enemy"] {
            modules.insert(id.into(), Module::new(id, &tiny(id)).unwrap());
        }
        let old = modules["camera"].bytecode.clone();
        modules.remove("captain");
        let recorder = modules.remove("recorder").unwrap();
        assert_eq!(recorder.bytecode, tiny("recorder"));
        assert_eq!(modules.remove("enemy").unwrap().bytecode, tiny("enemy"));
        assert_eq!(modules["camera"].bytecode, old);
        let sha = "a".repeat(64);
        assert_eq!(
            parse_manifest(&manifest(&sha, &sha, &modules), &sha, &sha)
                .unwrap()
                .len(),
            1
        );
    }
    #[test]
    fn codec_round_trip_and_reject_truncated_module() {
        let raw: Vec<_> = (0..140003)
            .map(|n| ((n * 31 + n / 13) % 256) as u8)
            .collect();
        assert_eq!(unpack(&pack(&raw).unwrap()).unwrap(), raw);
        let bytes = tiny("camera");
        assert!(Module::new("camera", &bytes[..bytes.len() - 1]).is_err());
    }

    fn raw_fixture() -> Vec<u8> {
        let chunk = tiny("original");
        let mut raw = vec![0; 260];
        raw[..4].copy_from_slice(&2u32.to_le_bytes());
        let other = [7; 16];
        raw.extend(BOOT_ID);
        raw.extend(other);
        for identifier in [BOOT_ID, other] {
            raw.extend(identifier);
            for value in [1u32, 0, 0, chunk.len() as u32 + 8, 0, chunk.len() as u32, 2] {
                raw.extend(value.to_le_bytes());
            }
            raw.extend(&chunk);
        }
        raw
    }

    #[test]
    fn validates_entire_resource_table_before_editing() {
        let raw = raw_fixture();
        let (start, size) = boot_record(&raw).unwrap();
        assert_eq!(start, 292);
        assert_eq!(
            original_boot_hash(&pack(&raw).unwrap()).unwrap(),
            hash(&tiny("original"))
        );
        let mut duplicate = raw.clone();
        duplicate[276..292].copy_from_slice(&BOOT_ID);
        duplicate[start + 36 + size..start + 52 + size].copy_from_slice(&BOOT_ID);
        assert!(boot_record(&duplicate).is_err());
        let mut bad_index = raw.clone();
        bad_index[276] ^= 1;
        assert!(boot_record(&bad_index).is_err());
        let mut bad_size = raw.clone();
        bad_size[start + 28..start + 32].copy_from_slice(&u32::MAX.to_le_bytes());
        assert!(boot_record(&bad_size).is_err());
        assert!(boot_record(&raw[..raw.len() - 1]).is_err());
        let mut trailing = raw.clone();
        trailing.push(0);
        assert!(boot_record(&trailing).is_err());
        assert!(Boot::Vanilla
            .validate_original(&pack(&raw).unwrap())
            .is_err());
    }
}
