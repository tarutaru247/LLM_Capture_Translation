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
    # ロックされている場合はスキップし、新しい dist/build パスを使う
    dist_dir = "dist"
    build_dir = "build"
    try:
        if os.path.exists(dist_dir):
            shutil.rmtree(dist_dir)
            print("既存の 'dist' フォルダを削除しました。")
    except Exception as exc:
        print(f"dist フォルダの削除に失敗したためスキップします: {exc}")
        dist_dir = "dist_new"
    try:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
            print("既存の 'build' フォルダを削除しました。")
    except Exception as exc:
        print(f"build フォルダの削除に失敗したためスキップします: {exc}")
        build_dir = "build_new"
    # 旧名称のspecも掃除（日本語名を避けるためASCII名に統一）
    for spec_name in ("OCR翻訳ツール.spec", "スクショAI翻訳.spec", "ocr_translator.spec"):
        if os.path.exists(spec_name):
            os.remove(spec_name)
            print(f"既存の '{spec_name}' を削除しました。")
    
    # PyInstallerがインストールされているか確認
    try:
        import PyInstaller
    except ImportError:
        print("PyInstallerがインストールされていません。インストールします...")
        subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 必要なライブラリがインストールされているか確認
    required_packages = [
        ("PyQt5", "PyQt5"),
        ("PIL", "Pillow"),
        ("google.genai", "google-genai"),
    ]
    for import_name, package_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            print(f"{package_name}がインストールされていません。インストールします...")
            subprocess.call([sys.executable, "-m", "pip", "install", package_name])
    
    # PyInstallerコマンドの構築
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=ocr_translator",  # ASCII名に統一
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
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
