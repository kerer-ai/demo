import requests
import json
import time
from datetime import datetime, timedelta,timezone
from typing import List, Dict, Optional
import csv
import os

class GitCodePRCrawler:
    def __init__(self, access_token: str = None):
        """
        初始化爬虫
        
        Args:
            access_token: GitCode API访问令牌（可选，但推荐使用）
        """
        self.base_url = "https://api.gitcode.com/api/v5"
        self.headers = {
            "Content-Type": "application/json"
        }
        self.access_token = ""
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_boostkit_projects(self, page: int = 1, per_page: int = 20) -> List[Dict]:
        """
        获取boostkit社区的项目列表
        https://api.gitcode.com/api/v5/orgs/:org/repos
        https://api.gitcode.com/api/v5/orgs/boostkit/repos?access_token=xxxxxxxxxxxxxxx&page=1&per_page=2
        """
        url = f"{self.base_url}/orgs/boostkit/repos?access_token={self.access_token}&page={page}&per_page={per_page}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"获取项目列表失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            return []
    
  
    def get_project_merge_requests(self, project_path: str, days: int = 30) -> List[Dict]:
        """
        获取指定项目的合并请求（PR）
        
        Args:
            project_id: 项目ID
            days: 统计最近多少天的PR
            https://api.gitcode.com/api/v5/repos/:owner/:repo/pulls

        """        
        # 计算时间范围
        tz = timezone(timedelta(hours=8))
        since_date = (datetime.now(tz) - timedelta(days=days)).isoformat()
        print(since_date)

        
        all_mrs = []
        page = 1
        
        while True:
            url = f"{self.base_url}/repos/boostkit/{project_path}/pulls?access_token={self.access_token}&since={since_date}&per_page=100&page={page}"

            try:
                response = self.session.get(url)
                response.raise_for_status()
                mrs = response.json()
                
                if not mrs:
                    break
                    
                all_mrs.extend(mrs)
                
                # 检查是否还有更多页面
                if len(mrs) < 100:
                    break
                    
                page += 1
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                print(f"获取项目 {project_path} 的PR失败: {e}")
                break
        
        return all_mrs

 
    def analyze_pr_activity(self, mrs: List[Dict]) -> Dict:
        """
        分析PR活跃情况
        """
        now = datetime.now().astimezone()
        activity = {
            "total": len(mrs),
            "opened": 0,
            "merged": 0,
            "closed": 0,
            "last_7_days": 0,
            "last_30_days": 0,
            "avg_response_time_hours": 0,
            "recent_activity": []
        }
        
        response_times = []
        
        for mr in mrs:
            # 统计状态
            if mr.get("state") == "open":
                activity["opened"] += 1
            elif mr.get("state") == "merged":
                activity["merged"] += 1
            elif mr.get("state") == "closed":
                activity["closed"] += 1
            
            # 统计时间范围内的PR
            created_at = datetime.fromisoformat(mr["created_at"])
            days_ago = (now - created_at).days
            
            if days_ago <= 7:
                activity["last_7_days"] += 1
            if days_ago <= 30:
                activity["last_30_days"] += 1
            
            # 计算响应时间（从创建到第一次更新或关闭的时间）
            if mr.get("updated_at"):
                updated_at = datetime.fromisoformat(mr["updated_at"].replace('Z', '+00:00'))
                response_time = (updated_at - created_at).total_seconds() / 3600  # 转换为小时
                response_times.append(response_time)
            
            # 记录最近的活动
            activity["recent_activity"].append({
                "title": mr.get("title", ""),
                "author": mr.get("author", {}).get("name", ""),
                "state": mr.get("state", ""),
                "created_at": mr["created_at"],
                "updated_at": mr.get("updated_at", ""),
                "web_url": mr.get("web_url", "")
            })
        
        # 计算平均响应时间
        if response_times:
            activity["avg_response_time_hours"] = sum(response_times) / len(response_times)
        
        # 按更新时间排序最近活动
        activity["recent_activity"].sort(
            key=lambda x: x["updated_at"] if x["updated_at"] else x["created_at"], 
            reverse=True
        )
        
        return activity
    
    def crawl_boostkit_pr_activity(self, days: int = 30) -> Dict:
        """
        主函数：爬取boostkit社区所有项目的PR活跃情况
        """
        print("开始爬取boostkit社区PR活跃情况...")
        
        # 获取所有项目
        projects = self.get_boostkit_projects()

        print(projects)
        
        results = {}
        
        for project in projects:
            project_id = project["id"]
            project_name = project["name"]
            project_path = project["path"]
            project_url = project["html_url"]
            
            print(f"正在分析项目: {project_name} (ID: {project_id})")
            
            # 获取项目的PR
            mrs = self.get_project_merge_requests(project_path, days)
            
            # 分析PR活跃情况
            activity = self.analyze_pr_activity(mrs)
            
            results[project_name] = {
                "project_info": {
                    "id": project_id,
                    "name": project_name,
                    "url": project_url,
                    "description": project.get("description", "")
                },
                "pr_activity": activity
            }
            
            print(f"  - 共找到 {activity['total']} 个PR")
            print(f"  - 最近30天: {activity['last_30_days']} 个")
            print(f"  - 最近7天: {activity['last_7_days']} 个")
            
            time.sleep(1)  # 避免请求过于频繁
        
        return results
    
    def save_to_csv(self, results: Dict, filename: str = "boostkit_pr_activity.csv"):
        """
        将结果保存为CSV文件
        """
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = [
                '项目名称', '项目描述', '项目URL', '总PR数', '进行中PR', '已合并PR', 
                '已关闭PR', '最近7天PR', '最近30天PR', '平均响应时间(小时)'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for project_name, data in results.items():
                activity = data["pr_activity"]
                project_info = data["project_info"]
                
                writer.writerow({
                    '项目名称': project_name,
                    '项目描述': project_info.get('description', '')[:100],  # 限制描述长度
                    '项目URL': project_info.get('url', ''),
                    '总PR数': activity['total'],
                    '进行中PR': activity['opened'],
                    '已合并PR': activity['merged'],
                    '已关闭PR': activity['closed'],
                    '最近7天PR': activity['last_7_days'],
                    '最近30天PR': activity['last_30_days'],
                    '平均响应时间(小时)': round(activity['avg_response_time_hours'], 2)
                })
        
        print(f"结果已保存到: {filename}")
    
    def generate_report(self, results: Dict):
        """
        生成简单的文本报告
        """
        print("\n" + "="*80)
        print("boostKit社区PR活跃情况报告")
        print("="*80)
        
        total_projects = len(results)
        total_prs = sum(data["pr_activity"]["total"] for data in results.values())
        total_recent_30_days = sum(data["pr_activity"]["last_30_days"] for data in results.values())
        total_recent_7_days = sum(data["pr_activity"]["last_7_days"] for data in results.values())
        
        print(f"统计项目数量: {total_projects}")
        print(f"总PR数量: {total_prs}")
        print(f"最近30天PR数量: {total_recent_30_days}")
        print(f"最近7天PR数量: {total_recent_7_days}")
        print("\n")
        
        # 按活跃度排序
        sorted_projects = sorted(
            results.items(),
            key=lambda x: x[1]["pr_activity"]["last_30_days"],
            reverse=True
        )
        
        print("项目活跃度排名 (按最近30天PR数量):")
        print("-" * 80)
        for i, (project_name, data) in enumerate(sorted_projects[:10], 1):
            activity = data["pr_activity"]
            print(f"{i:2d}. {project_name:<30} | 总PR: {activity['total']:3d} | "
                  f"30天: {activity['last_30_days']:3d} | 7天: {activity['last_7_days']:3d} | "
                  f"进行中: {activity['opened']:2d}")
        
        # 显示最近的活动
        print("\n最近的活动:")
        print("-" * 80)
        recent_count = 0
        for project_name, data in sorted_projects[:5]:
            recent_activities = data["pr_activity"]["recent_activity"][:3]
            for activity in recent_activities:
                if recent_count >= 10:
                    break
                state_emoji = "🟢" if activity["state"] == "opened" else "🟣" if activity["state"] == "merged" else "🔴"
                print(f"{state_emoji} [{project_name}] {activity['title'][:50]}...")
                recent_count += 1

def main():
    """
    主函数
    """
    # 你可以从环境变量获取access token，或者直接写在代码里（不推荐）
    access_token = os.getenv('GITCODE_ACCESS_TOKEN', '')
    
    # 创建爬虫实例
    crawler = GitCodePRCrawler(access_token=access_token)
    
    # 爬取PR活跃情况（统计最近30天）
    results = crawler.crawl_boostkit_pr_activity(days=30)
    
    # 生成报告
    crawler.generate_report(results)
    
    # 保存到CSV
    crawler.save_to_csv(results)
    
    # 也可以保存详细数据到JSON
    with open('boostkit_pr_activity_detailed.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()