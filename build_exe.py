"""
PyInstallerを使用したパッケージング用スクリプト
"""
import os
import sys
import shutil
import subprocess

def create_executable():
    """PyInstallerを使用して実行ファイルを作成する"""
    print("PyInstallerを使用して実行ファイルを作成します...")
    
    # ビルドディレクトリと配布ディレクトリをクリーンアップ
    if os.path.exists("dist"):
        shutil.rmtree("dist")
        print("既存の 'dist' フォルダを削除しました。")
    if os.path.exists("build"):
        shutil.rmtree("build")
        print("既存の 'build' フォルダを削除しました。")
    if os.path.exists("OCR翻訳ツール.spec"):
        os.remove("OCR翻訳ツール.spec")
        print("既存の '.spec' ファイルを削除しました。")
    
    # PyInstallerがインストールされているか確認
    try:
        import PyInstaller
    except ImportError:
        print("PyInstallerがインストールされていません。インストールします...")
        subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 必要なライブラリがインストールされているか確認
    required_packages = ["PyQt5", "Pillow", "openai", "google-generativeai"]
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"{package}がインストールされていません。インストールします...")
            subprocess.call([sys.executable, "-m", "pip", "install", package])
    
    # PyInstallerコマンドの構築
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=キャプチャAI翻訳くん",
        "--windowed",  # GUIアプリケーション
        "--onefile",   # 単一の実行ファイル
        "--icon=resources/icon.ico",  # アイコン（存在する場合）
        "main.py"
    ]
    
    # アイコンファイルが存在しない場合は、そのオプションを削除
    if not os.path.exists("resources/icon.ico"):
        pyinstaller_cmd.remove("--icon=resources/icon.ico")
    
    # PyInstallerを実行
    print("実行ファイルをビルドしています...")
    subprocess.call(pyinstaller_cmd)
    
    print("ビルドが完了しました。")
    print("実行ファイルは 'dist' フォルダ内に作成されました。")

if __name__ == "__main__":
    create_executable()
