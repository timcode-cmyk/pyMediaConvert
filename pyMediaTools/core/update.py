import requests

def check_latest_release(repo="TimCode/pyMediaTools", current_version="1.0.0"):
    """
    使用 Requests 获取 GitHub 最新 Release 信息
    """
    try:
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", "").replace("v", "")
            
            has_update = False
            # 简单的版本号比对逻辑 (x.y.z)
            curr = current_version.replace("v", "").split('.')
            lat = latest_version.split('.')
            
            try:
                for i in range(min(len(curr), len(lat))):
                    if int(lat[i]) > int(curr[i]):
                        has_update = True
                        break
                    elif int(lat[i]) < int(curr[i]):
                        break
                else:
                    if len(lat) > len(curr):
                        has_update = True
            except (ValueError, IndexError):
                pass

            return {
                "has_update": has_update,
                "latest_version": latest_version,
                "release_notes": data.get("body", "无更新内容说明"),
                "download_url": data.get("html_url", ""),
                "assets": data.get("assets", [])
            }
    except Exception as e:
        print(f"Update check failed: {e}")
    
    return {
        "has_update": False,
        "latest_version": current_version,
        "release_notes": "",
        "download_url": "",
        "assets": []
    }