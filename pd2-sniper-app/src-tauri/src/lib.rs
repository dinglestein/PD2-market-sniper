use std::os::windows::process::CommandExt;
use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::{Manager, Listener, WebviewUrl, WebviewWindowBuilder};

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

#[tauri::command]
async fn open_pd2_login(app: tauri::AppHandle) -> Result<String, String> {
    // Open a webview to PD2 login page
    let label = "pd2-login".to_string();
    
    // Close existing login window if any
    if let Some(existing) = app.get_webview_window(&label) {
        let _ = existing.close();
    }

    let window = WebviewWindowBuilder::new(
        &app,
        &label,
        WebviewUrl::External("https://projectdiablo2.com".parse().unwrap()),
    )
    .title("PD2 Login — Log in then close this window")
    .inner_size(900.0, 700.0)
    .center()
    .initialization_script(r#"
        // Poll for the token in localStorage after page loads
        (function() {
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                try {
                    const token = window.localStorage.getItem('pd2-token');
                    if (token) {
                        clearInterval(interval);
                        // Send token back to the app via Tauri event
                        window.__TAURI__.event.emit('pd2-token-received', { token: token });
                    }
                } catch(e) {}
                // Give up after 5 minutes
                if (attempts > 1500) clearInterval(interval);
            }, 200);
        })();
    "#)
    .build()
    .map_err(|e| format!("Failed to open login window: {}", e))?;

    // Listen for the token event
    let (tx, rx) = tokio::sync::oneshot::channel::<String>();
    let tx = std::sync::Mutex::new(Some(tx));
    
    let app_clone = app.clone();
    let label_clone = label.clone();
    app.listen("pd2-token-received", move |event| {
        if let Ok(data) = event.payload().to_string().parse::<serde_json::Value>() {
            if let Some(token) = data.get("token").and_then(|t| t.as_str()) {
                if let Some(sender) = tx.lock().unwrap().take() {
                    let _ = sender.send(token.to_string());
                }
                // Close the login window
                if let Some(w) = app_clone.get_webview_window(&label_clone) {
                    let _ = w.close();
                }
            }
        }
    });

    // Wait for token with a 5-minute timeout
    match tokio::time::timeout(std::time::Duration::from_secs(300), rx).await {
        Ok(Ok(token)) => Ok(token),
        _ => {
            // Clean up window on timeout
            if let Some(w) = app.get_webview_window(&label) {
                let _ = w.close();
            }
            Err("Login timed out after 5 minutes".to_string())
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![open_pd2_login])
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
