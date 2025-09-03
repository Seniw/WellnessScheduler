import sys
import os
import subprocess
import multiprocessing

def get_paths():
    """
    Determines the absolute paths for the python executable and the app.py script,
    specifically for a --onedir bundled application.
    """
    if getattr(sys, 'frozen', False):
        # When frozen in --onedir mode, sys.executable is the path to the app's .exe.
        # The bundled python interpreter and app.py are in the same directory.
        app_dir = os.path.dirname(sys.executable)
        python_exe = os.path.join(app_dir, 'python.exe')
        app_script = os.path.join(app_dir, 'app.py')
        return python_exe, app_script
    else:
        # When running from source, sys.executable is the python interpreter,
        # and app.py is in the current directory.
        return sys.executable, 'app.py'

if __name__ == "__main__":
    multiprocessing.freeze_support()

    python_executable, app_path = get_paths()

    command = [
        python_executable,  # <-- CRITICAL CHANGE: Use the bundled python.exe directly
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.headless=true",
        "--global.developmentMode=false",
        "--server.runOnSave=false",
        "--server.fileWatcherType=none"
    ]
    
    subprocess.run(command)