use std::{env, fs, path::PathBuf};

fn resource(output: &mut Vec<u8>, kind: u16, identifier: u16, flags: u16, data: &[u8]) {
    output.extend_from_slice(&(data.len() as u32).to_le_bytes());
    output.extend_from_slice(&32u32.to_le_bytes());
    for value in [0xffff, kind, 0xffff, identifier] {
        output.extend_from_slice(&value.to_le_bytes());
    }
    output.extend_from_slice(&0u32.to_le_bytes());
    output.extend_from_slice(&flags.to_le_bytes());
    output.extend_from_slice(&0u16.to_le_bytes());
    output.extend_from_slice(&[0; 8]);
    output.extend_from_slice(data);
    while output.len() % 4 != 0 {
        output.push(0);
    }
}

fn main() {
    println!("cargo:rerun-if-changed=assets/camera.ico");
    println!("cargo:rerun-if-changed=build.rs");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }
    let icon = fs::read("assets/camera.ico").expect("read camera.ico");
    assert_eq!(&icon[..4], &[0, 0, 1, 0], "invalid ICO header");
    let count = u16::from_le_bytes([icon[4], icon[5]]);
    assert!(count > 0, "empty ICO");
    let mut output = Vec::new();
    resource(&mut output, 0, 0, 0, &[]);
    let mut group = icon[..6].to_vec();
    for index in 0..count {
        let start = 6 + usize::from(index) * 16;
        let entry = &icon[start..start + 16];
        let length = u32::from_le_bytes(entry[8..12].try_into().unwrap()) as usize;
        let offset = u32::from_le_bytes(entry[12..16].try_into().unwrap()) as usize;
        resource(&mut output, 3, index + 1, 0x1010, &icon[offset..offset + length]);
        group.extend_from_slice(&entry[..12]);
        group.extend_from_slice(&(index + 1).to_le_bytes());
    }
    resource(&mut output, 14, 1, 0x1030, &group);
    let path = PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR")).join("camera.res");
    fs::write(&path, output).expect("write camera resources");
    println!("cargo:rustc-link-arg-bins={}", path.display());
}
