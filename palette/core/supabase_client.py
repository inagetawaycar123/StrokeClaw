from supabase import create_client, Client
import os

SUPABASE_URL = "https://ppyexzqdbsnwqfyugfvc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBweWV4enFkYnNud3FmeXVnZnZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1Nzc3ODAsImV4cCI6MjA4MzE1Mzc4MH0.EjDH3eufPKBF8MJiHM6SVzPQlsWvGqhLQPKKhVG5Ffo"

print("=== 自测：读取的配置信息 ===")
print(f"URL是否读取成功: {SUPABASE_URL}")  # 应该打印你的完整URL
print(f"KEY是否读取成功: {SUPABASE_KEY}")  # 应该打印完整的anon公钥，不是None/空
print("============================")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ✅ 封装【插入患者信息】的数据库操作函数，给app.py调用
def insert_patient_info(patient_data: dict):
    """
    插入患者信息到Supabase的patient_info表
    :param patient_data: 前端传过来的患者信息字典
    :return: tuple: (是否成功, 结果数据/错误信息)
    """
    try:
        # ============ 新增：打印完整日志，精准排查 ============
        print("=" * 60)
        print(f"✅ 后端已接收完整患者数据：{patient_data}")
        # 执行插入操作，你的原有代码不变
        if "create_time" in patient_data:
            del patient_data["create_time"]

        response = supabase.table("patient_info").insert([patient_data]).execute()
        print(f"✅ Supabase执行结果详情：{response}")
        print(f"✅ Supabase返回数据：{response.data}")
        print("=" * 60)

        # 精准判断：只要返回数据不为空，就是成功
        if response.data and len(response.data) > 0:
            return (True, response.data[0])
        # 无数据的精准错误提示
        else:
            return (
                False,
                "写入失败：Supabase返回空数据，大概率是【行级安全策略未关闭】或表权限未开",
            )
    except Exception as e:
        err_detail = str(e)
        print(f"❌ 写入数据库异常：{err_detail}")
        return (False, f"写入失败：{err_detail}")
