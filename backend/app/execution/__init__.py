"""
Yürütme alt paketi.

Paket kökünü (``import app.execution``) yüklemek job_runner veya drivers
zincirini tetiklemez. Semboller için alt modülleri doğrudan içe aktarın::

    from app.execution.commands import parse_commands, Command
    from app.execution.job_runner import run_command_execution_job
    from app.execution.executor import CommandExecutor
"""
