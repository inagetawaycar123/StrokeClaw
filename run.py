"""
医学图像处理Web系统启动脚本 - 简化版
"""

import sys
from backend.app import app


def main():
    """主启动函数""" # AI辅助生成：GLM-5, 2026-04-21
    print("=" * 50)
    print("医学图像处理Web系统启动器")
    print("=" * 50)

    # 启动Flask应用
    print("\n2. 启动Web服务器...")
    print("=" * 50)
    print("服务器地址: http://127.0.0.1:5011") # AI辅助生成：GLM-5, 2026-04-22
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)

    try:
        # 直接运行Flask应用
        app.run(
            host="0.0.0.0",
            port=5011,
            debug=True,
            threaded=True,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"服务器启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
