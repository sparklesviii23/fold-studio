"""Remote GPU task action names, kept free of provider SDK imports."""
ACTIONS = {'gpu_tasks_catalog', 'gpu_tasks_list', 'gpu_task_submit', 'gpu_task_launch', 'gpu_task_status', 'gpu_task_cancel', 'gpu_task_exec',
           'gpu_task_terminal', 'gpu_task_terminal_remote',
           'gpu_task_record', 'gpu_task_rna3d_compare', 'compute_servers', 'compute_server_select',
           # Provider-process only (not in the Tauri allowlist):
           'gpu_task_poll', 'gpu_task_fetch', 'gpu_task_cancel_remote', 'gpu_task_exec_remote', 'compute_server_probe'}
