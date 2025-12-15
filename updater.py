import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
import urllib.request
import urllib.error
from typing import Callable, Optional

VERSION = "2.2.0"
GITHUB_USER = "YALOKGARua"
GITHUB_REPO = "PC-optimization"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"


def is_frozen():
    return getattr(sys, 'frozen', False)


def get_app_path():
    if is_frozen():
        return sys.executable
    return os.path.abspath(__file__)


def get_app_dir():
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class Updater:
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log = log_callback or print
        self.current_version = VERSION
        self.latest_version = None
        self.download_url = None
        self.exe_download_url = None
        self.update_available = False
    
    def _parse_version(self, version_str: str) -> tuple:
        try:
            clean = version_str.lstrip('v').strip()
            parts = clean.split('.')
            return tuple(int(p) for p in parts[:3])
        except:
            return (0, 0, 0)
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        v1_tuple = self._parse_version(v1)
        v2_tuple = self._parse_version(v2)
        
        if v1_tuple > v2_tuple:
            return 1
        elif v1_tuple < v2_tuple:
            return -1
        return 0
    
    def check_for_updates(self) -> dict:
        self._log("Проверка обновлений...")
        
        result = {
            "current_version": self.current_version,
            "latest_version": None,
            "update_available": False,
            "download_url": None,
            "is_exe": is_frozen(),
            "error": None
        }
        
        try:
            req = urllib.request.Request(
                GITHUB_API,
                headers={
                    'User-Agent': 'YalokgarOptimizer',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            self.latest_version = data.get('tag_name', '').lstrip('v')
            result["latest_version"] = self.latest_version
            
            assets = data.get('assets', [])
            for asset in assets:
                name = asset.get('name', '').lower()
                url = asset.get('browser_download_url')
                
                if name.endswith('.exe'):
                    self.exe_download_url = url
                    if is_frozen():
                        self.download_url = url
                        result["download_url"] = url
                
                elif name.endswith('.zip'):
                    if not is_frozen():
                        self.download_url = url
                        result["download_url"] = url
            
            if not self.download_url and data.get('zipball_url') and not is_frozen():
                self.download_url = data.get('zipball_url')
                result["download_url"] = self.download_url
            
            if self._compare_versions(self.latest_version, self.current_version) > 0:
                self.update_available = True
                result["update_available"] = True
                self._log(f"  Доступна новая версия: {self.latest_version}")
                self._log(f"  Текущая версия: {self.current_version}")
                
                if is_frozen() and not self.exe_download_url:
                    result["error"] = "EXE файл не найден в релизе"
                    self._log("  ⚠️ EXE файл не найден в релизе на GitHub")
            else:
                self._log(f"  У вас последняя версия: {self.current_version}")
                
        except urllib.error.URLError as e:
            result["error"] = f"Ошибка сети: {e.reason}"
            self._log(f"  Ошибка проверки: {e.reason}")
        except json.JSONDecodeError:
            result["error"] = "Ошибка разбора ответа"
            self._log("  Ошибка разбора ответа сервера")
        except Exception as e:
            result["error"] = str(e)
            self._log(f"  Ошибка: {e}")
        
        return result
    
    def download_update(self, progress_callback: Optional[Callable[[int], None]] = None) -> str:
        if not self.download_url:
            self._log("  URL загрузки не найден")
            return None
        
        self._log(f"Загрузка обновления v{self.latest_version}...")
        
        try:
            temp_dir = tempfile.mkdtemp()
            
            if is_frozen():
                file_path = os.path.join(temp_dir, "Yalokgar Optimizer_new.exe")
            else:
                file_path = os.path.join(temp_dir, "update.zip")
            
            req = urllib.request.Request(
                self.download_url,
                headers={'User-Agent': 'YalokgarOptimizer'}
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 8192
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(progress)
            
            self._log(f"  Загружено: {downloaded / (1024*1024):.2f} MB")
            return file_path
            
        except Exception as e:
            self._log(f"  Ошибка загрузки: {e}")
            return None
    
    def apply_update(self, downloaded_path: str) -> bool:
        if not downloaded_path or not os.path.exists(downloaded_path):
            self._log("  Файл обновления не найден")
            return False
        
        self._log("Установка обновления...")
        
        if is_frozen():
            return self._apply_exe_update(downloaded_path)
        else:
            return self._apply_source_update(downloaded_path)
    
    def _apply_exe_update(self, new_exe_path: str) -> bool:
        try:
            current_exe = sys.executable
            app_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            
            old_exe_backup = os.path.join(app_dir, exe_name + ".old")
            updater_bat = os.path.join(tempfile.gettempdir(), "yalokgar_update.bat")
            
            bat_content = f'''@echo off
title Yalokgar Optimizer - Updating...
echo Обновление Yalokgar Optimizer...
echo Ожидание закрытия приложения...
timeout /t 2 /nobreak >nul

:waitloop
tasklist /FI "PID eq %CURRENT_PID%" 2>nul | find /I "%CURRENT_PID%" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)

echo Установка обновления...
if exist "{old_exe_backup}" del /f /q "{old_exe_backup}"
move /y "{current_exe}" "{old_exe_backup}"
move /y "{new_exe_path}" "{current_exe}"

echo Запуск обновлённой версии...
start "" "{current_exe}"

if exist "{old_exe_backup}" del /f /q "{old_exe_backup}"
del /f /q "%~f0"
'''
            bat_content = bat_content.replace("%CURRENT_PID%", str(os.getpid()))
            
            with open(updater_bat, 'w', encoding='cp866') as f:
                f.write(bat_content)
            
            self._log("  Запуск установщика обновления...")
            self._log("  ⚠️ Приложение будет перезапущено")
            
            subprocess.Popen(
                ['cmd', '/c', updater_bat],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True
            )
            
            return True
            
        except Exception as e:
            self._log(f"  Ошибка установки EXE: {e}")
            return False
    
    def _apply_source_update(self, zip_path: str) -> bool:
        try:
            app_dir = get_app_dir()
            temp_extract = tempfile.mkdtemp()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
            
            extracted_items = os.listdir(temp_extract)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract, extracted_items[0])):
                source_dir = os.path.join(temp_extract, extracted_items[0])
            else:
                source_dir = temp_extract
            
            files_to_update = ['main.py', 'optimizer.py', 'updater.py']
            
            for filename in files_to_update:
                src_file = os.path.join(source_dir, filename)
                dst_file = os.path.join(app_dir, filename)
                
                if os.path.exists(src_file):
                    if os.path.exists(dst_file):
                        backup = dst_file + '.backup'
                        shutil.copy2(dst_file, backup)
                    
                    shutil.copy2(src_file, dst_file)
                    self._log(f"  Обновлён: {filename}")
            
            shutil.rmtree(temp_extract, ignore_errors=True)
            shutil.rmtree(os.path.dirname(zip_path), ignore_errors=True)
            
            self._log("  Обновление установлено!")
            self._log("  ⚠️ Перезапустите приложение")
            return True
            
        except Exception as e:
            self._log(f"  Ошибка установки: {e}")
            return False
    
    def run_update(self, progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        check = self.check_for_updates()
        
        if check.get("error"):
            return False
        
        if not check.get("update_available"):
            return True
        
        downloaded = self.download_update(progress_callback)
        if not downloaded:
            return False
        
        return self.apply_update(downloaded)
    
    def get_version(self) -> str:
        return self.current_version


def get_version():
    return VERSION
