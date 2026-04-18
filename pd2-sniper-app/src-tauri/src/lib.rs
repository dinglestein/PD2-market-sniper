use std::os::windows::process::CommandExt;
use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

static PYTHON_SERVER: Mutex<Option<Child>> = Mutex::new(None);

fn start_python_server(scripts_dir: &str) {
    // Try python3 first, then python
    let python_cmd = if std::process::Command::new("python3")
        .arg("--version")
        .creation_flags(0x08000000)
        .output()
        .is_ok()
    {
        "python3"
    } else {
        "python"
    };

    let child = Command::new(python_cmd)
        .arg(format!("{}/sniper.py", scripts_dir))
        .arg("serve")
        .arg("--no-browser")
        .arg("--port")
        .arg("8420")
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .spawn()
        .expect("Failed to start Python server");

    *PYTHON_SERVER.lock().unwrap() = Some(child);
    println!("Python server starting on port 8420 (using {})...", python_cmd);
}

#[tauri::command]
async fn open_pd2_login(app: tauri::AppHandle) -> Result<String, String> {
    let label = "pd2-login".to_string();
    
    // Close existing login window if any
    if let Some(existing) = app.get_webview_window(&label) {
        let _ = existing.close();
    }

    // We'll use a local HTML page that iframes PD2 and reads localStorage
    // Actually, simpler: open PD2 webview, inject a "Done" button that 
    // stores token in window title, then poll the title from Rust
    
    let _webview_window = WebviewWindowBuilder::new(
        &app,
        &label,
        WebviewUrl::External("https://projectdiablo2.com".parse().unwrap()),
    )
    .title("PD2 Login — Log in, then click ✓ Capture Token in top-right")
    .inner_size(1000.0, 750.0)
    .center()
    .initialization_script(r#"
        (function() {
            function addCaptureButton() {
                if (document.getElementById('pd2-capture-btn')) return;
                const btn = document.createElement('div');
                btn.id = 'pd2-capture-btn';
                btn.innerHTML = '✓ Capture Token';
                btn.style.cssText = 'position:fixed;top:12px;right:12px;z-index:999999;background:linear-gradient(135deg,#f59e0b,#d97706);color:#000;padding:12px 24px;border-radius:8px;font-size:15px;font-weight:bold;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.4);font-family:system-ui;user-select:none;transition:transform 0.1s;';
                btn.onmouseenter = function() { btn.style.transform = 'scale(1.05)'; };
                btn.onmouseleave = function() { btn.style.transform = 'scale(1)'; };
                btn.onclick = function() {
                    try {
                        const token = window.localStorage.getItem('pd2-token')
                            || window.localStorage.getItem('pd2Token')
                            || window.localStorage.getItem('token');
                        if (token) {
                            // Put token in document title so Rust can read it
                            document.title = 'PD2_TOKEN_CAPTURED:' + token;
                            btn.innerHTML = '✅ Captured!';
                            btn.style.background = '#22c55e';
                        } else {
                            btn.innerHTML = '❌ Not logged in yet';
                            btn.style.background = '#ef4444';
                            setTimeout(() => {
                                btn.innerHTML = '✓ Capture Token';
                                btn.style.background = 'linear-gradient(135deg,#f59e0b,#d97706)';
                            }, 2000);
                        }
                    } catch(e) {
                        btn.innerHTML = '❌ Error: ' + e.message;
                    }
                };
                document.body.appendChild(btn);
            }

            // Keep trying to add button until body exists
            const interval = setInterval(() => {
                if (document.body) {
                    addCaptureButton();
                    // Re-add if it gets removed (SPA navigation)
                    new MutationObserver(() => {
                        if (!document.getElementById('pd2-capture-btn')) addCaptureButton();
                    }).observe(document.body, { childList: true, subtree: true });
                    clearInterval(interval);
                }
            }, 300);
        })();
    "#)
    .build()
    .map_err(|e| format!("Failed to open login window: {}", e))?;

    // Poll the window title for the token (title-based IPC — works cross-origin)
    let (tx, rx) = tokio::sync::oneshot::channel::<String>();
    let tx = std::sync::Mutex::new(Some(tx));
    
    // Spawn a polling task
    let app_handle = app.clone();
    let label_clone = label.clone();
    tokio::spawn(async move {
        let prefix = "PD2_TOKEN_CAPTURED:";
        for _ in 0..600 { // 5 min = 600 * 500ms
            tokio::time::sleep(std::time::Duration::from_millis(500)).await;
            if let Some(w) = app_handle.get_webview_window(&label_clone) {
                if let Ok(title) = w.title() {
                    if let Some(token) = title.strip_prefix(prefix) {
                        if let Some(sender) = tx.lock().unwrap().take() {
                            let _ = sender.send(token.to_string());
                        }
                        return;
                    }
                }
            } else {
                break; // Window was closed manually
            }
        }
        // Timeout or window closed — drop the sender to signal failure
    });

    // Wait for token
    match tokio::time::timeout(std::time::Duration::from_secs(300), rx).await {
        Ok(Ok(token)) => {
            if let Some(w) = app.get_webview_window(&label) {
                let _ = w.close();
            }
            Ok(token)
        }
        _ => {
            if let Some(w) = app.get_webview_window(&label) {
                let _ = w.close();
            }
            Err("Login window closed without capturing token".to_string())
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

            // Wait for server to be ready (poll up to 15 seconds)
            println!("Waiting for server to be ready...");
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
