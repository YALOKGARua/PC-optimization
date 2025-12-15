import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE_DIR = os.path.join(SCRIPT_DIR, "release")
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")

SOURCE_FILES = [
    "main.py",
    "optimizer.py", 
    "updater.py",
    "build.py",
    "requirements.txt",
    "icon.ico"
]

def get_version():
    try:
        with open(os.path.join(SCRIPT_DIR, "updater.py"), "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VERSION"):
                    version = line.split("=")[1].strip().strip('"\'')
                    return version
    except:
        pass
    return "unknown"

def create_release_folder():
    print("Создание папки release...")
    if os.path.exists(RELEASE_DIR):
        shutil.rmtree(RELEASE_DIR)
    os.makedirs(RELEASE_DIR)
    print(f"  Папка: {RELEASE_DIR}")

def create_source_zip(version):
    print("\nСоздание source.zip...")
    
    zip_name = f"Yalokgar_Optimizer_v{version}_source.zip"
    zip_path = os.path.join(RELEASE_DIR, zip_name)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in SOURCE_FILES:
            filepath = os.path.join(SCRIPT_DIR, filename)
            if os.path.exists(filepath):
                zf.write(filepath, filename)
                print(f"  + {filename}")
            else:
                print(f"  - {filename} (не найден)")
    
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  Создан: {zip_name} ({size_mb:.2f} MB)")
    return zip_path

def create_requirements():
    print("\nСоздание requirements.txt...")
    
    req_path = os.path.join(SCRIPT_DIR, "requirements.txt")
    requirements = """customtkinter>=5.2.0
psutil>=5.9.0
wmi>=1.5.1
pillow>=10.0.0
pyinstaller>=6.0.0
"""
    
    with open(req_path, "w", encoding="utf-8") as f:
        f.write(requirements)
    
    print(f"  Создан: requirements.txt")

def build_exe():
    print("\nСборка EXE файла...")
    
    build_script = os.path.join(SCRIPT_DIR, "build.py")
    result = subprocess.run([sys.executable, build_script], cwd=SCRIPT_DIR)
    
    return result.returncode == 0

def copy_exe_to_release(version):
    print("\nКопирование EXE в release...")
    
    src_exe = os.path.join(DIST_DIR, "Yalokgar Optimizer.exe")
    
    if not os.path.exists(src_exe):
        print("  Ошибка: EXE не найден!")
        return None
    
    exe_name = f"Yalokgar_Optimizer_v{version}.exe"
    dst_exe = os.path.join(RELEASE_DIR, exe_name)
    
    shutil.copy2(src_exe, dst_exe)
    
    size_mb = os.path.getsize(dst_exe) / (1024 * 1024)
    print(f"  Скопирован: {exe_name} ({size_mb:.1f} MB)")
    return dst_exe

def create_changelog(version):
    print("\nСоздание CHANGELOG.txt...")
    
    changelog_path = os.path.join(RELEASE_DIR, "CHANGELOG.txt")
    
    content = f"""Yalokgar Optimizer v{version}
========================
Дата: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Что нового:
-----------
• [Добавь описание изменений]

Файлы релиза:
-------------
• Yalokgar_Optimizer_v{version}.exe - Готовая программа
• Yalokgar_Optimizer_v{version}_source.zip - Исходный код

Установка EXE:
--------------
1. Скачай Yalokgar_Optimizer_v{version}.exe
2. Запусти от имени администратора

Установка из исходников:
------------------------
1. Распакуй source.zip
2. pip install -r requirements.txt
3. python main.py

GitHub: https://github.com/YALOKGARua/PC-optimization
"""
    
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"  Создан: CHANGELOG.txt")

def main():
    print("=" * 60)
    print("  YALOKGAR OPTIMIZER - RELEASE BUILDER")
    print("=" * 60)
    
    version = get_version()
    print(f"\n  Версия: v{version}")
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    create_requirements()
    
    create_release_folder()
    
    create_source_zip(version)
    
    if build_exe():
        copy_exe_to_release(version)
    else:
        print("\n  ⚠️ Ошибка сборки EXE!")
    
    create_changelog(version)
    
    print("\n" + "=" * 60)
    print("  РЕЛИЗ ГОТОВ!")
    print("=" * 60)
    print(f"\n  Папка: {RELEASE_DIR}")
    print("\n  Файлы для GitHub Release:")
    
    if os.path.exists(RELEASE_DIR):
        for f in os.listdir(RELEASE_DIR):
            filepath = os.path.join(RELEASE_DIR, f)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                if size > 1024 * 1024:
                    size_str = f"{size / (1024*1024):.1f} MB"
                else:
                    size_str = f"{size / 1024:.1f} KB"
                print(f"    • {f} ({size_str})")
    
    print("\n  Инструкция:")
    print("  1. Иди на https://github.com/YALOKGARua/PC-optimization/releases")
    print("  2. Нажми 'Create a new release'")
    print(f"  3. Tag: v{version}")
    print("  4. Прикрепи файлы из папки release/")
    print("  5. Publish release!")
    print()
    
    os.startfile(RELEASE_DIR)

if __name__ == "__main__":
    main()

