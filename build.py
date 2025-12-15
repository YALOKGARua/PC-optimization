import subprocess
import sys
import os

def install_requirements():
    print("Установка зависимостей для сборки...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "pillow", "-q"])

def create_icon():
    print("Создание иконки...")
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        sizes = [256, 128, 64, 48, 32, 16]
        images = []
        
        for size in sizes:
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            padding = size // 8
            draw.rounded_rectangle(
                [padding, padding, size - padding, size - padding],
                radius=size // 6,
                fill=(13, 13, 13, 255),
                outline=(0, 255, 65, 255),
                width=max(1, size // 32)
            )
            
            center = size // 2
            bolt_color = (0, 255, 65, 255)
            s = size // 6
            
            points = [
                (center + s//2, center - s),
                (center - s//3, center),
                (center + s//4, center),
                (center - s//2, center + s),
                (center + s//3, center),
                (center - s//4, center),
            ]
            draw.polygon(points, fill=bolt_color)
            
            images.append(img)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        images[0].save(icon_path, format='ICO', sizes=[(s, s) for s in sizes], append_images=images[1:])
        print(f"  Иконка создана: {icon_path}")
        return icon_path
        
    except Exception as e:
        print(f"  Ошибка создания иконки: {e}")
        return None

def build_exe():
    print("Сборка EXE файла...")
    
    icon_path = create_icon()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_file = os.path.join(script_dir, "main.py")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "Yalokgar Optimizer",
        "--add-data", f"optimizer.py;.",
        "--add-data", f"updater.py;.",
        "--clean",
        "--noconfirm",
    ]
    
    if icon_path and os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
    
    cmd.append(main_file)
    
    print(f"  Команда: {' '.join(cmd)}")
    print("  Это может занять несколько минут...")
    print()
    
    result = subprocess.run(cmd, cwd=script_dir)
    
    if result.returncode == 0:
        exe_path = os.path.join(script_dir, "dist", "Yalokgar Optimizer.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print()
            print("=" * 50)
            print("СБОРКА ЗАВЕРШЕНА!")
            print("=" * 50)
            print(f"  Файл: {exe_path}")
            print(f"  Размер: {size_mb:.1f} MB")
            print()
            print("  EXE файл находится в папке 'dist'")
            return True
    else:
        print("  Ошибка сборки!")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("YALOKGAR OPTIMIZER - BUILD TOOL")
    print("=" * 50)
    print()
    
    install_requirements()
    print()
    build_exe()