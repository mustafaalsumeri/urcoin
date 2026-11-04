"""
Creates a Windows Desktop Shortcut for UrMiner Pro with the custom logo icon.
"""

import os
import sys

def create_desktop_shortcut():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    bat_path = os.path.join(project_dir, "UrMiner.bat")
    lnk_path = os.path.join(desktop, "UrMiner Pro.lnk")
    icon_path = os.path.join(project_dir, "assets", "urcoin_logo.ico")

    icon_clause = f'oLink.IconLocation = "{icon_path},0"' if os.path.exists(icon_path) else ''

    vbs_content = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{lnk_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{bat_path}"
oLink.WorkingDirectory = "{project_dir}"
oLink.Description = "UrMiner Pro - Kryptex GPU Mining Suite for Ur Coin (URC)"
{icon_clause}
oLink.Save
"""
    vbs_path = os.path.join(project_dir, "make_lnk.vbs")
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    os.system(f'cscript //nologo "{vbs_path}"')
    if os.path.exists(vbs_path):
        os.remove(vbs_path)

    print(f"[OK] Desktop Shortcut with Logo created successfully: {lnk_path}")

if __name__ == "__main__":
    create_desktop_shortcut()
