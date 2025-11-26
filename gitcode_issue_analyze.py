import requests
from datetime import datetime, timedelta
import time
import pytz  # 导入pytz库

# 配置信息
BASE_URL = "https://api.gitcode.com"
OWNER = "xxxxx"
REPO = "xxxxx"
ACCESS_TOKEN = "xxx"  # 请替换为你的访问令牌

# 统一使用东八区时区（通过pytz获取）
TZ = pytz.timezone("Asia/Shanghai")

def get_branch_count():
    """获取分支总数"""
    url = f"{BASE_URL}/api/v5/repos/{OWNER}/{REPO}/branches"
    params = {
        "access_token": ACCESS_TOKEN,
        "per_page": 100,
        "page": 1
    }
    
    total_count = 0
    while True:
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            branches = response.json()
            
            if not branches:
                break
            
            total_count += len(branches)
            params["page"] += 1
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"获取分支信息出错: {e}")
            return 0
    
    return total_count

def get_issues():
    """获取所有issues"""
    url = f"{BASE_URL}/api/v5/repos/{OWNER}/{REPO}/issues"
    params = {
        "access_token": ACCESS_TOKEN,
        "state": "all",  # 获取所有状态
        "per_page": 100,
        "page": 1
    }
    
    all_issues = []
    while True:
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            issues = response.json()
            
            if not issues:
                break
            
            all_issues.extend(issues)
            params["page"] += 1
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"获取issues出错: {e}")
            return []
    
    return all_issues

def analyze_issues(issues):
    total_issues = len(issues)
    # 计算30天前的时间（带东八区时区）
    thirty_days_ago = datetime.now(TZ) - timedelta(days=30)
    closed_in_30_days = 0
    older_than_30_days_open = 0
    
    for issue in issues:
        # 解析创建时间（API返回格式如：2024-04-18T14:35:15.479+08:00）
        created_at_str = issue["created_at"]
        created_at = datetime.fromisoformat(created_at_str)
        # 转换为东八区时区（pytz方式）
        created_at = TZ.localize(created_at.replace(tzinfo=None))
        
        # 处理30天内关闭的issue
        if issue["state"] == "closed" and issue.get("finished_at"):
            finished_at_str = issue["finished_at"]
            finished_at = datetime.fromisoformat(finished_at_str)
            finished_at = TZ.localize(finished_at.replace(tzinfo=None))  # 统一时区
            if finished_at >= thirty_days_ago:
                closed_in_30_days += 1
        
        # 处理超过30天未关闭的issue
        if issue["state"] in ["open", "opened"]:
            if created_at < thirty_days_ago:
                older_than_30_days_open += 1
    
    return {
        "total_issues": total_issues,
        "closed_in_30_days": closed_in_30_days,
        "older_than_30_days_open": older_than_30_days_open
    }

def main():
    print(f"正在统计 {OWNER}/{REPO} 的相关信息...")
    
    branch_count = get_branch_count()
    print(f"分支总数: {branch_count}")
    
    issues = get_issues()
    if issues:
        issue_stats = analyze_issues(issues)
        print(f"Issue总数: {issue_stats['total_issues']}")
        print(f"30天内关闭的Issue数: {issue_stats['closed_in_30_days']}")
        print(f"超过30天未关闭的Issue数: {issue_stats['older_than_30_days_open']}")
    else:
        print("无法获取Issue数据")


if __name__ == "__main__":
    main()