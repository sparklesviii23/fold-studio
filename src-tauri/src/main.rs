#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde_json::Value;
use std::io::Write;
use std::process::{Command, Stdio};
use tauri::Manager;

const ACTIONS: &[&str] = &["mpnn_start", "mpnn_jobs", "fold_engine_status", "fold_fragment", "fold_structure", "fold_compute", "bindcraft_validate", "bindcraft_prepare", "bindcraft_campaigns", "bindcraft_import", "bindcraft_start", "intelligence_overlay_mix", "intelligence_prepare", "intelligence_register_chains", "intelligence_auto", "intelligence_prioritize", "intelligence_overlay", "intelligence_assign", "intelligence_cancel", "intelligence_candidate_save", "intelligence_candidates", "intelligence_compare", "intelligence_confidence_import", "intelligence_evidence", "intelligence_export", "intelligence_hotspots", "intelligence_inspect", "intelligence_result", "intelligence_resume", "intelligence_scramble", "intelligence_screen", "intelligence_start", "intelligence_tasks", "record_update", "record_remove", "record_restore", "library", "setting_set", "project_create", "project_update", "project_delete", "record_save", "sequence_save", "mutate", "fasta_parse", "fasta_import", "uniprot_search", "uniprot_get", "structures", "structure_download", "import_structure", "asset_read", "compute", "install_engine", "prediction_start", "prediction_resources", "job_read", "job_cancel", "cloud_prepare", "cloud_opened", "cloud_import", "export_project", "export_file", "reconcile", "chimerax_measure", "chimerax_scene", "chimerax_camera", "chimerax_selection", "chimerax_python", "chimerax_inventory", "chimerax_atoms", "chimerax_session_save", "chimerax_session_restore", "chimerax_catalog", "chimerax_execute", "chimerax_focus", "chimerax_import", "chimerax_open", "chimerax_start", "chimerax_state", "chimerax_status", "confidence_fetch", "confidence_export", "comparison_run", "chimerax_select", "console_sync", "console_clear", "console_history", "console_record", "observatory_delete", "observatory_library", "observatory_save", "amino_acids", "peptide_library", "peptide_save", "peptide_delete", "peptide_versions", "peptide_geometry", "peptide_structure", "peptide_transfer", "arcade_load", "arcade_save", "arcade_status", "molecular_draft_load", "molecular_draft_save", "molecular_graph_validate", "molecular_draft_import"];

#[tauri::command]
async fn scientific(app: tauri::AppHandle, action: String, payload: Value) -> Result<Value, String> {
    if !ACTIONS.contains(&action.as_str()) { return Err("Unsupported scientific action".into()); }
    let root = if let Ok(dir) = std::env::var("FOLD_DATA_DIR") { std::path::PathBuf::from(dir) } else { app.path().app_data_dir().map_err(|e|e.to_string())? };
    let resources = app.path().resource_dir().map_err(|e|e.to_string())?;
    let development = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
    let base = if resources.join("scientific/worker.py").exists() { resources } else { development };
    let bundled_python = base.join("runtime/bin/python3.12");
    let python = std::env::var("FOLD_PYTHON").unwrap_or_else(|_| if bundled_python.is_file() { bundled_python.to_string_lossy().into_owned() } else { "/usr/bin/python3".into() });
    tauri::async_runtime::spawn_blocking(move || {
        let mut child = Command::new(python).arg("-B").env("FOLD_HOST_PID", std::process::id().to_string()).arg(base.join("scientific/worker.py")).arg("--root").arg(root).arg("--fixtures").arg(base.join("fixtures"))
            .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().map_err(|e| format!("Python scientific service could not start: {e}"))?;
        let request = serde_json::json!({"action":action,"payload":payload});
        child.stdin.take().unwrap().write_all(request.to_string().as_bytes()).map_err(|e|e.to_string())?;
        let output = child.wait_with_output().map_err(|e|e.to_string())?;
        let response: Value = serde_json::from_slice(&output.stdout).map_err(|_| format!("Scientific service failed: {}", String::from_utf8_lossy(&output.stderr)))?;
        if let Some(error) = response.get("error") { return Err(error.as_str().unwrap_or("Scientific service error").to_string()); }
        Ok(response["result"].clone())
    }).await.map_err(|e|e.to_string())?
}
fn main() {
    tauri::Builder::default().plugin(tauri_plugin_dialog::init()).plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![scientific])
        .run(tauri::generate_context!()).expect("FOLD STUDIO could not launch");
}
