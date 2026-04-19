import subprocess
import sys


def run_command(command, shell=False):
    """Runs a command and checks the result"""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=shell, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    print("Successfully completed")
    return result


def main():
    try:
        print("\n=== Starting PyInstaller ===")
        pyinstaller_cmd = [
            "uv",
            "run",
            "pyinstaller",
            "--clean",
            "--noconsole",
            "--noconfirm",
            "--onedir",
            "--icon=.\\icons\\icon_tr.ico",
            "--add-data=icons\\battery_0.ico;.\\icons",
            "--add-data=icons\\battery_50.ico;.\\icons",
            "--add-data=icons\\battery_100.ico;.\\icons",
            "--add-data=icons\\battery_100_green.ico;.\\icons",
            "--name=ATK_tray",
            "atk_tray.py",
        ]
        run_command(pyinstaller_cmd)
        print(f"\n=== Release successfully created! ===")

    except Exception as e:
        print(f"Error creating release: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
