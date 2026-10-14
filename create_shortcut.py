import os

def create_desktop_shortcut():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    bat_path = os.path.abspath("UrMiner.bat")
    lnk_path = os.path.join(desktop, "UrMiner.lnk")

    vbs_content = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{lnk_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{bat_path}"
oLink.WorkingDirectory = "{os.path.dirname(bat_path)}"
oLink.Description = "UrMiner - GPU Mining Suite"
oLink.Save
"""
    vbs_path = "make_lnk.vbs"
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    os.system(f'cscript //nologo "{vbs_path}"')
    if os.path.exists(vbs_path):
        os.remove(vbs_path)

    print(f"[OK] Desktop Shortcut created successfully: {lnk_path}")

if __name__ == "__main__":
    create_desktop_shortcut()
