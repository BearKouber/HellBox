use std::ffi::c_void;
type Handle = *mut c_void;
const TH32CS_SNAPPROCESS: u32 = 2;
#[repr(C)]
#[derive(Clone, Copy)]
struct ProcessEntry32W {
    dw_size: u32,
    cnt_usage: u32,
    th32_process_id: u32,
    th32_default_heap_id: usize,
    th32_module_id: u32,
    cnt_threads: u32,
    th32_parent_process_id: u32,
    pc_pri_class_base: i32,
    dw_flags: u32,
    sz_exe_file: [u16; 260],
}

#[link(name = "kernel32")]
extern "system" {
    fn CreateToolhelp32Snapshot(flags: u32, pid: u32) -> Handle;
    fn Process32FirstW(handle: Handle, entry: *mut ProcessEntry32W) -> i32;
    fn Process32NextW(handle: Handle, entry: *mut ProcessEntry32W) -> i32;
    fn OpenProcess(access: u32, inherit: i32, pid: u32) -> Handle;
    fn CloseHandle(handle: Handle) -> i32;
    fn QueryFullProcessImageNameW(
        handle: Handle,
        flags: u32,
        name: *mut u16,
        size: *mut u32,
    ) -> i32;
}
pub fn process_image_path(pid: u32) -> Option<std::path::PathBuf> {
    unsafe {
        let handle = OpenProcess(0x1000, 0, pid);
        if handle.is_null() {
            return None;
        }
        let mut text = vec![0u16; 32768];
        let mut size = text.len() as u32;
        let ok = QueryFullProcessImageNameW(handle, 0, text.as_mut_ptr(), &mut size);
        CloseHandle(handle);
        (ok != 0)
            .then(|| std::path::PathBuf::from(String::from_utf16_lossy(&text[..size as usize])))
    }
}
pub fn find_pid(name: &str) -> Option<u32> {
    let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) };
    if snapshot as isize == -1 {
        return None;
    }
    let mut entry: ProcessEntry32W = unsafe { std::mem::zeroed() };
    entry.dw_size = std::mem::size_of::<ProcessEntry32W>() as u32;

    let mut found = None;
    let mut ok = unsafe { Process32FirstW(snapshot, &mut entry) } != 0;
    while ok {
        let raw = &entry.sz_exe_file;
        let len = raw.iter().position(|&c| c == 0).unwrap_or(raw.len());
        let exe = String::from_utf16_lossy(&raw[..len]);
        if exe.eq_ignore_ascii_case(name) {
            found = Some(entry.th32_process_id);
            break;
        }
        ok = unsafe { Process32NextW(snapshot, &mut entry) } != 0;
    }
    unsafe {
        CloseHandle(snapshot);
    }
    found
}
