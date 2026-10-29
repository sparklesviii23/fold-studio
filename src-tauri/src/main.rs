#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde_json::Value;
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use tauri::Manager;
use std::path::PathBuf;
use std::sync::Mutex;

struct WorkspaceRoot(Mutex<Option<PathBuf>>);

fn remember_workspace(app: &tauri::AppHandle, root: &PathBuf) -> Result<(), String> {
    let config = app.path().app_config_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&config).map_err(|e| e.to_string())?;
    let pending = config.join("workspace-selection.pending");
    std::fs::write(&pending, serde_json::json!({"schemaVersion":1,"path":root}).to_string()).map_err(|e| e.to_string())?;
    std::fs::rename(pending, config.join("workspace-selection.json")).map_err(|e| e.to_string())
}

fn workspace_root(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let state = app.state::<WorkspaceRoot>();
    let mut selected = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(root) = selected.as_ref() { return Ok(root.clone()); }
    let config = app.path().app_config_dir().map_err(|e| e.to_string())?.join("workspace-selection.json");
    let root = if let Ok(dir) = std::env::var("FOLD_DATA_DIR") {
        let path = PathBuf::from(dir);
        if !path.join("library.sqlite3").is_file() { return Err("The requested research library is missing. Choose an existing workspace; no replacement was created.".into()); }
        path
    } else if config.is_file() {
        let value: Value = serde_json::from_slice(&std::fs::read(&config).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        let path = PathBuf::from(value["path"].as_str().ok_or("Saved research workspace is invalid")?);
        if !path.join("library.sqlite3").is_file() { return Err("The saved research workspace is unavailable. Restore its location or choose another existing library; its data was not replaced.".into()); }
        path
    } else { app.path().app_data_dir().map_err(|e| e.to_string())? };
    remember_workspace(app, &root)?;
    *selected = Some(root.clone());
    Ok(root)
}


const ACTIONS: &[&str] = &["molecular_inspect", "molecular_rcsb", "molecular_rcsb_search", "editcraft_state", "editcraft_save", "editcraft_notebook", "editcraft_prepare", "editcraft_submit", "editcraft_refresh", "editcraft_cancel", "editcraft_result", "editcraft_deploy", "editcraft_health", "editcraft_import_text", "editcraft_models_prepare", "editcraft_reference_prepare", "editcraft_dataset_import", "editcraft_dataset_prepare", "editcraft_artifact_export", "editcraft_diagnostics", "cloud_shell_containers", "cloud_shell_execute", "cloud_gpu_registry", "cloud_accounts", "cloud_account_save", "cloud_account_switch", "cloud_account_rename", "cloud_account_remove", "cloud_campaign_snapshot", "cloud_campaign_events", "cloud_console", "cloud_candidate_open", "cloud_engine_audit", "biology_cloud_prepare_models", "cloud_engine_deploy", "cloud_engine_deployment_status", "execution_backend_get", "execution_backend_select", "biology_modal_qualify", "biology_unified_prepare", "biology_modal_check", "biology_modal_auth_start", "biology_modal_auth_status", "biology_modal_connection_test", "biology_peptide_chemistry_start", "biology_agent_start", "biology_counterfactual_start", "biology_boltz_reconcile", "biology_boltz_import", "biology_bindcraft_prepare", "biology_chemistry_derive", "biology_model_register", "biology_services_configure", "biology_evidence_list", "biology_evidence_search", "biology_reference_map", "biology_agent_ask", "biology_agent_status", "biology_modal_cancel", "biology_modal_configure", "biology_modal_deploy", "biology_modal_import", "biology_modal_jobs", "biology_modal_prepare", "biology_modal_refresh", "biology_modal_setup", "biology_modal_status", "biology_modal_submit", "biology_provider_credentials", "biology_pipeline_start", "biology_pipeline_jobs", "biology_pipeline_report", "biology_pipeline_plan", "biology_runtime_register", "biology_engines", "biology_boltz_prepare", "biology_boltz_quote", "biology_boltz_start", "biology_boltz_read", "biology_boltz_jobs", "biology_boltz_stop", "evolution_list", "evolution_import", "evolution_derive", "evolution_decide", "evolution_assess", "evolution_compare", "evolution_manifest", "evolution_manifests", "research_contacts", "research_full_scene", "workspace_current", "workspace_select", "research_variants", "research_screen_plan", "research_candidate", "research_annotation", "research_assay_save", "research_full_target", "research_export", "cinema_validate_views", "cinema_save", "cinema_list", "cinema_begin", "cinema_frame", "cinema_finish", "cinema_cancel", "cinema_status", "gpu_rapid_export", "gpu_rapid_target", "gpu_rapid_install", "gpu_rapid_status", "gpu_rapid_call", "gpu_rapid_submit", "gpu_rapid_import", "gpu_connection_test", "gpu_host_scan", "gpu_host_trust", "gpu_parse_connection", "gpu_profile_archive", "gpu_profile_save", "gpu_profiles", "gpu_worker_health", "gpu_worker_prepare", "gpu_worker_selftest", "bindcraft_results", "bindcraft_review", "bindcraft_resume", "dynamics_continue", "dynamics_start", "dynamics_jobs", "dynamics_status", "dynamics_analyze", "ligand_start", "ligand_jobs", "ligand_export", "mpnn_start", "mpnn_jobs", "fold_engine_status", "fold_fragment", "fold_structure", "fold_target", "fold_compute", "bindcraft_validate", "bindcraft_prepare", "bindcraft_campaigns", "bindcraft_import", "bindcraft_start", "bindcraft_repeat", "intelligence_overlay_mix", "intelligence_prepare", "intelligence_register_chains", "intelligence_auto", "intelligence_prioritize", "intelligence_overlay", "intelligence_assign", "intelligence_cancel", "intelligence_candidate_save", "intelligence_candidates", "intelligence_compare", "intelligence_confidence_import", "intelligence_evidence", "intelligence_export", "intelligence_hotspots", "intelligence_inspect", "intelligence_result", "intelligence_resume", "intelligence_scramble", "intelligence_screen", "intelligence_start", "intelligence_tasks", "record_update", "record_remove", "record_restore", "library", "setting_set", "project_create", "project_update", "project_delete", "record_save", "sequence_save", "mutate", "fasta_parse", "fasta_import", "uniprot_search", "uniprot_get", "structures", "structure_download", "import_structure", "asset_read", "compute", "install_engine", "prediction_start", "prediction_resources", "job_read", "job_cancel", "cloud_prepare", "cloud_opened", "cloud_import", "export_project", "genome_import", "genome_import_annotated", "genome_evidence_import", "genome_evidence", "genome_variant", "genome_variant_save", "genome_vcf_import", "periodic_lj_status", "periodic_lj_run", "periodic_lj_results", "periodic_lj_jobs", "genomic_io_status", "indexed_genome_import", "indexed_genomes", "indexed_genome_region", "indexed_genome_region_save", "indexed_genome_export", "genomic_alignment_import", "genomic_alignments", "genomic_io_jobs", "chemical_screen", "chemical_screens", "sequence_align", "sequence_alignments", "reads_import", "reads_list", "quantum_reaction", "quantum_reactions", "quantum_status", "quantum_list", "quantum_jobs", "quantum_calculate", "genome_orfs", "genome_public_search", "genome_public_summary", "genome_public_fetch", "genome_list", "genome_region", "genome_features", "genome_search", "genome_region_save", "genome_product", "genome_product_save", "research_assay_import", "project_archive_inspect", "project_archive_import", "project_archive_snapshots", "project_archive_snapshot_read", "project_archive_original_export", "research_assay_summary", "research_assay_fit", "export_file", "reconcile", "chimerax_measure", "chimerax_scene", "chimerax_camera", "chimerax_selection", "chimerax_python", "chimerax_inventory", "chimerax_atoms", "chimerax_session_save", "chimerax_session_restore", "chimerax_catalog", "chimerax_execute", "chimerax_focus", "chimerax_import", "chimerax_open", "chimerax_start", "chimerax_state", "chimerax_status", "confidence_fetch", "confidence_export", "comparison_run", "chimerax_select", "console_sync", "console_clear", "console_history", "console_record", "observatory_delete", "observatory_library", "observatory_save", "amino_acids", "peptide_library", "peptide_save", "peptide_delete", "peptide_versions", "peptide_geometry", "peptide_structure", "peptide_transfer", "arcade_load", "arcade_save", "arcade_status", "molecular_draft_load", "molecular_draft_save", "molecular_graph_validate", "molecular_draft_import"];

#[tauri::command]
async fn scientific(app: tauri::AppHandle, action: String, payload: Value) -> Result<Value, String> {
    if !ACTIONS.contains(&action.as_str()) { return Err("Unsupported scientific action".into()); }
    if action == "workspace_select" {
        let requested = PathBuf::from(payload["path"].as_str().ok_or("Choose an existing research folder")?);
        let path = requested.canonicalize().map_err(|e| e.to_string())?;
        let mut db = std::fs::File::open(path.join("library.sqlite3")).map_err(|_| "Choose a folder containing an existing library.sqlite3".to_string())?;
        let mut header = [0u8; 16];
        db.read_exact(&mut header).map_err(|_| "The selected database has no valid header".to_string())?;
        if &header != b"SQLite format 3\0" { return Err("The selected folder does not contain a SQLite research library".into()); }
        let check = Command::new("/usr/bin/sqlite3").arg("-readonly").arg(path.join("library.sqlite3")).arg("SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('records','projects','jobs','settings');").output().map_err(|e|e.to_string())?;
        if !check.status.success() || String::from_utf8_lossy(&check.stdout).trim() != "4" { return Err("The selected database is not a Fold Studio research library".into()); }
        let old = workspace_root(&app).unwrap_or(app.path().app_data_dir().map_err(|e|e.to_string())?);
        let processes = Command::new("/bin/ps").args(["-axo","command="]).output().map_err(|e|e.to_string())?;
        if String::from_utf8_lossy(&processes.stdout).lines().any(|line| line.contains(&old.to_string_lossy().to_string()) && ["--run-job", "--dynamics-job", "--bindcraft-cpu-job", "--intelligence-job", "--mpnn-job", "--ligand-job"].iter().any(|flag| line.contains(flag))) {
            return Err("Finish or cancel the active local calculation before switching research libraries".into());
        }
        let state = app.state::<WorkspaceRoot>();
        let mut selected = state.0.lock().map_err(|e|e.to_string())?;
        remember_workspace(&app, &path)?;
        *selected = Some(path.clone());
        return Ok(serde_json::json!({"path":path,"state":"selected"}));
    }
    let root = workspace_root(&app)?;
    if action == "workspace_current" { return Ok(serde_json::json!({"path":root,"persistent":true})); }
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
    tauri::Builder::default().manage(WorkspaceRoot(Mutex::new(None))).plugin(tauri_plugin_dialog::init()).plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![scientific])
        .run(tauri::generate_context!()).expect("FOLD STUDIO could not launch");
}
