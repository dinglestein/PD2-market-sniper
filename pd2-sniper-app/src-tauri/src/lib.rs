use std::os::windows::process::CommandExt;
use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::Manager;

static PYTHON_SERVER: Mutex<Option<Child>> = Mutex::new(None);

fn start_python_server(scripts_dir: &str) {
    let sniper_path = format!("{}\\sniper.py", scripts_dir.replace('/', "\\"));
    let python_cmd = "python";
    
    println!("Starting server: {} {} serve --no-browser --port 8420", python_cmd, sniper_path);
    
    match Command::new(python_cmd)
        .arg(&sniper_path)
        .arg("serve")
        .arg("--no-browser")
        .arg("--port")
        .arg("8420")
        .creation_flags(0x08000000)
        .spawn()
    {
        Ok(child) => {
            let pid = child.id();
            *PYTHON_SERVER.lock().unwrap() = Some(child);
            println!("Python server process spawned (pid: {})", pid);
        }
        Err(e) => {
            eprintln!("ERROR: Failed to start Python server: {}", e);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![])
        .setup(|_app| {
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

            // Poll for server readiness in a background thread (don't block window)
            std::thread::spawn(move || {
                for i in 0..30 {
                    std::thread::sleep(std::time::Duration::from_millis(500));
                    if std::net::TcpStream::connect("127.0.0.1:8420").is_ok() {
                        println!("Server ready after {}ms", (i + 1) * 500);
                        break;
                    }
                    if i == 29 {
                        println!("WARNING: Server did not become ready after 15s");
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|_window, event| {
            // Clean up Python server when window closes
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut server) = PYTHON_SERVER.lock() {
                    if let Some(ref mut child) = *server {
                        let pid = child.id();
                        // Kill the process tree (parent + children)
                        let _ = std::process::Command::new("taskkill")
                            .args(["/PID", &pid.to_string(), "/T", "/F"])
                            .creation_flags(0x08000000)
                            .output();
                        let _ = child.kill();
                        println!("Python server stopped (pid {})", pid);
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
