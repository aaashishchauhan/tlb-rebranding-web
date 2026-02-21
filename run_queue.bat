@echo off
echo 🚀 Starting Enterprise Email Processor...

:: Create logs directory if not exists
if not exist logs mkdir logs

echo [1/2] Starting Producer (IMAP Fetcher)...
start "Producer" cmd /k "python producer.py"

echo [2/2] Starting Worker (Job Processor)...
start "Worker" cmd /k "python worker.py"

echo ✅ System is running! Check the new terminal windows for logs.
pause
