use std::{
    path::PathBuf,
    time::{Duration, Instant},
};
fn run() -> Result<(), String> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("watch") if args.len()==3=>{
            let mask=args[1].parse::<u32>().map_err(|_|"掩码 0、1、3、4、5 或 7")?;
            if !camera_ctrl::valid_mask(mask){return Err("掩码 0、1、3、4、5 或 7".into());}
            let seconds=args[2].parse::<u64>().map_err(|_|"秒数 1..300")?;
            if !(1..=300).contains(&seconds){return Err("秒数 1..300".into());}
            let mut client=camera_ctrl::Client::new()?;
            let start=Instant::now();
            while start.elapsed()<Duration::from_secs(seconds){
                if let Some(reply)=client.control(mask)?{println!("{:?} {}",reply,reply.message());}
                std::thread::sleep(Duration::from_millis(200));
            }
            client.cancel();
            let restore=Instant::now();
            while restore.elapsed()<Duration::from_secs(4){
                if let Some(reply)=client.control(0)?{println!("restore: {:?}",reply);if reply.owned==0{return Ok(());}}
                std::thread::sleep(Duration::from_millis(200));
            }
            return Err("尚未确认还原；若在远处请返回团队范围".into());
        }
        Some("install"|"uninstall") if args.len()<=2=>{
            let game=args.get(1).map(PathBuf::from).or_else(||helldivers_bridge_core::discover::game(None)).ok_or("未找到游戏目录，请指定路径")?;
            println!("{}",camera_ctrl::install(&game,args[0]=="uninstall")?);
        }
        Some("prepare") if args.len()==3=>{
            let game=PathBuf::from(&args[1]); let out=PathBuf::from(&args[2]);
            let (boot,_)=helldivers_bridge_core::boot::read(&game)?;
            let bytes=helldivers_bridge_core::install::prepare_game(&game,camera_ctrl::module()?)?;
            std::fs::create_dir(&out).map_err(|e|e.to_string())?;
            std::fs::write(out.join(boot.bundle()),bytes).map_err(|e|e.to_string())?;
        }
        Some("inspect") if args.len()==1=>{
            let mut client=camera_ctrl::Client::new()?;let start=Instant::now();
            while start.elapsed()<Duration::from_secs(4) {
                if let Some(detail)=client.poll()?{println!("{detail}");return Ok(());}
                std::thread::sleep(Duration::from_millis(100));
            }
            return Err("检查超时".into());
        }
        _=>return Err("用法：CameraCTRL-bridge install/uninstall [游戏目录] | inspect | prepare <游戏目录> <新输出目录>".into()),
    }
    Ok(())
}
fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}
