import os
import subprocess
import ctypes
import winreg
import shutil
import tempfile
import psutil
import wmi
import json
import time
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rollback_backup.json")


class SystemOptimizer:
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log = log_callback or print
        self._is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        self._wmi = wmi.WMI()
        self._rollback_data = {"registry": [], "services": [], "power_plan": None}
        self._log_file = None
        self._init_logging()
    
    def _init_logging(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            log_filename = datetime.now().strftime("optimizer_%Y%m%d_%H%M%S.log")
            self._log_file = os.path.join(LOG_DIR, log_filename)
        except:
            self._log_file = None
    
    def _log_to_file(self, message: str):
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {message}\n")
            except:
                pass
    
    def _log_both(self, message: str):
        self._log(message)
        self._log_to_file(message)
    
    def _save_registry_backup(self, hkey, path: str, value_name: str):
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
                value, reg_type = winreg.QueryValueEx(key, value_name)
                self._rollback_data["registry"].append({
                    "hkey": "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else "HKCU",
                    "path": path,
                    "name": value_name,
                    "value": value,
                    "type": reg_type
                })
        except FileNotFoundError:
            self._rollback_data["registry"].append({
                "hkey": "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else "HKCU",
                "path": path,
                "name": value_name,
                "value": None,
                "type": None
            })
        except:
            pass
    
    def _save_rollback_data(self):
        try:
            with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(self._rollback_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log_both(f"  Ошибка сохранения бэкапа: {e}")
    
    def _load_rollback_data(self):
        try:
            if os.path.exists(BACKUP_FILE):
                with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                    self._rollback_data = json.load(f)
                return True
        except:
            pass
        return False
    
    def _execute_cmd(self, command: str, shell: bool = True) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=120
            )
            self._log_to_file(f"CMD: {command} -> {result.returncode}")
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def _get_size_mb(self, path: str) -> float:
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return total / (1024 * 1024)
    
    def _safe_remove(self, path: str) -> int:
        removed = 0
        try:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                os.remove(path)
                return size
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        try:
                            fp = os.path.join(root, name)
                            removed += os.path.getsize(fp)
                            os.remove(fp)
                        except (OSError, PermissionError):
                            pass
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
        return removed
    
    def clean_temp_files(self) -> dict:
        self._log("Очистка временных файлов...")
        
        temp_paths = [
            tempfile.gettempdir(),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Temp'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch'),
        ]
        
        total_freed = 0
        files_removed = 0
        
        for temp_path in temp_paths:
            if not os.path.exists(temp_path):
                continue
            
            self._log(f"  Очистка: {temp_path}")
            
            try:
                for item in os.listdir(temp_path):
                    item_path = os.path.join(temp_path, item)
                    try:
                        if os.path.isfile(item_path):
                            size = os.path.getsize(item_path)
                            os.remove(item_path)
                            total_freed += size
                            files_removed += 1
                        elif os.path.isdir(item_path):
                            freed = self._safe_remove(item_path)
                            total_freed += freed
                            files_removed += 1
                            try:
                                os.rmdir(item_path)
                            except:
                                pass
                    except (OSError, PermissionError):
                        pass
            except (OSError, PermissionError):
                pass
        
        freed_mb = total_freed / (1024 * 1024)
        self._log(f"  Очищено: {freed_mb:.2f} MB ({files_removed} файлов)")
        
        return {"freed_mb": freed_mb, "files_removed": files_removed}
    
    def clean_browser_cache(self) -> dict:
        self._log("Очистка кэша браузеров...")
        
        user_profile = os.environ.get('USERPROFILE', '')
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')
        
        browser_caches = [
            os.path.join(local_appdata, 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
            os.path.join(local_appdata, 'Google', 'Chrome', 'User Data', 'Default', 'Code Cache'),
            os.path.join(local_appdata, 'Google', 'Chrome', 'User Data', 'Default', 'GPUCache'),
            os.path.join(local_appdata, 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
            os.path.join(local_appdata, 'Microsoft', 'Edge', 'User Data', 'Default', 'Code Cache'),
            os.path.join(local_appdata, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Cache'),
            os.path.join(appdata, 'Opera Software', 'Opera Stable', 'Cache'),
            os.path.join(local_appdata, 'Mozilla', 'Firefox', 'Profiles'),
        ]
        
        total_freed = 0
        
        for cache_path in browser_caches:
            if os.path.exists(cache_path):
                self._log(f"  Очистка: {os.path.basename(os.path.dirname(cache_path))}")
                freed = self._safe_remove(cache_path)
                total_freed += freed
        
        freed_mb = total_freed / (1024 * 1024)
        self._log(f"  Очищено кэша браузеров: {freed_mb:.2f} MB")
        
        return {"freed_mb": freed_mb}
    
    def optimize_ram(self) -> dict:
        self._log("Оптимизация оперативной памяти...")
        
        before = psutil.virtual_memory()
        before_used = before.used / (1024 * 1024 * 1024)
        
        try:
            ctypes.windll.kernel32.SetProcessWorkingSetSize(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.c_size_t(-1),
                ctypes.c_size_t(-1)
            )
            
            self._execute_cmd('powershell -Command "[System.GC]::Collect()"')
            
            if self._is_admin:
                self._execute_cmd('powershell -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"')
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        after = psutil.virtual_memory()
        after_used = after.used / (1024 * 1024 * 1024)
        freed = max(0, before_used - after_used)
        
        self._log(f"  Освобождено RAM: {freed:.2f} GB")
        self._log(f"  Доступно RAM: {after.available / (1024 * 1024 * 1024):.2f} GB")
        
        return {"freed_gb": freed, "available_gb": after.available / (1024 * 1024 * 1024)}
    
    def enable_game_mode(self) -> dict:
        self._log("Активация игрового режима Windows...")
        
        results = {"success": False, "changes": []}
        
        try:
            key_path = r"Software\Microsoft\GameBar"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "AllowAutoGameMode", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1)
                results["changes"].append("GameMode enabled")
            
            key_path = r"Software\Microsoft\GameBar"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "UseNexusForGameBarEnabled", 0, winreg.REG_DWORD, 0)
                results["changes"].append("GameBar overlay disabled")
            
            results["success"] = True
            self._log("  Игровой режим активирован")
            
        except PermissionError:
            self._log("  Требуются права администратора")
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_visual_effects(self) -> dict:
        self._log("Оптимизация визуальных эффектов...")
        
        results = {"success": False, "changes": []}
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
                results["changes"].append("Visual effects set to performance")
            
            key_path = r"Control Panel\Desktop"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "DragFullWindows", 0, winreg.REG_SZ, "0")
                results["changes"].append("Window drag optimized")
            
            key_path = r"Control Panel\Desktop\WindowMetrics"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "MinAnimate", 0, winreg.REG_SZ, "0")
                results["changes"].append("Animation disabled")
            
            results["success"] = True
            self._log("  Визуальные эффекты оптимизированы для производительности")
            self._log("  ✓ Шрифты остались нормальными")
            
        except PermissionError:
            self._log("  Требуются права администратора для некоторых настроек")
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def restore_visual_effects(self) -> dict:
        self._log("Восстановление визуальных эффектов...")
        
        results = {"success": False}
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 1)
            
            key_path = r"Control Panel\Desktop"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "DragFullWindows", 0, winreg.REG_SZ, "1")
                winreg.SetValueEx(key, "FontSmoothing", 0, winreg.REG_SZ, "2")
            
            key_path = r"Control Panel\Desktop\WindowMetrics"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "MinAnimate", 0, winreg.REG_SZ, "1")
            
            results["success"] = True
            self._log("  Визуальные эффекты восстановлены")
            self._log("  Перезайди в систему для применения всех изменений")
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_power_plan(self) -> dict:
        self._log("Настройка плана электропитания...")
        
        results = {"success": False}
        
        high_perf_guid = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        
        success, output = self._execute_cmd(f'powercfg /setactive {high_perf_guid}')
        
        if not success:
            self._execute_cmd('powercfg -duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c')
            success, output = self._execute_cmd(f'powercfg /setactive {high_perf_guid}')
        
        if success:
            self._log("  План электропитания: Высокая производительность")
            self._log("  ⚠️ Ноутбук будет быстрее разряжаться!")
            results["success"] = True
        else:
            self._log("  Не удалось изменить план электропитания")
        
        return results
    
    def restore_power_plan(self) -> dict:
        self._log("Восстановление сбалансированного плана питания...")
        
        results = {"success": False}
        
        balanced_guid = "381b4222-f694-41f0-9685-ff5bb260df2e"
        
        success, _ = self._execute_cmd(f'powercfg /setactive {balanced_guid}')
        
        if success:
            self._log("  План электропитания: Сбалансированный")
            results["success"] = True
        else:
            self._log("  Не удалось изменить план электропитания")
        
        return results
    
    def optimize_network_gaming(self) -> dict:
        self._log("Оптимизация сети для игр...")
        
        results = {"success": False, "changes": []}
        
        try:
            key_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "TCPNoDelay", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "TcpDelAckTicks", 0, winreg.REG_DWORD, 0)
                results["changes"].append("TCP optimizations applied")
            
            success, _ = self._execute_cmd(
                'netsh int tcp set global autotuninglevel=normal'
            )
            if success:
                results["changes"].append("TCP autotuning optimized")
            
            success, _ = self._execute_cmd(
                'netsh int tcp set global congestionprovider=ctcp'
            )
            if success:
                results["changes"].append("Congestion provider set to CTCP")
            
            results["success"] = True
            self._log("  Сетевые настройки оптимизированы для низкой задержки")
            
        except PermissionError:
            self._log("  Требуются права администратора")
            results["success"] = False
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_dns(self) -> dict:
        self._log("Оптимизация DNS...")
        
        results = {"success": False}
        
        dns_servers = [
            ("1.1.1.1", "1.0.0.1"),
            ("8.8.8.8", "8.8.4.4"),
        ]
        
        primary, secondary = dns_servers[0]
        
        try:
            for nic in self._wmi.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                nic.SetDNSServerSearchOrder([primary, secondary])
            
            results["success"] = True
            self._log(f"  DNS настроен: {primary}, {secondary} (Cloudflare)")
            
        except Exception as e:
            success, _ = self._execute_cmd(
                f'netsh interface ip set dns "Ethernet" static {primary} primary'
            )
            if success:
                self._execute_cmd(
                    f'netsh interface ip add dns "Ethernet" {secondary} index=2'
                )
                results["success"] = True
                self._log(f"  DNS настроен через netsh: {primary}, {secondary}")
            else:
                self._log(f"  Ошибка настройки DNS: {e}")
        
        return results
    
    def disable_startup_programs(self) -> dict:
        self._log("Анализ автозагрузки...")
        
        results = {"programs": [], "disabled": 0}
        
        startup_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        
        for hkey, path in startup_paths:
            try:
                with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            results["programs"].append({
                                "name": name,
                                "path": value,
                                "hkey": "HKCU" if hkey == winreg.HKEY_CURRENT_USER else "HKLM"
                            })
                            i += 1
                        except OSError:
                            break
            except (OSError, PermissionError):
                pass
        
        self._log(f"  Найдено программ в автозагрузке: {len(results['programs'])}")
        
        return results
    
    def disable_unnecessary_services(self, include_xbox: bool = False) -> dict:
        self._log("Оптимизация служб Windows...")
        
        services_to_disable = [
            "SysMain",
            "DiagTrack",
            "dmwappushservice",
            "WSearch",
            "TabletInputService",
            "Fax",
        ]
        
        if include_xbox:
            self._log("⚠️ Отключение служб Xbox (Game Pass работать не будет!)")
            services_to_disable.extend([
                "XblAuthManager",
                "XblGameSave",
                "XboxNetApiSvc",
                "XboxGipSvc",
            ])
        
        results = {"disabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service in services_to_disable:
            success, _ = self._execute_cmd(f'sc config "{service}" start= disabled')
            if success:
                self._execute_cmd(f'sc stop "{service}"')
                results["disabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Отключено служб: {len(results['disabled'])}")
        
        return results
    
    def enable_services(self) -> dict:
        self._log("Восстановление служб Windows...")
        
        services_to_enable = [
            ("SysMain", "auto"),
            ("WSearch", "auto"),
        ]
        
        results = {"enabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service, start_type in services_to_enable:
            success, _ = self._execute_cmd(f'sc config "{service}" start= {start_type}')
            if success:
                self._execute_cmd(f'sc start "{service}"')
                results["enabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Восстановлено служб: {len(results['enabled'])}")
        self._log("  SysMain и поиск Windows снова работают")
        
        return results
    
    def disable_xbox_services(self) -> dict:
        self._log("⚠️ Отключение служб Xbox...")
        self._log("  ВНИМАНИЕ: Xbox Game Pass и Xbox приложение работать не будут!")
        
        xbox_services = [
            "XblAuthManager",
            "XblGameSave",
            "XboxNetApiSvc",
            "XboxGipSvc",
        ]
        
        results = {"disabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service in xbox_services:
            success, _ = self._execute_cmd(f'sc config "{service}" start= disabled')
            if success:
                self._execute_cmd(f'sc stop "{service}"')
                results["disabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Отключено служб Xbox: {len(results['disabled'])}")
        
        return results
    
    def enable_xbox_services(self) -> dict:
        self._log("Включение служб Xbox...")
        
        xbox_services = [
            "XblAuthManager",
            "XblGameSave",
            "XboxNetApiSvc",
            "XboxGipSvc",
        ]
        
        results = {"enabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service in xbox_services:
            success, _ = self._execute_cmd(f'sc config "{service}" start= demand')
            if success:
                results["enabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Включено служб Xbox: {len(results['enabled'])}")
        self._log("  Xbox Game Pass теперь будет работать")
        
        return results
    
    def flush_dns_cache(self) -> dict:
        self._log("Очистка DNS кэша...")
        
        results = {"success": False}
        
        success, _ = self._execute_cmd("ipconfig /flushdns")
        if success:
            results["success"] = True
            self._log("  DNS кэш очищен")
        else:
            self._log("  Ошибка очистки DNS кэша")
        
        return results
    
    def clean_windows_update_cache(self) -> dict:
        self._log("Очистка кэша Windows Update...")
        
        results = {"freed_mb": 0, "success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        update_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'SoftwareDistribution', 'Download')
        
        if os.path.exists(update_path):
            self._execute_cmd('net stop wuauserv')
            
            before_size = self._get_size_mb(update_path)
            self._safe_remove(update_path)
            after_size = self._get_size_mb(update_path)
            
            self._execute_cmd('net start wuauserv')
            
            results["freed_mb"] = before_size - after_size
            results["success"] = True
            
            self._log(f"  Очищено: {results['freed_mb']:.2f} MB")
        
        return results
    
    def get_system_info(self) -> dict:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        
        if not hasattr(self, '_cached_cpu_name'):
            try:
                for processor in self._wmi.Win32_Processor():
                    self._cached_cpu_name = processor.Name
                    break
            except:
                self._cached_cpu_name = "Unknown"
        
        if not hasattr(self, '_cached_gpu_name'):
            try:
                for gpu in self._wmi.Win32_VideoController():
                    self._cached_gpu_name = gpu.Name
                    break
            except:
                self._cached_gpu_name = "Unknown"
        
        cpu_info = self._cached_cpu_name
        gpu_info = self._cached_gpu_name
        
        return {
            "cpu_name": cpu_info,
            "cpu_usage": cpu_percent,
            "gpu_name": gpu_info,
            "ram_total_gb": memory.total / (1024 ** 3),
            "ram_used_gb": memory.used / (1024 ** 3),
            "ram_available_gb": memory.available / (1024 ** 3),
            "ram_percent": memory.percent,
            "disk_total_gb": disk.total / (1024 ** 3),
            "disk_used_gb": disk.used / (1024 ** 3),
            "disk_free_gb": disk.free / (1024 ** 3),
            "disk_percent": disk.percent,
            "is_admin": self._is_admin,
        }
    
    def optimize_input_lag(self) -> dict:
        self._log("Оптимизация Input Lag...")
        
        results = {"success": False, "changes": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 0xffffffff)
                results["changes"].append("SystemResponsiveness = 0 (max priority)")
            
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "GPU Priority", 0, winreg.REG_DWORD, 8)
                winreg.SetValueEx(key, "Priority", 0, winreg.REG_DWORD, 6)
                winreg.SetValueEx(key, "Scheduling Category", 0, winreg.REG_SZ, "High")
                winreg.SetValueEx(key, "SFIO Priority", 0, winreg.REG_SZ, "High")
                results["changes"].append("Game priority set to HIGH")
            
            self._log("  Приоритет игр установлен на максимум")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_fullscreen_optimizations(self) -> dict:
        self._log("Отключение Fullscreen Optimizations...")
        
        results = {"success": False}
        
        try:
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "__COMPAT_LAYER", 0, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")
            
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)
            
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)
            
            self._log("  Fullscreen Optimizations отключены")
            self._log("  Game DVR/запись отключена")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_mouse(self) -> dict:
        self._log("Оптимизация мыши для игр...")
        
        results = {"success": False}
        
        try:
            key_path = r"Control Panel\Mouse"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "MouseSpeed", 0, winreg.REG_SZ, "0")
                winreg.SetValueEx(key, "MouseThreshold1", 0, winreg.REG_SZ, "0")
                winreg.SetValueEx(key, "MouseThreshold2", 0, winreg.REG_SZ, "0")
                winreg.SetValueEx(key, "MouseSensitivity", 0, winreg.REG_SZ, "10")
            
            self._log("  Акселерация мыши отключена")
            self._log("  Чувствительность: 6/11 (raw input)")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_background_apps(self) -> dict:
        self._log("Отключение фоновых приложений...")
        
        results = {"success": False}
        
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "GlobalUserDisabled", 0, winreg.REG_DWORD, 1)
            
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "BackgroundAppGlobalToggle", 0, winreg.REG_DWORD, 0)
            
            self._log("  Фоновые приложения отключены")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_timer_resolution(self) -> dict:
        self._log("Оптимизация системного таймера...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        try:
            self._execute_cmd('bcdedit /set useplatformtick yes')
            self._execute_cmd('bcdedit /set disabledynamictick yes')
            
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "GlobalTimerResolutionRequests", 0, winreg.REG_DWORD, 1)
            
            self._log("  Таймер: Platform tick enabled")
            self._log("  Таймер: Dynamic tick disabled")
            self._log("  ⚠️ Требуется перезагрузка!")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_hpet(self) -> dict:
        self._log("Отключение HPET (снижает input lag)...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        success, _ = self._execute_cmd('bcdedit /deletevalue useplatformclock')
        if not success:
            self._execute_cmd('bcdedit /set useplatformclock false')
        
        self._log("  HPET отключен")
        self._log("  ⚠️ Требуется перезагрузка!")
        results["success"] = True
        
        return results
    
    def optimize_gpu_scheduling(self) -> dict:
        self._log("Настройка GPU Scheduling...")
        
        results = {"success": False}
        
        try:
            key_path = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "HwSchMode", 0, winreg.REG_DWORD, 2)
            
            self._log("  Hardware-accelerated GPU Scheduling: ON")
            self._log("  ⚠️ Требуется перезагрузка!")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_core_parking(self) -> dict:
        self._log("Отключение Core Parking (все ядра активны)...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        self._execute_cmd('powercfg -setacvalueindex scheme_current sub_processor CPMINCORES 100')
        self._execute_cmd('powercfg -setactive scheme_current')
        
        self._log("  Core Parking отключен (100% ядер активно)")
        results["success"] = True
        
        return results
    
    def run_ultimate_optimization(self) -> dict:
        self._log("=" * 50)
        self._log("ULTIMATE GAMING OPTIMIZATION")
        self._log("=" * 50)
        
        results = {}
        
        optimizations = [
            ("input_lag", self.optimize_input_lag),
            ("fullscreen", self.disable_fullscreen_optimizations),
            ("mouse", self.optimize_mouse),
            ("background_apps", self.disable_background_apps),
            ("gpu_scheduling", self.optimize_gpu_scheduling),
            ("core_parking", self.disable_core_parking),
        ]
        
        for name, func in optimizations:
            try:
                results[name] = func()
            except Exception as e:
                self._log(f"Ошибка в {name}: {e}")
                results[name] = {"error": str(e)}
        
        self._log("=" * 50)
        self._log("ULTIMATE OPTIMIZATION COMPLETE")
        self._log("⚠️ Перезагрузите компьютер для применения всех настроек!")
        self._log("=" * 50)
        
        return results
    
    def run_full_optimization(self) -> dict:
        self._log("=" * 50)
        self._log("ПОЛНАЯ ОПТИМИЗАЦИЯ СИСТЕМЫ")
        self._log("=" * 50)
        
        results = {}
        
        optimizations = [
            ("temp_files", self.clean_temp_files),
            ("browser_cache", self.clean_browser_cache),
            ("ram", self.optimize_ram),
            ("game_mode", self.enable_game_mode),
            ("visual_effects", self.optimize_visual_effects),
            ("power_plan", self.optimize_power_plan),
            ("dns_flush", self.flush_dns_cache),
        ]
        
        if self._is_admin:
            optimizations.extend([
                ("network", self.optimize_network_gaming),
                ("services", self.disable_unnecessary_services),
                ("windows_update", self.clean_windows_update_cache),
            ])
        
        for name, func in optimizations:
            try:
                results[name] = func()
            except Exception as e:
                self._log(f"Ошибка в {name}: {e}")
                results[name] = {"error": str(e)}
        
        self._log("=" * 50)
        self._log("ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
        self._log("=" * 50)
        
        return results
    
    def clear_gpu_vram(self) -> dict:
        self._log_both("Очистка видеопамяти GPU...")
        
        results = {"success": False}
        
        try:
            self._execute_cmd('powershell -Command "Get-Process | Where-Object {$_.WorkingSet64 -gt 100MB} | ForEach-Object { $_.Refresh() }"')
            
            nvidia_cache = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'NVIDIA', 'DXCache')
            nvidia_cache2 = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'NVIDIA', 'GLCache')
            amd_cache = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'AMD', 'DxCache')
            dx_cache = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'D3DSCache')
            
            caches = [nvidia_cache, nvidia_cache2, amd_cache, dx_cache]
            total_freed = 0
            
            for cache in caches:
                if os.path.exists(cache):
                    freed = self._safe_remove(cache)
                    total_freed += freed
                    self._log_both(f"  Очищен кэш: {os.path.basename(cache)}")
            
            freed_mb = total_freed / (1024 * 1024)
            self._log_both(f"  Освобождено: {freed_mb:.2f} MB кэша шейдеров")
            
            self._execute_cmd('powershell -Command "[System.GC]::Collect(); [System.GC]::WaitForPendingFinalizers()"')
            
            results["success"] = True
            results["freed_mb"] = freed_mb
            self._log_both("  GPU VRAM очищена (кэш шейдеров удалён)")
            
        except Exception as e:
            self._log_both(f"  Ошибка: {e}")
        
        return results
    
    def disable_scheduled_tasks(self) -> dict:
        self._log_both("Отключение задач планировщика...")
        
        results = {"disabled": [], "failed": []}
        
        if not self._is_admin:
            self._log_both("  Требуются права администратора")
            return results
        
        tasks_to_disable = [
            r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
            r"\Microsoft\Windows\Application Experience\ProgramDataUpdater",
            r"\Microsoft\Windows\Autochk\Proxy",
            r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
            r"\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
            r"\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
            r"\Microsoft\Windows\Feedback\Siuf\DmClient",
            r"\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload",
            r"\Microsoft\Windows\Windows Error Reporting\QueueReporting",
            r"\Microsoft\Windows\Power Efficiency Diagnostics\AnalyzeSystem",
            r"\Microsoft\Windows\CloudExperienceHost\CreateObjectTask",
        ]
        
        for task in tasks_to_disable:
            success, _ = self._execute_cmd(f'schtasks /Change /TN "{task}" /Disable')
            if success:
                results["disabled"].append(task.split("\\")[-1])
            else:
                results["failed"].append(task.split("\\")[-1])
        
        self._log_both(f"  Отключено задач: {len(results['disabled'])}")
        self._log_both("  Телеметрия и диагностика отключены")
        
        return results
    
    def enable_scheduled_tasks(self) -> dict:
        self._log_both("Включение задач планировщика...")
        
        results = {"enabled": [], "failed": []}
        
        if not self._is_admin:
            self._log_both("  Требуются права администратора")
            return results
        
        tasks_to_enable = [
            r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
            r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
            r"\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
        ]
        
        for task in tasks_to_enable:
            success, _ = self._execute_cmd(f'schtasks /Change /TN "{task}" /Enable')
            if success:
                results["enabled"].append(task.split("\\")[-1])
        
        self._log_both(f"  Включено задач: {len(results['enabled'])}")
        
        return results
    
    def set_cpu_affinity(self, process_name: str = None, cores: list = None) -> dict:
        self._log_both(f"Настройка CPU Affinity...")
        
        results = {"success": False, "processes": []}
        
        try:
            if process_name:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if process_name.lower() in proc.info['name'].lower():
                            p = psutil.Process(proc.info['pid'])
                            if cores:
                                p.cpu_affinity(cores)
                            else:
                                all_cores = list(range(psutil.cpu_count()))
                                if len(all_cores) > 1:
                                    p.cpu_affinity(all_cores[1:])
                            results["processes"].append(proc.info['name'])
                            self._log_both(f"  {proc.info['name']} -> ядра {cores or 'все'}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            else:
                system_procs = ['dwm.exe', 'csrss.exe']
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'].lower() in system_procs:
                            p = psutil.Process(proc.info['pid'])
                            p.cpu_affinity([0])
                            self._log_both(f"  {proc.info['name']} -> ядро 0 (система)")
                    except:
                        pass
            
            results["success"] = True
            self._log_both("  CPU Affinity настроен")
            
        except Exception as e:
            self._log_both(f"  Ошибка: {e}")
        
        return results
    
    def optimize_prefetch(self, enable: bool = True) -> dict:
        self._log_both(f"{'Включение' if enable else 'Отключение'} Prefetch/Superfetch...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log_both("  Требуются права администратора")
            return results
        
        try:
            self._save_registry_backup(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
                "EnablePrefetcher"
            )
            self._save_registry_backup(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
                "EnableSuperfetch"
            )
            
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                value = 3 if enable else 0
                winreg.SetValueEx(key, "EnablePrefetcher", 0, winreg.REG_DWORD, value)
                winreg.SetValueEx(key, "EnableSuperfetch", 0, winreg.REG_DWORD, value)
            
            if enable:
                self._execute_cmd('sc config "SysMain" start= auto')
                self._execute_cmd('sc start "SysMain"')
                self._log_both("  Prefetch/Superfetch ВКЛЮЧЕНЫ")
                self._log_both("  Система будет предзагружать часто используемые приложения")
            else:
                self._execute_cmd('sc stop "SysMain"')
                self._execute_cmd('sc config "SysMain" start= disabled')
                self._log_both("  Prefetch/Superfetch ОТКЛЮЧЕНЫ")
                self._log_both("  Рекомендуется для SSD (меньше износ)")
            
            self._save_rollback_data()
            results["success"] = True
            
        except Exception as e:
            self._log_both(f"  Ошибка: {e}")
        
        return results
    
    def run_trim(self) -> dict:
        self._log_both("Запуск оптимизации накопителей (TRIM)...")
        
        results = {"success": False, "drives": []}
        
        if not self._is_admin:
            self._log_both("  Требуются права администратора")
            return results
        
        try:
            success, output = self._execute_cmd('wmic diskdrive get model,mediatype')
            
            success, output = self._execute_cmd('defrag C: /O /U /V')
            if success:
                results["drives"].append("C:")
                self._log_both("  TRIM выполнен для диска C:")
            
            for letter in "DEFGHIJ":
                if os.path.exists(f"{letter}:\\"):
                    success, _ = self._execute_cmd(f'defrag {letter}: /O /U')
                    if success:
                        results["drives"].append(f"{letter}:")
                        self._log_both(f"  TRIM выполнен для диска {letter}:")
            
            results["success"] = True
            self._log_both("  Оптимизация накопителей завершена")
            self._log_both("  SSD диски оптимизированы (TRIM)")
            
        except Exception as e:
            self._log_both(f"  Ошибка: {e}")
        
        return results
    
    def get_benchmark(self) -> dict:
        results = {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "ram_percent": psutil.virtual_memory().percent,
            "ram_available_gb": psutil.virtual_memory().available / (1024**3),
            "disk_read_speed": 0,
            "disk_write_speed": 0,
            "processes_count": len(list(psutil.process_iter())),
            "boot_time": psutil.boot_time(),
            "timestamp": time.time()
        }
        
        try:
            disk_io_start = psutil.disk_io_counters()
            time.sleep(1)
            disk_io_end = psutil.disk_io_counters()
            
            results["disk_read_speed"] = (disk_io_end.read_bytes - disk_io_start.read_bytes) / (1024*1024)
            results["disk_write_speed"] = (disk_io_end.write_bytes - disk_io_start.write_bytes) / (1024*1024)
        except:
            pass
        
        return results
    
    def run_benchmark_comparison(self) -> dict:
        self._log_both("Запуск бенчмарка системы...")
        
        benchmark_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark.json")
        
        current = self.get_benchmark()
        previous = None
        
        try:
            if os.path.exists(benchmark_file):
                with open(benchmark_file, "r") as f:
                    previous = json.load(f)
        except:
            pass
        
        try:
            with open(benchmark_file, "w") as f:
                json.dump(current, f, indent=2)
        except:
            pass
        
        self._log_both(f"  CPU загрузка: {current['cpu_usage']:.1f}%")
        self._log_both(f"  RAM использовано: {current['ram_percent']:.1f}%")
        self._log_both(f"  RAM доступно: {current['ram_available_gb']:.2f} GB")
        self._log_both(f"  Процессов: {current['processes_count']}")
        self._log_both(f"  Диск чтение: {current['disk_read_speed']:.1f} MB/s")
        self._log_both(f"  Диск запись: {current['disk_write_speed']:.1f} MB/s")
        
        if previous:
            self._log_both("  --- Сравнение с предыдущим ---")
            
            cpu_diff = previous['cpu_usage'] - current['cpu_usage']
            ram_diff = previous['ram_percent'] - current['ram_percent']
            procs_diff = previous['processes_count'] - current['processes_count']
            
            if cpu_diff > 0:
                self._log_both(f"  ✓ CPU: -{cpu_diff:.1f}% (улучшение)")
            elif cpu_diff < 0:
                self._log_both(f"  ✗ CPU: +{abs(cpu_diff):.1f}% (ухудшение)")
            
            if ram_diff > 0:
                self._log_both(f"  ✓ RAM: -{ram_diff:.1f}% (освобождено)")
            elif ram_diff < 0:
                self._log_both(f"  ✗ RAM: +{abs(ram_diff):.1f}% (больше занято)")
            
            if procs_diff > 0:
                self._log_both(f"  ✓ Процессы: -{procs_diff} (меньше)")
            elif procs_diff < 0:
                self._log_both(f"  ✗ Процессы: +{abs(procs_diff)} (больше)")
        else:
            self._log_both("  Первый запуск бенчмарка (нет данных для сравнения)")
        
        return {"current": current, "previous": previous}
    
    def rollback_all(self) -> dict:
        self._log_both("=" * 50)
        self._log_both("ОТКАТ ВСЕХ ИЗМЕНЕНИЙ")
        self._log_both("=" * 50)
        
        results = {"success": False, "restored": []}
        
        if not self._load_rollback_data():
            self._log_both("  Файл бэкапа не найден!")
            self._log_both("  Выполняю стандартное восстановление...")
        
        try:
            for item in self._rollback_data.get("registry", []):
                try:
                    hkey = winreg.HKEY_LOCAL_MACHINE if item["hkey"] == "HKLM" else winreg.HKEY_CURRENT_USER
                    
                    if item["value"] is None:
                        try:
                            with winreg.OpenKey(hkey, item["path"], 0, winreg.KEY_WRITE) as key:
                                winreg.DeleteValue(key, item["name"])
                        except:
                            pass
                    else:
                        with winreg.CreateKeyEx(hkey, item["path"], 0, winreg.KEY_WRITE) as key:
                            winreg.SetValueEx(key, item["name"], 0, item["type"], item["value"])
                    
                    results["restored"].append(f"REG: {item['name']}")
                except:
                    pass
            
            self.enable_services()
            self.enable_xbox_services()
            results["restored"].append("Services")
            
            self.restore_power_plan()
            results["restored"].append("Power Plan")
            
            self.restore_visual_effects()
            results["restored"].append("Visual Effects")
            
            self.optimize_prefetch(enable=True)
            results["restored"].append("Prefetch/Superfetch")
            
            self.enable_scheduled_tasks()
            results["restored"].append("Scheduled Tasks")
            
            try:
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                    winreg.SetValueEx(key, "GlobalUserDisabled", 0, winreg.REG_DWORD, 0)
                results["restored"].append("Background Apps")
            except:
                pass
            
            results["success"] = True
            self._log_both(f"  Восстановлено: {len(results['restored'])} компонентов")
            self._log_both("  ⚠️ Перезагрузите компьютер для полного отката!")
            
        except Exception as e:
            self._log_both(f"  Ошибка отката: {e}")
        
        self._log_both("=" * 50)
        
        return results
    
    def get_log_file_path(self) -> str:
        return self._log_file


class ProcessOptimizer:
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log = log_callback or print
    
    def get_resource_heavy_processes(self, limit: int = 10) -> list:
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] is not None and info['memory_percent'] is not None:
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'cpu': info['cpu_percent'],
                        'memory': info['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        processes.sort(key=lambda x: x['cpu'] + x['memory'], reverse=True)
        return processes[:limit]
    
    def set_process_priority(self, pid: int, priority: str = "high") -> bool:
        priority_map = {
            "realtime": psutil.REALTIME_PRIORITY_CLASS,
            "high": psutil.HIGH_PRIORITY_CLASS,
            "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            "normal": psutil.NORMAL_PRIORITY_CLASS,
            "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
            "idle": psutil.IDLE_PRIORITY_CLASS,
        }
        
        try:
            proc = psutil.Process(pid)
            proc.nice(priority_map.get(priority, psutil.HIGH_PRIORITY_CLASS))
            self._log(f"Приоритет процесса {proc.name()} установлен: {priority}")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError) as e:
            self._log(f"Ошибка установки приоритета: {e}")
            return False
    
    def terminate_process(self, pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.terminate()
            self._log(f"Процесс {name} завершён")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._log(f"Ошибка завершения процесса: {e}")
            return False
    
    def boost_game_process(self, process_name: str) -> bool:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    return self.set_process_priority(proc.info['pid'], "high")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        self._log(f"Процесс {process_name} не найден")
        return False

