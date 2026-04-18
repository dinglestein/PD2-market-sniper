use std::os::windows::process::CommandExt;
use std::process::{Command, Child};
use std::sync::Mutex;

static PYTHON_SERVER: Mutex<Option<Child>> = Mutex::new(None);

fn start_python_server(scripts_dir: &str) {
    let child = Command::new("python")
        .arg(format!("{}/sniper.py", scripts_dir))
        .arg("serve")
        .arg("--no-browser")
        .arg("--port")
        .arg("8420")
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .spawn()
        .expect("Failed to start Python server");

    *PYTHON_SERVER.lock().unwrap() = Some(child);
    println!("Python server started on port 8420");
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            // Determine scripts directory relative to the exe
            let exe_dir = std::env::current_exe()
                .expect("Cannot find exe path")
                .parent()
                .expect("Cannot find exe directory")
                .to_path_buf();

            // Look for sniper.py in common locations
            let scripts_dir = if exe_dir.join("sniper.py").exists() {
                exe_dir.to_str().unwrap().to_string()
            } else if exe_dir.join("scripts/sniper.py").exists() {
                format!("{}/scripts", exe_dir.to_str().unwrap())
            } else if exe_dir.join("../scripts/sniper.py").exists() {
                exe_dir.parent()
                    .and_then(|p| p.parent())
                    .map(|p| format!("{}/scripts", p.to_str().unwrap()))
                    .unwrap_or_else(|| ".".to_string())
            } else {
                // Default: try the skill directory
                "C:/Users/jding/.agents/skills/pd2-market-sniper/scripts".to_string()
            };

            println!("Looking for sniper.py in: {}", scripts_dir);

            // Start Python server in background
            start_python_server(&scripts_dir);

            // Wait briefly for server to be ready
            std::thread::sleep(std::time::Duration::from_secs(2));

            Ok(())
        })
        .on_window_event(|_window, event| {
            // Clean up Python server when window closes
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut server) = PYTHON_SERVER.lock() {
                    if let Some(ref mut child) = *server {
                        let _ = child.kill();
                        println!("Python server stopped");
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
