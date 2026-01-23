# clean_data.py
import os
import shutil

def clean():
    print("🧹 开始清理本地旧数据...")
    
    # 1. 删除数据库 (强制重新同步邮件)
    if os.path.exists("local_mail.db"):
        try:
            os.remove("local_mail.db")
            print("✅ 已删除旧数据库: local_mail.db")
        except Exception as e:
            print(f"❌ 无法删除数据库: {e}")
    else:
        print("ℹ️ 数据库不存在，跳过")

    # 2. 清理附件目录 (可选，保持干净)
    if os.path.exists("attachments"):
        try:
            shutil.rmtree("attachments")
            print("✅ 已清空旧附件目录")
        except Exception as e:
            print(f"❌ 无法清理附件目录: {e}")
    
    print("\n🎉 清理完成！")
    print("请重新运行 main.py，并点击【接收】按钮，")
    print("系统将重新下载所有邮件及真实的附件文件。")

if __name__ == "__main__":
    clean()