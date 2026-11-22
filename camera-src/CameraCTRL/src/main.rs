#![windows_subsystem = "windows"]
use std::{
    path::PathBuf,
    sync::mpsc,
    time::{Duration, Instant},
};
struct App {
    path: Option<PathBuf>,
    message: String,
    detail: String,
    client: Option<camera_ctrl::Client>,
    last: Instant,
    job: Option<mpsc::Receiver<Result<String, String>>>,
    independent: bool,
    unlocked: bool,
    host_spawning: bool,
    spawn_settings: camera_ctrl::SpawnSettings,
    view_settings: camera_ctrl::ViewSettings,
    enemy_edit_running: bool,
    last_enemy_check: Instant,
    status: String,
    last_height: f32,
}
impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _: &mut eframe::Frame) {
        ctx.request_repaint_after(Duration::from_millis(200));
        if self.last_enemy_check.elapsed() >= Duration::from_secs(1) {
            self.last_enemy_check = Instant::now();
            self.enemy_edit_running =
                helldivers_bridge_core::win::find_pid("EnemyEdit.exe").is_some();
        }
        if let Some(result) = self.job.as_ref().and_then(|rx| rx.try_recv().ok()) {
            self.message = result.unwrap_or_else(|e| e);
            self.job = None;
        }
        if self.last.elapsed() > Duration::from_millis(250) {
            self.last = Instant::now();
            if helldivers_bridge_core::win::find_pid("helldivers.exe").is_none() {
                self.client = None;
                self.detail = "游戏未运行".into();
                self.status = "游戏未运行；所选功能将在任务就绪后应用".into();
            } else {
                if self.client.is_none() {
                    match camera_ctrl::Client::new() {
                        Ok(c) => self.client = Some(c),
                        Err(e) => self.detail = e,
                    }
                }
                if let Some(client) = &mut self.client {
                    let mut mask = if self.unlocked {
                        3
                    } else if self.independent {
                        1
                    } else {
                        0
                    };
                    if self.host_spawning {
                        mask |= 4;
                    }
                    match client.control_with_view(mask, self.spawn_settings, self.view_settings) {
                        Ok(Some(reply)) => self.status = reply.message(),
                        Err(e) => self.status = e,
                        _ => {}
                    }
                    match client.poll() {
                        Ok(Some(text)) => self.detail = text,
                        Err(e) => self.detail = e,
                        _ => {}
                    }
                }
            }
        }
        let mut content_height = 0.0;
        egui::CentralPanel::default().show(ctx, |ui| {
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
            let content_top = ui.cursor().top();
            ui.heading("CameraCTRL");
            ui.label("独立桥接 · 个人视角与位置");
            ui.separator();
            ui.label(
                self.path
                    .as_ref()
                    .map(|p| p.display().to_string())
                    .unwrap_or("未找到游戏目录".into()),
            );
            ui.add_enabled_ui(self.job.is_none(), |ui| {
                if ui.button("选择游戏目录").clicked() {
                    match helldivers_bridge_core::discover::choose_game() {
                        Ok(Some(p)) => self.path = Some(p),
                        Err(e) => self.message = e,
                        _ => {}
                    }
                }
                ui.horizontal(|ui| {
                    let install = ui.button("安装 / 更新 Camera 模块").clicked();
                    let remove = ui.button("卸载 Camera 模块").clicked();
                    if install || remove {
                        if let Some(path) = self.path.clone() {
                            let (tx, rx) = mpsc::channel();
                            self.job = Some(rx);
                            self.message = "正在处理安装资源…".into();
                            std::thread::spawn(move || {
                                let _ = tx.send(camera_ctrl::install(&path, remove));
                            });
                        } else {
                            self.message = "请先选择游戏目录".into();
                        }
                    }
                });
            });
            if !self.message.is_empty() {
                ui.label(&self.message);
            }
            ui.separator();
            if ui
                .checkbox(
                    &mut self.independent,
                    "解除视角限制（只跟随自己，保留团队位置边界）",
                )
                .on_hover_text("上下载具时镜头平滑移动约 0.5 秒。死亡后停留 2 秒，再观战存活队友；W/A 切换上一位，S/D 切换下一位。聊天输入时不切换，复活后恢复跟随自己。")
                .changed()
                && !self.independent
            {
                self.unlocked = false;
            }
            ui.add_enabled_ui(self.independent, |ui| {
                ui.checkbox(&mut self.unlocked, "解除位置限制（允许离开团队屏幕）")
                    .on_hover_text("载具全员开启个人视角与位置解锁后才能离屏；有公共视角乘员时保留公共边界。\n同时保留本机复活信标落点，并在本机控制撤离信标时改为有人留守即可继续撤离，全部离开仍按原版倒计时取消。");
            });
            ui.checkbox(&mut self.host_spawning, "房主刷怪区域扩展（覆盖离屏玩家）")
                .on_hover_text("只在你当房主时生效，队友无需安装。每区与合计额度同时限制，不能把总额度集中生成在一区。区域重叠合并；降低额度不清除已有敌人。沿用任务难度、整队人数、随机兵种与生成队列。");
            if !self.enemy_edit_running {
                ui.collapsing("刷怪量配置", |ui| {
                    let before = self.spawn_settings;
                    for (label, value) in [
                        ("增援总倍率", &mut self.spawn_settings.encounter),
                        ("巡逻总倍率", &mut self.spawn_settings.patrol),
                    ] {
                        ui.horizontal(|ui| {
                            ui.label(label);
                            ui.add(egui::DragValue::new(value).range(1..=100).speed(0.1).suffix(" 倍"));
                            ui.label(format!("每区最多 {} 倍", camera_ctrl::SpawnSettings::regional(*value)));
                        });
                    }
                    ui.weak("合计不超过所设倍率；每区=max(1,倍率÷4)。同屏算一区，任务中调整自动应用。");
                    if ui.button("恢复默认倍率（增援 2 / 巡逻 4）").clicked() {
                        self.spawn_settings = camera_ctrl::SpawnSettings::default();
                    }
                    if self.spawn_settings != before {
                        if let Err(error) = self.spawn_settings.save() { self.message = error; }
                    }
                });
            }
            ui.collapsing("个人视口比例", |ui| {
                let before=self.view_settings;
                egui::ComboBox::from_id_salt("personal_view_ratio").selected_text(self.view_settings.label()).show_ui(ui, |ui| {
                    for &(value,label) in camera_ctrl::ViewSettings::CHOICES {
                        ui.selectable_value(&mut self.view_settings.0,value,label);
                    }
                });
                ui.weak("仅改变个人视角的可视区域；按比例留黑边，不改变队友的公共边界。关闭个人视角时不应用。");
                if before!=self.view_settings {
                    if let Err(error)=self.view_settings.save() { self.message=error; }
                }
            });
            if ui.button("还原全部").clicked() {
                self.independent = false;
                self.unlocked = false;
                self.host_spawning = false;
                if let Some(client) = &mut self.client {
                    client.cancel();
                }
            }
            ui.label(&self.status);
            ui.weak("实验功能：远处取消视角需先归队。数量上限同时受每区额度与合计额度限制。");
            ui.collapsing("只读诊断", |ui| {
                egui::ScrollArea::both().id_salt("diagnostics").max_height(180.0).show(ui, |ui| {
                    ui.monospace(&self.detail);
                });
            });
            content_height = ui.cursor().top() - content_top;
            });
        });
        let monitor_height = ctx
            .input(|input| input.viewport().monitor_size.map(|size| size.y))
            .unwrap_or(1080.0);
        let height = (content_height + 16.0).clamp(280.0, (monitor_height - 80.0).max(280.0));
        if (height - self.last_height).abs() > 2.0 {
            self.last_height = height;
            let width = ctx
                .input(|input| input.viewport().inner_rect.map(|rect| rect.width()))
                .unwrap_or(530.0);
            ctx.send_viewport_cmd(egui::ViewportCommand::InnerSize(egui::vec2(width, height)));
        }
    }
}
fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([530.0, 310.0])
            .with_min_inner_size([430.0, 280.0])
            .with_icon(
                eframe::icon_data::from_png_bytes(include_bytes!("../assets/camera.png"))
                    .expect("embedded camera icon"),
            ),
        ..Default::default()
    };
    eframe::run_native(
        "CameraCTRL",
        options,
        Box::new(|cc| {
            let mut fonts = egui::FontDefinitions::default();
            let font = std::env::var_os("WINDIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| PathBuf::from("C:/Windows"))
                .join("Fonts/msyh.ttc");
            if let Ok(bytes) = std::fs::read(font) {
                fonts
                    .font_data
                    .insert("chinese".into(), egui::FontData::from_owned(bytes).into());
                for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
                    fonts
                        .families
                        .entry(family)
                        .or_default()
                        .push("chinese".into());
                }
            }
            cc.egui_ctx.set_fonts(fonts);
            let saved_settings = camera_ctrl::SpawnSettings::load();
            let saved_view = camera_ctrl::ViewSettings::load();
            let mut message = saved_settings
                .as_ref()
                .err()
                .map(|error| format!("{error}；本次使用默认倍率"))
                .unwrap_or_default();
            if let Err(error) = &saved_view {
                if !message.is_empty() {
                    message.push('\n');
                }
                message.push_str(&format!("{error}；本次跟随游戏比例"));
            }
            Ok(Box::new(App {
                path: helldivers_bridge_core::discover::game(None),
                message,
                detail: String::new(),
                client: None,
                last: Instant::now(),
                job: None,
                independent: false,
                unlocked: false,
                host_spawning: false,
                spawn_settings: saved_settings.unwrap_or_default(),
                view_settings: saved_view.unwrap_or_default(),
                enemy_edit_running: helldivers_bridge_core::win::find_pid("EnemyEdit.exe")
                    .is_some(),
                last_enemy_check: Instant::now(),
                status: "未启用".into(),
                last_height: 310.0,
            }))
        }),
    )
}
