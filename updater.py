import os
import sys
import json
import shutil
import zipfile
import tempfile
import urllib.request
import urllib.error
from typing import Callable, Optional

VERSION = "2.1.0"
GITHUB_USER = "YALOKGARua"
GITHUB_REPO = "PC-optimization"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"


class Updater:
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log = log_callback or print
        self.current_version = VERSION
        self.latest_version = None
        self.download_url = None
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
                if asset.get('name', '').endswith('.zip'):
                    self.download_url = asset.get('browser_download_url')
                    result["download_url"] = self.download_url
                    break
            
            if not self.download_url and data.get('zipball_url'):
                self.download_url = data.get('zipball_url')
                result["download_url"] = self.download_url
            
            if self._compare_versions(self.latest_version, self.current_version) > 0:
                self.update_available = True
                result["update_available"] = True
                self._log(f"  Доступна новая версия: {self.latest_version}")
                self._log(f"  Текущая версия: {self.current_version}")
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
            zip_path = os.path.join(temp_dir, "update.zip")
            
            req = urllib.request.Request(
                self.download_url,
                headers={'User-Agent': 'YalokgarOptimizer'}
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 8192
                
                with open(zip_path, 'wb') as f:
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
            return zip_path
            
        except Exception as e:
            self._log(f"  Ошибка загрузки: {e}")
            return None
    
    def apply_update(self, zip_path: str) -> bool:
        if not zip_path or not os.path.exists(zip_path):
            self._log("  Файл обновления не найден")
            return False
        
        self._log("Установка обновления...")
        
        try:
            app_dir = os.path.dirname(os.path.abspath(__file__))
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
        
        zip_path = self.download_update(progress_callback)
        if not zip_path:
            return False
        
        return self.apply_update(zip_path)
    
    def get_version(self) -> str:
        return self.current_version


def get_version():
    return VERSION

